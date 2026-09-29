"""
Serve the events database from a local copy of a file on slow storage.

In production /app/data is a GCSFuse mount of the events bucket. SQLite over
GCSFuse is slow and unsafe:

  * every page read becomes a Cloud Storage range request, with no file cache,
    so the first request after a cold start took ~26s and warm ones ~1.6s
    (the same page renders in 0.17s / 0.08s from local disk);
  * opening the file read-write makes the web service upload events.db back to
    the bucket at startup, which can overwrite a fresh scraper upload with the
    older copy the instance started from.

The web service never writes events, so a read-only local copy loses nothing.
The scraper replaces events.db in the bucket once a day; DbMirror notices the
new size/mtime and swaps in a fresh copy.
"""
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)


def _remove_copy(path: str) -> None:
    """Delete a mirrored copy and any WAL sidecars SQLite made beside it."""
    for suffix in ('', '-wal', '-shm'):
        try:
            os.remove(path + suffix)
        except FileNotFoundError:
            pass


class DbMirror:
    """Keep a local copy of ``source`` in ``cache_dir`` and refresh it on change."""

    def __init__(
        self,
        source: str,
        cache_dir: str,
        check_interval: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.source = Path(source)
        self.cache_dir = Path(cache_dir)
        self.check_interval = check_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._signature: Optional[Tuple[int, int]] = None
        self._last_check = float('-inf')
        self._generation = 0
        self.path: Optional[str] = None
        # The copy replaced by the last refresh. It is deleted one refresh
        # later, not immediately: a request that read the old path just
        # before the swap may still be about to connect() to it, and a
        # connect() to a missing file silently creates an empty database.
        self._retired: Optional[str] = None

    def _stat(self) -> Optional[Tuple[int, int]]:
        try:
            st = os.stat(self.source)
        except FileNotFoundError:
            return None
        return (st.st_size, st.st_mtime_ns)

    def _copy(self, signature: Tuple[int, int]) -> str:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._generation += 1
        # pid in the name so two processes sharing the directory never collide.
        target = self.cache_dir / (
            f'{self.source.stem}.{os.getpid()}.{self._generation}{self.source.suffix}'
        )
        tmp = target.with_name(target.name + '.part')
        start = time.monotonic()
        try:
            shutil.copyfile(self.source, tmp)
            copied = os.path.getsize(tmp)
            if copied != signature[0]:
                # The object changed between the stat and the read.
                raise OSError(f'copied {copied} bytes, expected {signature[0]}')
            os.replace(tmp, target)
        except BaseException:
            tmp.unlink(missing_ok=True)  # /tmp is RAM on Cloud Run
            raise
        logger.info(
            'Mirrored %s -> %s (%d bytes, %.2fs)',
            self.source, target, signature[0], time.monotonic() - start,
        )
        return str(target)

    def sync(self) -> str:
        """Make the first copy. If the source is missing, point at an empty
        local file so the app still starts (it will be refreshed later)."""
        with self._lock:
            self._last_check = self._clock()
            signature = self._stat()
            if signature is None:
                logger.warning('%s not found; starting with an empty database', self.source)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                self.path = str(self.cache_dir / f'{self.source.stem}.empty{self.source.suffix}')
            else:
                self.path = self._copy(signature)
            self._signature = signature
            return self.path

    def due(self) -> bool:
        """Cheap check, safe to call on the event loop: is a stat due?"""
        return self._clock() - self._last_check >= self.check_interval

    def refresh_if_changed(
        self, on_new: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """Return the path of a new copy if the source changed, else None.

        Stats the source at most once per ``check_interval``. ``on_new`` is
        called with the new path before it goes live and may raise to reject
        it. The replaced copy is kept until the next refresh (see _retired);
        connections open on it keep working after the unlink on POSIX.
        """
        if not self.due():
            return None
        if not self._lock.acquire(blocking=False):
            return None  # another request is already refreshing
        try:
            self._last_check = self._clock()
            signature = self._stat()
            if signature is None or signature == self._signature:
                return None
            old = self.path
            new = self._copy(signature)
            if on_new is not None:
                try:
                    on_new(new)
                except Exception:
                    _remove_copy(new)  # /tmp is RAM on Cloud Run; don't leak it
                    raise
            self.path = new
            self._signature = signature
            if self._retired:
                _remove_copy(self._retired)
            self._retired = old
            return self.path
        except Exception:
            logger.exception('Refreshing %s failed; keeping the current copy', self.source)
            return None
        finally:
            self._lock.release()

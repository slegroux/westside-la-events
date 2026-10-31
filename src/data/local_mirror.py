"""
Keep a local-disk copy of a read-only SQLite database that lives on a slow mount.

Why: in production /app/data is a GCSFuse mount of the events bucket. SQLite
in WAL mode touches `<db>-shm` on every connection, which GCSFuse cannot do
(BufferedWriteHandler.OutOfOrderError), so each request paid ~1.5-2s of
network retries. The web app only *reads* events.db -- the scraper service
writes a fresh copy to the bucket once a day -- so serving from a local copy
is safe and takes page renders back to ~80ms.

The copy is a plain sequential file copy (no SQLite on the mount at all),
validated locally, then published under a new versioned filename. Readers
open a new connection per request, so pointing the shared Database at the new
path swaps every reader over on its next request, and connections still open
on the old file are unaffected.
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)


class LocalDbMirror:
    """Copy `source_path` into `target_dir` and re-copy when the source changes."""

    def __init__(
        self,
        source_path: str,
        target_dir: str,
        stem: str = "events",
        prepare: Optional[Callable[[str], object]] = None,
    ):
        """
        prepare: called with the path of a validated copy before it is
        published (e.g. to apply schema migrations). If it raises, the copy
        is discarded and the previous one stays in service.
        """
        self.source_path = source_path
        self.prepare = prepare
        self.target_dir = Path(target_dir)
        self.stem = stem
        self.current_path: Optional[str] = None
        self._signature: Optional[Tuple[int, int]] = None

    def _source_signature(self) -> Tuple[int, int]:
        st = os.stat(self.source_path)
        return (st.st_mtime_ns, st.st_size)

    def refresh(self) -> Optional[str]:
        """
        Take a new local copy if the source changed since the last one.

        Returns the new local path when a copy was published, or None when the
        source is unchanged. Raises if the source is missing or the copy is
        not a readable events database; the previous copy stays in service.
        """
        signature = self._source_signature()
        if signature == self._signature and self.current_path:
            return None

        self.target_dir.mkdir(parents=True, exist_ok=True)
        final = self.target_dir / f"{self.stem}-{signature[0]}-{signature[1]}.db"
        # Per-process name so several workers never truncate each other's copy
        partial = final.with_name(f"{final.name}.{os.getpid()}.partial")

        shutil.copyfile(self.source_path, partial)
        try:
            self._validate(partial)
            if self.prepare is not None:
                self.prepare(str(partial))
        except Exception:
            self._remove(partial)
            raise
        finally:
            # prepare() may have opened the copy in WAL mode
            self._remove(Path(f"{partial}-wal"), Path(f"{partial}-shm"))
        os.replace(partial, final)

        previous = self.current_path
        self.current_path = str(final)
        self._signature = signature
        self._prune(keep={str(final), previous})
        return self.current_path

    @staticmethod
    def _validate(path: Path) -> None:
        # A copy taken while the bucket object was being replaced can be torn.
        # quick_check reads every page; COUNT(*) alone is answered from the
        # smallest index and would miss damage elsewhere. An empty events
        # table is refused too, so a bad upload never replaces a good copy.
        conn = sqlite3.connect(str(path))
        try:
            result = conn.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise sqlite3.DatabaseError(f"quick_check failed: {result}")
            if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
                raise sqlite3.DatabaseError("events table is empty")
        finally:
            conn.close()

    @staticmethod
    def _remove(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as e:  # pragma: no cover - best effort cleanup
                logger.warning(f"Could not remove {path}: {e}")

    def _prune(self, keep: set) -> None:
        # Keep the current copy and the one before it: requests that opened a
        # connection just before the swap may still be reading it.
        for path in self.target_dir.glob(f"{self.stem}-*.db"):
            if str(path) in keep:
                continue
            self._remove(path, Path(f"{path}-wal"), Path(f"{path}-shm"))

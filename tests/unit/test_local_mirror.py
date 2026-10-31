"""Tests for LocalDbMirror, the local-disk copy of the mounted events database."""
import os
import sqlite3

import pytest

from src.data.local_mirror import LocalDbMirror


def _make_events_db(path, titles):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, title TEXT)")
    conn.execute("DELETE FROM events")
    conn.executemany("INSERT INTO events (title) VALUES (?)", [(t,) for t in titles])
    conn.commit()
    # Checkpoint so the main file holds everything, as the uploaded bucket copy does
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def _titles(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT title FROM events ORDER BY id")]
    finally:
        conn.close()


def _bump_mtime(path, seconds):
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "mount" / "events.db"
    src.parent.mkdir()
    _make_events_db(str(src), ["a", "b"])
    return src


def test_first_refresh_copies_to_local_dir(source, tmp_path):
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    path = mirror.refresh()
    assert path is not None
    assert path.startswith(str(tmp_path / "local"))
    assert _titles(path) == ["a", "b"]
    assert mirror.current_path == path


def test_refresh_is_noop_when_source_unchanged(source, tmp_path):
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    first = mirror.refresh()
    assert mirror.refresh() is None
    assert mirror.current_path == first


def test_refresh_picks_up_changed_source(source, tmp_path):
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    first = mirror.refresh()
    _make_events_db(str(source), ["a", "b", "c"])
    _bump_mtime(source, 10)
    second = mirror.refresh()
    assert second is not None and second != first
    assert _titles(second) == ["a", "b", "c"]
    # The copy being served before the swap is left for in-flight readers
    assert os.path.exists(first)


def test_prune_keeps_only_current_and_previous(source, tmp_path):
    local = tmp_path / "local"
    mirror = LocalDbMirror(str(source), str(local))
    paths = [mirror.refresh()]
    for i in range(3):
        _bump_mtime(source, 10)
        paths.append(mirror.refresh())
    remaining = sorted(p.name for p in local.glob("events-*.db"))
    assert remaining == sorted(os.path.basename(p) for p in paths[-2:])


def test_torn_copy_is_rejected_and_previous_kept(source, tmp_path):
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    good = mirror.refresh()
    source.write_bytes(b"not a sqlite database at all" * 100)
    _bump_mtime(source, 10)
    with pytest.raises(sqlite3.DatabaseError):
        mirror.refresh()
    assert mirror.current_path == good
    assert _titles(good) == ["a", "b"]
    assert not list((tmp_path / "local").glob("*.partial"))


def test_missing_source_raises(tmp_path):
    mirror = LocalDbMirror(str(tmp_path / "nope.db"), str(tmp_path / "local"))
    with pytest.raises(FileNotFoundError):
        mirror.refresh()


def test_never_opens_sqlite_on_the_source(source, tmp_path):
    """No -shm/-wal may appear next to the source: that is the GCSFuse failure."""
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    mirror.refresh()
    siblings = sorted(p.name for p in source.parent.iterdir())
    assert siblings == ["events.db"]


def test_empty_events_table_is_rejected(source, tmp_path):
    mirror = LocalDbMirror(str(source), str(tmp_path / "local"))
    good = mirror.refresh()
    _make_events_db(str(source), [])
    _bump_mtime(source, 10)
    with pytest.raises(sqlite3.DatabaseError, match="empty"):
        mirror.refresh()
    assert mirror.current_path == good


def test_failed_prepare_keeps_previous_and_retries(source, tmp_path):
    calls = []

    def prepare(path):
        calls.append(path)
        if len(calls) == 2:
            raise sqlite3.OperationalError("database is locked")

    local = tmp_path / "local"
    mirror = LocalDbMirror(str(source), str(local), prepare=prepare)
    good = mirror.refresh()
    _bump_mtime(source, 10)
    with pytest.raises(sqlite3.OperationalError):
        mirror.refresh()
    assert mirror.current_path == good
    assert [p.name for p in local.iterdir()] == [os.path.basename(good)]
    # The failed copy did not advance the signature, so the next tick retries
    retried = mirror.refresh()
    assert retried is not None and retried != good
    assert os.path.exists(good)


def test_prepare_runs_on_copy_before_publish(tmp_path):
    from src.data.database import Database
    real = tmp_path / "mount" / "events.db"
    Database(str(real))  # real schema, as produced by the scrapers
    conn = sqlite3.connect(str(real))
    conn.execute("INSERT INTO events (title, source, url) VALUES ('a', 's', 'u')")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    local = tmp_path / "local"
    mirror = LocalDbMirror(str(real), str(local), prepare=Database)
    path = mirror.refresh()
    assert _titles(path) == ["a"]
    # Only the published file remains: no partials or stray WAL files
    assert sorted(p.name for p in local.iterdir()) == [os.path.basename(path)]

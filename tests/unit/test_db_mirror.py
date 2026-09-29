"""Tests for serving the events database from a local mirror."""
import os
import sqlite3

import pytest

from src.data.db_mirror import DbMirror


def _make_db(path, rows):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE t (v INTEGER)')
    conn.executemany('INSERT INTO t VALUES (?)', [(r,) for r in rows])
    conn.commit()
    conn.close()


def _rows(path):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute('SELECT v FROM t ORDER BY v')]
    finally:
        conn.close()


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


@pytest.fixture
def setup(tmp_path):
    src = tmp_path / 'mount' / 'events.db'
    src.parent.mkdir()
    _make_db(src, [1])
    clock = FakeClock()
    mirror = DbMirror(str(src), str(tmp_path / 'cache'), check_interval=60, clock=clock)
    return src, mirror, clock


def _replace_source(src, rows):
    """Mimic the scraper's upload: a new file with a new mtime."""
    _make_db(src, rows)
    st = os.stat(src)
    os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))


def test_sync_copies_source_outside_the_mount(setup, tmp_path):
    src, mirror, _ = setup
    path = mirror.sync()
    assert path.startswith(str(tmp_path / 'cache'))
    assert _rows(path) == [1]


def test_writes_to_the_copy_never_reach_the_source(setup):
    src, mirror, _ = setup
    before = src.read_bytes()
    conn = sqlite3.connect(mirror.sync())
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('INSERT INTO t VALUES (99)')
    conn.commit()
    conn.close()
    assert src.read_bytes() == before


def test_no_refresh_when_source_unchanged(setup):
    _, mirror, clock = setup
    mirror.sync()
    clock.now += 120
    assert mirror.refresh_if_changed() is None


def test_refresh_is_throttled(setup):
    src, mirror, clock = setup
    mirror.sync()
    _replace_source(src, [1, 2])
    clock.now += 30
    assert mirror.refresh_if_changed() is None
    clock.now += 31
    assert mirror.refresh_if_changed() is not None


def test_refresh_switches_before_deleting_old_copy(setup):
    src, mirror, clock = setup
    old = mirror.sync()
    _replace_source(src, [1, 2, 3])
    clock.now += 61
    seen = {}

    def on_new(new):
        seen['old_exists'] = os.path.exists(old)
        seen['new_rows'] = _rows(new)

    new = mirror.refresh_if_changed(on_new)
    assert new != old
    assert seen == {'old_exists': True, 'new_rows': [1, 2, 3]}
    assert mirror.path == new
    # Kept one more cycle for requests that already read the old path.
    assert os.path.exists(old)

    _replace_source(src, [4])
    clock.now += 61
    newest = mirror.refresh_if_changed()
    assert not os.path.exists(old)
    assert os.path.exists(new) and os.path.exists(newest)


def test_failed_copy_leaves_no_partial_file(setup, tmp_path, monkeypatch):
    src, mirror, clock = setup
    old = mirror.sync()
    _replace_source(src, [7])
    clock.now += 61

    import shutil as _shutil
    real = _shutil.copyfile

    def half_copy(a, b):
        real(a, b)
        with open(b, 'r+b') as f:
            f.truncate(100)  # simulate a short read from the mount

    monkeypatch.setattr('src.data.db_mirror.shutil.copyfile', half_copy)
    assert mirror.refresh_if_changed() is None
    assert mirror.path == old
    assert sorted(os.listdir(tmp_path / 'cache')) == [os.path.basename(old)]


def test_failed_switch_keeps_current_copy_and_cleans_up(setup, tmp_path):
    src, mirror, clock = setup
    old = mirror.sync()
    _replace_source(src, [5])
    clock.now += 61

    def boom(new):
        raise RuntimeError('schema upgrade failed')

    assert mirror.refresh_if_changed(boom) is None
    assert mirror.path == old and os.path.exists(old)
    assert sorted(os.listdir(tmp_path / 'cache')) == [os.path.basename(old)]


def test_missing_source_still_starts(tmp_path):
    mirror = DbMirror(str(tmp_path / 'nope.db'), str(tmp_path / 'cache'))
    path = mirror.sync()
    assert path.startswith(str(tmp_path / 'cache'))


def test_app_lifespan_serves_from_mirror(tmp_path, monkeypatch):
    """With DB_CACHE_DIR set, the app never opens DATABASE_PATH in place."""
    import config
    from src.data.database import Database
    from src.web import app as app_module
    from src.web.state import state

    src = tmp_path / 'mount' / 'events.db'
    src.parent.mkdir()
    Database(str(src))  # a real schema, as the scraper would upload
    before = src.read_bytes()

    monkeypatch.setattr(config, 'DATABASE_PATH', str(src))
    monkeypatch.setattr(config, 'DB_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setattr(config, 'ENABLE_ANALYTICS', False)
    monkeypatch.setattr(state, 'db', None)
    monkeypatch.setattr(state, 'search', None)
    monkeypatch.setattr(state, 'db_mirror', None)
    monkeypatch.setattr(state, 'analytics', None)
    monkeypatch.setattr(app_module, '_tally_cache', {})

    from starlette.testclient import TestClient
    with TestClient(app_module.app) as client:
        assert client.get('/').status_code == 200
        assert state.db.db_path.startswith(str(tmp_path / 'cache'))

    assert src.read_bytes() == before
    assert not os.path.exists(str(src) + '-wal')
    assert not os.path.exists(str(src) + '-shm')


def test_request_picks_up_new_upload(tmp_path, monkeypatch):
    """A new events.db in the bucket is served without restarting."""
    import config
    from src.data.database import Database
    from src.web import app as app_module
    from src.web.state import state

    src = tmp_path / 'mount' / 'events.db'
    src.parent.mkdir()
    Database(str(src))

    monkeypatch.setattr(config, 'DATABASE_PATH', str(src))
    monkeypatch.setattr(config, 'DB_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setattr(config, 'ENABLE_ANALYTICS', False)
    monkeypatch.setattr(state, 'db', None)
    monkeypatch.setattr(state, 'search', None)
    monkeypatch.setattr(state, 'db_mirror', None)
    monkeypatch.setattr(state, 'analytics', None)
    monkeypatch.setattr(app_module, '_tally_cache', {})

    from starlette.testclient import TestClient
    with TestClient(app_module.app) as client:
        first = state.db.db_path
        state.db_mirror.check_interval = 0

        # The scraper uploads a new file: write it elsewhere, then swap it in.
        staged = tmp_path / 'staged.db'
        db = Database(str(staged))
        with db.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute(
                "INSERT INTO events (title, event_date, source, url) "
                "VALUES ('Fresh', '2099-01-01 19:00:00', 'test', 'https://x')"
            )
        os.replace(staged, src)
        st = os.stat(src)
        os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))

        assert client.get('/').status_code == 200
        assert state.db.db_path != first
        with state.db.get_connection() as conn:
            assert conn.execute("SELECT title FROM events").fetchone()[0] == 'Fresh'


def test_refresh_rejects_copy_without_events(tmp_path, monkeypatch):
    """An upload with an empty catalog is not swapped in."""
    import config
    from src.data.database import Database
    from src.web import app as app_module
    from src.web.state import state

    src = tmp_path / 'mount' / 'events.db'
    src.parent.mkdir()
    db = Database(str(src))
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO events (title, event_date, source, url) "
            "VALUES ('Old', '2099-01-01 19:00:00', 'test', 'https://x')"
        )

    monkeypatch.setattr(config, 'DATABASE_PATH', str(src))
    monkeypatch.setattr(config, 'DB_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setattr(config, 'ENABLE_ANALYTICS', False)
    monkeypatch.setattr(state, 'db', None)
    monkeypatch.setattr(state, 'search', None)
    monkeypatch.setattr(state, 'db_mirror', None)
    monkeypatch.setattr(state, 'analytics', None)
    monkeypatch.setattr(app_module, '_tally_cache', {})

    from starlette.testclient import TestClient
    with TestClient(app_module.app) as client:
        first = state.db.db_path
        state.db_mirror.check_interval = 0
        os.remove(src)
        Database(str(src))  # schema, zero events
        st = os.stat(src)
        os.utime(src, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))

        assert client.get('/').status_code == 200
        assert state.db.db_path == first
        assert sorted(os.listdir(tmp_path / 'cache')) == [os.path.basename(first)]

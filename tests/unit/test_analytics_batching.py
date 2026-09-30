"""Batched analytics writes: tracking must not touch the database on the
request path when flush_interval > 0, and nothing queued may be lost or
mis-stamped when it is flushed."""
import sqlite3
import time

import pytest

import src.data.analytics as analytics_mod
from src.data.analytics import Analytics


def _count(db_path, table):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "analytics.db")


@pytest.fixture
def batched(db_path):
    # An interval long enough that only explicit flush()/close() writes.
    a = Analytics(db_path, flush_interval=3600)
    yield a
    a._stop.set()


def test_unbatched_writes_immediately(db_path):
    a = Analytics(db_path)
    a.track_page_view("s1", "/")
    assert _count(db_path, "page_views") == 1
    assert a._writer is None


def test_batched_tracking_does_not_touch_the_database(batched, db_path, monkeypatch):
    def unreachable():
        raise AssertionError("tracking opened a connection on the request path")

    monkeypatch.setattr(batched, "get_connection", unreachable)
    batched.track_page_view("s1", "/")
    batched.track_search("s1", query="jazz")
    batched.track_event_interaction("s1", 7, "click")
    assert len(batched._pending) == 3


def test_flush_writes_all_queued_rows_and_counters(batched, db_path):
    batched.track_page_view("s1", "/")
    batched.track_page_view("s1", "/?date=today")
    batched.track_search("s1", query="jazz", categories=["music"])
    batched.track_event_interaction("s1", 7, "view")
    batched.track_event_interaction("s1", 7, "click")
    assert _count(db_path, "page_views") == 0

    batched.flush()

    assert _count(db_path, "page_views") == 2
    assert _count(db_path, "search_queries") == 1
    assert _count(db_path, "event_interactions") == 2
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT page_views, searches, events_viewed, events_clicked "
            "FROM sessions WHERE session_id = 's1'"
        ).fetchone()
    assert row == (2, 1, 1, 1)
    assert batched._pending == []


def test_rows_keep_the_time_they_were_tracked(batched, db_path, monkeypatch):
    monkeypatch.setattr(analytics_mod, "_utc_now", lambda: "2020-01-02 03:04:05")
    batched.track_page_view("s1", "/")
    monkeypatch.setattr(analytics_mod, "_utc_now", lambda: "2030-01-01 00:00:00")
    batched.flush()

    with sqlite3.connect(db_path) as conn:
        created = conn.execute("SELECT created_at FROM page_views").fetchone()[0]
        first_seen = conn.execute("SELECT first_seen FROM sessions").fetchone()[0]
    assert created == "2020-01-02 03:04:05"
    assert first_seen == "2020-01-02 03:04:05"


def test_a_failing_write_is_rolled_back_without_losing_the_batch(batched, db_path):
    def half_written(conn):
        conn.execute("INSERT INTO page_views (session_id, path) VALUES ('bad', '/')")
        # A row-level error: session_id is NOT NULL.
        conn.execute("INSERT INTO page_views (session_id, path) VALUES (NULL, '/')")

    batched.track_page_view("s1", "/a")
    batched._submit(half_written)
    batched.track_page_view("s1", "/b")
    batched.flush()

    with sqlite3.connect(db_path) as conn:
        paths = [r[0] for r in conn.execute("SELECT path FROM page_views ORDER BY id")]
    assert paths == ["/a", "/b"]


def test_close_flushes_and_stops_the_writer(batched, db_path):
    batched.track_page_view("s1", "/")
    batched.close()
    assert _count(db_path, "page_views") == 1
    assert not batched._writer.is_alive()


def test_writer_thread_flushes_on_its_own(db_path):
    a = Analytics(db_path, flush_interval=0.05)
    try:
        a.track_page_view("s1", "/")
        deadline = time.monotonic() + 3
        while _count(db_path, "page_views") == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert _count(db_path, "page_views") == 1
    finally:
        a.close()


def test_queue_is_capped_by_dropping_the_oldest(batched, monkeypatch):
    monkeypatch.setattr(analytics_mod, "MAX_PENDING_WRITES", 3)
    for i in range(5):
        batched.track_page_view("s1", f"/{i}")
    assert len(batched._pending) == 3


def test_a_locked_database_fails_the_batch_once_and_it_is_retried(batched, db_path, monkeypatch):
    monkeypatch.setattr(analytics_mod, "WRITER_TIMEOUT_SECONDS", 0.1)
    for i in range(20):
        batched.track_page_view("s1", f"/{i}")

    blocker = sqlite3.connect(db_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    started = time.monotonic()
    batched.flush()
    elapsed = time.monotonic() - started
    blocker.execute("ROLLBACK")
    blocker.close()

    # One busy wait for the whole batch, not one per op.
    assert elapsed < 1.0
    assert len(batched._pending) == 20
    assert _count(db_path, "page_views") == 0

    batched.flush()
    assert _count(db_path, "page_views") == 20
    assert batched._pending == []


def test_a_batch_that_keeps_failing_is_eventually_dropped(batched, monkeypatch):
    monkeypatch.setattr(batched, "_write_batch", lambda ops: False)
    batched.track_page_view("s1", "/")
    for _ in range(analytics_mod.MAX_FLUSH_ATTEMPTS - 1):
        batched.flush()
        assert len(batched._pending) == 1
    batched.flush()
    assert batched._pending == []


def test_out_of_order_batches_do_not_move_session_times_backwards(batched, db_path, monkeypatch):
    monkeypatch.setattr(analytics_mod, "_utc_now", lambda: "2026-01-01 12:00:00")
    batched.track_page_view("s1", "/")
    batched.flush()
    # A batch from another instance, stamped earlier, lands later.
    monkeypatch.setattr(analytics_mod, "_utc_now", lambda: "2026-01-01 11:00:00")
    batched.track_page_view("s1", "/")
    batched.flush()

    with sqlite3.connect(db_path) as conn:
        first, last = conn.execute(
            "SELECT first_seen, last_seen FROM sessions WHERE session_id = 's1'"
        ).fetchone()
    assert (first, last) == ("2026-01-01 11:00:00", "2026-01-01 12:00:00")

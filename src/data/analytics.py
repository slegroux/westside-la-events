"""
Analytics and metrics tracking for LA Events Aggregator.

This module provides privacy-friendly analytics tracking for:
- Page views and user sessions
- Event interactions (views, clicks, favorites)
- Search queries and filter usage
- Geographic and demographic data
- Source performance metrics
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Dict, List, Tuple
from contextlib import contextmanager
import hashlib
import logging
import threading

logger = logging.getLogger(__name__)

# Most writes kept queued while the writer is blocked or failing; beyond this
# the oldest are dropped rather than growing memory without bound.
MAX_PENDING_WRITES = 10_000
# A batch that fails this many flushes in a row is dropped, so one bad write
# cannot be retried forever.
MAX_FLUSH_ATTEMPTS = 3
# Busy timeout for the writer's connection. Short, so a locked database fails
# the batch quickly (and it is retried) instead of stalling the writer, and so
# the final flush at shutdown fits in Cloud Run's 10s SIGTERM grace.
WRITER_TIMEOUT_SECONDS = 5.0


def _utc_now() -> str:
    """Current UTC time in SQLite's CURRENT_TIMESTAMP format.

    Tracking calls stamp their own rows instead of relying on the column
    default, which would record when a batch was flushed, not when the
    visitor acted.
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


class Analytics:
    """Analytics tracking and reporting."""

    def __init__(self, db_path: str, flush_interval: float = 0):
        """
        Initialize analytics database.

        Args:
            db_path: Path to SQLite analytics database
            flush_interval: Seconds between batched writes. 0 writes each
                tracking call immediately. In production analytics.db sits on
                the GCSFuse mount, where one commit costs ~0.5s and GCS
                throttles repeated writes to the same object (HTTP 429), so
                the app queues tracking calls and a background thread commits
                them together; requests never wait on the mount.
        """
        self.db_path = db_path
        self._ensure_database()

        self._flush_interval = flush_interval
        self._failed_flushes = 0
        self._pending: List[Callable[[sqlite3.Connection], None]] = []
        self._pending_lock = threading.Lock()
        self._stop = threading.Event()
        self._writer: Optional[threading.Thread] = None
        if flush_interval > 0:
            self._writer = threading.Thread(
                target=self._run_writer, name='analytics-writer', daemon=True
            )
            self._writer.start()

    def _ensure_database(self):
        """Create analytics tables if they don't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            # Page views table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS page_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    path TEXT NOT NULL,
                    referrer TEXT,
                    user_agent TEXT,
                    ip_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_session ON page_views(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_path ON page_views(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_created ON page_views(created_at)")

            # Event interactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS event_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_id INTEGER NOT NULL,
                    interaction_type TEXT NOT NULL,
                    source TEXT,
                    category TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_ei_event ON event_interactions(event_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ei_session ON event_interactions(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ei_type ON event_interactions(interaction_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ei_created ON event_interactions(created_at)")

            # Search queries table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS search_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    query TEXT,
                    date_filter TEXT,
                    categories TEXT,
                    sources TEXT,
                    free_only BOOLEAN,
                    results_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_sq_session ON search_queries(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sq_query ON search_queries(query)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sq_created ON search_queries(created_at)")

            # User sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    page_views INTEGER DEFAULT 0,
                    events_viewed INTEGER DEFAULT 0,
                    events_clicked INTEGER DEFAULT 0,
                    searches INTEGER DEFAULT 0
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_s_session ON sessions(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s_first_seen ON sessions(first_seen)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_s_last_seen ON sessions(last_seen)")

            # Daily metrics summary table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE NOT NULL,
                    unique_visitors INTEGER DEFAULT 0,
                    page_views INTEGER DEFAULT 0,
                    events_viewed INTEGER DEFAULT 0,
                    events_clicked INTEGER DEFAULT 0,
                    searches INTEGER DEFAULT 0,
                    favorites_added INTEGER DEFAULT 0
                )
            """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_dm_date ON daily_metrics(date)")

            conn.commit()

        # Enable WAL mode after schema is created
        self._enable_wal_mode()

    @contextmanager
    def get_connection(self, timeout: float = 30.0):
        """Get database connection context manager."""
        # Use longer timeout for better concurrent access
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row

        # Set busy timeout (30 seconds by default)
        conn.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')

        try:
            yield conn
        finally:
            conn.close()

    def _enable_wal_mode(self):
        """Enable WAL mode for better concurrent access. Call once during initialization."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            # Enable WAL mode for concurrent reads and writes
            conn.execute('PRAGMA journal_mode=WAL')
            conn.commit()
            conn.close()
        except Exception as e:
            # WAL mode enablement failed, but continue anyway
            # (may not be supported on some filesystems)
            pass

    def _hash_ip(self, ip: str) -> str:
        """Hash IP address for privacy."""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    # ---- Writes -------------------------------------------------------------
    #
    # Every tracking call is a closure over one connection. _submit either runs
    # it now (flush_interval=0) or queues it for the writer thread, which runs
    # the whole queue in a single transaction.

    def _submit(self, op: Callable[[sqlite3.Connection], None]) -> None:
        if self._writer is None:
            self._write_batch([op])
            return
        with self._pending_lock:
            self._pending.append(op)
            self._trim_pending_locked()

    def _trim_pending_locked(self) -> None:
        overflow = len(self._pending) - MAX_PENDING_WRITES
        if overflow > 0:
            del self._pending[:overflow]
            logger.warning('Analytics queue full; dropped %d oldest writes', overflow)

    def _write_batch(self, ops: List[Callable[[sqlite3.Connection], None]]) -> bool:
        """Apply ops in one transaction; return False if the batch failed.

        A row-level error (bad data, constraint) rolls back that op alone and
        the rest still commit. An OperationalError -- locked, I/O, the mount
        misbehaving -- is about the database, not the row, so it fails the
        whole batch at once rather than being hit again for every op.
        """
        try:
            with self.get_connection(timeout=WRITER_TIMEOUT_SECONDS) as conn:
                # IMMEDIATE takes the write lock up front: a busy database
                # fails here once, not inside each op.
                conn.execute('BEGIN IMMEDIATE')
                for op in ops:
                    conn.execute('SAVEPOINT op')
                    try:
                        op(conn)
                    except sqlite3.OperationalError:
                        raise
                    except Exception as e:
                        if not conn.in_transaction:
                            # SQLite rolled back the whole transaction.
                            raise
                        conn.execute('ROLLBACK TO op')
                        logger.warning(f"Skipping analytics row: {e}")
                    conn.execute('RELEASE op')
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error writing {len(ops)} analytics rows: {e}")
            return False

    def flush(self) -> None:
        """Write everything queued so far.

        A failed batch goes back to the front of the queue and is retried on
        the next flush, up to MAX_FLUSH_ATTEMPTS times in a row.
        """
        with self._pending_lock:
            ops, self._pending = self._pending, []
        if not ops:
            return
        if self._write_batch(ops):
            self._failed_flushes = 0
            return
        self._failed_flushes += 1
        if self._failed_flushes >= MAX_FLUSH_ATTEMPTS:
            logger.error(
                'Dropping %d analytics rows after %d failed flushes',
                len(ops), self._failed_flushes,
            )
            self._failed_flushes = 0
            return
        with self._pending_lock:
            self._pending[:0] = ops
            self._trim_pending_locked()

    def _run_writer(self) -> None:
        while not self._stop.wait(self._flush_interval):
            try:
                self.flush()
            except Exception:
                logger.exception('Analytics writer failed; retrying next interval')

    def close(self) -> None:
        """Stop the writer thread and flush what is left. Call on shutdown.

        Bounded to fit Cloud Run's 10s SIGTERM grace: at most 3s waiting for
        an in-progress flush, then one final flush with a 5s busy timeout.
        """
        self._stop.set()
        if self._writer is not None:
            self._writer.join(timeout=min(self._flush_interval, 3))
        self.flush()

    @staticmethod
    def _touch_session(conn: sqlite3.Connection, session_id: str, at: str) -> None:
        """Create the session record, or widen its first_seen/last_seen.

        MIN/MAX rather than overwrite: batches from different instances can
        land out of order, and must not move last_seen backwards.
        """
        conn.execute("""
            INSERT INTO sessions (session_id, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                first_seen = MIN(first_seen, excluded.first_seen),
                last_seen = MAX(last_seen, excluded.last_seen)
        """, (session_id, at, at))

    def track_page_view(
        self,
        session_id: str,
        path: str,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Track a page view.

        Args:
            session_id: User session ID
            path: Page path/URL
            referrer: HTTP referrer
            user_agent: User agent string
            ip_address: User IP address (will be hashed)
        """
        at = _utc_now()
        ip_hash = self._hash_ip(ip_address) if ip_address else None

        def op(conn):
            self._touch_session(conn, session_id, at)
            conn.execute("""
                INSERT INTO page_views (session_id, path, referrer, user_agent, ip_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, path, referrer, user_agent, ip_hash, at))

            # Update session page views counter
            conn.execute("""
                UPDATE sessions
                SET page_views = page_views + 1
                WHERE session_id = ?
            """, (session_id,))

        self._submit(op)

    def track_event_interaction(
        self,
        session_id: str,
        event_id: int,
        interaction_type: str,
        source: Optional[str] = None,
        category: Optional[str] = None
    ) -> None:
        """
        Track an event interaction.

        Args:
            session_id: User session ID
            event_id: Event ID
            interaction_type: Type of interaction (view, click, favorite, unfavorite, calendar)
            source: Event source
            category: Event category
        """
        at = _utc_now()

        def op(conn):
            self._touch_session(conn, session_id, at)
            conn.execute("""
                INSERT INTO event_interactions
                (session_id, event_id, interaction_type, source, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, event_id, interaction_type, source, category, at))

            # Update session counters
            if interaction_type == 'view':
                conn.execute("""
                    UPDATE sessions
                    SET events_viewed = events_viewed + 1
                    WHERE session_id = ?
                """, (session_id,))
            elif interaction_type == 'click':
                conn.execute("""
                    UPDATE sessions
                    SET events_clicked = events_clicked + 1
                    WHERE session_id = ?
                """, (session_id,))

        self._submit(op)

    def track_search(
        self,
        session_id: str,
        query: Optional[str] = None,
        date_filter: Optional[str] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        free_only: bool = False,
        results_count: int = 0
    ) -> None:
        """
        Track a search query.

        Args:
            session_id: User session ID
            query: Search query string
            date_filter: Date filter applied
            categories: Categories filtered
            sources: Sources filtered
            free_only: Whether free-only filter was applied
            results_count: Number of results returned
        """
        at = _utc_now()
        categories_str = ','.join(categories) if categories else None
        sources_str = ','.join(sources) if sources else None

        def op(conn):
            self._touch_session(conn, session_id, at)
            conn.execute("""
                INSERT INTO search_queries
                (session_id, query, date_filter, categories, sources, free_only, results_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, query, date_filter, categories_str, sources_str, free_only, results_count, at))

            # Update session searches counter
            conn.execute("""
                UPDATE sessions
                SET searches = searches + 1
                WHERE session_id = ?
            """, (session_id,))

        self._submit(op)

    def get_daily_metrics(self, date: datetime) -> Dict:
        """
        Get metrics for a specific date.

        Args:
            date: Date to get metrics for

        Returns:
            Dictionary of metrics
        """
        with self.get_connection() as conn:
            date_str = date.strftime('%Y-%m-%d')

            # Unique visitors (distinct sessions)
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT session_id)
                FROM page_views
                WHERE DATE(created_at) = ?
            """, (date_str,))
            unique_visitors = cursor.fetchone()[0]

            # Page views
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM page_views
                WHERE DATE(created_at) = ?
            """, (date_str,))
            page_views = cursor.fetchone()[0]

            # Events viewed
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM event_interactions
                WHERE DATE(created_at) = ? AND interaction_type = 'view'
            """, (date_str,))
            events_viewed = cursor.fetchone()[0]

            # Events clicked
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM event_interactions
                WHERE DATE(created_at) = ? AND interaction_type = 'click'
            """, (date_str,))
            events_clicked = cursor.fetchone()[0]

            # Searches
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM search_queries
                WHERE DATE(created_at) = ?
            """, (date_str,))
            searches = cursor.fetchone()[0]

            # Favorites added
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM event_interactions
                WHERE DATE(created_at) = ? AND interaction_type = 'favorite'
            """, (date_str,))
            favorites_added = cursor.fetchone()[0]

            return {
                'date': date_str,
                'unique_visitors': unique_visitors,
                'page_views': page_views,
                'events_viewed': events_viewed,
                'events_clicked': events_clicked,
                'searches': searches,
                'favorites_added': favorites_added
            }

    def get_date_range_metrics(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get metrics for a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of daily metrics
        """
        metrics = []
        current_date = start_date

        while current_date <= end_date:
            metrics.append(self.get_daily_metrics(current_date))
            current_date += timedelta(days=1)

        return metrics

    def get_popular_events(self, limit: int = 10, days: int = 7) -> List[Tuple[int, int, int]]:
        """
        Get most popular events by interactions.

        Args:
            limit: Number of events to return
            days: Number of days to look back

        Returns:
            List of (event_id, view_count, click_count) tuples
        """
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor = conn.execute("""
                SELECT
                    event_id,
                    SUM(CASE WHEN interaction_type = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN interaction_type = 'click' THEN 1 ELSE 0 END) as clicks
                FROM event_interactions
                WHERE DATE(created_at) >= ?
                GROUP BY event_id
                ORDER BY views DESC, clicks DESC
                LIMIT ?
            """, (start_date, limit))

            return [(row[0], row[1], row[2]) for row in cursor.fetchall()]

    def get_popular_searches(self, limit: int = 10, days: int = 7) -> List[Tuple[str, int]]:
        """
        Get most popular search queries.

        Args:
            limit: Number of queries to return
            days: Number of days to look back

        Returns:
            List of (query, count) tuples
        """
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor = conn.execute("""
                SELECT query, COUNT(*) as count
                FROM search_queries
                WHERE DATE(created_at) >= ?
                  AND query IS NOT NULL
                  AND query != ''
                GROUP BY query
                ORDER BY count DESC
                LIMIT ?
            """, (start_date, limit))

            return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_category_popularity(self, days: int = 7) -> List[Tuple[str, int]]:
        """
        Get event category popularity.

        Args:
            days: Number of days to look back

        Returns:
            List of (category, interaction_count) tuples
        """
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM event_interactions
                WHERE DATE(created_at) >= ?
                  AND category IS NOT NULL
                  AND interaction_type IN ('view', 'click')
                GROUP BY category
                ORDER BY count DESC
            """, (start_date,))

            return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_source_performance(self, days: int = 7) -> List[Dict]:
        """
        Get source performance metrics.

        Args:
            days: Number of days to look back

        Returns:
            List of source performance dictionaries
        """
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            cursor = conn.execute("""
                SELECT
                    source,
                    COUNT(*) as total_interactions,
                    SUM(CASE WHEN interaction_type = 'view' THEN 1 ELSE 0 END) as views,
                    SUM(CASE WHEN interaction_type = 'click' THEN 1 ELSE 0 END) as clicks,
                    SUM(CASE WHEN interaction_type = 'favorite' THEN 1 ELSE 0 END) as favorites
                FROM event_interactions
                WHERE DATE(created_at) >= ?
                  AND source IS NOT NULL
                GROUP BY source
                ORDER BY total_interactions DESC
            """, (start_date,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'source': row[0],
                    'total_interactions': row[1],
                    'views': row[2],
                    'clicks': row[3],
                    'favorites': row[4],
                    'click_through_rate': round((row[3] / row[2] * 100) if row[2] > 0 else 0, 2)
                })

            return results

    def get_session_stats(self, days: int = 7) -> Dict:
        """
        Get session statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary of session stats
        """
        with self.get_connection() as conn:
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

            # Total sessions
            cursor = conn.execute("""
                SELECT COUNT(*)
                FROM sessions
                WHERE DATE(first_seen) >= ?
            """, (start_date,))
            total_sessions = cursor.fetchone()[0]

            # Average page views per session
            cursor = conn.execute("""
                SELECT AVG(page_views)
                FROM sessions
                WHERE DATE(first_seen) >= ?
            """, (start_date,))
            avg_page_views = cursor.fetchone()[0] or 0

            # Average events viewed per session
            cursor = conn.execute("""
                SELECT AVG(events_viewed)
                FROM sessions
                WHERE DATE(first_seen) >= ?
            """, (start_date,))
            avg_events_viewed = cursor.fetchone()[0] or 0

            # Bounce rate (sessions with only 1 page view)
            cursor = conn.execute("""
                SELECT
                    COUNT(CASE WHEN page_views = 1 THEN 1 END) * 100.0 / COUNT(*)
                FROM sessions
                WHERE DATE(first_seen) >= ?
            """, (start_date,))
            bounce_rate = cursor.fetchone()[0] or 0

            return {
                'total_sessions': total_sessions,
                'avg_page_views': round(avg_page_views, 2),
                'avg_events_viewed': round(avg_events_viewed, 2),
                'bounce_rate': round(bounce_rate, 2)
            }

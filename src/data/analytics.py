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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from contextlib import contextmanager
import hashlib
import logging

logger = logging.getLogger(__name__)


class Analytics:
    """Analytics tracking and reporting."""

    def __init__(self, db_path: str):
        """
        Initialize analytics database.

        Args:
            db_path: Path to SQLite analytics database
        """
        self.db_path = db_path
        self._ensure_database()

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

    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _hash_ip(self, ip: str) -> str:
        """Hash IP address for privacy."""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def _get_or_create_session(self, session_id: str) -> None:
        """Get or create a session record."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, first_seen, last_seen)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP
            """, (session_id,))
            conn.commit()

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
        try:
            self._get_or_create_session(session_id)

            ip_hash = self._hash_ip(ip_address) if ip_address else None

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO page_views (session_id, path, referrer, user_agent, ip_hash)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, path, referrer, user_agent, ip_hash))

                # Update session page views counter
                conn.execute("""
                    UPDATE sessions
                    SET page_views = page_views + 1
                    WHERE session_id = ?
                """, (session_id,))

                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking page view: {e}")

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
        try:
            self._get_or_create_session(session_id)

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO event_interactions
                    (session_id, event_id, interaction_type, source, category)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, event_id, interaction_type, source, category))

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

                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking event interaction: {e}")

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
        try:
            self._get_or_create_session(session_id)

            categories_str = ','.join(categories) if categories else None
            sources_str = ','.join(sources) if sources else None

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO search_queries
                    (session_id, query, date_filter, categories, sources, free_only, results_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, query, date_filter, categories_str, sources_str, free_only, results_count))

                # Update session searches counter
                conn.execute("""
                    UPDATE sessions
                    SET searches = searches + 1
                    WHERE session_id = ?
                """, (session_id,))

                conn.commit()
        except Exception as e:
            logger.error(f"Error tracking search: {e}")

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

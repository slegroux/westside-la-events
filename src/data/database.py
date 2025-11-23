"""
Database connection and operations for the LA Events Aggregator.
Uses SQLite with full-text search capabilities.
"""
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from contextlib import contextmanager

from .models import Event
from src.utils.deduplication import (
    events_are_duplicates,
    find_duplicate,
    merge_event_data
)


def sanitize_fts_query(query: str) -> str:
    """
    Sanitize user input for FTS5 MATCH queries to prevent syntax errors.

    FTS5 has special characters and operators that can cause errors:
    - Quotes (", ') for phrase searches
    - Operators (AND, OR, NOT, NEAR, *)
    - Parentheses for grouping
    - Special prefixes (^, +, -)

    This function wraps the query in double quotes to treat it as a phrase search,
    escaping any internal quotes to prevent injection.

    Args:
        query: Raw user search query

    Returns:
        Sanitized query safe for FTS5 MATCH
    """
    if not query or not query.strip():
        return '""'

    # Remove leading/trailing whitespace
    query = query.strip()

    # Escape double quotes by doubling them (FTS5 phrase search syntax)
    query = query.replace('"', '""')

    # Wrap in quotes to treat as phrase search
    # This prevents special operators from being interpreted
    return f'"{query}"'


class Database:
    """Database manager for events."""

    def __init__(self, db_path: str = "data/events.db"):
        """Initialize database connection."""
        self.db_path = db_path
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        # Use longer timeout and WAL mode for better concurrent access
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for concurrent reads and writes
        conn.execute('PRAGMA journal_mode=WAL')

        # Set busy timeout to 30 seconds
        conn.execute('PRAGMA busy_timeout=30000')

        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_db(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Create events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    venue_name TEXT,
                    address TEXT,
                    latitude REAL,
                    longitude REAL,
                    event_date TIMESTAMP,
                    end_date TIMESTAMP,
                    category TEXT,
                    source TEXT NOT NULL,
                    url TEXT,
                    image_url TEXT,
                    source_logo_url TEXT,
                    price REAL,
                    is_free INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add columns if they don't exist (migration)
            try:
                cursor.execute("ALTER TABLE events ADD COLUMN source_logo_url TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE events ADD COLUMN price REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE events ADD COLUMN is_free INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute("ALTER TABLE events ADD COLUMN price_note TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_date
                ON events(event_date)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category
                ON events(category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_source
                ON events(source)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_location
                ON events(latitude, longitude)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_is_free
                ON events(is_free)
            """)

            # Create full-text search virtual table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                    title,
                    description,
                    venue_name,
                    content=events,
                    content_rowid=id
                )
            """)

            # Create triggers to keep FTS table in sync
            # Drop existing triggers to allow updates
            cursor.execute("DROP TRIGGER IF EXISTS events_ai")
            cursor.execute("DROP TRIGGER IF EXISTS events_ad")
            cursor.execute("DROP TRIGGER IF EXISTS events_bu")
            cursor.execute("DROP TRIGGER IF EXISTS events_au")

            cursor.execute("""
                CREATE TRIGGER events_ai AFTER INSERT ON events BEGIN
                    INSERT INTO events_fts(rowid, title, description, venue_name)
                    VALUES (new.id, new.title, new.description, new.venue_name);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER events_ad AFTER DELETE ON events BEGIN
                    DELETE FROM events_fts WHERE rowid = old.id;
                END
            """)

            # For UPDATE, we need TWO triggers: BEFORE to delete, AFTER to insert
            # This avoids the "database disk image is malformed" error with FTS5
            cursor.execute("""
                CREATE TRIGGER events_bu BEFORE UPDATE ON events BEGIN
                    DELETE FROM events_fts WHERE rowid = old.id;
                END
            """)

            cursor.execute("""
                CREATE TRIGGER events_au AFTER UPDATE ON events BEGIN
                    INSERT INTO events_fts(rowid, title, description, venue_name)
                    VALUES (new.id, new.title, new.description, new.venue_name);
                END
            """)

    def insert_event(
        self,
        event: Event,
        check_duplicates: bool = True,
        merge_if_duplicate: bool = True
    ) -> Tuple[int, bool]:
        """
        Insert a new event and return its ID.

        Args:
            event: Event to insert
            check_duplicates: Whether to check for duplicates before inserting
            merge_if_duplicate: If duplicate found, merge data and update instead

        Returns:
            Tuple of (event_id, was_duplicate)
            - event_id: ID of inserted or existing event
            - was_duplicate: True if duplicate was found and handled
        """
        # Check for duplicates if requested
        if check_duplicates:
            duplicate_result = self.find_duplicate_event(event)
            if duplicate_result:
                existing_event, scores = duplicate_result
                if merge_if_duplicate:
                    # Merge data from new event into existing
                    merged = merge_event_data(existing_event, event)
                    self.update_event(merged)
                    return existing_event.id, True
                else:
                    # Don't insert, just return existing ID
                    return existing_event.id, True

        # No duplicate found, insert new event
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (
                    title, description, venue_name, address,
                    latitude, longitude, event_date, end_date,
                    category, source, url, image_url, source_logo_url,
                    price, is_free, price_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.title, event.description, event.venue_name, event.address,
                event.latitude, event.longitude, event.event_date, event.end_date,
                event.category, event.source, event.url, event.image_url, event.source_logo_url,
                event.price, event.is_free, event.price_note
            ))
            return cursor.lastrowid, False

    def update_event(self, event: Event) -> bool:
        """Update an existing event."""
        if not event.id:
            return False

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE events SET
                    title = ?, description = ?, venue_name = ?, address = ?,
                    latitude = ?, longitude = ?, event_date = ?, end_date = ?,
                    category = ?, source = ?, url = ?, image_url = ?, source_logo_url = ?,
                    price = ?, is_free = ?, price_note = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                event.title, event.description, event.venue_name, event.address,
                event.latitude, event.longitude, event.event_date, event.end_date,
                event.category, event.source, event.url, event.image_url, event.source_logo_url,
                event.price, event.is_free, event.price_note,
                event.id
            ))
            return cursor.rowcount > 0

    def get_event(self, event_id: int) -> Optional[Event]:
        """Get a single event by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_event(row)
            return None

    def delete_event(self, event_id: int) -> bool:
        """Delete an event by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cursor.rowcount > 0

    def update_event_category(self, event_id: int, category: str) -> bool:
        """Update the category of an event."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE events
                SET category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (category, event_id))
            return cursor.rowcount > 0

    def search_events(
        self,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_filter: Optional[str] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        min_lat: Optional[float] = None,
        max_lat: Optional[float] = None,
        min_lng: Optional[float] = None,
        max_lng: Optional[float] = None,
        is_free: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Event]:
        """
        Search events with various filters.

        Args:
            query: Full-text search query
            start_date: Start date (datetime object) - for backwards compatibility
            end_date: End date (datetime object) - for backwards compatibility
            date_filter: SQLite-based date filter ('today', 'tomorrow', 'this_week', etc.)
                        This takes precedence over start_date/end_date for consistency with tallies
            categories: List of category filters
            sources: List of source filters
            min_lat: Minimum latitude
            max_lat: Maximum latitude
            min_lng: Minimum longitude
            max_lng: Maximum longitude
            is_free: Filter for free events
            limit: Maximum results
            offset: Pagination offset
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            conditions = []
            params = []

            # Full-text search
            if query:
                conditions.append("""
                    id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)
                """)
                # Sanitize query to prevent FTS syntax errors
                params.append(sanitize_fts_query(query))

            # Date filtering - use SQLite date functions for consistency with tallies
            # NOTE: Events are stored in local time with inconsistent timezone formats:
            # - Some as '2025-11-15 19:00:00' (no timezone)
            # - Some as '2025-11-15 19:00:00-08:00' (with Pacific timezone)
            # We use substr() to strip timezone suffix, then compare dates
            if date_filter:
                if date_filter == 'today':
                    conditions.append("date(substr(event_date, 1, 19)) = date('now', 'localtime')")
                elif date_filter == 'tomorrow':
                    conditions.append("date(substr(event_date, 1, 19)) = date('now', 'localtime', '+1 day')")
                elif date_filter == 'today_tomorrow':
                    conditions.append("date(substr(event_date, 1, 19)) <= date('now', 'localtime', '+1 day')")
                elif date_filter == 'this_week':
                    conditions.append("event_date >= date('now', 'localtime') AND event_date < date('now', 'localtime', 'weekday 0', '+7 days')")
                elif date_filter == 'this_weekend':
                    conditions.append("date(substr(event_date, 1, 19)) IN (date('now', 'localtime', 'weekday 6'), date('now', 'localtime', 'weekday 0', '+7 days'))")
                elif date_filter == 'this_month':
                    conditions.append("strftime('%Y-%m', substr(event_date, 1, 19)) = strftime('%Y-%m', 'now', 'localtime')")
                elif date_filter == 'upcoming':
                    conditions.append("event_date >= datetime('now', 'localtime')")
            elif start_date or end_date:
                # Fall back to Python datetime for backwards compatibility
                if start_date:
                    conditions.append("event_date >= ?")
                    params.append(start_date)
                if end_date:
                    conditions.append("event_date < ?")
                    params.append(end_date)

            # Categories
            if categories:
                placeholders = ','.join('?' * len(categories))
                conditions.append(f"category IN ({placeholders})")
                params.extend(categories)

            # Sources
            if sources:
                placeholders = ','.join('?' * len(sources))
                conditions.append(f"source IN ({placeholders})")
                params.extend(sources)

            # Free events filter
            if is_free is not None:
                conditions.append("is_free = ?")
                params.append(1 if is_free else 0)

            # Geographic bounds
            # Note: Allow events with NULL coordinates to pass through (they can't be geographically filtered)
            if min_lat is not None and max_lat is not None:
                conditions.append("(latitude IS NULL OR latitude BETWEEN ? AND ?)")
                params.extend([min_lat, max_lat])
            if min_lng is not None and max_lng is not None:
                conditions.append("(longitude IS NULL OR longitude BETWEEN ? AND ?)")
                params.extend([min_lng, max_lng])

            # Build query
            sql = "SELECT * FROM events"
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY event_date ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    def get_all_events(self, limit: Optional[int] = None, offset: int = 0) -> List[Event]:
        """Get all events with optional pagination."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if limit is None:
                # Get all events without limit
                cursor.execute("""
                    SELECT * FROM events
                    ORDER BY event_date ASC
                """)
            else:
                cursor.execute("""
                    SELECT * FROM events
                    ORDER BY event_date ASC
                    LIMIT ? OFFSET ?
                """, (limit, offset))
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    def get_upcoming_events(self, limit: int = 100) -> List[Event]:
        """Get upcoming events."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE event_date >= datetime('now', 'localtime')
                ORDER BY event_date ASC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    def get_events_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Event]:
        """Get events within a date range."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE event_date BETWEEN ? AND ?
                ORDER BY event_date ASC
            """, (start_date, end_date))
            rows = cursor.fetchall()
            return [self._row_to_event(row) for row in rows]

    def event_exists(self, url: str, event_date: datetime) -> bool:
        """Check if an event already exists by URL and date."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM events
                WHERE url = ? AND event_date = ?
            """, (url, event_date))
            count = cursor.fetchone()[0]
            return count > 0

    def find_duplicate_event(
        self,
        event: Event,
        date_tolerance_hours: int = 24
    ) -> Optional[Tuple[Event, dict]]:
        """
        Find if an event is a duplicate of any existing event in the database.

        This method uses a two-phase approach for efficiency:
        1. First checks for exact URL match (fastest, most reliable)
        2. Falls back to date-based similarity matching if no URL match

        Args:
            event: Event to check for duplicates
            date_tolerance_hours: How many hours before/after to search

        Returns:
            Tuple of (duplicate_event, similarity_scores) if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # PHASE 1: Check for exact URL match first (fastest check)
            # This catches the same event from different sources immediately
            if event.url:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE url = ?
                    LIMIT 1
                """, (event.url.strip(),))

                row = cursor.fetchone()
                if row:
                    existing_event = self._row_to_event(row)
                    # Create scores dict to match expected return format
                    scores = {
                        'same_url': True,
                        'same_source': existing_event.source == event.source,
                        'match_method': 'url',
                        'title_similarity': 0.0,
                        'venue_similarity': 0.0,
                        'date_diff_hours': None
                    }
                    return existing_event, scores

            # PHASE 2: No URL match, fall back to date-based similarity matching
            if not event.event_date:
                return None

            # Query events within date tolerance (excluding same source for non-URL matches)
            start_date = event.event_date - timedelta(hours=date_tolerance_hours)
            end_date = event.event_date + timedelta(hours=date_tolerance_hours)

            cursor.execute("""
                SELECT * FROM events
                WHERE event_date BETWEEN ? AND ?
                AND source != ?
            """, (start_date, end_date, event.source))

            rows = cursor.fetchall()
            existing_events = [self._row_to_event(row) for row in rows]

        # Use deduplication utility to find duplicate by title/venue similarity
        return find_duplicate(
            event,
            existing_events,
            date_tolerance_hours=date_tolerance_hours
        )

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """Convert database row to Event object."""
        # Helper to safely get column with default
        def safe_get(col_name, default=None):
            try:
                return row[col_name] if row[col_name] is not None else default
            except (IndexError, KeyError):
                return default

        return Event(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            venue_name=row['venue_name'],
            address=row['address'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            event_date=datetime.fromisoformat(row['event_date']) if row['event_date'] else None,
            end_date=datetime.fromisoformat(row['end_date']) if row['end_date'] else None,
            category=row['category'],
            source=row['source'],
            url=row['url'],
            image_url=row['image_url'],
            source_logo_url=safe_get('source_logo_url', ''),
            price=safe_get('price'),
            is_free=bool(safe_get('is_free', 0)),
            price_note=safe_get('price_note', ''),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )

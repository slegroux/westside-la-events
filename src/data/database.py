"""
Database connection and operations for the LA Events Aggregator.
Uses SQLite with full-text search capabilities.
"""
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager

from .models import Event
from src.utils.deduplication import (
    events_are_duplicates,
    find_duplicate,
    merge_event_data
)
import config


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
        # Use longer timeout for better concurrent access
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row

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

    @staticmethod
    def snapshot_db(source_path: str, target_path: str) -> None:
        """
        Create a consistent WAL-safe snapshot of a SQLite database.

        Why: WAL mode keeps uncommitted-to-main pages in `<db>-wal`. A naive
        file copy of `<db>` alone can omit committed rows. SQLite's backup API
        produces a single self-contained file with all data flushed.
        """
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()

        src = sqlite3.connect(source_path, timeout=30.0)
        try:
            dst = sqlite3.connect(str(target), timeout=30.0)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

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

            # Composite indexes for common filter combinations
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date_category
                ON events(event_date, category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date_source
                ON events(event_date, source)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date_is_free
                ON events(event_date, is_free)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_url_event_date
                ON events(url, event_date)
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

        # Enable WAL mode after schema is created
        self._enable_wal_mode()

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
                    # Shore Hotel is low-priority: if the existing event is Shore Hotel
                    # and the new event is from a richer source, use new event as primary
                    # so its URL, image, and description take precedence.
                    LOW_PRIORITY_SOURCES = {'Shore Hotel'}
                    if existing_event.source in LOW_PRIORITY_SOURCES and event.source not in LOW_PRIORITY_SOURCES:
                        merged = merge_event_data(event, existing_event)
                        merged.id = existing_event.id
                        merged.created_at = existing_event.created_at
                    else:
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

    @staticmethod
    def _date_sql(date_filter: str, specific_date: str = '') -> Tuple[str, list]:
        """
        Build a SQL condition fragment for the given date filter.

        Some event_date values include timezone offsets (e.g.
        '2026-03-20 19:00:00-07:00') even though all times are LA local.
        SQLite's date() converts those to UTC before extracting the date,
        which shifts evening events to the next day.  Use substr() to
        extract the raw YYYY-MM-DD prefix so comparisons stay in local time.

        Returns:
            (sql_condition, params) – sql_condition contains no trailing AND;
            params is a list of values to bind (usually empty except for
            specific_date mode which binds two datetime objects).
        """
        # Use substr to extract date without timezone conversion
        _D = "substr(event_date, 1, 10)"
        _E = "substr(end_date, 1, 10)"
        # Floor for multi-day: only include events that started within 90 days
        # to filter out recurring shows stored as year-long spans.
        _FLOOR = "date('now', 'localtime', '-90 days')"

        # _on: event is active on a specific date.
        # Used for "today"/"tomorrow" — includes multi-day events (exhibitions)
        # so that days with no new single-day events still show content.
        def _on(date_expr):
            return (
                f"({_D} = {date_expr}"
                f" OR ({_D} >= {_FLOOR} AND {_D} <= {date_expr}"
                f" AND {_E} >= {date_expr} AND end_date IS NOT NULL))"
            )

        _FIXED = {
            'today':        _on("date('now', 'localtime')"),
            'tomorrow':     _on("date('now', 'localtime', '+1 day')"),
            'today_tomorrow': (
                f"{_D} BETWEEN date('now', 'localtime') "
                "AND date('now', 'localtime', '+1 day')"
            ),
            'this_week': (
                f"{_D} >= date('now', 'localtime') "
                f"AND {_D} < date('now', 'localtime', 'weekday 0', '+7 days')"
            ),
            'this_weekend': (
                f"{_D} IN "
                "(date('now', 'localtime', 'weekday 6'), "
                "date('now', 'localtime', 'weekday 0', '+7 days'))"
            ),
            'this_month': (
                f"strftime('%Y-%m', {_D}) = strftime('%Y-%m', 'now', 'localtime')"
            ),
        }
        if date_filter == 'specific_date' and specific_date:
            try:
                date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                end_dt = date_obj + timedelta(days=1)
                return "event_date >= ? AND event_date < ?", [date_obj, end_dt]
            except ValueError:
                pass  # fall through to 'upcoming'
        return _FIXED.get(date_filter, f"{_D} >= date('now', 'localtime')"), []

    def search_events(
        self,
        query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_filter: Optional[str] = None,
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        venues: Optional[List[str]] = None,
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
            venues: List of venue_name filters
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
                params.append(sanitize_fts_query(query))

            # Date filtering
            if date_filter:
                cond, cond_params = self._date_sql(date_filter)
                conditions.append(cond)
                params.extend(cond_params)
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

            # Venues (venue_name filter)
            if venues:
                placeholders = ','.join('?' * len(venues))
                conditions.append(f"venue_name IN ({placeholders})")
                params.extend(venues)

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

    def get_filter_tallies(
        self,
        date_filter: str = 'upcoming',
        categories: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        free_only: str = '',
        specific_date: str = '',
        min_venue_count: int = 3
    ) -> Tuple[Dict[str, int], List[Tuple[str, int]], int]:
        """
        Get filter tallies for categories/venues and count of free events.

        Returns:
            Tuple(category_counts, venue_counts, free_events_count)
        """
        available_categories: Dict[str, int] = {}
        available_venues: List[Tuple[str, int]] = []
        free_events_count = 0

        with self.get_connection() as conn:
            # Build WHERE clause based on filters
            conditions: List[str] = []
            params: List = []

            # Always filter out NULL sources and categories
            base_conditions = ["source IS NOT NULL", "category IS NOT NULL"]

            # Apply Westside geographic filtering if enabled
            # Allow events with NULL coordinates to pass through (can't be geographically filtered)
            if config.ENABLE_GEOGRAPHIC_FILTERING:
                base_conditions.append(
                    f"(latitude IS NULL OR (latitude >= {config.WESTSIDE_BOUNDS['min_lat']} "
                    f"AND latitude <= {config.WESTSIDE_BOUNDS['max_lat']}))"
                )
                base_conditions.append(
                    f"(longitude IS NULL OR (longitude >= {config.WESTSIDE_BOUNDS['min_lng']} "
                    f"AND longitude <= {config.WESTSIDE_BOUNDS['max_lng']}))"
                )

            # Date filter
            date_cond, date_params = self._date_sql(date_filter, specific_date)
            conditions.append(date_cond)
            params.extend(date_params)

            # Free events filter for category and venue tallies
            if free_only == 'true':
                conditions.append("is_free = 1")

            # Get category counts (filtered by selected sources if provided)
            category_conditions = list(conditions)
            category_params = list(params)
            if sources:
                placeholders = ','.join('?' * len(sources))
                category_conditions.append(f"source IN ({placeholders})")
                category_params.extend(sources)

            category_where = " AND ".join(base_conditions + category_conditions)
            cursor = conn.execute(f"""
                SELECT category, COUNT(*) as count
                FROM events
                WHERE {category_where}
                GROUP BY category
                ORDER BY category
            """, category_params)
            available_categories = {row[0]: row[1] for row in cursor.fetchall()}

            # Get venue counts (filtered by selected categories if provided)
            venue_conditions = list(conditions)
            venue_params = list(params)
            if categories:
                placeholders = ','.join('?' * len(categories))
                venue_conditions.append(f"category IN ({placeholders})")
                venue_params.extend(categories)

            venue_where = " AND ".join(base_conditions + venue_conditions)
            cursor = conn.execute(f"""
                SELECT venue_name, COUNT(*) as count
                FROM events
                WHERE {venue_where}
                  AND venue_name IS NOT NULL AND venue_name != ''
                GROUP BY venue_name
                HAVING count >= ?
                ORDER BY count DESC
            """, venue_params + [min_venue_count])
            available_venues = [(row[0], row[1]) for row in cursor.fetchall()]

            # Get free events count (ignore free_only toggle itself)
            free_cond, free_params_date = self._date_sql(date_filter, specific_date)
            free_conditions: List[str] = [free_cond]
            free_params: List = list(free_params_date)

            if categories:
                placeholders = ','.join('?' * len(categories))
                free_conditions.append(f"category IN ({placeholders})")
                free_params.extend(categories)

            if sources:
                placeholders = ','.join('?' * len(sources))
                free_conditions.append(f"source IN ({placeholders})")
                free_params.extend(sources)

            free_conditions.append("is_free = 1")
            free_where = " AND ".join(base_conditions + free_conditions)
            cursor = conn.execute(f"""
                SELECT COUNT(*) as count
                FROM events
                WHERE {free_where}
            """, free_params)
            result = cursor.fetchone()
            free_events_count = result[0] if result else 0

        return available_categories, available_venues, free_events_count

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
                WHERE substr(event_date, 1, 10) >= date('now', 'localtime')
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

            # PHASE 1: Check for exact URL match first (fastest check).
            # We only consider a URL collision a duplicate when the event_date
            # is also within a day. Some venues (farmers markets, weekly
            # classes) emit every occurrence under a single canonical URL —
            # treating those as one event collapses an entire schedule into a
            # single row.
            if event.url:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE url = ?
                """, (event.url.strip(),))

                for row in cursor.fetchall():
                    existing_event = self._row_to_event(row)
                    if existing_event.event_date and event.event_date:
                        diff_h = abs(
                            (existing_event.event_date - event.event_date).total_seconds()
                        ) / 3600.0
                        if diff_h >= 24:
                            continue  # different occurrence, keep looking
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

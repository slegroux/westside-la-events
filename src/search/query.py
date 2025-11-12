"""
Search and query functionality for events.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from src.data.database import Database
from src.data.models import Event
import config


class EventSearch:
    """Search and filter events."""

    def __init__(self, db: Database, enable_geo_filter: bool = None):
        """
        Initialize event search.

        Args:
            db: Database instance
            enable_geo_filter: Enable geographic filtering (defaults to config.ENABLE_GEOGRAPHIC_FILTERING)
        """
        self.db = db
        self.enable_geo_filter = enable_geo_filter if enable_geo_filter is not None else config.ENABLE_GEOGRAPHIC_FILTERING

    def search(
        self,
        query: Optional[str] = None,
        date_filter: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
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
        Search events with filters.

        Args:
            query: Search query string
            date_filter: Predefined date filter (today, this_week, this_month, upcoming)
            start_date: Custom start date
            end_date: Custom end date
            categories: List of categories to filter by
            sources: List of sources to filter by
            min_lat: Minimum latitude for geographic bounds (overrides default Westside filter)
            max_lat: Maximum latitude for geographic bounds (overrides default Westside filter)
            min_lng: Minimum longitude for geographic bounds (overrides default Westside filter)
            max_lng: Maximum longitude for geographic bounds (overrides default Westside filter)
            is_free: Filter for free events only (True/False/None)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of Event objects
        """
        # Process date filter
        if date_filter:
            start_date, end_date = self._parse_date_filter(date_filter)

        # Apply Westside geographic filtering by default if enabled and no custom bounds provided
        if self.enable_geo_filter and min_lat is None and max_lat is None and min_lng is None and max_lng is None:
            min_lat = config.WESTSIDE_BOUNDS['min_lat']
            max_lat = config.WESTSIDE_BOUNDS['max_lat']
            min_lng = config.WESTSIDE_BOUNDS['min_lng']
            max_lng = config.WESTSIDE_BOUNDS['max_lng']

        # Search database
        return self.db.search_events(
            query=query,
            start_date=start_date,
            end_date=end_date,
            categories=categories,
            sources=sources,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lng=min_lng,
            max_lng=max_lng,
            is_free=is_free,
            limit=limit,
            offset=offset
        )

    def _parse_date_filter(self, date_filter: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse predefined date filter into start and end dates.

        Args:
            date_filter: Date filter string

        Returns:
            Tuple of (start_date, end_date)
        """
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if date_filter == 'today':
            start_date = today_start
            end_date = today_start + timedelta(days=1)

        elif date_filter == 'tomorrow':
            start_date = today_start + timedelta(days=1)
            end_date = start_date + timedelta(days=1)

        elif date_filter == 'this_week':
            # Start from today, end in 7 days
            start_date = today_start
            end_date = today_start + timedelta(days=7)

        elif date_filter == 'this_weekend':
            # Find next Saturday and Sunday
            days_until_saturday = (5 - now.weekday()) % 7
            if days_until_saturday == 0 and now.hour >= 12:
                days_until_saturday = 7
            saturday = today_start + timedelta(days=days_until_saturday)
            start_date = saturday
            end_date = saturday + timedelta(days=2)

        elif date_filter == 'this_month':
            start_date = today_start
            # Last day of current month
            if now.month == 12:
                end_date = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                end_date = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

        elif date_filter == 'next_month':
            # First day of next month
            if now.month == 12:
                start_date = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now.replace(year=now.year + 1, month=2, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 11:
                    end_date = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                else:
                    end_date = now.replace(month=now.month + 2, day=1, hour=0, minute=0, second=0, microsecond=0)

        elif date_filter == 'upcoming':
            start_date = today_start
            end_date = None  # No end date for upcoming

        else:
            start_date = None
            end_date = None

        return start_date, end_date

    def get_upcoming_events(self, limit: int = 100) -> List[Event]:
        """
        Get upcoming events.

        Args:
            limit: Maximum number of results

        Returns:
            List of Event objects
        """
        return self.db.get_upcoming_events(limit=limit)

    def get_events_by_category(self, category: str, limit: int = 100) -> List[Event]:
        """
        Get events by category.

        Args:
            category: Category name
            limit: Maximum number of results

        Returns:
            List of Event objects
        """
        return self.db.search_events(categories=[category], limit=limit)

    def get_events_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Event]:
        """
        Get events within a date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of Event objects
        """
        return self.db.get_events_by_date_range(start_date, end_date)

"""
Unit tests for search functionality.
"""
import pytest
from datetime import datetime, timedelta

from src.search.query import EventSearch


@pytest.mark.unit
class TestEventSearch:
    """Test EventSearch functionality."""

    def test_search_initialization(self, db):
        """Test EventSearch initializes correctly."""
        search = EventSearch(db)
        assert search is not None
        assert search.db == db

    def test_search_all_events(self, populated_db):
        """Test searching for all events."""
        search = EventSearch(populated_db)
        events = search.search()
        assert len(events) > 0

    def test_search_with_query(self, populated_db):
        """Test searching with a text query."""
        search = EventSearch(populated_db)
        events = search.search(query="music")

        assert len(events) >= 1
        # Check that results contain the search term
        assert any("music" in event.title.lower() or
                   "music" in (event.description or "").lower()
                   for event in events)

    def test_search_with_category_filter(self, populated_db):
        """Test searching with category filter."""
        search = EventSearch(populated_db)
        events = search.search(categories=["Music"])

        assert len(events) >= 1
        assert all(event.category == "Music" for event in events)

    def test_search_with_multiple_categories(self, populated_db):
        """Test searching with multiple category filters."""
        search = EventSearch(populated_db)
        events = search.search(categories=["Music", "Art"])

        assert len(events) >= 2
        assert all(event.category in ["Music", "Art"] for event in events)

    def test_search_today_filter(self, db):
        """Test searching for events today."""
        # Create an event for today
        from src.data.models import Event
        today_event = Event(
            title="Today's Event",
            event_date=datetime.now(),
            source="Test"
        )
        db.insert_event(today_event)

        search = EventSearch(db)
        events = search.search(date_filter="today")

        assert len(events) >= 1
        for event in events:
            if event.event_date:
                assert event.event_date.date() == datetime.now().date()

    def test_search_today_excludes_tomorrow_midnight(self, db):
        """Test that 'today' filter excludes events at exactly midnight tomorrow."""
        from src.data.models import Event
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)

        # Create event today at 11:59 PM
        late_today = Event(
            title="Late Today Event",
            event_date=today_start.replace(hour=23, minute=59),
            source="Test"
        )
        db.insert_event(late_today)

        # Create event at exactly midnight tomorrow
        midnight_tomorrow = Event(
            title="Midnight Tomorrow Event",
            event_date=tomorrow_start,
            source="Test"
        )
        db.insert_event(midnight_tomorrow)

        # Create event tomorrow at 1:00 AM
        early_tomorrow = Event(
            title="Early Tomorrow Event",
            event_date=tomorrow_start.replace(hour=1),
            source="Test"
        )
        db.insert_event(early_tomorrow)

        search = EventSearch(db)
        today_events = search.search(date_filter="today")
        tomorrow_events = search.search(date_filter="tomorrow")

        # Today events should include late_today but NOT midnight_tomorrow or early_tomorrow
        today_titles = [e.title for e in today_events]
        assert "Late Today Event" in today_titles
        assert "Midnight Tomorrow Event" not in today_titles
        assert "Early Tomorrow Event" not in today_titles

        # Tomorrow events should include both midnight_tomorrow and early_tomorrow
        tomorrow_titles = [e.title for e in tomorrow_events]
        assert "Midnight Tomorrow Event" in tomorrow_titles
        assert "Early Tomorrow Event" in tomorrow_titles
        assert "Late Today Event" not in tomorrow_titles

    def test_search_this_week_filter(self, populated_db):
        """Test searching for events this week."""
        search = EventSearch(populated_db)
        events = search.search(date_filter="this_week")

        # Should include events in the next 7 days
        week_from_now = datetime.now() + timedelta(days=7)
        for event in events:
            if event.event_date:
                assert event.event_date <= week_from_now

    def test_search_this_month_filter(self, populated_db):
        """Test searching for events this month."""
        search = EventSearch(populated_db)
        events = search.search(date_filter="this_month")

        # Should include events in the current month
        now = datetime.now()
        for event in events:
            if event.event_date:
                assert event.event_date.month == now.month
                assert event.event_date.year == now.year

    def test_search_upcoming_filter(self, populated_db):
        """Test searching for upcoming events."""
        search = EventSearch(populated_db)
        events = search.search(date_filter="upcoming")

        # Should only include future events (not past events)
        # The populated_db fixture has 3 future events (+1, +2, +3 days) and 1 past event (-1 day)
        # We expect to get the 3 future events
        assert len(events) >= 3

        # None of the events should be from yesterday or earlier
        # (Allow small timing buffer since fixture creation and test run aren't perfectly synchronized)
        cutoff_time = datetime.now() - timedelta(hours=12)  # Events from 12+ hours ago are definitely "past"
        for event in events:
            if event.event_date:
                assert event.event_date > cutoff_time, \
                    f"Event '{event.title}' date {event.event_date} is too far in the past"

    def test_search_with_limit(self, populated_db):
        """Test searching with result limit."""
        search = EventSearch(populated_db)
        events = search.search(limit=2)

        assert len(events) <= 2

    def test_search_combined_filters(self, populated_db):
        """Test searching with multiple filters combined."""
        search = EventSearch(populated_db)
        events = search.search(
            query="music",
            categories=["Music"],
            date_filter="upcoming",
            limit=10
        )

        # Verify all filters are applied
        for event in events:
            assert event.category == "Music"
            if event.event_date:
                assert event.event_date >= datetime.now()

    def test_search_no_results(self, populated_db):
        """Test searching with filters that return no results."""
        search = EventSearch(populated_db)
        events = search.search(query="nonexistent_event_xyz123")

        assert len(events) == 0

    def test_search_empty_database(self, db):
        """Test searching an empty database."""
        search = EventSearch(db)
        events = search.search()

        assert len(events) == 0

    def test_search_with_coordinates_only(self, populated_db):
        """Test that search can filter events with coordinates."""
        search = EventSearch(populated_db)
        all_events = search.search()

        # Count events with coordinates
        events_with_coords = [e for e in all_events if e.latitude and e.longitude]

        assert len(events_with_coords) >= 1

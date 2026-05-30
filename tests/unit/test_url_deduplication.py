"""
Tests for URL-based deduplication enhancement.

These tests verify that URL matching is prioritized over other deduplication methods
and that events with the same URL are never duplicated in the database.
"""
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.data.database import Database
from src.data.models import Event
from src.utils.deduplication import events_are_duplicates


class TestURLDeduplicationPriority:
    """Tests for URL matching priority in deduplication logic."""

    def test_same_url_different_titles_detected_as_duplicate(self):
        """Events with same URL but different titles should be detected as duplicates."""
        event1 = Event(
            title="Original Title",
            venue_name="Venue A",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/123"
        )
        event2 = Event(
            title="Completely Different Title",
            venue_name="Different Venue",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url="https://example.com/event/123"
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        assert is_dup is True
        assert scores['same_url'] is True
        assert scores['match_method'] == 'url'

    def test_same_url_different_dates_detected_as_duplicate(self):
        """Events with same URL but very different dates should still be duplicates."""
        event1 = Event(
            title="Event Title",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/123"
        )
        event2 = Event(
            title="Event Title",
            event_date=datetime(2025, 12, 25),  # 43 days later (outside date tolerance)
            source="Source2",
            url="https://example.com/event/123"
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        # URL match should override date tolerance
        assert is_dup is True
        assert scores['same_url'] is True
        assert scores['match_method'] == 'url'

    def test_same_url_same_source_detected_as_duplicate(self):
        """Events with same URL from same source should be detected as duplicates."""
        event1 = Event(
            title="Event Title",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/123"
        )
        event2 = Event(
            title="Event Title - Updated",
            event_date=datetime(2025, 11, 12),
            source="Source1",  # Same source
            url="https://example.com/event/123"
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        # URL match should override same-source exclusion
        assert is_dup is True
        assert scores['same_url'] is True
        assert scores['same_source'] is True
        assert scores['match_method'] == 'url'

    def test_url_with_whitespace_normalized(self):
        """URLs with leading/trailing whitespace should be normalized and matched."""
        event1 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="  https://example.com/event/123  "
        )
        event2 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url="https://example.com/event/123"
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        assert is_dup is True
        assert scores['same_url'] is True

    def test_no_url_falls_back_to_title_matching(self):
        """Events without URLs should use title-based matching."""
        event1 = Event(
            title="Same Event Title",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url=None
        )
        event2 = Event(
            title="Same Event Title",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url=None
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        assert is_dup is True
        assert scores['same_url'] is False
        assert scores['match_method'] == 'title'
        assert scores['title_similarity'] >= 0.85

    def test_different_urls_not_duplicates(self):
        """Events with different URLs should not be detected as URL duplicates."""
        event1 = Event(
            title="Same Event Title",
            venue_name="Same Venue",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/123"
        )
        event2 = Event(
            title="Same Event Title",
            venue_name="Same Venue",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url="https://example.com/event/456"
        )

        is_dup, scores = events_are_duplicates(event1, event2)

        # Should still be detected as duplicate by title, but not by URL
        assert is_dup is True
        assert scores['same_url'] is False
        assert scores['match_method'] == 'title'


class TestDatabaseURLDeduplication:
    """Tests for database-level URL deduplication."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(str(db_path))
            yield db

    def test_database_prevents_same_url_insertion(self, temp_db):
        """Database should prevent inserting events with the same URL."""
        event1 = Event(
            title="Original Event",
            venue_name="Venue A",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/unique-event"
        )
        event2 = Event(
            title="Updated Event",
            venue_name="Venue B",
            event_date=datetime(2025, 11, 12, 20, 0),  # same day, within the 24h URL window
            source="Source2",
            url="https://example.com/unique-event"  # Same URL
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        assert is_dup1 is False
        assert is_dup2 is True
        assert id1 == id2  # Same event ID returned

        # Verify only one event exists
        events = temp_db.get_all_events()
        assert len(events) == 1

    def test_database_same_url_far_apart_treated_as_separate(self, temp_db):
        """Same URL but dates >24h apart are distinct occurrences, not duplicates.

        Recurring venues (farmers markets, weekly classes) reuse one canonical
        URL for every occurrence; collapsing them would lose the schedule.
        This pins the behavior added in commit 1ef58f2.
        """
        event1 = Event(
            title="Weekly Market",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/recurring",
        )
        event2 = Event(
            title="Weekly Market",
            event_date=datetime(2025, 11, 19),  # one week later, same URL
            source="Source1",
            url="https://example.com/recurring",
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        assert is_dup1 is False
        assert is_dup2 is False  # kept as a separate occurrence
        assert len(temp_db.get_all_events()) == 2

    def test_database_url_check_faster_than_date_check(self, temp_db):
        """Database should find URL duplicates without needing date range query."""
        # Insert event with a date
        event1 = Event(
            title="Old Event",
            event_date=datetime(2024, 1, 1),  # Very old date
            source="Source1",
            url="https://example.com/event/999"
        )
        temp_db.insert_event(event1)

        # Try to insert same URL on the same day (within the 24h URL window).
        # The URL fast-path should match it without a date-range scan.
        event2 = Event(
            title="New Event",
            event_date=datetime(2024, 1, 1, 12, 0),  # same day, within the 24h URL window
            source="Source2",
            url="https://example.com/event/999"
        )

        result = temp_db.find_duplicate_event(event2)

        # Should find duplicate via URL check, not date check
        assert result is not None
        duplicate, scores = result
        assert scores['match_method'] == 'url'
        assert scores['same_url'] is True
        assert duplicate.url == event2.url

    def test_database_url_check_with_same_source(self, temp_db):
        """Database URL check should find duplicates even from same source."""
        event1 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/100"
        )
        temp_db.insert_event(event1)

        # Try to insert same URL from same source
        event2 = Event(
            title="Event - Updated",
            event_date=datetime(2025, 11, 12),
            source="Source1",  # Same source
            url="https://example.com/event/100"
        )

        result = temp_db.find_duplicate_event(event2)

        assert result is not None
        duplicate, scores = result
        assert scores['same_url'] is True
        assert scores['same_source'] is True
        assert scores['match_method'] == 'url'

    def test_database_merges_data_on_url_duplicate(self, temp_db):
        """Database should merge data when URL duplicate is found."""
        event1 = Event(
            title="Minimal Event",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url="https://example.com/event/200",
            description="Short"
        )
        id1, _ = temp_db.insert_event(event1)

        event2 = Event(
            title="Detailed Event",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url="https://example.com/event/200",
            description="Much longer and more detailed description",
            image_url="https://example.com/image.jpg",
            price=50.0
        )
        id2, is_dup = temp_db.insert_event(event2)

        assert is_dup is True
        assert id1 == id2

        # Check merged data
        merged = temp_db.get_event(id1)
        assert merged.source == "Source1"  # Keeps original source
        assert merged.description == "Much longer and more detailed description"
        assert merged.image_url == "https://example.com/image.jpg"
        assert merged.price == 50.0

    def test_database_handles_none_urls(self, temp_db):
        """Database should handle events with None URLs gracefully."""
        event1 = Event(
            title="Event without URL",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url=None
        )
        event2 = Event(
            title="Event without URL",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url=None
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        # Should detect as duplicate by title, not URL
        assert is_dup2 is True
        assert id1 == id2

        events = temp_db.get_all_events()
        assert len(events) == 1

    def test_database_handles_empty_string_urls(self, temp_db):
        """Database should handle events with empty string URLs."""
        event1 = Event(
            title="Event with empty URL",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            url=""
        )
        event2 = Event(
            title="Event with empty URL",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            url=""
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        # Should detect as duplicate by title
        assert is_dup2 is True
        assert id1 == id2

    def test_real_world_url_duplicate_scenario(self, temp_db):
        """Test with real-world duplicate URL scenario."""
        # Same event listed on multiple aggregators with same source URL
        timeout_event = Event(
            title="Tame Impala at Kia Forum",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="Timeout LA",
            url="https://www.kiaforum.com/events/tame-impala-2025"
        )

        discover_la_event = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="Discover LA",
            url="https://www.kiaforum.com/events/tame-impala-2025"  # Same venue URL
        )

        id1, _ = temp_db.insert_event(timeout_event)
        id2, is_dup = temp_db.insert_event(discover_la_event)

        assert is_dup is True
        assert id1 == id2

        events = temp_db.get_all_events()
        assert len(events) == 1
        assert events[0].url == "https://www.kiaforum.com/events/tame-impala-2025"


class TestURLDeduplicationPerformance:
    """Tests to verify URL deduplication is performed efficiently."""

    @pytest.fixture
    def temp_db_with_many_events(self):
        """Create a database with many events for performance testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(str(db_path))

            # Insert 100 events with different dates
            for i in range(100):
                event = Event(
                    title=f"Event {i}",
                    venue_name=f"Venue {i}",
                    event_date=datetime(2025, 11, 1) + timedelta(days=i),
                    source="Source1",
                    url=f"https://example.com/event/{i}"
                )
                db.insert_event(event, check_duplicates=False)

            yield db

    def test_url_check_finds_duplicate_quickly(self, temp_db_with_many_events):
        """URL check should find duplicate without scanning all events."""
        # Try to insert event with existing URL on the same day. event/50 was
        # inserted with date Nov 1 + 50 days = 2025-12-21, so stay within the
        # 24h URL window to exercise the direct URL fast-path.
        existing_url = "https://example.com/event/50"
        new_event = Event(
            title="New Event",
            event_date=datetime(2025, 12, 21, 12, 0),  # within the 24h URL window of event/50
            source="Source2",
            url=existing_url
        )

        result = temp_db_with_many_events.find_duplicate_event(new_event)

        # Should find duplicate via direct URL query
        assert result is not None
        duplicate, scores = result
        assert scores['match_method'] == 'url'
        assert duplicate.url == existing_url

    def test_no_url_falls_back_to_date_range_query(self, temp_db_with_many_events):
        """Events without URL should use efficient date range query."""
        new_event = Event(
            title="Event 50",  # Matches existing event title
            venue_name="Venue 50",
            event_date=datetime(2025, 11, 1) + timedelta(days=50),
            source="Source2",
            url=None
        )

        result = temp_db_with_many_events.find_duplicate_event(new_event)

        # Should find duplicate via title matching (not URL)
        assert result is not None
        duplicate, scores = result
        assert scores['match_method'] == 'title'
        assert scores['same_url'] is False

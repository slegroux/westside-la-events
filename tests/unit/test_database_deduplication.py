"""
Integration tests for database deduplication.
"""
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from src.data.database import Database
from src.data.models import Event


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(str(db_path))
        yield db


class TestDatabaseDeduplication:
    """Tests for database-level deduplication."""

    def test_insert_unique_events(self, temp_db):
        """Should insert unique events without duplication."""
        event1 = Event(
            title="Event A",
            venue_name="Venue A",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Event B",
            venue_name="Venue B",
            event_date=datetime(2025, 11, 13),
            source="Source1"
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        assert is_dup1 is False
        assert is_dup2 is False
        assert id1 != id2

        # Verify both events exist
        events = temp_db.get_all_events()
        assert len(events) == 2

    def test_detects_duplicate_from_different_source(self, temp_db):
        """Should detect and handle duplicates from different sources."""
        event1 = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="KCRW",
            description="Concert"
        )
        event2 = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="Discover LA",
            image_url="https://example.com/image.jpg"
        )

        # Insert first event
        id1, is_dup1 = temp_db.insert_event(event1)
        assert is_dup1 is False

        # Insert duplicate - should detect and merge
        id2, is_dup2 = temp_db.insert_event(event2)
        assert is_dup2 is True
        assert id1 == id2  # Should return same ID

        # Verify only one event exists
        events = temp_db.get_all_events()
        assert len(events) == 1

        # Verify merged data
        merged = events[0]
        assert merged.source == "KCRW"  # Keeps first source
        assert merged.description == "Concert"
        assert merged.image_url == "https://example.com/image.jpg"  # Added from second

    def test_allows_same_source_duplicates(self, temp_db):
        """Should allow duplicates from the same source."""
        event1 = Event(
            title="Same Event",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Same Event",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        assert is_dup1 is False
        assert is_dup2 is False  # Not detected as duplicate (same source)

        events = temp_db.get_all_events()
        assert len(events) == 2  # Both inserted

    def test_detects_similar_titles_with_venue_match(self, temp_db):
        """Should detect duplicates with similar titles and matching venues."""
        event1 = Event(
            title="Music Festival 2025",
            venue_name="Hollywood Bowl",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Music Festival",
            venue_name="Hollywood Bowl Los Angeles",
            event_date=datetime(2025, 11, 12),
            source="Source2"
        )

        id1, is_dup1 = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2)

        assert is_dup1 is False
        assert is_dup2 is True
        assert id1 == id2

        events = temp_db.get_all_events()
        assert len(events) == 1

    def test_respects_date_tolerance(self, temp_db):
        """Should only detect duplicates within date tolerance."""
        base_event = Event(
            title="Same Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12, 10, 0),
            source="Source1"
        )

        # Within tolerance (10 hours later)
        near_event = Event(
            title="Same Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12, 20, 0),
            source="Source2"
        )

        # Outside tolerance (2 days later)
        far_event = Event(
            title="Same Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 14, 10, 0),
            source="Source3"
        )

        id1, _ = temp_db.insert_event(base_event)
        id2, is_dup2 = temp_db.insert_event(near_event)
        id3, is_dup3 = temp_db.insert_event(far_event)

        assert is_dup2 is True  # Within tolerance
        assert id1 == id2

        assert is_dup3 is False  # Outside tolerance
        assert id3 != id1

        events = temp_db.get_all_events()
        assert len(events) == 2

    def test_can_disable_duplicate_checking(self, temp_db):
        """Should allow disabling duplicate checking."""
        event1 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source2"
        )

        id1, _ = temp_db.insert_event(event1)
        id2, is_dup2 = temp_db.insert_event(event2, check_duplicates=False)

        assert is_dup2 is False
        assert id1 != id2

        events = temp_db.get_all_events()
        assert len(events) == 2  # Both inserted

    def test_find_duplicate_event_method(self, temp_db):
        """Test find_duplicate_event method directly."""
        existing = Event(
            title="Existing Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        temp_db.insert_event(existing, check_duplicates=False)

        # Try to find duplicate
        new_event = Event(
            title="Existing Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source2"
        )

        result = temp_db.find_duplicate_event(new_event)
        assert result is not None

        duplicate, scores = result
        assert duplicate.title == "Existing Event"
        assert duplicate.source == "Source1"
        assert scores['title_similarity'] >= 0.85

    def test_no_duplicate_found(self, temp_db):
        """Should return None when no duplicate exists."""
        existing = Event(
            title="Event A",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        temp_db.insert_event(existing, check_duplicates=False)

        new_event = Event(
            title="Event B",
            event_date=datetime(2025, 11, 15),
            source="Source2"
        )

        result = temp_db.find_duplicate_event(new_event)
        assert result is None

    def test_real_world_duplicate_scenario(self, temp_db):
        """Test with real duplicate examples from the database."""
        # Example 1: Tame Impala
        kcrw_event = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            address="Kia Forum, Inglewood, CA",
            event_date=datetime(2025, 11, 12),
            source="KCRW",
            url="https://www.kcrw.com/events/tame-impala-2"
        )

        discover_la_event = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            address="Kia Forum, Inglewood, Los Angeles, CA",
            event_date=datetime(2025, 11, 12),
            source="Discover LA",
            url="https://www.discoverlosangeles.com/event/2025/11/11/tame-impala-0"
        )

        id1, _ = temp_db.insert_event(kcrw_event)
        id2, is_dup = temp_db.insert_event(discover_la_event)

        assert is_dup is True
        assert id1 == id2

        events = temp_db.get_all_events()
        assert len(events) == 1

        # Example 2: Paranormal Activity
        kcrw_paranormal = Event(
            title="'Paranormal Activity' Opening Night",
            venue_name="Center Theatre Group",
            event_date=datetime(2025, 11, 14),
            source="KCRW",
            url="https://www.kcrw.com/events/paranormal-activity-opening-night"
        )

        discover_paranormal = Event(
            title="Paranormal Activity (OPENING NIGHT)",
            venue_name="Ahmanson Theatre",
            event_date=datetime(2025, 11, 14),
            source="Discover LA",
            url="https://www.discoverlosangeles.com/event/2025/11/13/paranormal-activity-opening-night"
        )

        id3, _ = temp_db.insert_event(kcrw_paranormal)
        id4, is_dup2 = temp_db.insert_event(discover_paranormal)

        assert is_dup2 is True
        assert id3 == id4

        events = temp_db.get_all_events()
        assert len(events) == 2  # Tame Impala + Paranormal Activity

    def test_merge_enriches_data(self, temp_db):
        """Merged events should have enriched data from both sources."""
        minimal_event = Event(
            title="Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source1",
            description="Short"
        )

        detailed_event = Event(
            title="Event",
            venue_name="Venue",
            event_date=datetime(2025, 11, 12),
            source="Source2",
            description="Much longer and more detailed description",
            image_url="https://example.com/image.jpg",
            price=25.0,
            latitude=34.0522,
            longitude=-118.2437
        )

        id1, _ = temp_db.insert_event(minimal_event)
        id2, is_dup = temp_db.insert_event(detailed_event)

        assert is_dup is True
        assert id1 == id2

        # Verify merged data
        merged = temp_db.get_event(id1)
        assert merged.source == "Source1"  # Keeps original source
        assert merged.description == "Much longer and more detailed description"
        assert merged.image_url == "https://example.com/image.jpg"
        assert merged.price == 25.0
        assert merged.latitude == 34.0522
        assert merged.longitude == -118.2437

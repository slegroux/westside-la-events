"""
Tests for event deduplication utilities.
"""
import pytest
from datetime import datetime, timedelta

from src.data.models import Event
from src.utils.deduplication import (
    calculate_similarity,
    normalize_title,
    normalize_venue,
    events_are_duplicates,
    find_duplicate,
    merge_event_data
)


class TestCalculateSimilarity:
    """Tests for string similarity calculation."""

    def test_identical_strings(self):
        """Identical strings should have 100% similarity."""
        assert calculate_similarity("Hello World", "Hello World") == 1.0

    def test_case_insensitive(self):
        """Similarity should be case-insensitive."""
        assert calculate_similarity("Hello World", "hello world") == 1.0

    def test_completely_different(self):
        """Completely different strings should have low similarity."""
        similarity = calculate_similarity("abc", "xyz")
        assert similarity < 0.3

    def test_empty_strings(self):
        """Empty strings should return 0.0."""
        assert calculate_similarity("", "") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity("", "hello") == 0.0


class TestNormalizeTitle:
    """Tests for title normalization."""

    def test_removes_quotes(self):
        """Should remove various quote types."""
        assert normalize_title("'Paranormal Activity'") == "paranormal activity"
        assert normalize_title('"The Event"') == "the event"
        assert normalize_title("'Opening Night'") == "opening night"

    def test_normalizes_whitespace(self):
        """Should normalize multiple spaces."""
        assert normalize_title("Hello    World") == "hello world"
        assert normalize_title("  Event  ") == "event"

    def test_removes_special_chars(self):
        """Should remove special characters."""
        assert normalize_title("Event @ Venue") == "event venue"
        assert normalize_title("Music & Arts") == "music arts"

    def test_lowercase_conversion(self):
        """Should convert to lowercase."""
        assert normalize_title("TAME IMPALA") == "tame impala"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert normalize_title("") == ""
        assert normalize_title(None) == ""


class TestNormalizeVenue:
    """Tests for venue normalization."""

    def test_removes_location_suffix(self):
        """Should remove location suffixes."""
        assert normalize_venue("Kia Forum - Los Angeles") == "kia forum"
        assert normalize_venue("Venue Los Angeles") == "venue"
        assert normalize_venue("Place LA") == "place"

    def test_removes_venue_type(self):
        """Should remove venue type suffixes."""
        assert normalize_venue("Ahmanson Theatre") == "ahmanson"
        assert normalize_venue("LACMA Museum") == "lacma"
        assert normalize_venue("Arts Center") == "arts"

    def test_normalizes_whitespace(self):
        """Should normalize whitespace."""
        assert normalize_venue("  Center  Theatre  Group  ") == "center theatre group"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert normalize_venue("") == ""
        assert normalize_venue(None) == ""


class TestEventsAreDuplicates:
    """Tests for duplicate detection logic."""

    def test_same_title_and_date(self):
        """Events with identical titles and same date should be duplicates."""
        event1 = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="KCRW"
        )
        event2 = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="Discover LA"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['title_similarity'] >= 0.85

    def test_similar_title_with_quotes(self):
        """Should detect duplicates despite quote differences."""
        event1 = Event(
            title="'Paranormal Activity' Opening Night",
            venue_name="Center Theatre Group",
            event_date=datetime(2025, 11, 14),
            source="KCRW"
        )
        event2 = Event(
            title="Paranormal Activity (OPENING NIGHT)",
            venue_name="Ahmanson Theatre",
            event_date=datetime(2025, 11, 14),
            source="Discover LA"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['title_similarity'] >= 0.85

    def test_same_source_exact_duplicate(self):
        """Same source + exact same title + same venue + same date = duplicate.

        Mirrors a show listed by one source under two URLs (e.g. a venue's own
        page and its Eventbrite link). A matching venue is required so we never
        merge same-titled events when venue info is absent.
        """
        event1 = Event(
            title="Same Event",
            venue_name="Westside Comedy Theater",
            event_date=datetime(2025, 11, 12),
            source="KCRW"
        )
        event2 = Event(
            title="Same Event",
            venue_name="Westside Comedy Theater",
            event_date=datetime(2025, 11, 12),
            source="KCRW"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['same_source'] is True
        assert scores['match_method'] == 'exact_same_source'

    def test_same_source_different_title_not_duplicate(self):
        """Same source but different titles should not be duplicates."""
        event1 = Event(
            title="Concert A",
            event_date=datetime(2025, 11, 12),
            source="KCRW"
        )
        event2 = Event(
            title="Concert B",
            event_date=datetime(2025, 11, 12),
            source="KCRW"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is False
        assert scores['same_source'] is True

    def test_different_dates_not_duplicate(self):
        """Events with same title but different dates should not be duplicates."""
        event1 = Event(
            title="Concert",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Concert",
            event_date=datetime(2025, 11, 15),  # 3 days later
            source="Source2"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is False
        assert scores['date_diff_hours'] > 24

    def test_within_date_tolerance(self):
        """Events within date tolerance should be considered."""
        event1 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12, 10, 0),
            source="Source1"
        )
        event2 = Event(
            title="Event",
            event_date=datetime(2025, 11, 12, 20, 0),  # 10 hours later
            source="Source2"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['date_diff_hours'] <= 24

    def test_similar_title_matching_venue(self):
        """Somewhat similar title + matching venue = duplicate."""
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

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['title_similarity'] >= 0.7
        assert scores['venue_similarity'] >= 0.8

    def test_same_url_different_source(self):
        """Same URL from different sources should be duplicate."""
        event1 = Event(
            title="Event A",
            event_date=datetime(2025, 11, 12),
            url="https://example.com/event",
            source="Source1"
        )
        event2 = Event(
            title="Event B",
            event_date=datetime(2025, 11, 12),
            url="https://example.com/event",
            source="Source2"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is True
        assert scores['same_url'] is True

    def test_completely_different_events(self):
        """Completely different events should not be duplicates."""
        event1 = Event(
            title="Concert at Venue A",
            venue_name="Venue A",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )
        event2 = Event(
            title="Art Exhibition at Gallery B",
            venue_name="Gallery B",
            event_date=datetime(2025, 11, 12),
            source="Source2"
        )

        is_dup, scores = events_are_duplicates(event1, event2)
        assert is_dup is False


class TestFindDuplicate:
    """Tests for finding duplicates in a list."""

    def test_finds_duplicate_in_list(self):
        """Should find duplicate event in existing list."""
        existing = [
            Event(
                title="Event A",
                event_date=datetime(2025, 11, 10),
                source="Source1"
            ),
            Event(
                title="Tame Impala",
                venue_name="Kia Forum",
                event_date=datetime(2025, 11, 12),
                source="KCRW"
            ),
            Event(
                title="Event C",
                event_date=datetime(2025, 11, 14),
                source="Source1"
            ),
        ]

        new_event = Event(
            title="Tame Impala",
            venue_name="Kia Forum",
            event_date=datetime(2025, 11, 12),
            source="Discover LA"
        )

        result = find_duplicate(new_event, existing)
        assert result is not None
        duplicate, scores = result
        assert duplicate.source == "KCRW"

    def test_no_duplicate_found(self):
        """Should return None when no duplicate exists."""
        existing = [
            Event(
                title="Event A",
                event_date=datetime(2025, 11, 10),
                source="Source1"
            ),
            Event(
                title="Event B",
                event_date=datetime(2025, 11, 12),
                source="Source1"
            ),
        ]

        new_event = Event(
            title="Event C",
            event_date=datetime(2025, 11, 14),
            source="Source2"
        )

        result = find_duplicate(new_event, existing)
        assert result is None

    def test_empty_list(self):
        """Should return None for empty list."""
        new_event = Event(
            title="Event",
            event_date=datetime(2025, 11, 12),
            source="Source1"
        )

        result = find_duplicate(new_event, [])
        assert result is None


class TestMergeEventData:
    """Tests for merging duplicate event data."""

    def test_prefers_primary_source(self):
        """Merged event should keep primary source."""
        primary = Event(
            id=1,
            title="Event",
            source="Primary",
            event_date=datetime(2025, 11, 12)
        )
        secondary = Event(
            id=2,
            title="Event",
            source="Secondary",
            event_date=datetime(2025, 11, 12)
        )

        merged = merge_event_data(primary, secondary)
        assert merged.source == "Primary"
        assert merged.id == 1

    def test_fills_missing_fields(self):
        """Should fill missing fields from secondary."""
        primary = Event(
            id=1,
            title="Event",
            venue_name="Venue",
            source="Primary",
            event_date=datetime(2025, 11, 12)
        )
        secondary = Event(
            id=2,
            title="Event",
            venue_name="Venue",
            description="Detailed description",
            image_url="https://example.com/image.jpg",
            source="Secondary",
            event_date=datetime(2025, 11, 12)
        )

        merged = merge_event_data(primary, secondary)
        assert merged.description == "Detailed description"
        assert merged.image_url == "https://example.com/image.jpg"
        assert merged.source == "Primary"

    def test_prefers_longer_description(self):
        """Should prefer longer description."""
        primary = Event(
            id=1,
            title="Event",
            description="Short",
            source="Primary",
            event_date=datetime(2025, 11, 12)
        )
        secondary = Event(
            id=2,
            title="Event",
            description="Much longer and more detailed description",
            source="Secondary",
            event_date=datetime(2025, 11, 12)
        )

        merged = merge_event_data(primary, secondary)
        assert merged.description == "Much longer and more detailed description"

    def test_keeps_primary_non_empty_fields(self):
        """Should not overwrite primary's non-empty fields."""
        primary = Event(
            id=1,
            title="Primary Title",
            venue_name="Primary Venue",
            description="Primary desc",
            source="Primary",
            event_date=datetime(2025, 11, 12)
        )
        secondary = Event(
            id=2,
            title="Secondary Title",
            venue_name="Secondary Venue",
            description="Sec",
            source="Secondary",
            event_date=datetime(2025, 11, 12)
        )

        merged = merge_event_data(primary, secondary)
        assert merged.title == "Primary Title"
        assert merged.venue_name == "Primary Venue"
        assert merged.description == "Primary desc"

    def test_handles_price_and_free(self):
        """Should merge price and is_free fields."""
        primary = Event(
            id=1,
            title="Event",
            source="Primary",
            event_date=datetime(2025, 11, 12),
            is_free=False
        )
        secondary = Event(
            id=2,
            title="Event",
            source="Secondary",
            event_date=datetime(2025, 11, 12),
            price=25.0,
            is_free=True
        )

        merged = merge_event_data(primary, secondary)
        assert merged.price == 25.0
        assert merged.is_free is True  # Takes True from secondary

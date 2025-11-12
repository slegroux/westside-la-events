"""
Unit tests for the database layer.
"""
import pytest
from datetime import datetime, timedelta

from src.data.database import Database, sanitize_fts_query
from src.data.models import Event


@pytest.mark.unit
class TestDatabase:
    """Test Database class functionality."""

    def test_database_initialization(self, temp_db_path):
        """Test that database initializes correctly."""
        db = Database(temp_db_path)
        assert db is not None
        assert db.db_path == temp_db_path

    def test_insert_event(self, db, sample_event):
        """Test inserting a single event."""
        event_id = db.insert_event(sample_event)
        assert event_id is not None
        assert event_id > 0

        # Verify the event can be retrieved
        retrieved = db.get_event(event_id)
        assert retrieved is not None
        assert retrieved.title == sample_event.title

    def test_insert_duplicate_event(self, db, sample_event):
        """Test that duplicate events are detected."""
        # Insert event first time
        event_id = db.insert_event(sample_event)
        assert event_id is not None

        # Try to insert the same event again (same URL and date)
        duplicate_event = Event(
            title=sample_event.title,
            venue_name=sample_event.venue_name,
            event_date=sample_event.event_date,
            source=sample_event.source,
            url=sample_event.url
        )
        # Check if duplicate exists
        exists = db.event_exists(duplicate_event.url, duplicate_event.event_date)
        assert exists is True

    def test_get_event(self, db, sample_event):
        """Test retrieving a single event by ID."""
        event_id = db.insert_event(sample_event)
        assert event_id is not None

        retrieved_event = db.get_event(event_id)
        assert retrieved_event is not None
        assert retrieved_event.id == event_id
        assert retrieved_event.title == sample_event.title
        assert retrieved_event.venue_name == sample_event.venue_name

    def test_get_nonexistent_event(self, db):
        """Test retrieving a non-existent event returns None."""
        event = db.get_event(99999)
        assert event is None

    def test_get_all_events(self, populated_db):
        """Test getting all events from database."""
        events = populated_db.get_all_events()
        assert len(events) == 4
        assert all(isinstance(event, Event) for event in events)

    def test_get_events_with_limit(self, populated_db):
        """Test getting events with a limit."""
        events = populated_db.get_all_events(limit=2)
        assert len(events) == 2

    def test_search_events_by_query(self, populated_db):
        """Test searching events by keyword."""
        events = populated_db.search_events(query="music")
        assert len(events) >= 1
        assert any("music" in event.title.lower() for event in events)

    def test_search_events_by_category(self, populated_db):
        """Test searching events by category."""
        events = populated_db.search_events(categories=["Music"])
        assert len(events) >= 1
        assert all(event.category == "Music" for event in events)

    def test_search_events_by_date_range(self, populated_db):
        """Test searching events within a date range."""
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=7)

        events = populated_db.search_events(
            start_date=start_date,
            end_date=end_date
        )

        assert len(events) >= 1
        for event in events:
            if event.event_date:
                assert start_date <= event.event_date <= end_date

    def test_event_exists(self, db, sample_event):
        """Test checking if event exists."""
        # Event should not exist initially
        exists = db.event_exists(sample_event.url, sample_event.event_date)
        assert exists is False

        # Insert event
        db.insert_event(sample_event)

        # Now it should exist
        exists = db.event_exists(sample_event.url, sample_event.event_date)
        assert exists is True

    def test_delete_event(self, db, sample_event):
        """Test deleting an event."""
        # Insert event
        event_id = db.insert_event(sample_event)
        assert event_id is not None

        # Verify it exists
        retrieved = db.get_event(event_id)
        assert retrieved is not None

        # Delete the event
        result = db.delete_event(event_id)
        assert result is True

        # Verify it's gone
        deleted_event = db.get_event(event_id)
        assert deleted_event is None

    def test_update_event(self, db, sample_event):
        """Test updating an event."""
        # Insert event
        event_id = db.insert_event(sample_event)
        assert event_id is not None

        # Set the ID on the event object (insert_event doesn't do this automatically)
        sample_event.id = event_id

        # Update the event
        sample_event.title = "Updated Title"
        sample_event.description = "Updated Description"
        result = db.update_event(sample_event)
        assert result is True

        # Retrieve and verify
        updated_event = db.get_event(event_id)
        assert updated_event.title == "Updated Title"
        assert updated_event.description == "Updated Description"


@pytest.mark.unit
class TestEvent:
    """Test Event model functionality."""

    def test_event_creation(self, sample_event):
        """Test creating an Event object."""
        assert sample_event.title == "Test Event"
        assert sample_event.venue_name == "Test Venue"
        assert sample_event.category == "Music"
        assert sample_event.latitude == 34.0194
        assert sample_event.longitude == -118.4912

    def test_event_to_dict(self, sample_event):
        """Test converting Event to dictionary."""
        event_dict = sample_event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict['title'] == sample_event.title
        assert event_dict['venue_name'] == sample_event.venue_name
        assert event_dict['category'] == sample_event.category
        assert event_dict['latitude'] == sample_event.latitude
        assert event_dict['longitude'] == sample_event.longitude

    def test_event_from_dict(self, sample_event):
        """Test creating Event from dictionary."""
        event_dict = sample_event.to_dict()
        new_event = Event.from_dict(event_dict)

        assert new_event.title == sample_event.title
        assert new_event.venue_name == sample_event.venue_name
        assert new_event.category == sample_event.category

    def test_event_with_minimal_data(self):
        """Test creating Event with minimal required data."""
        event = Event(title="Minimal Event")
        assert event.title == "Minimal Event"
        assert event.description == ""
        assert event.latitude is None
        assert event.longitude is None


@pytest.mark.unit
class TestFTSSanitization:
    """Test FTS5 query sanitization for security."""

    def test_sanitize_normal_query(self):
        """Test sanitization of normal search queries."""
        assert sanitize_fts_query("music concert") == '"music concert"'
        assert sanitize_fts_query("jazz") == '"jazz"'
        assert sanitize_fts_query("art exhibition") == '"art exhibition"'

    def test_sanitize_query_with_quotes(self):
        """Test that quotes are properly escaped."""
        # Double quotes should be doubled (FTS5 escaping)
        assert sanitize_fts_query('hello "world"') == '"hello ""world"""'
        assert sanitize_fts_query('"test"') == '"""test"""'

    def test_sanitize_query_with_fts_operators(self):
        """Test that FTS operators are neutralized."""
        # These should be treated as literal text, not operators
        assert sanitize_fts_query("test AND query") == '"test AND query"'
        assert sanitize_fts_query("hello OR world") == '"hello OR world"'
        assert sanitize_fts_query("NOT important") == '"NOT important"'
        assert sanitize_fts_query("NEAR term") == '"NEAR term"'

    def test_sanitize_query_with_special_chars(self):
        """Test that special FTS characters are neutralized."""
        # Parentheses, asterisks, etc. should be treated as literals
        assert sanitize_fts_query("test*") == '"test*"'
        assert sanitize_fts_query("(grouped)") == '"(grouped)"'
        assert sanitize_fts_query("^prefix") == '"^prefix"'
        assert sanitize_fts_query("+important") == '"+important"'

    def test_sanitize_empty_query(self):
        """Test that empty queries are handled safely."""
        assert sanitize_fts_query("") == '""'
        assert sanitize_fts_query("   ") == '""'
        assert sanitize_fts_query(None) == '""'

    def test_sanitize_query_with_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        assert sanitize_fts_query("  hello world  ") == '"hello world"'
        assert sanitize_fts_query("\t\ntab\n\t") == '"tab"'

    def test_search_with_malicious_queries(self, populated_db):
        """Test that malicious queries don't crash the database."""
        # These queries would previously cause FTS syntax errors
        malicious_queries = [
            'test"',  # Unmatched quote
            '"broken',  # Unmatched quote
            'query AND',  # Incomplete operator
            'test OR',  # Incomplete operator
            '(((',  # Unmatched parentheses
            'NOT',  # Standalone operator
            '*',  # Wildcard alone
            'test AND (broken',  # Mixed operators and unmatched parens
            '"test" OR "broken',  # Mixed valid and invalid
        ]

        for query in malicious_queries:
            try:
                # Should not raise exception
                results = populated_db.search_events(query=query)
                # Results can be empty or non-empty, just shouldn't crash
                assert isinstance(results, list)
            except Exception as e:
                pytest.fail(f"Query '{query}' caused exception: {e}")

    def test_search_with_sanitized_queries_returns_results(self, populated_db):
        """Test that sanitized queries still return relevant results."""
        # Add an event with special characters in the title
        event = Event(
            title='Art & Music: A "Special" Event',
            venue_name="Test Venue",
            event_date=datetime.now() + timedelta(days=1),
            source="test",
            category="Music"
        )
        populated_db.insert_event(event)

        # Search for the event with special characters
        results = populated_db.search_events(query='Art & Music')
        assert len(results) >= 1
        assert any('Art & Music' in e.title for e in results)

    def test_search_preserves_functionality(self, populated_db):
        """Test that sanitization doesn't break normal search functionality."""
        # Normal searches should still work
        results = populated_db.search_events(query="music")
        music_events = [e for e in results if "music" in e.title.lower() or "music" in e.description.lower()]
        assert len(music_events) >= 1

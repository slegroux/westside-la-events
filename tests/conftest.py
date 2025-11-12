"""
Pytest configuration and shared fixtures for testing.
"""
import pytest
import sys
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.data.database import Database
from src.data.models import Event
from src.search.query import EventSearch


# Block problematic pytest plugins
def pytest_configure(config):
    """Configure pytest and block problematic plugins."""
    # List of plugins to block
    blocked_plugins = [
        'rostest',
        'launch_testing',
        'launch_testing_ros',
        'ament_xmllint',
        'ament_lint',
        'ament_pep257',
        'ament_flake8',
        'ament_copyright',
        'dash',
    ]

    for plugin in blocked_plugins:
        if config.pluginmanager.has_plugin(plugin):
            config.pluginmanager.unregister(name=plugin)


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db(temp_db_path):
    """Create a test database instance."""
    database = Database(temp_db_path)
    yield database


@pytest.fixture
def search(db):
    """Create a test EventSearch instance."""
    return EventSearch(db)


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        title="Test Event",
        description="A test event description",
        venue_name="Test Venue",
        address="123 Test St, Santa Monica, CA",
        latitude=34.0194,
        longitude=-118.4912,
        event_date=datetime.now() + timedelta(days=1),
        end_date=datetime.now() + timedelta(days=1, hours=2),
        category="Music",
        source="Test Source",
        url="https://example.com/event",
        image_url="https://example.com/image.jpg"
    )


@pytest.fixture
def sample_events():
    """Create multiple sample events for testing."""
    now = datetime.now()
    return [
        Event(
            title="Music Concert",
            description="Live music performance",
            venue_name="Santa Monica Pier",
            address="Santa Monica, CA",
            latitude=34.0099,
            longitude=-118.4987,
            event_date=now + timedelta(days=1),
            category="Music",
            source="Test Source",
            url="https://example.com/event1"
        ),
        Event(
            title="Art Exhibition",
            description="Contemporary art show",
            venue_name="Getty Center",
            address="Los Angeles, CA",
            latitude=34.0781,
            longitude=-118.4741,
            event_date=now + timedelta(days=2),
            category="Art",
            source="Test Source",
            url="https://example.com/event2"
        ),
        Event(
            title="Food Festival",
            description="Culinary experience",
            venue_name="Venice Beach",
            address="Venice, CA",
            latitude=33.9850,
            longitude=-118.4695,
            event_date=now + timedelta(days=3),
            category="Food & Drink",
            source="Test Source",
            url="https://example.com/event3"
        ),
        Event(
            title="Past Event",
            description="This event already happened",
            venue_name="Old Venue",
            address="Los Angeles, CA",
            latitude=34.0522,
            longitude=-118.2437,
            event_date=now - timedelta(days=1),
            category="Other",
            source="Test Source",
            url="https://example.com/event4"
        )
    ]


@pytest.fixture
def populated_db(db, sample_events):
    """Create a database with sample events."""
    for event in sample_events:
        db.insert_event(event)
    return db


@pytest.fixture
def app_client():
    """Create a test client for the FastHTML app."""
    from httpx import AsyncClient
    from src.web.app import app

    return AsyncClient(app=app, base_url="http://test")


@pytest.fixture
def mock_geocoding_service(monkeypatch):
    """Mock the geocoding service for testing without API calls."""
    from src.utils.geocoding import GeocodingService

    class MockGeocodingService:
        def __init__(self, *args, **kwargs):
            self.cache = {}

        def geocode(self, address):
            """Return mock coordinates for testing."""
            # Return mock coordinates based on address
            if "santa monica" in address.lower():
                return (34.0194, -118.4912)
            elif "los angeles" in address.lower():
                return (34.0522, -118.2437)
            elif "venice" in address.lower():
                return (33.9850, -118.4695)
            return (34.0522, -118.2437)  # Default LA coordinates

        def is_in_westside(self, lat, lng):
            """Mock westside check."""
            return True

    monkeypatch.setattr("src.utils.geocoding.GeocodingService", MockGeocodingService)
    return MockGeocodingService()


@pytest.fixture
def temp_geocode_cache():
    """Create a temporary geocoding cache file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_path = f.name
    yield cache_path
    # Cleanup
    if os.path.exists(cache_path):
        os.unlink(cache_path)

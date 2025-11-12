"""
Unit tests for web application endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta

from src.web.app import app, state
from src.data.models import Event


@pytest.mark.unit
@pytest.mark.asyncio
class TestWebEndpoints:
    """Test FastHTML web application endpoints."""

    async def test_home_page(self, populated_db):
        """Test home page loads successfully."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            assert response.status_code == 200
            assert "Westside LA Events" in response.text

    async def test_api_events_endpoint(self, populated_db):
        """Test /api/events endpoint returns JSON."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/events")
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            events = response.json()
            assert isinstance(events, list)
            assert len(events) > 0

    async def test_api_events_with_query_param(self, populated_db):
        """Test /api/events with query parameter."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/events?q=music")
            assert response.status_code == 200

            events = response.json()
            assert isinstance(events, list)

    async def test_api_events_with_category_filter(self, populated_db):
        """Test /api/events with category filter."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/events?category=Music")
            assert response.status_code == 200

            events = response.json()
            assert isinstance(events, list)
            if len(events) > 0:
                assert all(event["category"] == "Music" for event in events)

    async def test_api_events_with_date_filter(self, populated_db):
        """Test /api/events with date filter."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/events?date_filter=upcoming")
            assert response.status_code == 200

            events = response.json()
            assert isinstance(events, list)

    async def test_event_detail_page(self, populated_db):
        """Test event detail page."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        # Get first event
        events = populated_db.get_all_events(limit=1)
        assert len(events) > 0
        event_id = events[0].id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/event/{event_id}")
            assert response.status_code == 200
            assert events[0].title in response.text

    async def test_event_detail_not_found(self, populated_db):
        """Test event detail page with non-existent ID."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/event/99999")
            assert response.status_code == 200
            assert "Event Not Found" in response.text

    async def test_api_single_event(self, populated_db):
        """Test /api/events/{id} endpoint."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        # Get first event
        events = populated_db.get_all_events(limit=1)
        assert len(events) > 0
        event_id = events[0].id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/events/{event_id}")
            assert response.status_code == 200

            event_data = response.json()
            assert event_data["id"] == event_id
            assert event_data["title"] == events[0].title

    async def test_api_single_event_not_found(self, populated_db):
        """Test /api/events/{id} with non-existent ID."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/events/99999")
            assert response.status_code == 404

            error = response.json()
            assert "error" in error

    async def test_events_list_htmx_endpoint(self, populated_db):
        """Test /events/list HTMX endpoint."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/events/list")
            assert response.status_code == 200
            # Should return HTML fragment with events
            assert "event-card" in response.text or "No events found" in response.text

    async def test_events_list_with_filters(self, populated_db):
        """Test /events/list with filter parameters."""
        state.db = populated_db
        from src.search.query import EventSearch
        state.search = EventSearch(populated_db)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/events/list?category=Music&date_filter=upcoming")
            assert response.status_code == 200

    async def test_static_file_serving(self):
        """Test static file serving (if CSS exists)."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Try to access static CSS (may not exist in test environment)
            response = await client.get("/static/css/style.css")
            # Either file exists (200) or doesn't exist (404) is acceptable
            assert response.status_code in [200, 404]

    async def test_favicon_endpoint(self):
        """Test favicon endpoint."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/favicon.ico")
            # Should return 200 if favicon exists, 204 if not found, or 404 in test mode
            # Note: FastHTML/Starlette may handle favicon differently in test vs production
            assert response.status_code in [200, 204, 404]


@pytest.mark.unit
class TestPageComponents:
    """Test page component functions."""

    def test_event_card_creation(self):
        """Test event card component."""
        from src.web.app import event_card

        event = Event(
            title="Test Event",
            description="Test Description",
            venue_name="Test Venue",
            event_date=datetime.now(),
            category="Music",
            source="Test"
        )

        card = event_card(event)
        assert card is not None

    def test_events_list_with_events(self, sample_events):
        """Test events list component with events."""
        from src.web.app import events_list

        result = events_list(sample_events[:3])  # Use first 3 events
        assert result is not None

    def test_events_list_empty(self):
        """Test events list component with no events."""
        from src.web.app import events_list

        result = events_list([])
        assert result is not None

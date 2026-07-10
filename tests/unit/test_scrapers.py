"""
Unit tests for scrapers.
"""
import pytest
import requests
from datetime import datetime
from unittest.mock import Mock, patch

from src.scrapers.base import BaseScraper, ScraperError
from src.scrapers.timeout import TimeoutScraper
from src.data.models import Event


@pytest.mark.unit
class TestBaseScraper:
    """Test BaseScraper functionality."""

    def test_base_scraper_initialization(self):
        """Test BaseScraper initializes correctly."""
        # Create a concrete implementation for testing
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test Source")
        assert scraper.source_name == "Test Source"
        assert scraper.geocoding_service is not None
        assert scraper.session is not None

    def test_create_event_with_address(self, mock_geocoding_service):
        """Test creating an event with geocoding."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test Source")

        event = scraper.create_event(
            title="Test Event",
            description="Test Description",
            venue_name="Test Venue",
            address="Santa Monica, CA"
        )

        assert event.title == "Test Event"
        assert event.venue_name == "Test Venue"
        assert event.source == "Test Source"

    def test_create_event_without_address(self, mock_geocoding_service):
        """Test creating an event without address."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test Source")

        # Create event with venue name in Westside area to pass location validation
        event = scraper.create_event(
            title="Test Event",
            description="Test Description",
            venue_name="Santa Monica Pier"  # Known Westside venue
        )

        # Should create event even without address if venue_name validates
        assert event is not None
        assert event.title == "Test Event"

    def test_clean_text(self):
        """Test text cleaning utility."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test")

        # Test with extra whitespace
        cleaned = scraper.clean_text("  Test   Event   ")
        assert cleaned == "Test Event"

        # Test with None
        cleaned = scraper.clean_text(None)
        assert cleaned == ""

        # Test with newlines and tabs
        cleaned = scraper.clean_text("Test\n\tEvent\n")
        assert cleaned == "Test Event"

    def test_normalize_url_absolute(self):
        """Test URL normalization with absolute URL."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test")

        url = scraper.normalize_url("https://example.com/event", "https://base.com")
        assert url == "https://example.com/event"

    def test_normalize_url_relative(self):
        """Test URL normalization with relative URL."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test")

        # Test with leading slash
        url = scraper.normalize_url("/events/123", "https://example.com")
        assert url == "https://example.com/events/123"

        # Test without leading slash
        url = scraper.normalize_url("events/123", "https://example.com/")
        assert url == "https://example.com/events/123"

    def test_parse_html(self):
        """Test HTML parsing."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = TestScraper("Test")

        html = "<html><body><h1>Test</h1></body></html>"
        soup = scraper.parse_html(html)

        assert soup is not None
        assert soup.find('h1').text == "Test"

    @patch('requests.Session.get')
    def test_fetch_page_success(self, mock_get):
        """Test successful page fetch."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        # Mock successful response
        mock_response = Mock()
        mock_response.text = "<html>Test</html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        scraper = TestScraper("Test")
        html = scraper.fetch_page("https://example.com")

        assert html == "<html>Test</html>"
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_fetch_page_failure(self, mock_get):
        """Test failed page fetch."""
        class TestScraper(BaseScraper):
            def scrape(self):
                return []

        # Mock failed response with requests.RequestException
        mock_get.side_effect = requests.RequestException("Connection error")

        scraper = TestScraper("Test")
        html = scraper.fetch_page("https://example.com")

        assert html is None


@pytest.mark.unit
class TestTimeoutScraper:
    """Test TimeoutScraper functionality."""

    def test_timeout_scraper_initialization(self):
        """Test TimeoutScraper initializes correctly."""
        scraper = TimeoutScraper()
        assert scraper.source_name == "Timeout LA"
        assert scraper.base_url == "https://www.timeout.com"

    @patch.object(TimeoutScraper, 'fetch_page')
    def test_scrape_no_page(self, mock_fetch):
        """Test scraping when page fetch fails."""
        mock_fetch.return_value = None

        scraper = TimeoutScraper()
        events = scraper.scrape()

        assert events == []

    @patch.object(TimeoutScraper, 'fetch_page')
    def test_scrape_empty_page(self, mock_fetch):
        """Test scraping with page containing no events."""
        mock_fetch.return_value = "<html><body><p>No events</p></body></html>"

        scraper = TimeoutScraper()
        events = scraper.scrape()

        assert events == []

    @patch.object(TimeoutScraper, 'fetch_page')
    @patch.object(TimeoutScraper, 'create_event')
    def test_scrape_with_events(self, mock_create_event, mock_fetch):
        """Test scraping with valid event cards."""
        # Mock HTML with event card structure
        html = """
        <html><body>
            <article class="tile">
                <h3 data-testid="tile-title_testID">Test Event</h3>
                <p>Test Description</p>
                <a data-testid="tile-link_testID" href="/events/test">Link</a>
                <img src="/image.jpg" />
                <section data-testid="tags_testID">
                    <ul>
                        <li>Music</li>
                        <li>Santa Monica</li>
                        <li><time datetime="2025-12-01T19:00:00">Dec 1</time></li>
                    </ul>
                </section>
            </article>
        </body></html>
        """
        mock_fetch.return_value = html

        # Mock event creation
        mock_event = Event(title="Test Event", source="Timeout LA")
        mock_create_event.return_value = mock_event

        scraper = TimeoutScraper()
        events = scraper.scrape()

        # Verify create_event was called
        assert mock_create_event.called


@pytest.mark.unit
class TestGeocodingService:
    """Test GeocodingService functionality."""

    def test_geocoding_service_initialization(self, temp_geocode_cache):
        """Test GeocodingService initializes."""
        from src.utils.geocoding import GeocodingService

        service = GeocodingService(cache_file=temp_geocode_cache)
        assert service is not None
        assert service.geolocator is not None

    def test_geocoding_cache(self, temp_geocode_cache):
        """A repeated lookup is served from cache and does not re-hit the API."""
        from unittest.mock import MagicMock
        from src.utils.geocoding import GeocodingService

        service = GeocodingService(cache_file=temp_geocode_cache)
        # Mock the underlying geocoder so this unit test never touches the
        # network (the live Nominatim call was flaky under rate limiting).
        service.geolocator.geocode = MagicMock(
            return_value=MagicMock(latitude=34.0194, longitude=-118.4912)
        )

        result1 = service.geocode("Santa Monica, CA")  # cache miss -> calls API
        result2 = service.geocode("Santa Monica, CA")  # cache hit -> no API call

        assert result1 == result2
        assert result1 == (34.0194, -118.4912)
        # Proves the cache worked: the API was invoked only once.
        assert service.geolocator.geocode.call_count == 1

    def test_geocoding_empty_address(self, temp_geocode_cache):
        """Test geocoding with empty address."""
        from src.utils.geocoding import GeocodingService

        service = GeocodingService(cache_file=temp_geocode_cache)

        result = service.geocode("")
        assert result is None

        result = service.geocode(None)
        assert result is None

    def test_is_in_westside(self, temp_geocode_cache):
        """Test westside boundary check."""
        from src.utils.geocoding import GeocodingService

        service = GeocodingService(cache_file=temp_geocode_cache)

        # Santa Monica coordinates (should be in Westside)
        assert service.is_in_westside(34.0194, -118.4912) is True

        # Coordinates far from Westside
        assert service.is_in_westside(40.7128, -74.0060) is False


@pytest.mark.unit
class TestCategoryClassification:
    """Test event category classification."""

    def test_classify_event_music(self):
        """Test classification of music events."""
        from src.utils.categories import classify_event

        category = classify_event("Concert at the Bowl", "Live music performance", "")
        assert category == "Music"

    def test_classify_event_art(self):
        """Test classification of art events."""
        from src.utils.categories import classify_event

        category = classify_event("Art Exhibition", "Contemporary art show", "")
        assert category == "Art"

    def test_classify_event_food(self):
        """Test classification of food events."""
        from src.utils.categories import classify_event

        category = classify_event("Food Festival", "Taste local cuisine", "")
        assert category == "Food & Drink"

    def test_classify_event_default(self):
        """Test classification with no clear category."""
        from src.utils.categories import classify_event

        category = classify_event("Random Event", "Some description", "")
        assert category in ["Other", "Community", "Education"]

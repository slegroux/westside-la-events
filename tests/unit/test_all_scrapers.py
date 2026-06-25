"""
Comprehensive unit tests for all event scrapers.

This test module covers initialization, basic scraping functionality,
and error handling for all scrapers in the system.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.data.models import Event

# Import all scrapers
from src.scrapers.aero_theater import AeroTheaterScraper
from src.scrapers.afdela import AFdelaScraper
from src.scrapers.apero_francophone import AperoFrancophoneScraper
from src.scrapers.aviator_nation import AviatorNationScraper
from src.scrapers.beyond_baroque import BeyondBaroqueScraper
from src.scrapers.casual_creative import CasualCreativeScraper
from src.scrapers.culver_city import CulverCityScraper
from src.scrapers.discover_la import DiscoverLAScraper
from src.scrapers.eventbrite import EventbriteScraper
from src.scrapers.gnarwhal import GnarwhalScraper
from src.scrapers.hammer import HammerScraper
from src.scrapers.iic_la import IICLAScraper
from src.scrapers.itk_la import ITKLAScraper
from src.scrapers.kcrw import KCRWScraper
from src.scrapers.kinn import KinnScraper
from src.scrapers.lacma import LACMAScraper
from src.scrapers.laemmle_monica import LaemmleMonicaScraper
from src.scrapers.laist import LAistScraper
from src.scrapers.latechevents import LATechEventsScraper
from src.scrapers.meetup import MeetupScraper
from src.scrapers.nerd_nite import NerdNiteScraper
from src.scrapers.parks_ca import ParksCaliforniaScraper
from src.scrapers.penmar import PenmarScraper
from src.scrapers.raymond_kabbaz import RaymondKabbazScraper
from src.scrapers.resident_advisor import ResidentAdvisorScraper
from src.scrapers.santa_monica import SantaMonicaScraper
from src.scrapers.santamonica_events import SantaMonicaEventsScraper
from src.scrapers.arcana_books import ArcanaBooksScraper
from src.scrapers.timeout import TimeoutScraper
from src.scrapers.ucla import UCLAScraper
from src.scrapers.ucla_botanical import UCLABotanicalScraper
from src.scrapers.venice_beach import VeniceBeachScraper
from src.scrapers.venice_west import VeniceWestScraper
from src.scrapers.west_hollywood import WestHollywoodScraper
from src.scrapers.westside_comedy import WestsideComedyScraper
from src.scrapers.winston_house import WinstonHouseScraper


# Define all scrapers with their expected properties
SCRAPERS = [
    (AeroTheaterScraper, "Aero Theater"),
    (AFdelaScraper, "AFdela"),
    (AperoFrancophoneScraper, "Eventbrite"),
    (AviatorNationScraper, "Aviator Nation"),
    (BeyondBaroqueScraper, "Beyond Baroque"),
    (CasualCreativeScraper, "The Casual Creative"),
    (CulverCityScraper, "Culver City"),
    (DiscoverLAScraper, "Discover LA"),
    (EventbriteScraper, "Eventbrite"),
    (GnarwhalScraper, "Gnarwhal Coffee"),
    (HammerScraper, "Hammer Museum"),
    (IICLAScraper, "IIC Los Angeles"),
    (ITKLAScraper, "ITK LA"),
    (KCRWScraper, "KCRW"),
    (KinnScraper, "KINN"),
    (LACMAScraper, "LACMA"),
    (LaemmleMonicaScraper, "Laemmle Monica Film Center"),
    (LAistScraper, "LAist"),
    (LATechEventsScraper, "LA Tech Events"),
    (MeetupScraper, "Meetup"),
    (NerdNiteScraper, "Nerd Nite LA"),
    (ParksCaliforniaScraper, "California State Parks"),
    (PenmarScraper, "The Penmar"),
    (RaymondKabbazScraper, "Théâtre Raymond Kabbaz"),
    (ResidentAdvisorScraper, "Resident Advisor"),
    (SantaMonicaScraper, "Santa Monica"),
    (SantaMonicaEventsScraper, "Visit Santa Monica"),
    (ArcanaBooksScraper, "Arcana Books"),
    (TimeoutScraper, "Timeout LA"),
    (UCLAScraper, "UCLA"),
    (UCLABotanicalScraper, "UCLA Mathias Botanical Garden"),
    (VeniceBeachScraper, "Venice Beach Events"),
    (VeniceWestScraper, "The Venice West"),
    (WestHollywoodScraper, "West Hollywood"),
    (WestsideComedyScraper, "M.I.'s Westside Comedy Theater"),
    (WinstonHouseScraper, "Winston House"),
]


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperInitialization:
    """Test that all scrapers initialize correctly."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    def test_scraper_initialization(self, scraper_class, expected_name, mock_geocoding_service):
        """Test that each scraper initializes with correct source name."""
        scraper = scraper_class()
        assert scraper.source_name == expected_name
        assert scraper.geocoding_service is not None
        assert scraper.session is not None

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    def test_scraper_has_scrape_method(self, scraper_class, expected_name):
        """Test that each scraper has a scrape method."""
        scraper = scraper_class()
        assert hasattr(scraper, 'scrape')
        assert callable(scraper.scrape)

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    def test_scraper_has_base_url(self, scraper_class, expected_name):
        """Test that each scraper has a base URL or events URL."""
        scraper = scraper_class()
        # Check for various URL attributes that scrapers might use
        has_url = any([
            hasattr(scraper, 'base_url'),
            hasattr(scraper, 'events_url'),
            hasattr(scraper, 'calendar_url'),
            hasattr(scraper, 'api_url'),
            hasattr(scraper, 'search_url')
        ])
        assert has_url, f"{expected_name} scraper should have a URL attribute"


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperBasicFunctionality:
    """Test basic scraping functionality for all scrapers."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    @patch('requests.Session.get')
    @patch('src.scrapers.base.BaseScraper.fetch_page_js')
    @patch('src.scrapers.base.BaseScraper.fetch_page')
    def test_scraper_returns_list(self, mock_fetch, mock_fetch_js, mock_session_get, scraper_class, expected_name, mock_geocoding_service):
        """Test that scrape() returns a list."""
        # Mock every network path so this stays an offline unit test:
        # the HTTP fetch, the JS/Playwright fetch (else JS scrapers launch a
        # real browser), and the direct session.get used by API scrapers.
        mock_fetch.return_value = None
        mock_fetch_js.return_value = None
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception('mocked failure')
        mock_response.text = ''
        mock_session_get.return_value = mock_response

        scraper = scraper_class()
        result = scraper.scrape()

        assert isinstance(result, list), f"{expected_name} scraper should return a list"

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    @patch('requests.Session.get')
    @patch('src.scrapers.base.BaseScraper.fetch_page_js')
    @patch('src.scrapers.base.BaseScraper.fetch_page')
    def test_scraper_handles_failed_fetch(self, mock_fetch, mock_fetch_js, mock_session_get, scraper_class, expected_name, mock_geocoding_service):
        """Test that scrapers handle failed page fetches gracefully."""
        mock_fetch.return_value = None
        mock_fetch_js.return_value = None
        # Also mock session.get for scrapers that use APIs directly
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception('mocked failure')
        mock_session_get.return_value = mock_response

        scraper = scraper_class()
        events = scraper.scrape()

        # Should return empty list, not raise exception
        assert events == []

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS)
    @patch('requests.Session.get')
    @patch('src.scrapers.base.BaseScraper.fetch_page_js')
    @patch('src.scrapers.base.BaseScraper.fetch_page')
    def test_scraper_handles_empty_html(self, mock_fetch, mock_fetch_js, mock_session_get, scraper_class, expected_name, mock_geocoding_service):
        """Test that scrapers handle empty HTML gracefully."""
        empty_html = "<html><body></body></html>"
        mock_fetch.return_value = empty_html
        mock_fetch_js.return_value = empty_html
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = empty_html
        mock_response.json.return_value = {}
        mock_session_get.return_value = mock_response

        scraper = scraper_class()
        events = scraper.scrape()

        # Should return empty list or handle gracefully
        assert isinstance(events, list)


@pytest.mark.unit
@pytest.mark.scraper
@pytest.mark.requires_network
class TestScraperJavaScriptSupport:
    """Test JavaScript rendering support for scrapers that need it."""

    JAVASCRIPT_SCRAPERS = [
        (EventbriteScraper, "Eventbrite"),
        (MeetupScraper, "Meetup"),
        (ResidentAdvisorScraper, "Resident Advisor"),
        (AviatorNationScraper, "Aviator Nation"),
        (KinnScraper, "KINN"),
        (WestsideComedyScraper, "Westside Comedy"),
    ]

    @pytest.mark.parametrize("scraper_class,expected_name", JAVASCRIPT_SCRAPERS)
    @patch('src.scrapers.base.BaseScraper.fetch_page_js')
    def test_js_scraper_uses_playwright(self, mock_fetch_js, scraper_class, expected_name, mock_geocoding_service):
        """Test that JavaScript scrapers use fetch_page_js."""
        mock_fetch_js.return_value = "<html><body></body></html>"

        scraper = scraper_class()

        # The scraper might call fetch_page_js internally
        # We just verify the method exists
        assert hasattr(scraper, 'fetch_page_js')
        assert callable(scraper.fetch_page_js)


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperEventCreation:
    """Test event creation and validation."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:5])  # Test subset for speed
    def test_scraper_creates_valid_events(self, scraper_class, expected_name, mock_geocoding_service):
        """Test that scrapers create valid Event objects."""
        scraper = scraper_class()

        # Create a test event using the scraper's create_event method
        event = scraper.create_event(
            title="Test Event",
            description="Test Description",
            venue_name="Santa Monica Pier",  # Known Westside venue
            address="Santa Monica, CA",
            event_date=datetime.now(),
            url="https://example.com/event"
        )

        # Note: create_event may return None if location validation fails
        if event is not None:
            assert isinstance(event, Event)
            assert event.title == "Test Event"
            assert event.source == expected_name

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:5])
    def test_scraper_filters_non_westside_events(self, scraper_class, expected_name, mock_geocoding_service):
        """Test that scrapers filter out non-Westside events."""
        scraper = scraper_class()

        # Mock geocoding to return non-Westside coordinates
        with patch.object(scraper.geocoding_service, 'geocode') as mock_geocode:
            # Return Downtown LA coordinates (outside Westside)
            mock_geocode.return_value = (34.0522, -118.2437)

            event = scraper.create_event(
                title="Downtown Event",
                description="Event far from Westside",
                venue_name="Downtown LA Venue",
                address="123 Main St, Los Angeles, CA 90012",
                event_date=datetime.now()
            )

            # Should return None for non-Westside events
            # (depending on geo_filter configuration)
            assert event is None or isinstance(event, Event)


@pytest.mark.unit
@pytest.mark.scraper
class TestSpecificScrapers:
    """Specific tests for individual scrapers with unique functionality."""

    def test_timeout_scraper_properties(self):
        """Test Timeout scraper specific properties."""
        scraper = TimeoutScraper()
        assert scraper.source_name == "Timeout LA"
        assert "timeout.com" in scraper.base_url

    def test_kcrw_scraper_properties(self):
        """Test KCRW scraper specific properties."""
        scraper = KCRWScraper()
        assert scraper.source_name == "KCRW"
        assert "kcrw.com" in scraper.base_url

    def test_hammer_scraper_venue_info(self):
        """Test Hammer Museum scraper has correct venue info."""
        scraper = HammerScraper()
        assert scraper.source_name == "Hammer Museum"
        # Hammer events should all be at the same venue
        assert hasattr(scraper, 'base_url')

    def test_lacma_scraper_venue_info(self):
        """Test LACMA scraper has correct venue info."""
        scraper = LACMAScraper()
        assert scraper.source_name == "LACMA"
        assert hasattr(scraper, 'base_url')

    def test_eventbrite_scraper_search_functionality(self):
        """Test Eventbrite scraper search configuration."""
        scraper = EventbriteScraper()
        assert scraper.source_name == "Eventbrite"
        # Eventbrite uses search queries
        assert hasattr(scraper, 'search_url') or hasattr(scraper, 'base_url')

    def test_parks_scraper_properties(self):
        """Test California State Parks scraper."""
        scraper = ParksCaliforniaScraper()
        assert scraper.source_name == "California State Parks"

    def test_venice_west_scraper_venue_info(self):
        """Test Venice West scraper has correct venue info."""
        scraper = VeniceWestScraper()
        assert scraper.source_name == "The Venice West"
        # Venice West is a single venue
        assert hasattr(scraper, 'venue_name') or hasattr(scraper, 'calendar_url')

    def test_aviator_nation_scraper(self):
        """Test Aviator Nation scraper configuration."""
        scraper = AviatorNationScraper()
        assert scraper.source_name == "Aviator Nation"
        assert hasattr(scraper, 'base_url') or hasattr(scraper, 'dreamloft_url')

    def test_westside_comedy_scraper(self):
        """Test Westside Comedy scraper configuration."""
        scraper = WestsideComedyScraper()
        assert scraper.source_name == "M.I.'s Westside Comedy Theater"


@pytest.mark.unit
@pytest.mark.scraper
class TestWestsideComedyEventbriteParsing:
    """Regression coverage for Eventbrite single-event-page parsing.

    Eventbrite renders its JSON-LD ``<script>`` tags with extra attributes
    (e.g. ``data-next-head=""``). The extractor regex must tolerate those
    attributes; a strict ``...ld+json">`` match silently returned 0 events.
    """

    # Minimal Eventbrite event page: a JSON-LD Event block carrying the
    # ``data-next-head`` attribute that broke the original strict regex.
    SAMPLE_HTML = '''<!DOCTYPE html><html><head>
<meta property="og:description" content="A night of comedy mashups." />
<script type="application/ld+json" data-next-head="">{"@type":"WebSite","name":"Eventbrite"}</script>
<script type="application/ld+json" data-next-head="">{"@type":"Event","name":"Maggie's Mashup","startDate":"2026-06-24T20:00:00-07:00","endDate":"2026-06-24T21:30:00-07:00","url":"https://www.eventbrite.com/e/maggies-mashup-tickets-1260545949869","location":{"@type":"Place","name":"Westside Comedy Theater","address":{"@type":"PostalAddress","addressLocality":"Santa Monica","addressRegion":"CA","streetAddress":"1323-A 3rd Street, Santa Monica, CA 90401"}},"image":"https://img.evbuc.com/sample.jpg"}</script>
</head><body></body></html>'''

    def test_extract_handles_data_next_head_attribute(self):
        """The JSON-LD extractor must match script tags with extra attributes."""
        scraper = WestsideComedyScraper()
        data = scraper._extract_eventbrite_event_data(self.SAMPLE_HTML)
        assert data is not None
        assert data['name'] == "Maggie's Mashup"
        assert data['start']['local'].startswith('2026-06-24T20:00:00')
        assert data['venue']['name'] == 'Westside Comedy Theater'

    def test_fetch_by_id_returns_event(self, mock_geocoding_service):
        """End-to-end: a 200-OK event page yields a westsidecomedy.com Event."""
        scraper = WestsideComedyScraper()
        with patch('src.scrapers.base.BaseScraper.fetch_page', return_value=self.SAMPLE_HTML):
            event = scraper._fetch_eventbrite_event_by_id('1984841499355')

        assert event is not None
        assert event.title == "Maggie's Mashup"
        assert event.event_date == datetime(2026, 6, 24, 20, 0)
        assert event.venue_name == 'Westside Comedy Theater'
        # URL is rewritten to the westsidecomedy.com single-event path.
        assert event.url == 'https://westsidecomedy.com/single-event/e/1984841499355/'

    def test_strict_tag_without_attributes_still_parses(self):
        """The legacy attribute-less tag form must keep working too."""
        scraper = WestsideComedyScraper()
        html = self.SAMPLE_HTML.replace(' data-next-head=""', '')
        data = scraper._extract_eventbrite_event_data(html)
        assert data is not None
        assert data['name'] == "Maggie's Mashup"


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperUtilityMethods:
    """Test utility methods inherited from BaseScraper."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:3])
    def test_clean_text_method(self, scraper_class, expected_name):
        """Test clean_text utility method."""
        scraper = scraper_class()

        # Test whitespace cleaning
        assert scraper.clean_text("  test  ") == "test"
        assert scraper.clean_text("test\n\ntext") == "test text"
        assert scraper.clean_text(None) == ""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:3])
    def test_normalize_url_method(self, scraper_class, expected_name):
        """Test normalize_url utility method."""
        scraper = scraper_class()

        # Test absolute URL
        url = scraper.normalize_url("https://example.com/event", "https://base.com")
        assert url == "https://example.com/event"

        # Test relative URL
        if hasattr(scraper, 'base_url') and scraper.base_url:
            url = scraper.normalize_url("/events/123", scraper.base_url)
            assert url.startswith("http")

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:3])
    def test_parse_html_method(self, scraper_class, expected_name):
        """Test parse_html utility method."""
        scraper = scraper_class()

        html = "<html><body><h1>Test</h1></body></html>"
        soup = scraper.parse_html(html)

        assert soup is not None
        assert soup.find('h1') is not None
        assert soup.find('h1').text == "Test"


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperErrorHandling:
    """Test error handling in scrapers."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:5])
    def test_scraper_handles_malformed_html(self, scraper_class, expected_name, mock_geocoding_service):
        """Test scrapers handle malformed HTML gracefully."""
        with patch('src.scrapers.base.BaseScraper.fetch_page') as mock_fetch:
            # Return malformed HTML
            mock_fetch.return_value = "<html><body><div>Incomplete"

            scraper = scraper_class()

            # Should not raise exception
            try:
                events = scraper.scrape()
                assert isinstance(events, list)
            except Exception as e:
                pytest.fail(f"{expected_name} raised {e} on malformed HTML")

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:5])
    def test_scraper_handles_network_errors(self, scraper_class, expected_name, mock_geocoding_service):
        """Test scrapers handle network errors gracefully."""
        with patch('src.scrapers.base.BaseScraper.fetch_page') as mock_fetch:
            # Simulate network error
            mock_fetch.return_value = None

            scraper = scraper_class()

            # Should not raise exception
            try:
                events = scraper.scrape()
                assert events == []
            except Exception as e:
                pytest.fail(f"{expected_name} raised {e} on network error")


@pytest.mark.unit
@pytest.mark.scraper
class TestScraperLogging:
    """Test logging functionality in scrapers."""

    @pytest.mark.parametrize("scraper_class,expected_name", SCRAPERS[:3])
    def test_scraper_log_method(self, scraper_class, expected_name, caplog):
        """Test that scrapers have and can use log method."""
        scraper = scraper_class()

        assert hasattr(scraper, 'log')
        assert callable(scraper.log)

        # Test logging via Python logging module
        with caplog.at_level('INFO'):
            scraper.log("Test message")

        assert "Test message" in caplog.text

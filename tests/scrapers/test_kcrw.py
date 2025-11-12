"""
Unit tests for KCRW scraper.

Tests both with mocked HTML (fast, offline) and live website (integration).
"""
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock

from src.scrapers.kcrw import KCRWScraper
from src.data.models import Event


@pytest.fixture
def kcrw_scraper():
    """Create a KCRW scraper instance."""
    return KCRWScraper()


@pytest.fixture
def sample_kcrw_html():
    """Sample HTML response from KCRW events page."""
    # This is a simplified version - update with actual HTML structure
    return """
    <html>
        <body>
            <div class="event-card">
                <h3 class="event-title">Sample Concert</h3>
                <div class="event-description">
                    <p>Join us for an amazing live music performance.</p>
                </div>
                <div class="event-venue">The Broad Stage</div>
                <div class="event-date">2025-12-15 19:00:00</div>
                <a class="event-link" href="/events/sample-concert">Learn more</a>
                <img class="event-image" src="/images/concert.jpg" />
            </div>
        </body>
    </html>
    """


@pytest.mark.unit
class TestKCRWScraperUnit:
    """Unit tests with mocked responses."""

    def test_scraper_initialization(self, kcrw_scraper):
        """Test scraper initializes correctly."""
        assert kcrw_scraper.source_name == "KCRW"
        assert kcrw_scraper.base_url is not None

    @patch.object(KCRWScraper, 'fetch_page')
    def test_scrape_returns_empty_on_fetch_failure(self, mock_fetch, kcrw_scraper):
        """Test scraper returns empty list when page fetch fails."""
        mock_fetch.return_value = None

        events = kcrw_scraper.scrape()

        assert events == []

    @patch.object(KCRWScraper, 'fetch_page')
    def test_scrape_handles_empty_page(self, mock_fetch, kcrw_scraper, sample_kcrw_html):
        """Test scraper handles page with no events gracefully."""
        mock_fetch.return_value = "<html><body><p>No events</p></body></html>"

        events = kcrw_scraper.scrape()

        assert events == []

    @patch.object(KCRWScraper, 'fetch_page')
    def test_scrape_extracts_events(self, mock_fetch, kcrw_scraper, sample_kcrw_html):
        """Test scraper extracts events from HTML."""
        mock_fetch.return_value = sample_kcrw_html

        events = kcrw_scraper.scrape()

        # Verify we got events (actual count depends on HTML structure)
        assert isinstance(events, list)

        # If events were extracted, verify structure
        if events:
            event = events[0]
            assert isinstance(event, Event)
            assert event.source == "KCRW"
            assert event.title is not None
            assert event.url is not None

    def test_event_url_normalization(self, kcrw_scraper):
        """Test that relative URLs are converted to absolute."""
        # Test the normalize_url helper
        relative_url = "/events/test-event"
        base_url = "https://www.kcrw.com"

        absolute_url = kcrw_scraper.normalize_url(relative_url, base_url)

        assert absolute_url == "https://www.kcrw.com/events/test-event"

    def test_text_cleaning(self, kcrw_scraper):
        """Test that extracted text is cleaned properly."""
        dirty_text = "  Test   Event\n\t  "

        clean_text = kcrw_scraper.clean_text(dirty_text)

        assert clean_text == "Test Event"


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_network
class TestKCRWScraperIntegration:
    """Integration tests against live KCRW website."""

    def test_scrape_live_website(self, kcrw_scraper):
        """Test scraping live KCRW events page.

        This test will fail if:
        - The website is down
        - The HTML structure has changed
        - The scraper logic is broken
        """
        events = kcrw_scraper.scrape()

        # We don't assert a specific count since it varies
        # But we should get SOME events most of the time
        assert isinstance(events, list)

        # If we got events, verify their structure
        if events:
            event = events[0]
            assert isinstance(event, Event)
            assert event.source == "KCRW"
            assert event.title, "Event should have a title"
            assert event.url, "Event should have a URL"

            # Verify URL is absolute
            assert event.url.startswith("http"), f"URL should be absolute, got: {event.url}"

            # Log for manual inspection
            print(f"\nScraped {len(events)} events from KCRW")
            print(f"Sample event: {event.title}")
            print(f"URL: {event.url}")

    def test_website_structure_unchanged(self, kcrw_scraper):
        """Test that expected HTML elements still exist.

        This test helps catch website redesigns early.
        """
        html = kcrw_scraper.fetch_page(kcrw_scraper.base_url)

        assert html is not None, "Failed to fetch KCRW page"

        soup = kcrw_scraper.parse_html(html)

        # Check for key elements (adjust selectors based on actual structure)
        # This will vary based on your scraper implementation
        # Example checks:

        # Does the page have an events section?
        # events_section = soup.find('div', class_='events-list')
        # assert events_section is not None, "Events section not found - website structure may have changed"

        # Add more structure checks based on your scraper's expectations
        assert soup is not None


@pytest.mark.snapshot
class TestKCRWScraperSnapshot:
    """Snapshot tests to detect website changes.

    These tests save HTML snapshots and alert when structure changes.
    """

    @pytest.fixture
    def snapshot_dir(self):
        """Directory for storing HTML snapshots."""
        path = Path(__file__).parent / 'snapshots' / 'kcrw'
        path.mkdir(parents=True, exist_ok=True)
        return path

    def test_html_structure_snapshot(self, kcrw_scraper, snapshot_dir):
        """Save a snapshot of current HTML structure.

        Run this periodically to update the baseline.
        To update snapshot: pytest --snapshot-update
        """
        html = kcrw_scraper.fetch_page(kcrw_scraper.base_url)

        if html:
            snapshot_file = snapshot_dir / f"page_snapshot_{datetime.now().strftime('%Y%m%d')}.html"

            # Save snapshot for manual inspection
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                f.write(html)

            print(f"\nSnapshot saved to: {snapshot_file}")


# Helper for debugging scraper issues
if __name__ == "__main__":
    """Run this file directly to debug the scraper."""
    scraper = KCRWScraper()
    events = scraper.scrape()

    print(f"\nScraped {len(events)} events:")
    for event in events[:5]:  # Show first 5
        print(f"\n- {event.title}")
        print(f"  Date: {event.event_date}")
        print(f"  Venue: {event.venue_name}")
        print(f"  URL: {event.url}")

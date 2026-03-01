"""
Tests for Old Town Music Hall scraper.
"""
import pytest
from datetime import datetime
from src.scrapers.old_town_music_hall import OldTownMusicHallScraper


class TestOldTownMusicHallScraper:
    """Test suite for Old Town Music Hall scraper."""

    def test_scraper_initialization(self):
        """Test scraper initializes correctly."""
        scraper = OldTownMusicHallScraper()
        assert scraper.source == 'Old Town Music Hall'
        assert scraper.venue_name == 'Old Town Music Hall'
        assert 'El Segundo' in scraper.venue_address
        assert 'agileticketing.net' in scraper.events_url

    def test_categorize_event(self):
        """Test event categorization logic."""
        scraper = OldTownMusicHallScraper()

        # Film titles should be categorized as Film
        assert scraper._categorize_event("North by Northwest") == "Film"
        assert scraper._categorize_event("The Lion King") == "Film"
        assert scraper._categorize_event("Die Hard") == "Film"

        # Music events should be categorized as Music
        assert scraper._categorize_event("Janet Klein and Her Parlor Boys") == "Music"
        assert scraper._categorize_event("Jazz Concert") == "Music"
        assert scraper._categorize_event("An Old Town Christmas with Rob Richards") == "Music"

    @pytest.mark.integration
    def test_scrape_returns_events(self):
        """Test that scraper returns events (integration test)."""
        scraper = OldTownMusicHallScraper()
        events = scraper.scrape()

        # Should return some events (or empty list if no events scheduled)
        assert isinstance(events, list)

        # If events exist, verify they have required fields
        if events:
            event = events[0]
            assert event.title
            assert event.venue_name == 'Old Town Music Hall'
            assert '140 Richmond Street' in event.address
            assert 'El Segundo' in event.address
            assert event.event_date
            assert event.source == 'Old Town Music Hall'
            assert event.category in ['Film', 'Music']
            assert event.url  # Should have event URL

    @pytest.mark.integration
    def test_scrape_events_have_dates(self):
        """Test that scraped events have valid future dates."""
        scraper = OldTownMusicHallScraper()
        events = scraper.scrape()

        if events:
            for event in events:
                # All events should have dates
                assert event.event_date is not None
                # All events should be in the future (scraper filters past events)
                assert event.event_date > datetime.now()

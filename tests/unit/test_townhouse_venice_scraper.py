"""
Unit tests for the Townhouse & Del Monte scraper (a DiceVenueScraper subclass).

The DICE parsing itself is covered by test_arts_2220_scraper.py; these tests pin
what is specific to this venue: its DICE page, fixed location and region.
"""
import pytest

from src.scrapers.townhouse_venice import TownhouseVeniceScraper
from tests.unit.test_arts_2220_scraper import _future, _listing_event, _venue_page


def _run(scraper, venue_html):
    def fetch_page(url, retry=3):
        return venue_html if url == TownhouseVeniceScraper.LISTING_URL else None

    scraper.fetch_page = fetch_page
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


@pytest.mark.unit
def test_venue_page_and_westside_location(mock_geocoding_service):
    """Reads its own DICE page; Venice is inside the box, so no beyond region."""
    assert TownhouseVeniceScraper.LISTING_URL == 'https://dice.fm/venue/townhouse-venice-d8ve'
    when = _future()
    listed = [
        _listing_event('jazz1', "JIJI's Jazz Club Presents Friendsgiving", when, low='18.03'),
        _listing_event('free1', 'Open Mic', _future(12), low='0.00'),
    ]

    events = _run(TownhouseVeniceScraper(), _venue_page(listed))

    assert [e.title for e in events] == ["JIJI's Jazz Club Presents Friendsgiving", 'Open Mic']
    jazz, free = events
    assert jazz.source == 'Townhouse & Del Monte'
    assert jazz.venue_name == 'Townhouse & Del Monte'
    assert jazz.address == '52 Windward Ave, Venice, CA 90291'
    assert abs(jazz.latitude - 33.9871405) < 1e-6
    assert jazz.region == 'westside'
    assert jazz.price == 18.03 and not jazz.is_free
    assert free.is_free and free.price is None
    assert jazz.event_date == when


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert _run(TownhouseVeniceScraper(), '<html><body>Just a moment...</body></html>') == []
    scraper = TownhouseVeniceScraper()
    scraper.fetch_page = lambda url, retry=3: None
    assert scraper.scrape() == []

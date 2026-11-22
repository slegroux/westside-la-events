"""
Unit tests for the Zebulon scraper (a DiceVenueScraper subclass).

The DICE parsing itself is covered by test_arts_2220_scraper.py; these tests pin
what is specific to this venue: its DICE page, fixed location and beyond region.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.zebulon import ZebulonScraper
from tests.unit.test_arts_2220_scraper import _future, _listing_event, _venue_page


def _run(scraper, venue_html):
    def fetch_page(url, retry=3):
        return venue_html if url == ZebulonScraper.LISTING_URL else None

    scraper.fetch_page = fetch_page
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


@pytest.mark.unit
def test_frogtown_events_land_in_beyond_region(mock_geocoding_service):
    """Frogtown is outside the Westside box: events carry region 'beyond'."""
    assert ZebulonScraper.LISTING_URL == 'https://dice.fm/venue/zebulon-y8bv'
    when = _future(days=3, hour=21)
    listed = [
        _listing_event('free1', 'Bad Bunny Party', when, low='0.00',
                       endDate=None),
        _listing_event('paid1', 'Fred Eaglesmith', _future(5), low='62.32'),
        _listing_event('past1', 'Old Show', datetime.now() - timedelta(days=2)),
    ]

    events = _run(ZebulonScraper(), _venue_page(listed))

    assert [e.title for e in events] == ['Bad Bunny Party', 'Fred Eaglesmith']
    free, paid = events
    assert free.source == 'Zebulon' and free.venue_name == 'Zebulon'
    assert free.address == '2478 Fletcher Dr, Los Angeles, CA 90039'
    assert free.region == 'beyond'
    assert free.is_free and free.price is None
    assert paid.price == 62.32 and not paid.is_free
    assert free.event_date == when


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert _run(ZebulonScraper(), '<html><body>Just a moment...</body></html>') == []
    scraper = ZebulonScraper()
    scraper.fetch_page = lambda url, retry=3: None
    assert scraper.scrape() == []

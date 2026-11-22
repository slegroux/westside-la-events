"""
Unit tests for the Highways Performance Space scraper.

Highways shares its Wix Events parser with Sam First (see
test_sam_first_scraper.py for the parser's edge cases); these tests cover what
is specific to Highways: its venue, category and the per-performance URLs.
"""
import pytest

from src.scrapers.wix_events import HighwaysScraper
from tests.unit.wix_helpers import future, home_page, raw_event, run

HOME = HighwaysScraper.LISTING_URL
ADDRESS = '1651 18th St, Santa Monica, CA 90404, USA'


@pytest.mark.unit
def test_parses_highways_events(mock_geocoding_service):
    """A run is listed as one event per performance, each with its own slug/URL."""
    first, second = future(6, hour=20, minute=0), future(7, hour=20, minute=0)
    page = home_page([
        raw_event('waiting-room-1', 'The Waiting Room', first, hours=2, price='20.50',
                  venue='Highways', address=ADDRESS, lat=34.0235, lng=-118.4774),
        raw_event('waiting-room-2', 'The Waiting Room', second, hours=2, price='20.50',
                  venue='Highways', address=ADDRESS, lat=34.0235, lng=-118.4774),
    ])

    events = run(HighwaysScraper(), {HOME: page})

    assert [e.event_date for e in events] == [first, second]
    assert len({e.url for e in events}) == 2
    assert events[0].url == 'https://www.highwaysperformance.org/events/waiting-room-1'
    e = events[0]
    assert e.source == 'Highways Performance Space'
    assert e.venue_name == 'Highways'
    assert e.address == '1651 18th St, Santa Monica, CA 90404, USA'
    assert e.category == 'Theater'
    assert e.price == 20.5
    assert e.region == 'westside'


@pytest.mark.unit
def test_external_ticketing_leaves_price_empty(mock_geocoding_service):
    """A show ticketed elsewhere has no price here: no badge, not 'TBD'."""
    page = home_page([raw_event('echo', 'Echo Lubimovka', future(3), price=None,
                                venue='Highways', address=ADDRESS, lat=34.0235, lng=-118.4774)])

    (event,) = run(HighwaysScraper(), {HOME: page})

    assert event.price is None and event.price_note == '' and not event.is_free


@pytest.mark.unit
def test_empty_page_yields_nothing(mock_geocoding_service):
    assert run(HighwaysScraper(), {HOME: '<html></html>'}) == []

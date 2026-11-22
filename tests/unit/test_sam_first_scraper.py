"""
Unit tests for the Sam First scraper (Wix Events).

Fully offline: fetch_page/prefetch_pages are replaced with hand-built copies of
the Wix home page (embedded events JSON), the event sitemap, and event pages
(JSON-LD). Dates are generated relative to today in LA-local time.
"""
import pytest

from src.scrapers.wix_events import SamFirstScraper
from tests.unit.wix_helpers import (
    event_page, future, home_page, raw_event, run, sitemap,
)

HOME = SamFirstScraper.LISTING_URL
SITEMAP = SamFirstScraper.SITEMAP_URL


def _url(slug):
    return f'https://www.samfirstbar.com/events/{slug}'


@pytest.mark.unit
def test_parses_embedded_event(mock_geocoding_service):
    """UTC instants become naive LA-local times; price, image and URL come through."""
    when = future(10)
    page = home_page([raw_event('trio-night', 'Trio Night', when, price='16.80')])

    events = run(SamFirstScraper(), {HOME: page})

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Trio Night'
    assert e.event_date == when and e.event_date.tzinfo is None
    assert e.end_date.hour == (when.hour + 3) % 24
    assert e.url == _url('trio-night')
    assert e.image_url == 'https://img.example/trio-night.jpg'
    assert e.price == 16.8 and not e.is_free and e.price_note == ''
    assert e.category == 'Music'
    assert e.venue_name == 'Sam First'
    assert abs(e.latitude - 33.9458) < 1e-4
    # Westchester is inside the coverage area: default region.
    assert e.region == 'westside'


@pytest.mark.unit
def test_sold_out_and_free_pricing(mock_geocoding_service):
    page = home_page([
        raw_event('sold', 'Sold Show', future(5), sold_out=True, price=None),
        raw_event('free', 'Free Show', future(6), price='0.00'),
        raw_event('unknown', 'No Ticketing', future(7), price=None),
    ])

    sold, free, unknown = run(SamFirstScraper(), {HOME: page})

    assert sold.price is None and sold.price_note == 'Sold out'
    assert free.is_free and free.price is None
    assert unknown.price is None and unknown.price_note == '' and not unknown.is_free


@pytest.mark.unit
def test_skips_past_ended_cancelled_tbd_and_duplicates(mock_geocoding_service):
    page = home_page([
        raw_event('keep', 'Kept Show', future(10)),
        raw_event('keep', 'Kept Show', future(10)),
        raw_event('past', 'Old Show', future(-3)),
        raw_event('ended', 'Ended Show', future(4), status=2),
        raw_event('cancelled', 'Cancelled Show', future(5), status=3),
        raw_event('tbd', 'Undated Show', future(6), tbd=True),
    ])

    events = run(SamFirstScraper(), {HOME: page})

    assert [e.title for e in events] == ['Kept Show']


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert run(SamFirstScraper(), {}) == []
    assert run(SamFirstScraper(), {HOME: '<html><body>Just a moment...</body></html>'}) == []


@pytest.mark.unit
def test_has_more_reads_overflow_from_event_pages(mock_geocoding_service):
    """Events past the widget's first page come from the sitemap + JSON-LD,
    and only those dated after the last listed event are kept."""
    last_listed = future(20)
    page = home_page([raw_event('listed', 'Listed Show', last_listed)], has_more=True)
    smap = sitemap([
        ('listed', '2026-10-26'),
        ('later-show', '2026-11-10'),       # recent, dated after the listing: kept
        ('earlier-show', '2026-11-12'),     # recent, dated before the last listed event: dropped
        ('old-show', '2024-01-01'),         # lastmod below the floor: never fetched
        ('cancelled-show', '2026-11-11'),
    ])
    pages = {
        HOME: page,
        SITEMAP: smap,
        _url('later-show'): event_page('Later Show', future(40), low='28'),
        _url('earlier-show'): event_page('Earlier Show', future(15)),
        _url('old-show'): event_page('Old Show', future(50)),
        _url('cancelled-show'): event_page('Cancelled Show', future(45), cancelled=True),
    }

    events = run(SamFirstScraper(), pages)

    assert sorted(e.title for e in events) == ['Later Show', 'Listed Show']
    later = next(e for e in events if e.title == 'Later Show')
    assert later.url == _url('later-show')
    assert later.event_date == future(40)
    assert later.price == 28.0
    assert later.description == 'From the event page.'
    # No coordinates on a JSON-LD page: the venue's fixed ones are used.
    assert abs(later.latitude - SamFirstScraper.VENUE_LAT) < 1e-6


@pytest.mark.unit
def test_has_more_without_sitemap_keeps_the_listing(mock_geocoding_service):
    page = home_page([raw_event('listed', 'Listed Show', future(10))], has_more=True)

    events = run(SamFirstScraper(), {HOME: page})

    assert [e.title for e in events] == ['Listed Show']

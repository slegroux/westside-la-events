"""
Unit tests for the 2220 Arts + Archives scraper.

Fully offline: fetch_page and prefetch_pages are replaced, so the scraper reads
hand-built copies of the DICE venue page (JSON-LD Place + Next.js data blob)
and event pages (JSON-LD Event). Dates are generated relative to today.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.arts_2220 import Arts2220Scraper


def _iso(dt):
    """DICE writes LA-local ISO timestamps with a UTC offset (PST or PDT)."""
    return dt.replace(tzinfo=ZoneInfo('America/Los_Angeles')).isoformat()


def _ld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


def _listing_event(event_id, name, start, low='20.00', **extra):
    return {
        '@type': 'Event',
        'url': f'https://dice.fm/event/{event_id}',
        'name': name,
        'startDate': _iso(start),
        'endDate': _iso(start + timedelta(hours=3)),
        'eventStatus': 'https://schema.org/EventScheduled',
        'image': [f'https://img.example/{event_id}.jpg'],
        'offers': {'@type': 'AggregateOffer', 'lowPrice': low, 'highPrice': low},
        **extra,
    }


def _venue_page(listed, statuses=None):
    place = {'@type': 'Place', 'name': '2220 Arts + Archives', 'event': listed}
    next_data = {'props': {'pageProps': {'profile': {'sections': [{
        'events': [{'id': i, 'status': s} for i, s in (statuses or {}).items()]
    }]}}}}
    return (
        '<html><head>'
        + _ld({'@type': 'Organization', 'name': 'DICE'})
        + _ld(place)
        + f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        + '</head></html>'
    )


def _run(scraper, venue_html, details=None):
    """Serve venue_html for the listing and details[url] for event pages."""
    details = details or {}

    def fetch_page(url, retry=3):
        if url == Arts2220Scraper.LISTING_URL:
            return venue_html
        detail = details.get(url)
        return f'<html><head>{_ld(detail)}</head></html>' if detail else None

    scraper.fetch_page = fetch_page
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


def _future(days=10, hour=20):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


@pytest.mark.unit
def test_event_page_enriches_listing(mock_geocoding_service):
    """Description, canonical URL and type come from the event page."""
    when = _future()
    listed = _listing_event('abc123', 'Zsela *Live*', when, low='27.18')
    detail = {
        **listed,
        '@type': 'MusicEvent',
        'url': 'https://dice.fm/event/g5vr7a-zsela-tickets',
        'description': 'Pretty But Wicked presents *Zsela*!\n\n~\n\nSee [her site](https://x.example).',
    }

    events = _run(Arts2220Scraper(), _venue_page([listed]), {listed['url']: detail})

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Zsela Live'
    assert Arts2220Scraper()._clean_description('M*A*S*H at 5*3') == 'M*A*S*H at 5*3'
    assert Arts2220Scraper()._clean_description(r'Pop \* pop Art') == 'Pop * pop Art'
    assert e.description == 'Pretty But Wicked presents Zsela! See her site.'
    assert e.url == 'https://dice.fm/event/g5vr7a-zsela-tickets'
    assert e.category == 'Music'
    assert e.price == 27.18 and not e.is_free and e.price_note == ''
    assert e.image_url == 'https://img.example/abc123.jpg'
    # Offset-aware source times are stored as naive LA-local.
    assert e.event_date == when and e.event_date.tzinfo is None
    assert e.end_date == when + timedelta(hours=3)
    assert e.venue_name == '2220 Arts + Archives'
    assert e.address == '2220 Beverly Blvd, Los Angeles, CA 90057'
    assert abs(e.latitude - 34.0672209) < 1e-6
    # Historic Filipinotown is outside the Westside box: kept via the beyond tab.
    assert e.region == 'beyond'


@pytest.mark.unit
def test_listing_alone_is_enough_when_event_page_fails(mock_geocoding_service):
    """An unreachable event page still yields the event from listing data."""
    when = _future()
    listed = _listing_event('abc123', 'Acropolis Cinema: a screening', when)

    events = _run(Arts2220Scraper(), _venue_page([listed]))

    assert len(events) == 1
    e = events[0]
    assert e.url == 'https://dice.fm/event/abc123'
    assert e.description == ''
    assert e.price == 20.0
    # No schema type to go on -> keyword classifier, which knows "screening".
    assert e.category == 'Film'


@pytest.mark.unit
def test_free_and_sold_out_pricing(mock_geocoding_service):
    """Zero price is FREE; sold-out replaces the price with a note."""
    listed = [
        _listing_event('free1', 'Analog Media Fair', _future(5), low='0.00'),
        _listing_event('sold1', 'Sold Show', _future(6), low='30.00'),
    ]
    html = _venue_page(listed, statuses={'free1': 'on-sale', 'sold1': 'sold-out'})
    # The event page's canonical URL carries a slug, not the id the status map
    # is keyed by; the lookup has to use the listing URL.
    details = {listed[1]['url']: {**listed[1], 'url': 'https://dice.fm/event/xyz-sold-show-tickets'}}

    free, sold = _run(Arts2220Scraper(), html, details)

    assert free.is_free and free.price is None and free.price_note == ''
    assert sold.price is None and not sold.is_free and sold.price_note == 'Sold out'


@pytest.mark.unit
def test_skips_past_cancelled_and_duplicate_events(mock_geocoding_service):
    """Past, cancelled/postponed and repeated listings are dropped."""
    when = _future()
    keep = _listing_event('keep1', 'Kept Show', when)
    listed = [
        keep,
        _listing_event('dup1', 'Kept Show', when),
        _listing_event('past1', 'Old Show', datetime.now() - timedelta(days=3)),
        _listing_event('canc1', 'Cancelled Show', _future(12),
                       eventStatus='https://schema.org/EventCancelled'),
        _listing_event('post1', 'Postponed Show', _future(13),
                       eventStatus='https://schema.org/EventPostponed'),
        {'@type': 'Event', 'name': 'No date'},
    ]

    events = _run(Arts2220Scraper(), _venue_page(listed))

    assert [e.title for e in events] == ['Kept Show']


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    """A fetch failure or a page without the venue JSON-LD returns []."""
    scraper = Arts2220Scraper()
    scraper.fetch_page = lambda url, retry=3: None
    assert scraper.scrape() == []

    assert _run(Arts2220Scraper(), '<html><body>Just a moment...</body></html>') == []

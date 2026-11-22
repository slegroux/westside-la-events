"""
Unit tests for the Harvelle's (Santa Monica) scraper.

Fully offline: fetch_page is replaced with hand-built SeatEngine pages. The real
pages use single-quoted <script type='application/ld+json'> tags, which the
fixtures copy. Dates are generated relative to today; the source writes UTC.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.harvelles import HarvellesScraper

LA = ZoneInfo('America/Los_Angeles')
SM_URL, MAIN_URL = HarvellesScraper.LISTING_URLS


def _utc(local_dt):
    """The source's 'Z' timestamp for an LA-local wall-clock time."""
    return local_dt.replace(tzinfo=LA).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _show(city, show_id, name, local_dt, image='https://files.seatengine.com/x.jpg'):
    host = 'santamonica' if city == 'Santa Monica' else 'longbeach'
    return {
        '@context': 'http://schema.org',
        '@type': 'Event',
        'name': name,
        'location': {
            '@type': 'PostalAddress',
            'name': f"Harvelle's {city} ",
            'streetAddress': '1432 4th Street',
            'addressLocality': city,
            'addressRegion': 'CA',
        },
        'startDate': _utc(local_dt),
        'description': '<p>Doors open at 8 PM.</p><p>2 drink minimum.</p>',
        'image': image,
        'url': f'https://{host}.harvelles.com/shows/{show_id}',
    }


def _page(*places):
    """places: (city, [events]) -> a page with one Place JSON-LD block each."""
    blocks = ''.join(
        "<script type='application/ld+json'>"
        + json.dumps({'@type': 'Place', 'name': f"Harvelle's {city}", 'events': events})
        + '</script>'
        for city, events in places
    )
    return f'<html><head>{blocks}</head></html>'


def _future(days=5, hour=21, minute=30):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def _run(pages):
    scraper = HarvellesScraper()
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    return scraper.scrape()


@pytest.mark.unit
def test_parses_santa_monica_show(mock_geocoding_service):
    """UTC start becomes naive LA time; description is flattened; no price."""
    when = _future()
    page = _page(('Santa Monica', [_show('Santa Monica', 1, 'THE TOLEDO SHOW', when)]))

    events = _run({SM_URL: page})

    assert len(events) == 1
    e = events[0]
    assert e.title == 'THE TOLEDO SHOW'
    assert e.event_date == when and e.event_date.tzinfo is None
    assert e.description == 'Doors open at 8 PM. 2 drink minimum.'
    assert e.url == 'https://santamonica.harvelles.com/shows/1'
    assert e.venue_name == "Harvelle's Santa Monica"
    assert e.address == '1432 4th St, Santa Monica, CA 90401'
    assert e.category == 'Music'
    assert e.price is None and not e.is_free and e.price_note == ''
    assert e.image_url == 'https://files.seatengine.com/x.jpg'
    assert e.region == 'westside'


@pytest.mark.unit
def test_long_beach_events_are_dropped(mock_geocoding_service):
    """harvelles.com lists both clubs; only Santa Monica shows are kept."""
    page = _page(
        ('Santa Monica', [_show('Santa Monica', 1, 'SM Show', _future(3))]),
        ('Long Beach', [_show('Long Beach', 2, 'Kraken Karaoke', _future(4))]),
    )

    # The subdomain page is empty, so the scraper falls back to harvelles.com.
    events = _run({SM_URL: '<html></html>', MAIN_URL: page})

    assert [e.title for e in events] == ['SM Show']


@pytest.mark.unit
def test_subdomain_wins_and_main_site_is_not_fetched(mock_geocoding_service):
    fetched = []
    page = _page(('Santa Monica', [_show('Santa Monica', 1, 'SM Show', _future())]))
    scraper = HarvellesScraper()
    scraper.fetch_page = lambda url, retry=3: (fetched.append(url), page)[1]

    assert len(scraper.scrape()) == 1
    assert fetched == [SM_URL]


@pytest.mark.unit
def test_skips_past_duplicate_and_placeholder_image(mock_geocoding_service):
    """Past shows and repeated URLs drop; SeatEngine's 'missing' image is blank."""
    page = _page(('Santa Monica', [
        _show('Santa Monica', 1, 'Old Show', datetime.now() - timedelta(days=2)),
        _show('Santa Monica', 2, 'Kept Show', _future(),
              image='/assets/headshot_missing.png'),
        _show('Santa Monica', 2, 'Kept Show', _future()),
        {'@type': 'Event', 'name': 'No date', 'location': {
            'address': {'addressLocality': 'Santa Monica'}}},
    ]))

    events = _run({SM_URL: page})

    assert [e.title for e in events] == ['Kept Show']
    assert events[0].image_url == ''


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert _run({}) == []
    assert _run({SM_URL: '<html><body>Just a moment...</body></html>',
                 MAIN_URL: '<html></html>'}) == []


@pytest.mark.unit
def test_shows_without_their_own_url_get_a_fragment_each(mock_geocoding_service):
    first, second = _show('Santa Monica', 1, 'Early Act', _future(5, 19)), _show('Santa Monica', 2, 'Late Act', _future(5, 22))
    del first['url'], second['url']

    events = _run({SM_URL: _page(('Santa Monica', [first, second]))})

    assert [e.title for e in events] == ['Early Act', 'Late Act']
    urls = [e.url for e in events]
    assert len(set(urls)) == 2
    assert all(u.startswith(HarvellesScraper().base_url + '#') for u in urls)

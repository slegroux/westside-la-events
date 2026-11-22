"""
Unit tests for the Vidiots scraper, which carries the tests for the shared
Filmbot parser (src/scrapers/filmbot.py). Brain Dead Studios' own rules are in
test_brain_dead_studios_scraper.py.

Fully offline: fetch_page is replaced with hand-built Filmbot pages (a JSON-LD
@graph of Movie and ScreeningEvent nodes). Showtimes are relative to today and
stamped with zoneinfo, so nothing depends on PST/PDT.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.filmbot import VidiotsScraper

BASE = 'https://vidiotsfoundation.org'


def _iso(dt):
    return dt.replace(tzinfo=ZoneInfo('America/Los_Angeles')).isoformat()


def _movie(slug, name, **extra):
    return {
        '@type': 'Movie',
        '@id': f'{BASE}/movies/{slug}/#movie',
        'name': name,
        'url': f'{BASE}/movies/{slug}/',
        'description': 'Rise, Roar, Revolt.\r\n<P><P />\r\nCan&#8217;t stop!',
        'image': f'https://img.example/{slug}.jpg',
        'duration': 'PT3H7M',
        'director': [{'@type': 'Person', 'name': 'S.S. Rajamouli'}],
        **extra,
    }


def _show(slug, name, start, offers=None, purchase=None, **extra):
    purchase = purchase or f'{BASE}/purchase/{slug}-{start:%m%d%H%M}/'
    if offers is None:
        offers = [{'name': 'General Admission', 'price': '12.00',
                   'availability': 'https://schema.org/InStock'},
                  {'name': 'Wheelchair Accessible Space', 'price': '9.00',
                   'availability': 'https://schema.org/InStock'}]
    return {
        '@type': 'ScreeningEvent',
        'name': f'{name} - {start:%m/%d/%y} @ {start:%I:%M %p}',
        'startDate': _iso(start),
        'endDate': _iso(start + timedelta(hours=2)),
        'url': purchase,
        'eventStatus': 'https://schema.org/EventScheduled',
        'workPresented': {'@id': f'{BASE}/movies/{slug}/#movie'},
        'offers': offers,
        **extra,
    }


def _page(*nodes):
    graph = {'@context': 'https://schema.org', '@graph': list(nodes)}
    return f'<html><head><script type="application/ld+json">{json.dumps(graph)}</script></head></html>'


def _run(scraper, pages):
    """pages maps URL -> HTML; returns the events and the URLs fetched."""
    fetched = []

    def fetch_page(url, retry=3):
        fetched.append(url)
        return pages.get(url)

    scraper.fetch_page = fetch_page
    return scraper.scrape(), fetched


def _future(days=3, hour=19, minute=0):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


COMING = f'{BASE}/coming-soon/'


@pytest.mark.unit
def test_parses_one_event_per_film_per_day(mock_geocoding_service):
    d1 = _future(3, 16, 30)
    d2 = _future(3, 20, 0)  # second showing the same day
    d3 = _future(4, 19, 0)  # next day: its own event
    page = _page(
        _movie('rrr', 'RRR'),
        _show('rrr', 'RRR', d1),
        _show('rrr', 'RRR', d2),
        _show('rrr', 'RRR', d3),
    )

    events, fetched = _run(VidiotsScraper(), {COMING: page})

    assert fetched == [COMING]  # the stale homepage is not read
    assert len(events) == 2
    day1, day2 = sorted(events, key=lambda e: e.event_date)
    assert day1.title == 'RRR'
    assert day1.event_date == d1 and day1.event_date.tzinfo is None
    assert 'Showtimes - 4:30pm, 8:00pm' in day1.description
    assert '187 min' in day1.description and 'A film by S.S. Rajamouli' in day1.description
    assert 'Rise, Roar, Revolt. Can’t stop!' in day1.description
    assert day1.category == 'Film'
    assert day1.image_url == 'https://img.example/rrr.jpg'
    assert day1.venue_name == 'Vidiots'
    assert day1.address == '4884 Eagle Rock Blvd, Los Angeles, CA 90041'
    assert (day1.latitude, day1.longitude) == (34.1393, -118.2118)
    assert day1.region == 'beyond'
    # Headline price is the first offer (general admission), not the wheelchair tier.
    assert day1.price == 12.0 and not day1.is_free and day1.price_note == ''
    # Consecutive days must not share a URL (insert_event would merge them).
    assert day1.url == f'{BASE}/movies/rrr/#{d1:%Y-%m-%d}'
    assert day2.url == f'{BASE}/movies/rrr/#{d3:%Y-%m-%d}'
    assert day1.url != day2.url


@pytest.mark.unit
def test_past_showings_are_dropped(mock_geocoding_service):
    past = datetime.now() - timedelta(hours=3)
    page = _page(
        _movie('old', 'Old Film'),
        _show('old', 'Old Film', past),
        _movie('new', 'New Film'),
        _show('new', 'New Film', _future()),
    )

    events, _ = _run(VidiotsScraper(), {COMING: page})

    assert [e.title for e in events] == ['New Film']


@pytest.mark.unit
def test_sold_out_and_free_pricing(mock_geocoding_service):
    sold = [{'name': 'General Admission', 'price': '12.00', 'availability': 'https://schema.org/SoldOut'}]
    free = [{'name': 'Free Matinee', 'price': '0', 'availability': 'https://schema.org/InStock'}]
    page = _page(
        _movie('sold', 'Sold Film'), _show('sold', 'Sold Film', _future(2), offers=sold),
        _movie('free', 'Free Film'), _show('free', 'Free Film', _future(3), offers=free),
        _movie('none', 'No Offers'), _show('none', 'No Offers', _future(4), offers=[]),
    )

    sold_e, free_e, none_e = _run(VidiotsScraper(), {COMING: page})[0]

    assert sold_e.price is None and sold_e.price_note == 'Sold out'
    assert free_e.is_free and free_e.price == 0.0
    # No offers is not a sell-out: price unknown, note left empty.
    assert none_e.price is None and none_e.price_note == '' and not none_e.is_free


@pytest.mark.unit
def test_sold_out_showing_is_flagged_but_day_stays_on_sale(mock_geocoding_service):
    sold = [{'name': 'General Admission', 'price': '12.00', 'availability': 'https://schema.org/SoldOut'}]
    page = _page(
        _movie('two', 'Double Day'),
        _show('two', 'Double Day', _future(3, 16, 0), offers=sold),
        _show('two', 'Double Day', _future(3, 20, 0)),
    )

    (event,) = _run(VidiotsScraper(), {COMING: page})[0]

    assert 'Showtimes - 4:00pm (sold out), 8:00pm' in event.description
    assert event.price == 12.0 and event.price_note == ''


@pytest.mark.unit
def test_orphan_screening_falls_back_to_its_name(mock_geocoding_service):
    page = _page(_show('ghost', 'Ghost Film', _future()))

    (event,) = _run(VidiotsScraper(), {COMING: page})[0]

    assert event.title == 'Ghost Film'  # the " - 11/21/26 @ 7:00 pm" suffix is stripped
    assert event.url.startswith(f'{BASE}/purchase/ghost-')


@pytest.mark.unit
def test_entities_in_titles_are_decoded(mock_geocoding_service):
    page = _page(_movie('mm', 'McCabe &amp; Mrs. Miller'), _show('mm', 'McCabe', _future()))

    (event,) = _run(VidiotsScraper(), {COMING: page})[0]

    assert event.title == 'McCabe & Mrs. Miller'


@pytest.mark.unit
def test_unusable_pages_yield_nothing(mock_geocoding_service):
    assert _run(VidiotsScraper(), {})[0] == []  # fetch failed
    assert _run(VidiotsScraper(), {COMING: '<html><body>Coming soon</body></html>'})[0] == []
    broken = '<script type="application/ld+json">{not json</script>'
    assert _run(VidiotsScraper(), {COMING: broken})[0] == []
    no_start = _page(_movie('x', 'X'), {**_show('x', 'X', _future()), 'startDate': 'soon'})
    assert _run(VidiotsScraper(), {COMING: no_start})[0] == []

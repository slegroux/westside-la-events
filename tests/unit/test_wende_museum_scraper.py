"""
Unit tests for the Wende Museum scraper (shared Tribe Events Calendar parser).

Fully offline: fetch_json is replaced with a hand-built Tribe API page shaped
like the live payload. Dates are generated relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.wende_museum import WendeMuseumScraper
from src.utils.geo_filter import is_in_coverage_area

MUSEUM = {
    'venue': 'The Wende Museum', 'address': '10808 Culver Boulevard',
    'city': 'Culver City', 'state': 'CA',
}
COMMUNITY_CENTER = {
    # Live names arrive HTML-escaped; no coordinates on any Wende venue.
    'venue': 'The Wende Museum&#8217;s Community Center',
    'address': '10858 Culver Boulevard', 'city': 'Culver City', 'state': 'CA',
}


def _stamp(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def _day(offset, hour=19):
    return (datetime.now() + timedelta(days=offset)).replace(
        hour=hour, minute=0, second=0, microsecond=0)


def _event(eid, title, start, venue=COMMUNITY_CENTER, categories=('Screening',), **extra):
    return {
        'id': eid,
        'title': title,
        'description': '<p>Films &amp; talk.</p>',
        'excerpt': '',
        'start_date': _stamp(start),
        'end_date': _stamp(start + timedelta(hours=2)),
        'url': f'https://wendemuseum.org/event/{eid}/',
        'cost': '',
        'all_day': False,
        'is_virtual': False,
        'venue': venue,
        'image': {'url': f'https://wendemuseum.org/img/{eid}.jpg'},
        'categories': [{'name': c} for c in categories],
        **extra,
    }


def _scraper(monkeypatch, events):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    s = WendeMuseumScraper()
    s.fetch_json = lambda *a, **k: {'total_pages': 1, 'events': events}
    return s


@pytest.mark.unit
def test_parses_event_with_pinned_community_center_venue(monkeypatch, mock_geocoding_service):
    when = _day(4)
    s = _scraper(monkeypatch, [_event('oscar-rabin', 'A Road of Many Colors', when)])

    [e] = s.scrape()

    assert e.title == 'A Road of Many Colors'
    assert e.event_date == when and e.end_date == when + timedelta(hours=2)
    assert e.venue_name == 'The Wende Museum’s Community Center'
    assert e.address == '10858 Culver Blvd, Culver City, CA 90230'
    assert (e.latitude, e.longitude) == (34.010829, -118.4049949)
    assert e.region == 'westside'
    assert e.category == 'Film'
    assert e.description == 'Films & talk.'
    assert e.url == 'https://wendemuseum.org/event/oscar-rabin/'
    assert e.image_url == 'https://wendemuseum.org/img/oscar-rabin.jpg'
    # Empty cost means unknown price: no badge.
    assert e.price is None and not e.is_free and e.price_note == ''


@pytest.mark.unit
def test_museum_venue_and_missing_venue_use_museum_coordinates(monkeypatch, mock_geocoding_service):
    s = _scraper(monkeypatch, [
        _event('family-day', 'Family Day', _day(3), venue=MUSEUM, categories=('Family',)),
        _event('no-venue', 'Health is Human', _day(5), venue=[], categories=('Community Partner',)),
    ])

    family, nowhere = s.scrape()

    assert family.venue_name == 'The Wende Museum'
    assert (family.latitude, family.longitude) == (34.011323, -118.4041322)
    assert family.category == 'Family'
    # An event with no venue record is held at the museum.
    assert nowhere.venue_name == 'The Wende Museum'
    assert nowhere.address == '10808 Culver Blvd, Culver City, CA 90230'
    assert nowhere.category == 'Community'


@pytest.mark.unit
def test_pinned_coordinates_are_in_the_coverage_area():
    for _needle, _addr, lat, lng in WendeMuseumScraper.VENUE_OVERRIDES:
        assert is_in_coverage_area(lat, lng)


@pytest.mark.unit
def test_drops_past_deadline_and_online_entries(monkeypatch, mock_geocoding_service):
    s = _scraper(monkeypatch, [
        _event('past', 'Last Week', _day(-6)),
        _event('deadline', 'Teen Council Applications Due', _day(6), venue=MUSEUM,
               categories=('Deadline',)),
        _event('online', 'Student Forum Applications', _day(7),
               venue={'venue': 'Online'}, categories=('Community Partner',)),
        _event('virtual', 'Zoom Talk', _day(8), is_virtual=True),
        _event('keep', 'Real Event', _day(9)),
    ])

    assert [e.title for e in s.scrape()] == ['Real Event']


@pytest.mark.unit
def test_category_rules(monkeypatch, mock_geocoding_service):
    cases = [
        (('Wellness', 'Workshop'), 'Wellness'),
        (('Community Partner', 'Wellness'), 'Wellness'),
        (('Workshop',), 'Education'),
        (('Conversation',), 'Education'),
        (('Music',), 'Music'),
        (('Special Event',), 'Art'),   # museum default
    ]
    events = [_event(f'e{i}', f'Event {i}', _day(2 + i), categories=cats)
              for i, (cats, _) in enumerate(cases)]

    got = [e.category for e in _scraper(monkeypatch, events).scrape()]

    assert got == [expected for _, expected in cases]


@pytest.mark.unit
def test_repeated_permalink_gets_unique_fragment(monkeypatch, mock_geocoding_service):
    first, second = _day(3, 10), _day(4, 10)
    same_url = 'https://wendemuseum.org/event/series/'
    s = _scraper(monkeypatch, [
        _event('a', 'Series', first, url=same_url),
        _event('b', 'Series', second, url=same_url),
    ])

    one, two = s.scrape()

    assert one.url == same_url
    assert two.url == f'{same_url}#{second:%Y-%m-%dT%H:%M}'


@pytest.mark.unit
def test_empty_and_failed_responses_return_nothing(monkeypatch, mock_geocoding_service):
    assert _scraper(monkeypatch, []).scrape() == []
    s = _scraper(monkeypatch, [])
    s.fetch_json = lambda *a, **k: None
    assert s.scrape() == []


@pytest.mark.unit
def test_event_without_a_start_date_is_skipped(monkeypatch, mock_geocoding_service):
    undated = _event('undated', 'No Date', _day(3), start_date='')
    assert _scraper(monkeypatch, [undated]).scrape() == []

"""
Unit tests for the Grateful Giraffes (The Oasis) scraper.

Fully offline: ``fetch_json`` is monkeypatched to return an events.json-shaped
payload, so no network call is made. The feed gives only a city per event, so
a small stub geocoder places the cities these tests use (the shared
``mock_geocoding_service`` fixture would send a bare "Los Angeles" downtown,
which is what the real geocoder does too, but knows nothing of Culver City).
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.grateful_giraffes import GratefulGiraffesScraper


_PLACES = (
    ('culver city', (34.0211, -118.3965)),
    ('topanga', (34.0937, -118.6015)),
    ('santa monica', (34.0195, -118.4912)),
    ('austin', (30.2672, -97.7431)),
    # Bare "Los Angeles" lands downtown, outside the Westside box.
    ('los angeles', (34.0522, -118.2437)),
)


class _Geocoder:
    def geocode_with_fallback(self, address, venue_name=None):
        text = (address or '').lower()
        for name, coords in _PLACES:
            if name in text:
                return coords
        return None

    def geocode(self, address):
        return self.geocode_with_fallback(address)


def _stamp(dt, offset='-08:00'):
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + offset


def _record(**overrides):
    """An in-person, future Culver City event; override to vary it."""
    start = (datetime.now() + timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    record = {
        'key': 'friendsgiving',
        'name': 'Friendsgiving',
        'url': 'https://app.grateful.gg/friendsgiving',
        'start': _stamp(start),
        'end': _stamp(start + timedelta(hours=3)),
        'time_zone': 'America/Los_Angeles',
        'city': 'Culver City',
        'online': False,
        'rsvp_open': True,
        'image': 'https://grateful.gg/x/hero.jpg',
    }
    record.update(overrides)
    return record


def _run(records):
    scraper = GratefulGiraffesScraper()
    scraper.geocoding_service = _Geocoder()
    scraper._fetch_events = lambda: records
    return scraper.scrape()


@pytest.mark.unit
def test_parses_a_westside_event():
    events = _run([_record()])

    assert len(events) == 1
    event = events[0]
    assert event.title == 'Friendsgiving'
    assert event.event_date.hour == 12
    assert event.end_date == event.event_date + timedelta(hours=3)
    assert event.address == 'Culver City'
    assert event.url == 'https://app.grateful.gg/friendsgiving'
    assert event.image_url == 'https://grateful.gg/x/hero.jpg'
    assert event.category == 'Food'
    # The feed carries no price: no badge, per the project convention.
    assert event.price_note == ''


@pytest.mark.unit
def test_aware_timestamp_is_converted_to_la_local():
    """A UTC stamp lands on the LA wall clock, not the UTC one."""
    start = (datetime.now() + timedelta(days=3)).replace(
        hour=20, minute=0, second=0, microsecond=0)
    events = _run([_record(start=_stamp(start, '+00:00'), end=None)])
    assert len(events) == 1
    assert events[0].event_date.hour in (12, 13)  # 20:00 UTC = 12:00 PST / 13:00 PDT


@pytest.mark.unit
def test_skips_online_events():
    assert _run([_record(online=True, city='Online')]) == []


@pytest.mark.unit
def test_drops_events_outside_the_westside():
    """An Austin event and a bare 'Los Angeles' one must not be pinned."""
    assert _run([_record(city='Austin'), _record(city='Los Angeles')]) == []


@pytest.mark.unit
def test_unreadable_start_is_skipped_not_fabricated():
    assert _run([_record(start=None), _record(start='soon')]) == []


@pytest.mark.unit
def test_end_before_start_is_dropped():
    start = (datetime.now() + timedelta(days=3)).replace(hour=12, minute=0, second=0, microsecond=0)
    events = _run([_record(end=_stamp(start - timedelta(hours=1)))])
    assert len(events) == 1
    assert events[0].end_date is None


@pytest.mark.unit
def test_fetch_events_reads_the_events_list():
    scraper = GratefulGiraffesScraper()
    scraper.fetch_json = lambda url, **kw: {'count': 1, 'events': [_record()]}
    assert len(scraper._fetch_events()) == 1
    scraper.fetch_json = lambda url, **kw: None  # e.g. HTTP error
    assert scraper._fetch_events() == []

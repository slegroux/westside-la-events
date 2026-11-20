"""
Unit tests for the California State Parks scraper.

Fully offline: fetch_json is monkeypatched to return small ArcGIS feature-service
payloads for the series layer (0) and the occurrence layer (1). Times are
relative to today and expressed as UTC epoch-ms, like the real service.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.parks_ca import ParksCaliforniaScraper

LA = ZoneInfo('America/Los_Angeles')
LAGOON = {'y_add_coordinates': 34.0386, 'x_add_coordinates': -118.6786}


def _series(gid, title, park='Malibu Lagoon State Beach', **kw):
    attrs = {
        'globalid': gid, 'event_title': title, 'park_unit': park,
        'district_pretty': 'Angeles District', 'event_description': 'Come along.',
        'park_address': '23200 Pacific Coast Highway, Malibu, CA 90265',
        'event_costType': 'Free', 'status': 'Approved',
        'event_signup_link': 'https://example.org/walk', **LAGOON,
    }
    attrs.update(kw)
    return {'attributes': attrs}


def _occ(parent, start_local, hours=1, **kw):
    """Occurrence whose naive LA-local start is `start_local`."""
    start = start_local.replace(tzinfo=LA)
    end = start + timedelta(hours=hours)
    attrs = {
        'parentglobalid': '{%s}' % parent.upper(), 'status': 'Active',
        'event_date_start': int(start.astimezone(timezone.utc).timestamp() * 1000),
        'event_date_end': int(end.astimezone(timezone.utc).timestamp() * 1000),
    }
    attrs.update(kw)
    return {'attributes': attrs}


def _run(series, occurrences):
    scraper = ParksCaliforniaScraper()

    def fake_fetch_json(url, json_body=None, headers=None, method='POST', retry=2):
        if '/FeatureServer/0/query' in url:
            return {'features': series}
        if '/FeatureServer/1/query' in url:
            return {'features': occurrences}
        return None

    scraper.fetch_json = fake_fetch_json
    return scraper.scrape()


@pytest.mark.unit
def test_builds_one_event_per_upcoming_occurrence(mock_geocoding_service):
    soon = (datetime.now() + timedelta(days=5)).replace(hour=8, minute=30, second=0, microsecond=0)
    later = soon + timedelta(days=7)
    events = _run(
        [_series('aaa', 'Bird Walk')],
        [_occ('aaa', later), _occ('aaa', soon)],
    )

    assert [e.event_date for e in events] == [soon, later]  # LA-local, sorted
    e = events[0]
    assert e.title == 'Bird Walk'
    assert e.venue_name == 'Malibu Lagoon State Beach'
    assert e.end_date == soon + timedelta(hours=1)
    assert e.is_free is True
    assert e.url == 'https://example.org/walk'
    assert not e.price_note


@pytest.mark.unit
def test_skips_cancelled_past_and_non_target(mock_geocoding_service):
    soon = datetime.now() + timedelta(days=3)
    events = _run(
        [
            _series('aaa', 'Bird Walk'),
            _series('bbb', 'Cancelled Walk', status='Cancelled'),
            _series('ccc', 'Elsewhere', park='Los Encinos State Historic Park'),
            _series('ddd', 'Partly Cancelled'),
        ],
        [
            _occ('aaa', soon),
            _occ('aaa', datetime.now() - timedelta(days=2)),  # already over
            _occ('bbb', soon),
            _occ('ccc', soon),
            _occ('ddd', soon, status='Cancelled'),
        ],
    )

    assert [e.title for e in events] == ['Bird Walk']


@pytest.mark.unit
def test_paid_event_price_and_parking_note(mock_geocoding_service):
    soon = datetime.now() + timedelta(days=3)
    events = _run(
        [_series('aaa', 'Guided Hike', event_costType='Cost', event_cost=15,
                 parking_yes_no='yes', parking_cost=12, event_signup_link=None)],
        [_occ('aaa', soon)],
    )

    e = events[0]
    assert e.price == 15.0 and not e.is_free
    assert e.price_note == 'Parking: $12'
    assert e.url == 'https://events.parks.ca.gov/'


@pytest.mark.unit
def test_service_failure_returns_nothing():
    scraper = ParksCaliforniaScraper()
    scraper.fetch_json = lambda *a, **k: None
    assert scraper.scrape() == []

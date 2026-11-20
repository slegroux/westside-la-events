"""
Unit tests for the Moments (momentsapp.no) venue scraper (Dr Paul Carlson Park).

Fully offline: fetch_page is monkeypatched with small JSON-LD fixtures, and the
429 case patches the HTTP session to check that a rate-limit/bot-challenge
response is requested exactly once.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from src.scrapers.momentsapp import CarlsonParkScraper


def _ld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


def _venue_page(*urls):
    items = [{'@type': 'ListItem', 'position': i + 1, 'item': u} for i, u in enumerate(urls)]
    return f'<html><head>{_ld({"@type": "ItemList", "itemListElement": items})}</head></html>'


def _event_page(url, name, start, **extra):
    data = {
        '@type': 'Event', 'name': name, 'url': url,
        'startDate': start.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'endDate': (start + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'location': {'geo': {'latitude': 34.0211, 'longitude': -118.3965}},
        'description': 'Free outdoor class.',
        'offers': {'price': '0'},
    }
    data.update(extra)
    return f'<html><head>{_ld(data)}</head></html>'


def _run(pages):
    scraper = CarlsonParkScraper()
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    scraper.prefetch_pages = lambda urls: None
    return scraper.scrape()


@pytest.mark.unit
def test_parses_upcoming_events_and_drops_past(mock_geocoding_service):
    scraper = CarlsonParkScraper()
    soon = datetime.now(timezone.utc) + timedelta(days=4)
    past = datetime.now(timezone.utc) - timedelta(days=4)
    u1, u2 = 'https://momentsapp.no/event/yoga', 'https://momentsapp.no/event/old'
    pages = {
        scraper.events_url: _venue_page(u1, u2),
        u1: _event_page(u1, 'Sunrise Yoga', soon),
        u2: _event_page(u2, 'Old Class', past),
    }

    events = _run(pages)

    assert [e.title for e in events] == ['Sunrise Yoga']
    e = events[0]
    assert e.is_free is True
    assert e.url == u1
    assert e.venue_name == 'Dr Paul Carlson Park'
    assert not e.price_note


@pytest.mark.unit
@pytest.mark.parametrize('status', [429, 403])
def test_challenge_or_rate_limit_is_requested_once(status):
    """A blocked venue page yields no events after a single request, no backoff."""
    response = Mock(status_code=status)
    response.raise_for_status.side_effect = requests.HTTPError(str(status), response=response)

    with patch('requests.Session.get', return_value=response) as mock_get, \
            patch('time.sleep') as mock_sleep:
        assert CarlsonParkScraper().scrape() == []

    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()

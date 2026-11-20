"""
Unit tests for how the Eventbrite scraper combines its search pages and
collection pages. Offline: the per-page scrapers are monkeypatched.
"""
from datetime import datetime, timedelta

import pytest
import requests
from unittest.mock import Mock, patch

from src.data.models import Event
from src.scrapers.eventbrite import EventbriteScraper


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    return EventbriteScraper()


def _event(slug, start):
    return Event(title=slug, event_date=start,
                 url=f'https://www.eventbrite.com/e/{slug}-tickets-1')


@pytest.mark.unit
def test_blocked_search_pages_do_not_stop_collection_scrape(scraper):
    """A search page blocked for this network (405) yields nothing; collections still run."""
    start = datetime.now() + timedelta(days=3)
    scraper._scrape_general_page = lambda url=None: []
    scraper._scrape_collection_page = lambda url: [_event('perrys-night', start)]

    events = scraper.scrape()

    assert [e.title for e in events] == ['perrys-night']


@pytest.mark.unit
def test_search_pages_are_all_visited_and_overlap_deduplicated(scraper):
    start = datetime.now() + timedelta(days=3)
    shared = _event('shared', start)
    pages = {
        scraper.listing_urls[0]: [shared, _event('la-only', start)],
        scraper.listing_urls[1]: [_event('shared', start), _event('sm-only', start)],
    }
    scraper._scrape_general_page = lambda url=None: pages.get(url, [])
    scraper._scrape_collection_page = lambda url: []

    events = scraper.scrape()

    assert len(scraper.listing_urls) >= 2
    assert sorted(e.title for e in events) == ['la-only', 'shared', 'sm-only']


@pytest.mark.unit
def test_405_on_search_page_is_requested_once(scraper):
    """The 405 bot wall must cost a single request, not three."""
    response = Mock(status_code=405)
    response.raise_for_status.side_effect = requests.HTTPError('405', response=response)

    with patch('requests.Session.get', return_value=response) as mock_get, \
            patch('time.sleep') as mock_sleep:
        assert scraper._scrape_general_page(scraper.listing_urls[0]) == []

    assert mock_get.call_count == 1
    mock_sleep.assert_not_called()

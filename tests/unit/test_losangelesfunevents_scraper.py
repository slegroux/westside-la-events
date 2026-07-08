"""
Unit tests for the Los Angeles Fun Events (Weary Livers) scraper.

Fully offline: fetch_page is monkeypatched to return HTML with an embedded Wix
``"events":[ ... ]`` data blob, so no network or browser is launched.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.scrapers.losangelesfunevents import LosAngelesFunEventsScraper


def _event_obj(title, slug, start_utc, *, address="2819 Pico Blvd, Santa Monica, CA 90405, USA"):
    """Build one Wix-shaped event object like the ones embedded on the site."""
    end_utc = start_utc + timedelta(hours=3)
    return {
        "id": slug,
        "title": title,
        "description": "A short tagline",
        "about": "",
        "slug": slug,
        "mainImage": {"url": "https://static.wixstatic.com/media/x~mv2.png"},
        "location": {
            "name": "Weary Livers Santa Monica",
            "address": address,
            "coordinates": {"lat": 34.0247155, "lng": -118.4600619},
        },
        "scheduling": {
            "config": {
                "startDate": start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "endDate": end_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "timeZoneId": "America/Los_Angeles",
            }
        },
    }


def _page_html(events):
    """Embed an events array inside surrounding JSON, as the Wix page does."""
    blob = json.dumps({"events": events, "listLayout": {}})
    return f'<html><body><script>window.__DATA={blob};</script></body></html>'


def _run(scraper, events):
    scraper.fetch_page = lambda url, retry=3: _page_html(events)
    return scraper.scrape()


@pytest.mark.unit
def test_parses_upcoming_events_with_category_mapping(mock_geocoding_service):
    """Upcoming events parse with coords, permalink, and mapped categories."""
    soon = datetime.now(timezone.utc) + timedelta(days=2)
    events = _run(
        LosAngelesFunEventsScraper(),
        [
            _event_obj("Musicians Night | Santa Monica | Open Play",
                       "musicians-night", soon),
            _event_obj("World Cup FINALS Watch Party", "wc-finals", soon),
            _event_obj("Comedy Show @ Weary Livers - Chris Thayer", "comedy", soon),
        ],
    )

    assert len(events) == 3
    by_title = {e.title: e for e in events}

    music = by_title["Musicians Night | Santa Monica | Open Play"]
    assert music.category == "Music"  # mapped, not the auto-classifier's "Art"
    assert music.venue_name == "Weary Livers Santa Monica"
    assert abs(music.latitude - 34.0247155) < 1e-6
    assert abs(music.longitude - (-118.4600619)) < 1e-6
    assert music.url == (
        "https://www.losangelesfunevents.com/event-details/musicians-night"
    )
    assert music.image_url.startswith("https://")

    assert by_title["World Cup FINALS Watch Party"].category == "Sports"
    assert by_title["Comedy Show @ Weary Livers - Chris Thayer"].category == "Comedy"


@pytest.mark.unit
def test_skips_past_events(mock_geocoding_service):
    """A past-dated event still listed on the page is dropped."""
    past = datetime.now(timezone.utc) - timedelta(days=5)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    events = _run(
        LosAngelesFunEventsScraper(),
        [
            _event_obj("Old Karaoke Night", "old-karaoke", past),
            _event_obj("Upcoming Karaoke Night", "new-karaoke", future),
        ],
    )

    assert [e.title for e in events] == ["Upcoming Karaoke Night"]


@pytest.mark.unit
def test_dedupes_repeated_slug(mock_geocoding_service):
    """The same event listed twice (same slug) is emitted only once."""
    soon = datetime.now(timezone.utc) + timedelta(days=3)
    events = _run(
        LosAngelesFunEventsScraper(),
        [
            _event_obj("Country Night for Singles", "country-night", soon),
            _event_obj("Country Night for Singles", "country-night", soon),
        ],
    )

    assert len(events) == 1
    assert events[0].category == "Music"

"""
Unit tests for the KCRW scraper's Next.js payload parsing.

Fully offline: fetch_page_js is monkeypatched to return a small page whose
`self.__next_f.push` flight data mirrors what kcrw.com embeds. Dates are
relative to today so the tests do not rot.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.kcrw import KCRWScraper


def _event(eid, title, start, city, venue, slug, category="Music", end=None):
    return {
        "__typename": "Event",
        "sys": {"id": eid},
        "title": title,
        "start": start,
        "end": end,
        "slug": slug,
        "venue": {"name": venue, "city": city, "state": "California"},
        "image": {"asset": {"url": f"https://images.ctfassets.net/{slug}.jpg"}},
        "categoriesCollection": {"items": [{"title": category}]},
    }


def _page(events, duplicate=False):
    """Embed events the way the RSC flight data does (escaped inside a JS string)."""
    flight = '1b:["$","$L1d",null,{"events":' + json.dumps(events) + "}]\n"
    pushes = [f"<script>self.__next_f.push({json.dumps([1, flight])})</script>"]
    if duplicate:  # the hero section repeats events in a second payload
        pushes.append(f"<script>self.__next_f.push({json.dumps([1, flight])})</script>")
    return f"<html><body>{''.join(pushes)}</body></html>"


def _iso(dt, offset=None):
    """ISO start with a real LA offset (DST-correct), or a fixed one if given."""
    if offset:
        return dt.strftime("%Y-%m-%dT%H:%M:00.000") + offset
    return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles")).isoformat()


def _run(html):
    s = KCRWScraper()
    s.fetch_page_js = lambda url, **kw: html
    return s.scrape()


@pytest.mark.unit
def test_parses_westside_event_from_payload(mock_geocoding_service):
    when = (datetime.now() + timedelta(days=9)).replace(hour=19, minute=30, second=0, microsecond=0)
    html = _page([
        _event("a", "Show At The Pier", _iso(when), "Santa Monica", "Santa Monica Pier", "show-at-the-pier"),
    ])

    events = _run(html)

    assert len(events) == 1
    e = events[0]
    assert e.title == "Show At The Pier"
    assert e.event_date == when  # tz-aware -08:00/-07:00 start converted to LA-local
    assert e.venue_name == "Santa Monica Pier"
    assert e.category == "Music"
    assert e.url == "https://www.kcrw.com/events/show-at-the-pier"
    assert e.image_url.endswith("show-at-the-pier.jpg")
    assert e.price_note == ""


@pytest.mark.unit
def test_non_candidate_cities_are_skipped_and_duplicates_collapsed(mock_geocoding_service):
    when = datetime.now() + timedelta(days=5)
    html = _page(
        [
            _event("a", "In Santa Monica", _iso(when), "Santa Monica", "Barker Hangar", "in-sm"),
            _event("b", "In Pasadena", _iso(when), "Pasadena", "Memorial Park", "in-pasadena"),
            _event("c", "In Kyoto", _iso(when, "+09:00"), "Kyoto", "Temple", "in-kyoto"),
        ],
        duplicate=True,
    )

    events = _run(html)

    assert [e.title for e in events] == ["In Santa Monica"]


@pytest.mark.unit
def test_no_payload_and_no_cards_returns_empty(mock_geocoding_service):
    assert _run("<html><body><h1>Vercel Security Checkpoint</h1></body></html>") == []


class CountingGeocoder:
    """Stands in for GeocodingService: a persistent-style cache that grows on each real lookup."""

    def __init__(self, cached=()):
        self.cache = {a.lower(): {"result": {"lat": 34.02, "lng": -118.49}} for a in cached}
        self.calls = []

    def geocode_with_fallback(self, address, venue_name=None):
        self.calls.append(address)
        self.cache.setdefault(address.lower().strip(), {"result": {"lat": 34.02, "lng": -118.49}})
        return (34.02, -118.49)


def _venue_events(n_venues, per_venue=1):
    when = (datetime.now() + timedelta(days=4)).replace(hour=20, minute=0, second=0, microsecond=0)
    return [
        _event(f"{v}-{i}", f"Show {v}-{i}", _iso(when), "Santa Monica", f"Venue {v}", f"show-{v}-{i}")
        for v in range(n_venues) for i in range(per_venue)
    ]


def _run_with(geocoder, html):
    s = KCRWScraper()
    s.geocoding_service = geocoder
    s.fetch_page_js = lambda url, **kw: html
    return s.scrape()


@pytest.mark.unit
def test_each_venue_is_geocoded_once_per_scrape():
    geocoder = CountingGeocoder()
    events = _run_with(geocoder, _page(_venue_events(3, per_venue=4)))

    assert len(events) == 12
    assert len(geocoder.calls) == 3
    assert all(e.latitude == 34.02 for e in events)


@pytest.mark.unit
def test_new_geocodes_are_capped_and_cached_venues_are_free(monkeypatch):
    monkeypatch.setattr(KCRWScraper, "MAX_NEW_GEOCODES", 2)
    cached = ["Venue 4, Santa Monica, California"]
    geocoder = CountingGeocoder(cached=cached)

    events = _run_with(geocoder, _page(_venue_events(6)))

    # Venues 0-1 use the budget; 2-3 are skipped; 4 is cached so it still lands; 5 skipped.
    assert sorted(e.title for e in events) == ["Show 0-0", "Show 1-0", "Show 4-0"]
    assert len(geocoder.calls) == 3  # 2 new + the cached venue (served without growing the cache)

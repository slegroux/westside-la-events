"""
Unit tests for the IO Music Academy LA scraper (Resident Advisor club #282834).

Offline: the GraphQL call (BaseScraper.fetch_json) is stubbed with a crafted
payload, so no network access. Covers past-event filtering, free/paid pricing,
the implausible-end guard, and the geo allowlist that lets this Hollywood venue
through the Westside filter.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.io_music_academy import IOMusicAcademyScraper
from src.utils.geo_filter import is_allowlisted_venue


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000")


def _payload():
    """A venue payload with one past event and three upcoming ones."""
    today = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    past = today - timedelta(days=10)
    soon = today + timedelta(days=5)
    bogus = today + timedelta(days=7)
    paid = today + timedelta(days=9)
    return {
        "data": {"venue": {
            "id": "282834",
            "name": "IO Music Academy LA",
            "address": "1550 N Gower St",
            "location": {"latitude": 34.1, "longitude": -118.32},
            "events": [
                {"id": "1", "title": "Past Workshop", "date": _iso(past),
                 "startTime": _iso(past), "endTime": _iso(past + timedelta(hours=3)),
                 "cost": "0", "content": "old", "contentUrl": "/events/1",
                 "flyerFront": "", "artists": []},
                {"id": "2", "title": "Intro to DJing", "date": _iso(soon),
                 "startTime": _iso(soon), "endTime": _iso(soon + timedelta(hours=3)),
                 "cost": "0", "content": "Learn to DJ", "contentUrl": "/events/2",
                 "flyerFront": "https://img.ra.co/flyer2.jpg",
                 "artists": [{"name": "Miles Otway"}]},
                {"id": "3", "title": "Producing Techno", "date": _iso(bogus),
                 "startTime": _iso(bogus),
                 "endTime": _iso(bogus + timedelta(days=1, hours=3)),  # implausible (~27h)
                 "cost": "", "content": "", "contentUrl": "/events/3",
                 "flyerFront": "", "artists": [{"name": "Pilo"}]},
                {"id": "4", "title": "Advanced Mixing", "date": _iso(paid),
                 "startTime": _iso(paid), "endTime": _iso(paid + timedelta(hours=4)),
                 "cost": "25", "content": "", "contentUrl": "/events/4",
                 "flyerFront": "", "artists": []},
            ],
        }}
    }


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv("SCRAPER_DISABLE_LOGOS", "true")
    s = IOMusicAcademyScraper()
    s.fetch_json = lambda *a, **k: _payload()   # stub the network call
    return s


@pytest.mark.unit
@pytest.mark.scraper
class TestIOMusicAcademyScraper:
    def test_filters_past_and_returns_upcoming(self, scraper):
        events = scraper.scrape()
        titles = [e.title for e in events]
        assert "Past Workshop" not in titles          # past dropped
        assert titles == ["Intro to DJing", "Producing Techno", "Advanced Mixing"]

    def test_venue_geo_and_category(self, scraper):
        e = scraper.scrape()[0]
        assert e.venue_name == "IO Music Academy LA"
        assert (e.latitude, e.longitude) == (34.1, -118.32)   # Hollywood coords kept
        assert e.address == "1550 N Gower St, Los Angeles, CA"
        assert e.category == "Education"
        assert e.url == "https://ra.co/events/2"

    def test_free_and_paid_pricing(self, scraper):
        by_title = {e.title: e for e in scraper.scrape()}
        assert by_title["Intro to DJing"].is_free is True
        assert by_title["Intro to DJing"].price is None
        assert by_title["Advanced Mixing"].is_free is False
        assert by_title["Advanced Mixing"].price == 25.0

    def test_lineup_in_description(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == "Intro to DJing")
        assert "Miles Otway" in e.description

    def test_implausible_end_is_dropped(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == "Producing Techno")
        # ~27h next-day end is discarded -> single-day event
        assert e.end_date is None

    def test_empty_response_returns_empty_list(self, scraper):
        scraper.fetch_json = lambda *a, **k: None
        assert scraper.scrape() == []


@pytest.mark.unit
class TestVenueAllowlist:
    def test_io_music_academy_is_allowlisted(self):
        assert is_allowlisted_venue(venue_name="IO Music Academy LA") is True

    def test_other_venue_not_allowlisted(self):
        assert is_allowlisted_venue(venue_name="Some Hollywood Bar") is False

    def test_allowlisted_hollywood_event_bypasses_geo(self, monkeypatch, mock_geocoding_service):
        # An allowlisted venue with out-of-area coords is still created;
        # a non-allowlisted one at the same coords is filtered out.
        monkeypatch.setenv("SCRAPER_DISABLE_LOGOS", "true")
        s = IOMusicAcademyScraper()
        kept = s.create_event(title="x", venue_name="IO Music Academy LA",
                              address="1550 N Gower St", event_date=datetime(2026, 7, 1, 19),
                              latitude=34.1, longitude=-118.32, category="Education")
        dropped = s.create_event(title="x", venue_name="Random Hollywood Venue",
                                 address="6121 Sunset Blvd", event_date=datetime(2026, 7, 1, 19),
                                 latitude=34.1, longitude=-118.32, category="Music")
        assert kept is not None
        assert dropped is None

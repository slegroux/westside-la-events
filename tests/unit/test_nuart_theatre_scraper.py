"""
Unit tests for the Nuart Theatre scraper.

Fully offline: fetch_json is stubbed with trimmed copies of the Landmark
`schedule` and `movies` API responses. Showtimes are relative to now.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.nuart_theatre import NuartTheatreScraper


def _st(dt):
    return {"id": dt.isoformat(), "startsAt": dt.strftime("%Y-%m-%dT%H:%M:%S")}


def _movie(movie_id, title, **extra):
    movie = {
        "id": movie_id,
        "title": title,
        "runtime": 6000,
        "certificate": "R",
        "poster": f"https://img.example/{movie_id}.jpg",
        "synopsis": "A cult classic.",
        "directors": {"nodes": [{"person": {"firstName": "Jim", "lastName": "Sharman"}}]},
    }
    movie.update(extra)
    return movie


def _scraper(schedule, movies):
    s = NuartTheatreScraper()
    calls = []

    def fake_fetch_json(url, json_body=None, headers=None, method="POST", retry=2):
        calls.append((method, url))
        if "/schedule?" in url:
            return {"X00CW": {"schedule": schedule}}
        if "/movies?" in url:
            return movies
        return None

    s.fetch_json = fake_fetch_json
    s.calls = calls
    return s


@pytest.mark.unit
def test_one_event_per_film_per_day_with_upcoming_times_only(mock_geocoding_service):
    now = datetime.now()
    d1 = (now + timedelta(days=3)).replace(hour=23, minute=0, second=0, microsecond=0)
    d2 = d1 + timedelta(days=7)
    past = now - timedelta(days=2)
    schedule = {
        "313": {
            d1.strftime("%Y-%m-%d"): [_st(d1), _st(d1)],  # API repeats the 11pm slot
            d2.strftime("%Y-%m-%d"): [_st(d2)],
        },
        "999": {past.strftime("%Y-%m-%d"): [_st(past)]},  # all in the past
        "888": {d1.strftime("%Y-%m-%d"): [_st(d1)]},       # no movie details
    }
    movies = [_movie("313", "The Rocky Horror Picture Show"), _movie("999", "Old Film")]

    scraper = _scraper(schedule, movies)
    events = scraper.scrape()

    assert [e.event_date for e in events] == [d1, d2]
    e = events[0]
    assert e.title == "The Rocky Horror Picture Show"
    assert e.category == "Film"
    assert e.venue_name == "Nuart Theatre"
    assert e.url == (
        "https://www.landmarktheatres.com/movies/313-the-rocky-horror-picture-show/?theater=X00CW"
    )
    assert e.image_url == "https://img.example/313.jpg"
    assert not e.price_note
    assert abs(e.latitude - 34.0433) < 1e-4
    assert "100 min. R" in e.description
    assert "A film by Jim Sharman" in e.description
    assert e.description.count("11:00pm") == 1
    # Schedule and movie details are both requested as GETs.
    assert all(method == "GET" for method, _ in scraper.calls)
    assert any("ids=313" in url for _, url in scraper.calls)


@pytest.mark.unit
def test_empty_schedule_returns_no_events(mock_geocoding_service):
    assert _scraper({}, []).scrape() == []

"""
Unit tests for the Laemmle Monica Film Center scraper.

Fully offline: fetch_page and fetch_json are stubbed with trimmed copies of the
site's Next.js markup and its /api/showtimes/<film uuid> JSON. Showtimes are
generated relative to now so the tests don't rot.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.laemmle_monica import LaemmleMonicaScraper

FILM_ID = "f19104b7-dce6-4a34-9eff-b2d77f5ce9e2"

THEATER_HTML = """
<html><body><main>
  <a href="/film/birds-war?x=1">Birds of War</a>
  <a href="/film/birds-war">Birds of War again</a>
  <a href="/film/glendale-only">Glendale Only</a>
  <a href="/film/missing-id">No id</a>
</main></body></html>
"""


def _film_html(title, film_id=FILM_ID):
    return f"""
    <html><body><main>
      <div class="film-poster"><img src="https://www.laemmle.com/posters/1.jpg" alt="{title}"/></div>
      <div class="film-badges"><span class="badge badge-rating">Not Rated</span>
        <span class="badge-meta">English <span class="badge-sep">·</span> 88 min</span></div>
      <h1 class="film-title" id="film-title">{title}</h1>
      <div data-synopsis-inner="true"><p>A love story across war.</p></div>
      <script>self.__next_f.push([1,"{{\\"filmId\\":\\"{film_id}\\",\\"x\\":1}}"])</script>
    </main></body></html>
    """


def _st(dt, slug="monica", qa=False):
    return {
        "id": dt.strftime("%H%M"),
        "startsAt": dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "theaterSlug": slug,
        "ticketUrl": "https://tickets.laemmle.com/x",
        "hasQandA": qa,
    }


def _scraper(pages, showtimes_by_id):
    s = LaemmleMonicaScraper()
    s.fetch_page = lambda url, retry=3: pages.get(url)
    s.prefetch_pages = lambda urls, max_concurrent=5: None
    s.fetch_json = lambda url, json_body=None, headers=None, method="POST", retry=2: {
        "showtimes": showtimes_by_id.get(url.rsplit("/", 1)[-1], [])
    }
    return s


@pytest.mark.unit
def test_only_monica_upcoming_showtimes_become_events(mock_geocoding_service):
    now = datetime.now()
    day = (now + timedelta(days=2)).replace(hour=19, minute=30, second=0, microsecond=0)
    later = day + timedelta(days=1)
    past = now - timedelta(days=1)
    base = "https://www.laemmle.com"
    pages = {
        f"{base}/theater/monica-film-center": THEATER_HTML,
        f"{base}/film/birds-war": _film_html("Birds of War"),
        f"{base}/film/glendale-only": _film_html("Glendale Only", "a" * 8 + "-aaaa-aaaa-aaaa-" + "a" * 12),
        f"{base}/film/missing-id": "<html><body><h1 class='film-title'>X</h1></body></html>",
    }
    showtimes = {
        FILM_ID: [
            _st(past),                       # already happened -> ignored
            _st(later, qa=True),
            _st(day),                        # earliest upcoming
            _st(day, slug="glendale"),       # other theater -> ignored
        ],
        "a" * 8 + "-aaaa-aaaa-aaaa-" + "a" * 12: [_st(day, slug="glendale")],
    }

    events = _scraper(pages, showtimes).scrape()

    assert len(events) == 1  # duplicate link collapsed, Glendale-only film skipped
    e = events[0]
    assert e.title == "Birds of War"
    assert e.event_date == day
    assert e.category == "Film"
    assert e.url == f"{base}/film/birds-war"
    assert e.image_url == "https://www.laemmle.com/posters/1.jpg"
    assert e.venue_name == "Laemmle Monica Film Center"
    assert abs(e.latitude - 34.0149) < 1e-4
    assert not e.price_note
    assert "88 min. Not Rated" in e.description
    assert "7:30pm" in e.description
    assert "Q&A" in e.description
    assert f"{day.strftime('%a %b')} {day.day}" in e.description
    assert f"{later.strftime('%a %b')} {later.day}" in e.description


@pytest.mark.unit
def test_no_theater_page_returns_empty(mock_geocoding_service):
    assert _scraper({}, {}).scrape() == []

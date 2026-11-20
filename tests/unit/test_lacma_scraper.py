"""
Unit tests for the LACMA scraper.

Fully offline: fetch_page is monkeypatched with small hand-built fixtures in
LACMA's two listing layouts (per-day ``<h3>`` calendar blocks, and the
paginated ``<h4 class="event-calendar-date-group">`` view). Dates are relative
to today.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.lacma import LACMAScraper

NOW = datetime.now()
D1 = NOW + timedelta(days=1)
D2 = NOW + timedelta(days=2)


def _card(slug, title, dt, location="LACMA", time="11 am", zone=""):
    return f"""
    <div class="col-sm-6 views-row"><div class="card-event">
      <div class="card-event__header"><span class="card-event__type">Talks</span></div>
      <div class="card-event__body">
        <div class="card-event__name"><a href="/event/{slug}">{title}</a></div>
        <div class="card-event__content"><p>About {slug}.</p></div>
        <div class="card-event__date"><span>{dt:%a %b} {dt.day}</span> | <span>{time}{zone}</span></div>
        <div class="card-event__location"><span>{location}</span></div>
      </div></div></div>"""


def _calendar_page(*days):
    """Layout A: one views-calendar-results block per day, <h3> with year."""
    out = ""
    for dt, cards in days:
        out += (f'<div class="views-calendar-results"><h3>{dt:%A}, {dt:%B} {dt.day}, {dt.year}</h3>'
                f'<div class="row">{"".join(cards)}</div></div>')
    return f"<html><head><title>Events</title></head><body>{out}</body></html>"


def _paged_page(*days):
    """Layout B: <h4 class="event-calendar-date-group"> with no year."""
    out = ""
    for dt, cards in days:
        out += (f'<h4 class="event-calendar-date-group">{dt:%A}, {dt:%B} {dt.day}</h4>'
                f'<div class="container"><div class="row">{"".join(cards)}</div></div>')
    return f"<html><head><title>Events</title></head><body>{out}</body></html>"


def _run(pages, detail=None):
    """pages: {url-suffix: html}; unknown URLs -> None (fetch failure)."""
    s = LACMAScraper()

    def fake_fetch(url, retry=3):
        if detail and '/event/' in url:
            return detail.get(url)
        for suffix, html in pages.items():
            if url.endswith(suffix):
                return html
        return None

    s.fetch_page = fake_fetch
    return s.scrape()


@pytest.mark.unit
def test_paginated_layout_collects_all_pages(mock_geocoding_service):
    p0 = _paged_page((D1, [_card("a", "Talk A", D1), _card("b", "Talk B", D1, time="2:30 pm", zone=" PT")]))
    p1 = _paged_page((D2, [_card("c", "Talk C", D2, location="BCAM, Level 3 &nbsp;|&nbsp; LACMA")]))
    events = _run({"?page=0": p0, "?page=1": p1})  # page 2 -> None -> stop

    assert [e.title for e in events] == ["Talk A", "Talk B", "Talk C"]
    assert events[0].event_date == D1.replace(hour=11, minute=0, second=0, microsecond=0)
    assert events[1].event_date.hour == 14 and events[1].event_date.minute == 30  # "PT" stripped
    assert events[2].venue_name == "LACMA — BCAM, Level 3"
    assert events[0].venue_name == "LACMA"
    assert events[0].url == "https://www.lacma.org/event/a"


@pytest.mark.unit
def test_falls_back_to_bare_calendar_layout(mock_geocoding_service):
    bare = _calendar_page((D1, [_card("a", "Talk A", D1)]), (D2, [_card("b", "Talk B", D2)]))
    # every ?page=N fetch fails; the bare /events-calendar page still parses
    events = _run({"/events-calendar": bare})

    assert [e.title for e in events] == ["Talk A", "Talk B"]
    assert events[1].event_date.date() == D2.date()


@pytest.mark.unit
def test_truncated_title_replaced_from_json_ld(mock_geocoding_service):
    full = "Curator Walkthrough of The Brockman Gallery: Los Angeles, 1967-1990"
    page = _paged_page((D1, [_card("walk", "Curator Walkthrough of The Brockman Gallery: Los Angeles, 19...", D1)]))
    ld = json.dumps({"@graph": [{"@type": "Event", "name": full}]})
    detail = {"https://www.lacma.org/event/walk": f'<script type="application/ld+json">{ld}</script>'}

    events = _run({"?page=0": page}, detail=detail)

    assert [e.title for e in events] == [full]


@pytest.mark.unit
def test_past_events_dropped(mock_geocoding_service):
    past = NOW - timedelta(days=3)
    page = _paged_page((past, [_card("old", "Old Talk", past)]), (D1, [_card("new", "New Talk", D1)]))
    assert [e.title for e in _run({"?page=0": page})] == ["New Talk"]


@pytest.mark.unit
def test_unrecognised_page_logs_what_was_received(mock_geocoding_service, caplog):
    block = "<html><head><title>Access Denied</title></head><body>Please verify you are human</body></html>"
    with caplog.at_level("INFO"):
        events = _run({"/events-calendar": block, "?page=0": block})

    assert events == []
    out = caplog.text
    assert "Access Denied" in out and "length=" in out


@pytest.mark.unit
def test_time_budget_stops_paging_and_keeps_collected_events(mock_geocoding_service, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr("src.scrapers.lacma.time.monotonic", lambda: clock["t"])
    p0 = _paged_page((D1, [_card("a", "Talk A", D1)]))
    p1 = _paged_page((D2, [_card("b", "Talk B", D2)]))
    s = LACMAScraper()
    fetched = []

    def fake_fetch(url, retry=3):
        fetched.append((url, retry))
        if url.endswith("?page=0"):
            clock["t"] += 95  # the site hung: page 0 alone spent the budget
            return p0
        return p1

    s.fetch_page = fake_fetch
    events = s.scrape()

    assert [e.title for e in events] == ["Talk A"]
    assert fetched == [("https://www.lacma.org/events-calendar?page=0", 1)]


@pytest.mark.unit
def test_hung_site_skips_bare_page_fallback_once_over_budget(mock_geocoding_service, monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr("src.scrapers.lacma.time.monotonic", lambda: clock["t"])
    s = LACMAScraper()
    fetched = []

    def fake_fetch(url, retry=3):
        fetched.append(retry)
        clock["t"] += 100  # every fetch times out
        return None

    s.fetch_page = fake_fetch

    assert s.scrape() == []
    assert fetched == [1]  # page 0 only, with a single attempt; no fallback fetch


@pytest.mark.unit
def test_hanging_site_never_runs_past_the_budget(mock_geocoding_service, monkeypatch):
    """Every request stalls for its whole timeout; the clamp keeps the total at the budget."""
    import requests

    clock = {"t": 0.0}
    monkeypatch.setattr("src.scrapers.lacma.time.monotonic", lambda: clock["t"])
    s = LACMAScraper()
    timeouts = []

    class HangingSession:
        headers = {}
        cookies = None

        def get(self, url, timeout=None, **kw):
            timeouts.append(timeout)
            clock["t"] += timeout  # the request stalls until its timeout fires
            raise requests.exceptions.ReadTimeout("hang")

    s.session._session = HangingSession()

    assert s.scrape() == []
    assert clock["t"] <= LACMAScraper.SCRAPE_BUDGET_SECONDS
    assert all(t <= 30 for t in timeouts)
    assert timeouts[-1] < 30  # the last request was cut short to fit
    assert len(timeouts) == 3  # 30 + 30 + 20, retry=1 each; no bare-page fallback


@pytest.mark.unit
def test_failed_page_is_skipped_and_paging_continues(mock_geocoding_service):
    p0 = _paged_page((D1, [_card("a", "Talk A", D1)]))
    p2 = _paged_page((D2, [_card("c", "Talk C", D2)]))
    events = _run({"?page=0": p0, "?page=2": p2})  # page 1 fails

    assert [e.title for e in events] == ["Talk A", "Talk C"]

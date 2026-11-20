"""
Unit tests for the UCLA Design Media Arts scraper.

Offline: fetch_page is monkeypatched with a minimal Next.js page whose
__NEXT_DATA__ blob holds events dated relative to today.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.scrapers.ucla_design import UCLADesignScraper


def _item(slug, title, days_from_now):
    when = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    return {"title": title, "slug": slug, "type": "Lecture", "description": "**Talk**",
            "date": when.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "images": []}


def _page(events):
    blob = json.dumps({"props": {"pageProps": {"events": events}}})
    return f'<html><body><script id="__NEXT_DATA__" type="application/json">{blob}</script></body></html>'


def _run(events):
    s = UCLADesignScraper()
    s.fetch_page = lambda url, retry=3: _page(events)
    return s.scrape()


@pytest.mark.unit
def test_keeps_upcoming_and_drops_past(mock_geocoding_service):
    events = _run([_item("future", "Fall Lecture", 10), _item("past", "Old Show", -40)])

    assert [e.title for e in events] == ["Fall Lecture"]
    assert events[0].url.endswith("/events/future")
    assert events[0].category == "Education"


@pytest.mark.unit
def test_all_past_logs_why_nothing_was_scraped(mock_geocoding_service, caplog):
    with caplog.at_level("INFO"):
        events = _run([_item("a", "Old A", -30), _item("b", "Old B", -60)])

    assert events == []
    assert "All 2 listed events are in the past" in caplog.text

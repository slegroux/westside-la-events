"""
Unit tests for the Hotel June scraper.

Fully offline: fetch_page is monkeypatched with a small JSON-LD @graph shaped
like the live page (events reference their venue by ``{"@id": ...}`` and carry
startDate stamps whose clock reading is UTC despite a "-08:00" label). Dates
are generated relative to today.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.hotel_june import HotelJuneScraper

HOTEL = "https://www.thehoteljune.com/west-los-angeles/"
CANTINA_ID = f"{HOTEL}#caravan-cantina"
CANTINA = {
    "@type": "Restaurant",
    "@id": CANTINA_ID,
    "name": "Caravan Cantina",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "8639 Lincoln Blvd",
        "addressLocality": "Los Angeles",
        "addressRegion": "CA",
        "postalCode": "90045",
    },
}

ALL_DAYS = [
    f"https://schema.org/{d}"
    for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
]


def _page(*events, places=(CANTINA,)):
    graph = list(places) + list(events)
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph})
    return f'<html><head><script type="application/ld+json">{ld}</script></head></html>'


def _stamp(local_dt):
    """Stamp a LA-local clock the way the site does: UTC clock, '-08:00' label."""
    utc = local_dt + timedelta(hours=8)  # PST is UTC-8; the code reads the clock as UTC
    return utc.strftime("%Y-%m-%dT%H:%M:%S") + "-08:00"


def _event(name, **extra):
    node = {"@type": "Event", "@id": f"{HOTEL}happenings/#{name}", "name": name,
            "location": {"@id": CANTINA_ID}}
    node.update(extra)
    return node


def _at(days, hour, minute=0):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)


def _run(html):
    scraper = HotelJuneScraper()
    scraper.fetch_page = lambda url, retry=3: html
    return scraper.scrape()


@pytest.mark.unit
def test_one_off_resolves_venue_reference_and_reads_utc_clock(mock_geocoding_service):
    day = _at(20, 15)
    end = day.replace(hour=20, minute=45)
    html = _page(_event("Thanksgiving", startDate=_stamp(day), endDate=_stamp(end),
                        image="https://example.com/i.jpg"))

    events = _run(html)

    assert len(events) == 1
    e = events[0]
    assert e.venue_name == "Caravan Cantina"
    assert "8639 Lincoln Blvd" in e.address
    assert e.event_date == day  # 3 PM, not the 23:00 shown in the stamp
    assert e.end_date == end
    assert e.image_url == "https://example.com/i.jpg"
    assert e.price_note == ""


@pytest.mark.unit
def test_past_one_off_is_dropped(mock_geocoding_service):
    assert _run(_page(_event("Old", startDate=_stamp(_at(-5, 15))))) == []


@pytest.mark.unit
def test_weekly_special_expands_despite_first_occurrence_end_date(mock_geocoding_service):
    """node endDate ends the first occurrence only; it must not cap the series."""
    first = _at(-8, 15)
    node = _event(
        "Golden Hour",
        startDate=_stamp(first),
        endDate=_stamp(first.replace(hour=18)),
        eventSchedule={
            "@type": "Schedule",
            "repeatFrequency": "P1W",
            "byDay": ["https://schema.org/Monday", "https://schema.org/Friday"],
            "startTime": "15:00:00",
            "endTime": "18:00:00",
            "startDate": first.strftime("%Y-%m-%d"),
        },
    )

    events = _run(_page(node))

    assert len(events) >= 8  # two weekdays across a 60 day window
    assert {e.event_date.weekday() for e in events} == {0, 4}
    assert all(e.event_date.hour == 15 for e in events)
    assert all(e.end_date == e.event_date.replace(hour=18) for e in events)
    assert all(e.event_date >= datetime.now() for e in events)


@pytest.mark.unit
def test_schedule_end_date_bounds_series(mock_geocoding_service):
    stop = datetime.now() + timedelta(days=10)
    node = _event(
        "Trivia",
        startDate=_stamp(_at(-1, 19)),
        eventSchedule={
            "byDay": ALL_DAYS,
            "startTime": "19:00:00",
            "endDate": stop.strftime("%Y-%m-%d"),
        },
    )

    events = _run(_page(node))

    assert events
    assert max(e.event_date for e in events).date() <= stop.date()


@pytest.mark.unit
def test_listing_without_street_address_is_skipped(mock_geocoding_service):
    place = {"@type": "Place", "@id": f"{HOTEL}#city", "name": "Somewhere",
             "address": {"addressLocality": "Los Angeles", "addressRegion": "CA"}}
    node = _event("Citywide", startDate=_stamp(_at(3, 15)))
    node["location"] = {"@id": f"{HOTEL}#city"}

    assert _run(_page(node, places=(CANTINA, place))) == []

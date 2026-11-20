"""
Unit tests for the Hotel June scraper.

Fully offline: fetch_page is monkeypatched with a small JSON-LD @graph shaped
like the live page (events reference their venue by ``{"@id": ...}`` and carry
startDate stamps whose clock reading is UTC despite a "-08:00" label). Dates
are generated relative to today.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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


LA = ZoneInfo("America/Los_Angeles")


def _stamp(local_dt):
    """Stamp a LA-local clock the way the site does: UTC clock, '-08:00' label."""
    utc = local_dt.replace(tzinfo=LA).astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S") + "-08:00"


def _true_stamp(local_dt):
    """Stamp a LA-local clock with its real offset ('-08:00' PST, '-07:00' PDT)."""
    return local_dt.replace(tzinfo=LA).isoformat(timespec="seconds")


def _anchor(local_first, stamp=_stamp):
    """A scheduled node: its startDate stamp vs startTime lets the scraper
    measure the page's skew. ``local_first`` is its first occurrence (15:00)."""
    return _event(
        "Anchor",
        startDate=stamp(local_first),
        eventSchedule={
            "repeatFrequency": "P1W",
            "byDay": ["https://schema.org/Monday"],
            "startTime": "15:00:00",
            "startDate": local_first.strftime("%Y-%m-%d"),
        },
    )


def _on(month, day, hour=15):
    """Next future occurrence of a calendar date (a known PST or PDT day)."""
    now = datetime.now()
    d = datetime(now.year, month, day, hour)
    return d if d > now + timedelta(days=2) else d.replace(year=now.year + 1)


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
    html = _page(_anchor(_at(-3, 15)),
                 _event("Thanksgiving", startDate=_stamp(day), endDate=_stamp(end),
                        image="https://example.com/i.jpg"))

    events = [e for e in _run(html) if e.title == "Thanksgiving"]

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
            "repeatFrequency": "P1W",
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


def _one_off(events):
    return [e for e in events if e.title == "Gala"]


@pytest.mark.unit
@pytest.mark.parametrize("anchor_month", [1, 7], ids=["anchor-in-PST", "anchor-in-PDT"])
@pytest.mark.parametrize("gala_month", [1, 7], ids=["gala-in-PST", "gala-in-PDT"])
def test_mislabelled_page_skew_is_measured_whatever_the_season(
        mock_geocoding_service, anchor_month, gala_month):
    gala = _on(gala_month, 15)
    html = _page(_anchor(datetime(2026, anchor_month, 15, 15)),
                 _event("Gala", startDate=_stamp(gala)))

    events = _one_off(_run(html))

    assert [e.event_date for e in events] == [gala]


@pytest.mark.unit
@pytest.mark.parametrize("month", [1, 7], ids=["PST", "PDT"])
def test_correctly_labelled_page_has_no_skew(mock_geocoding_service, month):
    gala = _on(month, 15)
    html = _page(_anchor(datetime(2026, month, 15, 15), stamp=_true_stamp),
                 _event("Gala", startDate=_true_stamp(gala)))

    assert [e.event_date for e in _one_off(_run(html))] == [gala]


@pytest.mark.unit
def test_unmeasurable_page_reads_clock_as_local(mock_geocoding_service):
    gala = _on(7, 15)  # PDT: "-07:00"
    html = _page(_event("Gala", startDate=_true_stamp(gala)))

    assert [e.event_date for e in _one_off(_run(html))] == [gala]


def _weekly(name, start_date, **schedule):
    return _event(
        name,
        startDate=_stamp(start_date),
        eventSchedule={
            "byDay": ALL_DAYS,
            "startTime": "15:00:00",
            "startDate": start_date.strftime("%Y-%m-%d"),
            **schedule,
        },
    )


@pytest.mark.unit
def test_future_start_series_does_not_run_before_its_start_date(mock_geocoding_service):
    start = _at(14, 15)
    events = _run(_page(_weekly("Soon", start, repeatFrequency="P1W")))

    assert events
    assert min(e.event_date for e in events).date() == start.date()


@pytest.mark.unit
@pytest.mark.parametrize("frequency", ["P2W", "P1M"])
def test_unsupported_repeat_frequency_is_skipped(mock_geocoding_service, frequency):
    assert _run(_page(_weekly("Biweekly", _at(-8, 15), repeatFrequency=frequency))) == []


@pytest.mark.unit
def test_p7d_frequency_is_weekly(mock_geocoding_service):
    assert _run(_page(_weekly("Daily-ish", _at(-8, 15), repeatFrequency="P7D")))


@pytest.mark.unit
def test_series_without_repeat_frequency_is_skipped(mock_geocoding_service):
    node = _weekly("Undated cadence", _at(-8, 15))
    assert _run(_page(node)) == []


@pytest.mark.unit
def test_one_outlier_node_does_not_move_a_correctly_labelled_page(mock_geocoding_service):
    anchors = []
    for i in range(7):
        a = _anchor(datetime(2026, 1, 12 + i, 15), stamp=_true_stamp)
        a["name"] = a["@id"] = f"Anchor{i}"
        anchors.append(a)
    off = _anchor(datetime(2026, 1, 20, 15), stamp=_true_stamp)
    off["name"] = off["@id"] = "Odd"
    off["startDate"] = _true_stamp(datetime(2026, 1, 20, 14))  # first occurrence 1 h off
    gala = _on(7, 15)

    events = _one_off(_run(_page(*anchors, off, _event("Gala", startDate=_true_stamp(gala)))))

    assert [e.event_date for e in events] == [gala]


@pytest.mark.unit
def test_date_only_node_is_not_measured(mock_geocoding_service):
    date_only = _anchor(datetime(2026, 1, 12, 15))
    date_only["startDate"] = "2026-01-12"  # would read as a 9 h skew from 00:00
    gala = _on(1, 15)
    html = _page(date_only, _event("Gala", startDate=_true_stamp(gala)))

    assert [e.event_date for e in _one_off(_run(html))] == [gala]


@pytest.mark.unit
def test_fixed_label_with_corrected_clock_in_summer(mock_geocoding_service):
    """Site fixed the clock but kept a '-08:00' label: July 15:00 stays 15:00."""
    def stamp(dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "-08:00"

    gala = _on(7, 15)
    html = _page(_anchor(datetime(2026, 1, 12, 15), stamp=stamp),
                 _event("Gala", startDate=stamp(gala)))

    assert [e.event_date for e in _one_off(_run(html))] == [gala]

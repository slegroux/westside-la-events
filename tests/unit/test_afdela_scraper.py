"""
Unit tests for the AFdela scraper.

Fully offline: fetch_page is monkeypatched with a small hand-written iCalendar
feed and a listing page. Dates are relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.afdela import AFdelaScraper

BASE = 'https://www.afdela.org'
CLASS_URL = 'https://anc.apm.activecommunities.com/alliancefrancaisela/activity/search/detail/9665'


def _ics_dt(dt):
    return dt.strftime('%Y%m%dT%H%M%S')


def _vevent(slug, title, start, hours=1, location='Alliance Française de Los Angeles',
            url=None, rrule=None, blurb='A lovely evening.', exdates=()):
    end = start + timedelta(hours=hours)
    url = url or f'{BASE}/events/{slug}'
    lines = [
        'BEGIN:VEVENT',
        f'UID:{slug}@afdela.org',
        f'DTSTART;TZID=America/Los_Angeles:{_ics_dt(start)}',
        f'DTEND;TZID=America/Los_Angeles:{_ics_dt(end)}',
    ]
    if rrule:
        lines.append(f'RRULE:{rrule}')
    # One EXDATE line per excluded start, as calendar exporters write them.
    lines += [f'EXDATE;TZID=America/Los_Angeles:{_ics_dt(d)}' for d in exdates]
    lines += [
        f'SUMMARY:{title}',
        f'LOCATION:{location.replace(",", chr(92) + ",")}',
        # Long lines are folded with a leading space, as in the real feed.
        f'DESCRIPTION:{blurb[:10]}',
        f' {blurb[10:]}\\nSaturday\\, Some Day · 7 PM\\n{url}',
        f'URL:{url}',
        'END:VEVENT',
    ]
    return '\r\n'.join(lines)


def _feed(*vevents):
    return '\r\n'.join(['BEGIN:VCALENDAR', 'VERSION:2.0', *vevents, 'END:VCALENDAR'])


LISTING = (
    '<html><body><main><article>'
    '<a href="/events/book-fair">Book Fair</a>'
    '<img src="/events/book-fair.jpg" alt="Flyer"></article></main></body></html>'
)


def _run(feed):
    scraper = AFdelaScraper()
    pages = {f'{BASE}/calendar.ics': feed, f'{BASE}/events': LISTING}
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    return scraper.scrape()


def _soon(days=10, hour=19):
    return (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


@pytest.mark.unit
def test_parses_event_from_calendar_feed(mock_geocoding_service):
    when = _soon()
    events = _run(_feed(_vevent('book-fair', 'Book Fair', when, hours=2,
                                blurb='Brand new French books for adults and kids.')))

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Book Fair'
    assert e.event_date == when
    assert e.end_date == when + timedelta(hours=2)
    assert e.venue_name == 'Alliance Française de Los Angeles'
    assert e.url == f'{BASE}/events/book-fair'
    assert e.image_url == f'{BASE}/events/book-fair.jpg'
    # Blurb kept; the human date line and URL are dropped.
    assert e.description == 'Brand new French books for adults and kids.'
    assert not e.price_note


@pytest.mark.unit
def test_skips_classes_past_and_online_events(mock_geocoding_service):
    when = _soon()
    events = _run(_feed(
        _vevent('class', 'Creative Writing', when, url=CLASS_URL),
        _vevent('old', 'Old Talk', datetime.now() - timedelta(days=30)),
        _vevent('zoom', 'Couture on Zoom', when, location='Online'),
        _vevent('keep', 'Keep Me', when + timedelta(days=1)),
    ))

    assert [e.title for e in events] == ['Keep Me']


@pytest.mark.unit
def test_recurring_event_yields_only_next_occurrence(mock_geocoding_service):
    first = _soon(days=-14)  # started two weeks ago, weekly for ~6 more weeks
    until = (first + timedelta(days=50)).strftime('%Y%m%dT235959Z')
    events = _run(_feed(_vevent('series', '8-Week Series', first,
                                rrule=f'FREQ=WEEKLY;UNTIL={until}')))

    assert len(events) == 1
    nxt = events[0].event_date
    assert nxt >= datetime.now() - timedelta(hours=1)
    assert nxt <= datetime.now() + timedelta(days=7)
    assert nxt.weekday() == first.weekday() and nxt.hour == first.hour


@pytest.mark.unit
def test_exdate_skips_excluded_occurrences(mock_geocoding_service):
    first = _soon(days=-14)
    rule = 'FREQ=WEEKLY;COUNT=20'
    plain = _run(_feed(_vevent('series', 'Series', first, rrule=rule)))
    nxt = plain[0].event_date

    one = _run(_feed(_vevent('series', 'Series', first, rrule=rule, exdates=[nxt])))
    assert one[0].event_date == nxt + timedelta(days=7)

    # Several EXDATE lines must all count, not just the last one.
    two = _run(_feed(_vevent('series', 'Series', first, rrule=rule,
                             exdates=[nxt, nxt + timedelta(days=7)])))
    assert two[0].event_date == nxt + timedelta(days=14)


@pytest.mark.unit
def test_finished_recurring_series_and_feed_failure(mock_geocoding_service):
    first = _soon(days=-60)
    until = (first + timedelta(days=21)).strftime('%Y%m%dT235959Z')
    assert _run(_feed(_vevent('done', 'Done', first, rrule=f'FREQ=WEEKLY;UNTIL={until}'))) == []

    scraper = AFdelaScraper()
    scraper.fetch_page = lambda url, retry=3: None
    assert scraper.scrape() == []

"""
Unit tests for the CAP UCLA scraper.

Fully offline: fetch_page is replaced with hand-built markup shaped like the
live Drupal calendar view. Timestamps are built with zoneinfo from today's
date, so the tests don't depend on PST vs PDT.

The page has two datetime conventions (see the scraper docstring): a "Z" stamp
on single nights that is really local wall-clock time, and suffix-less true UTC
stamps on multi-night runs.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.cap_ucla import CAPUCLAScraper
from src.utils.geo_filter import is_in_coverage_area

LA = ZoneInfo('America/Los_Angeles')


def _night(offset, hour=20, minute=0):
    """Naive LA wall-clock datetime `offset` days from today."""
    return (datetime.now() + timedelta(days=offset)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)


def _label(dt):
    return f'{dt:%a}, {dt:%b} {dt.day}'


def _clock(dt):
    hour = dt.hour % 12 or 12
    mins = f':{dt.minute:02d}' if dt.minute else ''
    return f'{hour}{mins} {"pm" if dt.hour >= 12 else "am"}'


def _single(dt):
    """Single night: "Z"-suffixed wall clock, then the shown time."""
    return (f'<time datetime="{dt:%Y-%m-%dT%H:%M:%S}Z">{_label(dt)}</time>'
            f'   &nbsp;| {_clock(dt)}\n')


def _utc(dt):
    return dt.replace(tzinfo=LA).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def _run(first, last):
    """Multi-night run: true-UTC stamps, no "Z", one shown time at the end."""
    return (f'<time datetime="{_utc(first)}">{_label(first)}</time> | '
            f'<time datetime="{_utc(last)}">{_label(last)}</time>&nbsp;| {_clock(first)}')


def _row(slug, date_html, artist, title, venue, kind='Live performance', genre='Dance'):
    def field(name, value):
        return (f'<div class="views-field views-field-field-event-{name}">'
                f'<div class="field-content">{value}</div></div>')
    return (
        f'<a href="/event/{slug}" class="views-row plain">'
        '<div class="container-left">'
        f'{field("image", f"<img loading=lazy src=/sites/default/files/{slug}.jpg alt=x>")}'
        '</div><div class="container-right">'
        f'{field("date", date_html)}{field("artist", artist)}{field("title", title)}'
        f'{field("venue", venue)}{field("type", kind)}{field("genre", genre)}'
        '</div></a>'
    )


def _page(*rows):
    return f'<html><body><div class="view-content">{"".join(rows)}</div></body></html>'


def _scrape(html):
    s = CAPUCLAScraper()
    s.fetch_page = lambda url, retry=3: html
    return s.scrape()


@pytest.fixture(autouse=True)
def _offline(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')


@pytest.mark.unit
def test_single_night_z_stamp_is_wall_clock_not_utc():
    night = _night(6)
    [e] = _scrape(_page(_row('cloud-gate', _single(night), 'Cloud Gate Dance Theatre of Taiwan',
                             'Blue Hour / Beckoning: A Double Bill', 'Royce Hall')))

    # Stored as 8 pm LA, not converted from UTC (which would give noon).
    assert e.event_date == night and e.event_date.tzinfo is None
    assert e.end_date is None
    assert e.title == 'Cloud Gate Dance Theatre of Taiwan: Blue Hour / Beckoning: A Double Bill'
    assert e.url == 'https://cap.ucla.edu/event/cloud-gate'
    assert e.image_url == 'https://cap.ucla.edu/sites/default/files/cloud-gate.jpg'
    assert e.category == 'Theater'
    # No price on the calendar: unknown, no badge.
    assert e.price is None and not e.is_free and e.price_note == ''


@pytest.mark.unit
def test_multi_night_run_converts_true_utc_and_lists_first_night():
    first, last = _night(10), _night(11)
    [e] = _scrape(_page(_row('pirates', _run(first, last), 'Pussy, King of the Pirates',
                             'Written by Kathy Acker and the Mekons', 'The Nimoy', genre='Theater')))

    # Fri 8 pm Pacific is Sat 04:00 UTC; it must come back as the Friday evening.
    assert e.event_date == first
    assert e.end_date is None
    assert e.title == 'Pussy, King of the Pirates written by Kathy Acker and the Mekons'


@pytest.mark.unit
def test_time_text_wins_when_the_stamp_disagrees():
    night = _night(7, hour=19)
    wrong = f'<time datetime="{night:%Y-%m-%dT}12:00:00Z">{_label(night)}</time> | 7 pm'

    [e] = _scrape(_page(_row('odd', wrong, 'Artist', 'Show', 'Royce Hall')))

    assert e.event_date == night


@pytest.mark.unit
def test_each_hall_gets_its_own_coordinates():
    rows = [
        _row('a', _single(_night(3)), 'A', 'One', 'Royce Hall'),
        _row('b', _single(_night(4)), 'B', 'Two', 'The Nimoy'),
        _row('c', _single(_night(5)), 'C', 'Three', 'Freud Playhouse'),
    ]

    royce, nimoy, freud = _scrape(_page(*rows))

    assert royce.venue_name == 'Royce Hall'
    assert (royce.latitude, royce.longitude) == (34.0728, -118.4421)
    assert nimoy.venue_name == 'The Nimoy Theater'
    assert (nimoy.latitude, nimoy.longitude) == (34.0577521, -118.4427816)
    assert freud.venue_name == 'Freud Playhouse'
    assert len({(e.latitude, e.longitude) for e in (royce, nimoy, freud)}) == 3
    assert all(e.region == 'westside' for e in (royce, nimoy, freud))


@pytest.mark.unit
def test_pinned_coordinates_are_in_the_coverage_area():
    for _needle, _name, _addr, lat, lng in CAPUCLAScraper.VENUES:
        assert is_in_coverage_area(lat, lng)


@pytest.mark.unit
def test_drops_past_k12_and_venueless_rows():
    rows = [
        _row('past', _single(_night(-5)), 'Old', 'Show', 'Royce Hall'),
        _row('school', _single(_night(4, hour=10, minute=45)), 'Violinist', 'School Matinee Grades 6-12',
             'The Nimoy', kind='K–12 programs'),
        _row('nowhere', _single(_night(5)), 'Mystery', 'Show', ''),
        _row('keep', _single(_night(6)), 'Keeper', 'Show', 'Royce Hall'),
    ]

    assert [e.title for e in _scrape(_page(*rows))] == ['Keeper: Show']


@pytest.mark.unit
def test_title_joins_and_co_billed_artists():
    rows = [
        _row('x', _single(_night(3)), 'POOR Magazine and Green Diamond Projects present',
             'Crushing Wheelchairs', 'The Nimoy', kind='Screening', genre='Film'),
        _row('y', _single(_night(4)), 'JENNIFER KOH, violin<br>VIJAY IYER, composer, piano',
             'Music for Violin and Piano', 'Royce Hall', genre='Contemporary Classical'),
        _row('z', _single(_night(5)), 'Cuervo', '', 'The Nimoy'),
    ]

    film, duo, solo = _scrape(_page(*rows))

    assert film.title == 'POOR Magazine and Green Diamond Projects present Crushing Wheelchairs'
    assert film.category == 'Film'
    assert duo.title == 'JENNIFER KOH, violin & VIJAY IYER, composer, piano: Music for Violin and Piano'
    assert duo.category == 'Music'
    assert solo.title == 'Cuervo'


@pytest.mark.unit
def test_same_page_listed_twice_gets_unique_urls():
    matinee, evening = _night(8, hour=14), _night(8, hour=20)
    rows = [_row('dup', _single(matinee), 'Artist', 'Show', 'Royce Hall'),
            _row('dup', _single(evening), 'Artist', 'Show', 'Royce Hall')]

    first, second = _scrape(_page(*rows))

    assert first.url == 'https://cap.ucla.edu/event/dup'
    assert second.url == f'https://cap.ucla.edu/event/dup#{evening:%Y-%m-%dT%H:%M}'


@pytest.mark.unit
def test_unrecognised_or_empty_page_returns_nothing():
    assert _scrape('<html><body><p>Maintenance</p></body></html>') == []
    assert _scrape(_page()) == []
    assert _scrape(None) == []
    # A row with no <time> is not guessed at.
    assert _scrape(_page(_row('undated', 'TBA', 'Artist', 'Show', 'Royce Hall'))) == []

"""
Unit tests for the REDCAT scraper.

Fully offline: fetch_page serves a hand-built listing and event pages (the
DATE / TIME facts list). Dates are generated relative to today; the year
inference is exercised through weekday-consistent dates.
"""
from datetime import date, datetime, timedelta

import pytest

from src.scrapers.redcat import RedcatScraper


def _listing(slugs):
    cards = ''.join(
        f'<a href=/events/{s}\n  class="event-card-stacked h-[610px] block"><div>card</div></a>'
        for s in slugs
    )
    return f'<html><body>{cards}<a class="event-card-stacked" href="/events/archive">Archive</a></body></html>'


def _event_page(title, facts, description='About the show.'):
    rows = ''.join(f'<dt class="uppercase">{k}</dt><dd>{v}</dd>' for k, v in facts.items())
    return (
        f'<html><head><title>{title} | REDCAT</title>'
        f'<meta name="description" content="{description}" />'
        '<meta property="og:image" content="https://www.redcat.org/img.jpg" /></head>'
        f'<body><dl class="grid">{rows}</dl></body></html>'
    )


def _md(d):
    """Site style: 'DEC 4'."""
    return f'{d:%b}'.upper() + f' {d.day}'


def _next_weekday(start, weekday):
    return start + timedelta(days=(weekday - start.weekday()) % 7)


def _at(d, hour, minute=0):
    return datetime(d.year, d.month, d.day, hour, minute)


def _run(listing, pages):
    scraper = RedcatScraper()

    def fetch_page(url, retry=3):
        if url == RedcatScraper.EVENTS_URL:
            return listing
        return pages.get(url.rsplit('/', 1)[-1])

    scraper.fetch_page = fetch_page
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


@pytest.mark.unit
def test_expands_thu_sat_run_into_performances(mock_geocoding_service):
    thursday = _next_weekday(date.today() + timedelta(days=7), 3)
    saturday = thursday + timedelta(days=2)
    facts = {
        'Price': '$25 + $2 Convenience Fee*',
        'Genres': 'Theater, Film, Dance, Music',
        'DATE': f'{_md(thursday)}-{_md(saturday)}',
        'TIME': 'THU-SAT, 8 PM',
    }
    events = _run(_listing(['now-week']), {'now-week': _event_page('NOW 2026: Week Three', facts)})

    assert [e.event_date for e in events] == [_at(thursday + timedelta(days=n), 20) for n in range(3)]
    e = events[0]
    assert e.title == 'NOW 2026: Week Three'
    assert e.price == 25.0 and not e.is_free and e.price_note == ''  # fee is extra, not the price
    assert e.category == 'Theater'
    assert e.description == 'About the show.'
    assert e.image_url == 'https://www.redcat.org/img.jpg'
    assert e.venue_name == 'REDCAT'
    # One URL per performance, or consecutive nights collapse in the database.
    assert len({x.url for x in events}) == 3
    assert e.url == f'https://redcat.org/events/now-week#{thursday.isoformat()}T20:00'
    # Downtown is outside the Westside box: beyond tab.
    assert e.region == 'beyond'


@pytest.mark.unit
def test_year_is_inferred_from_weekday(mock_geocoding_service):
    """A Saturday in two months is read in the year where that date IS a Saturday."""
    target = _next_weekday(date.today() + timedelta(days=60), 5)
    facts = {'DATE': _md(target), 'TIME': 'SAT, 3:30 PM'}

    (e,) = _run(_listing(['one']), {'one': _event_page('Matinee', facts)})

    assert e.event_date == _at(target, 15, 30)


@pytest.mark.unit
def test_two_ranges_and_multiple_times_per_day(mock_geocoding_service):
    thu1 = _next_weekday(date.today() + timedelta(days=14), 3)
    fri1 = thu1 + timedelta(days=1)
    thu2 = thu1 + timedelta(days=7)
    facts = {
        'DATE': f'{_md(thu1)}-{_md(fri1)} & {_md(thu2)}',
        'TIME': 'THU, 8 PM; FRI, 3 & 8 PM',
    }
    events = _run(_listing(['two']), {'two': _event_page('Split Run', facts)})

    assert [e.event_date for e in events] == [
        _at(thu1, 20), _at(fri1, 15), _at(fri1, 20), _at(thu2, 20)
    ]


@pytest.mark.unit
def test_past_performances_dropped(mock_geocoding_service):
    past_thu = _next_weekday(date.today() - timedelta(days=21), 3)
    if past_thu >= date.today():
        past_thu -= timedelta(days=7)
    facts = {'DATE': _md(past_thu), 'TIME': 'THU, 8 PM'}

    assert _run(_listing(['old']), {'old': _event_page('Old Show', facts)}) == []


@pytest.mark.unit
def test_exhibitions_and_unreadable_dates_are_skipped(mock_geocoding_service):
    pages = {
        # Exhibition: DATE range with HOURS, no TIME.
        'show': _event_page('Flesh Witness', {'Genre': 'Art', 'DATE': 'SEP 12 - DEC 13', 'HOURS': 'THU-FRI, 3-10 PM'}),
        # Times without AM/PM cannot be read safely.
        'vague': _event_page('Vague Times', {'DATE': 'DEC 5', 'TIME': 'SAT, 8'}),
        # Unrecognised date text.
        'odd': _event_page('Odd Dates', {'DATE': 'Opening night', 'TIME': 'SAT, 8 PM'}),
        # No facts at all.
        'bare': _event_page('Bare', {}),
    }

    assert _run(_listing(list(pages)), pages) == []


@pytest.mark.unit
def test_free_event_and_listing_filters(mock_geocoding_service):
    sat = _next_weekday(date.today() + timedelta(days=10), 5)
    pages = {'free': _event_page('Free Talk', {'Price': 'Free', 'Genre': 'Talk', 'DATE': _md(sat), 'TIME': 'SAT, 2 PM'})}

    # '/events/archive' is not an event, and a listed page that fails to load is skipped.
    (e,) = _run(_listing(['free', 'gone']), pages)

    assert e.is_free and e.price is None
    assert e.category == 'Education'


@pytest.mark.unit
@pytest.mark.parametrize('listing', ['<html><body>nothing</body></html>', None])
def test_empty_or_unrecognised_listing(mock_geocoding_service, listing):
    assert _run(listing, {}) == []


@pytest.mark.unit
@pytest.mark.parametrize('text, expected', [
    ('THU-SAT, 8 PM', [({3, 4, 5}, [(20, 0)])]),
    ('SUN, 3:30 PM', [({6}, [(15, 30)])]),
    ('FRI, 8 PM; SAT, 3 & 8 PM', [({4}, [(20, 0)]), ({5}, [(15, 0), (20, 0)])]),
    ('7:30 PM', [(None, [(19, 30)])]),
    ('SAT-MON, 12 PM', [({5, 6, 0}, [(12, 0)])]),
    ('THU, 6-8 PM', [({3}, [(18, 0)])]),
    ('SAT, 6:30-8 PM', [({5}, [(18, 30)])]),
    ('SUN, 11 AM-1 PM', [({6}, [(11, 0)])]),
    ('7:30 PM (DOORS 7 PM)', [(None, [(19, 30)])]),
    ('FRI, 8 PM, DOORS 7 PM', [({4}, [(20, 0)])]),
    ('THU-SAT, 8', []),
    ('TBA', []),
])
def test_time_grammar(text, expected):
    assert RedcatScraper._time_slots(text) == expected


@pytest.mark.unit
def test_door_time_is_not_a_second_show(mock_geocoding_service):
    sat = _next_weekday(date.today() + timedelta(days=10), 5)
    facts = {'DATE': _md(sat), 'TIME': 'SAT, 7:30 PM (DOORS 7 PM)'}

    (e,) = _run(_listing(['doors']), {'doors': _event_page('Doors Show', facts)})

    assert e.event_date == _at(sat, 19, 30)


@pytest.mark.unit
def test_time_range_is_one_show(mock_geocoding_service):
    sat = _next_weekday(date.today() + timedelta(days=10), 5)
    facts = {'DATE': _md(sat), 'TIME': 'SAT, 6-8 PM'}

    (e,) = _run(_listing(['rng']), {'rng': _event_page('Range Show', facts)})

    assert e.event_date == _at(sat, 18)


@pytest.mark.unit
def test_long_range_without_weekday_is_skipped(mock_geocoding_service):
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=50)
    facts = {'DATE': f'{_md(start)} - {_md(end)}', 'TIME': '8 PM'}

    assert _run(_listing(['long']), {'long': _event_page('Long Run', facts)}) == []


@pytest.mark.unit
def test_short_range_without_weekday_is_nightly(mock_geocoding_service):
    start = date.today() + timedelta(days=10)
    end = start + timedelta(days=2)
    facts = {'DATE': f'{_md(start)} - {_md(end)}', 'TIME': '8 PM'}

    events = _run(_listing(['short']), {'short': _event_page('Short Run', facts)})

    assert [e.event_date for e in events] == [_at(start + timedelta(days=i), 20) for i in range(3)]


@pytest.mark.unit
def test_and_separates_dates():
    # "DEC 4 AND 6": both days are read (the split is case-insensitive). Fixed today.
    got = RedcatScraper._performances('DEC 4 and 6', 'FRI, SUN, 8 PM', date(2026, 11, 20))

    assert got == [datetime(2026, 12, 4, 20), datetime(2026, 12, 6, 20)]


@pytest.mark.unit
@pytest.mark.parametrize('date_text', ['DEC 30 AND JAN 2', 'DEC 30 & JAN 2'])
def test_new_year_rollover_between_segments(date_text):
    got = RedcatScraper._performances(date_text, 'WED, SAT, 8 PM', date(2026, 12, 20))

    assert got == [datetime(2026, 12, 30, 20), datetime(2027, 1, 2, 20)]


@pytest.mark.unit
def test_new_year_rollover_next_day():
    got = RedcatScraper._performances('DEC 31 & JAN 1', 'THU, FRI, 8 PM', date(2026, 12, 20))

    assert got == [datetime(2026, 12, 31, 20), datetime(2027, 1, 1, 20)]


@pytest.mark.unit
def test_comma_separated_weekday_clauses_keep_their_own_times():
    # DEC 4-6 2026 is Fri-Sun.
    got = RedcatScraper._performances('DEC 4-6', 'FRI & SAT 8 PM, SUN 2 PM', date(2026, 11, 20))
    assert got == [datetime(2026, 12, 4, 20), datetime(2026, 12, 5, 20), datetime(2026, 12, 6, 14)]

    got = RedcatScraper._performances('DEC 4-6', 'FRI 8 PM, SAT 3 & 8 PM', date(2026, 11, 20))
    assert got == [datetime(2026, 12, 4, 20), datetime(2026, 12, 5, 15), datetime(2026, 12, 5, 20)]

    got = RedcatScraper._performances('DEC 4-6', 'FRI-SUN, 8 PM', date(2026, 11, 20))
    assert got == [datetime(2026, 12, d, 20) for d in (4, 5, 6)]


@pytest.mark.unit
@pytest.mark.parametrize('text', ['FRI 8 PM SAT 3 PM', 'FRI 8 PM, SAT', 'SAT 8 PM, 3'])
def test_ambiguous_clauses_are_skipped(text):
    assert RedcatScraper._time_slots(text) == []


@pytest.mark.unit
@pytest.mark.parametrize('text, expected', [
    ('SAT, 11-1 PM', []),
    ('SAT, 12-2 PM', [({5}, [(12, 0)])]),
    ('SAT, 11 AM-1 PM', [({5}, [(11, 0)])]),
])
def test_time_range_without_start_meridiem(text, expected):
    assert RedcatScraper._time_slots(text) == expected

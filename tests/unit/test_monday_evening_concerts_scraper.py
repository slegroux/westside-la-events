"""
Unit tests for the Monday Evening Concerts scraper.

Fully offline: fetch_page is replaced with hand-built Squarespace markup, one
home page (season list) and one page per concert. Dates are generated relative
to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.monday_evening_concerts import MondayEveningConcertsScraper

HOME = MondayEveningConcertsScraper.HOME_URL


def _long(text='The ensemble performs a landmark work. '):
    return text * 6


def _fmt(dt):
    return f"{dt.strftime('%A').upper()}, {dt.strftime('%B').upper()} {dt.day}, {dt.year}"


def _block(inner):
    return f'<div class="fe-block"><div class="sqs-block">{inner}</div></div>'


def _home_entry(href, date_text, venue, title_html, image='https://img.example/a.jpg'):
    return (
        _block(f'<p><a href="{href}">{date_text}<br><em>{venue}</em></a></p>')
        + _block(f'<a href="{href}"><img data-src="{image}"></a>')
        + _block(f'<p><a href="{href}">{title_html}</a></p>')
    )


def _home(upcoming, recent=''):
    return (
        '<html><body>'
        + _block('<h3>87th CONCERT SEASON</h3>')
        + upcoming
        + _block('<h3>RECENT EVENTS</h3>')
        + recent
        + '</body></html>'
    )


def _detail(date_lines, venue='ZIPPER HALL at the COLBURN SCHOOL',
            address='200 S GRAND AVE, LOS ANGELES, CA 90012', body=None):
    when_block = ''.join(f'<p>{ln}</p>' for ln in date_lines) + f'<p>{venue}</p><p>{address}</p>'
    return (
        '<html><body>'
        + _block('<p>SOME TITLE</p>')
        + _block(when_block)
        + _block('<p>PROGRAM</p>')
        + _block('<p>Composer - Work (1999)</p>')
        + _block('<p>PERFORMERS</p>')
        + _block('<p>Ensemble, piano</p>')
        + _block(f'<p>{body or _long()}</p>')
        + _block('<p>BIOS</p>')
        + _block(f'<p>{_long("A long biography sentence. ")}</p>')
        + '</body></html>'
    )


def _run(scraper, pages):
    requested = []

    def fetch_page(url, retry=3):
        requested.append(url)
        return pages.get(url)

    scraper.fetch_page = fetch_page
    return scraper.scrape(), requested


def _title_html(composer, work):
    return f'{composer} | “{work}”'


@pytest.mark.unit
def test_parses_concert_with_time_venue_and_image(mock_geocoding_service):
    when = datetime.now() + timedelta(days=40)
    home = _home(_home_entry(
        '/perfect-lives', _fmt(when), 'Zipper Concert Hall',
        _title_html('ROBERT ASHLEY', 'PERFECT LIVES'),
    ))
    detail = _detail([f'{_fmt(when)} | 8 PM'])
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/perfect-lives': detail,
    })
    assert len(events) == 1
    e = events[0]
    assert e.title == 'Robert Ashley: Perfect Lives'
    assert e.event_date == when.replace(hour=20, minute=0, second=0, microsecond=0)
    assert e.venue_name == 'Zipper Hall at the Colburn School'
    assert e.address == '200 S Grand Ave, Los Angeles, CA 90012'
    assert e.region == 'beyond'
    assert e.category == 'Music'
    assert e.image_url == 'https://img.example/a.jpg'
    assert e.price is None and e.price_note == ''
    assert e.description.startswith('The ensemble performs')
    assert e.url == f'{HOME}/perfect-lives#{when.strftime("%Y-%m-%d")}'


@pytest.mark.unit
def test_two_dates_make_two_events_with_unique_urls(mock_geocoding_service):
    first = datetime.now() + timedelta(days=30)
    second = first + timedelta(days=7)
    home = _home(_home_entry(
        '/canto-ostinato', 'MONDAYS, X and Y', 'Marciano Art Foundation',
        _title_html('SIMEON TEN HOLT', 'CANTO OSTINATO') + '<br>alongside<br>'
        + _title_html('TACITA DEAN', 'FILM'),
    ).replace('MONDAYS, X and Y', f'MONDAYS, {first.strftime("%B").upper()} {first.day} and {second.day}, {first.year}'))
    detail = _detail(
        [f'{_fmt(first)} | 7 PM', f'{_fmt(second)} | 7 PM'],
        venue='MARCIANO&nbsp;&nbsp;&nbsp;ART&nbsp;&nbsp;FOUNDATION',
        address='4357 WILSHIRE BLVD, LOS ANGELES CA 90010',
    )
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/canto-ostinato': detail,
    })
    assert [e.event_date.day for e in events] == [first.day, second.day]
    assert len({e.url for e in events}) == 2
    assert events[0].title == 'Simeon Ten Holt: Canto Ostinato alongside Tacita Dean: Film'
    assert events[0].venue_name == 'Marciano Art Foundation'
    assert events[0].address == '4357 Wilshire Blvd, Los Angeles, CA 90010'


@pytest.mark.unit
def test_undated_concert_is_skipped(mock_geocoding_service):
    home = _home(_home_entry(
        '/calder-piece', 'MARCH 2027 (DATES TBA)', 'Steve Tisch Theater at LACMA',
        _title_html('EARLE BROWN', 'CALDER PIECE'),
    ))
    detail = _detail(
        ['LATE FEB / EARLY MARCH 2027 (DATES TBA)'],
        venue='STEVE TISCH THEATER at LACMA',
        address='5905 WILSHIRE BLVD, LOS ANGELES, CA 90036',
    )
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/calder-piece': detail,
    })
    assert events == []


@pytest.mark.unit
def test_date_without_time_is_midnight(mock_geocoding_service):
    when = datetime.now() + timedelta(days=20)
    home = _home(_home_entry(
        '/x', _fmt(when), 'Zipper Concert Hall', _title_html('A COMPOSER', 'A WORK'),
    ))
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/x': _detail([_fmt(when)]),
    })
    assert events[0].event_date == when.replace(hour=0, minute=0, second=0, microsecond=0)


@pytest.mark.unit
def test_past_dated_concert_is_dropped(mock_geocoding_service):
    past = datetime.now() - timedelta(days=30)
    home = _home(_home_entry(
        '/old', _fmt(past), 'Zipper Concert Hall', _title_html('A COMPOSER', 'OLD WORK'),
    ))
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/old': _detail([f'{_fmt(past)} | 8 PM']),
    })
    assert events == []


@pytest.mark.unit
def test_recent_events_section_is_not_fetched(mock_geocoding_service):
    when = datetime.now() + timedelta(days=15)
    past = datetime.now() - timedelta(days=15)
    home = _home(
        _home_entry('/new', _fmt(when), 'Zipper Concert Hall', _title_html('NEW', 'PIECE')),
        recent=_home_entry('/old', _fmt(past), 'Zipper Concert Hall', _title_html('OLD', 'PIECE')),
    )
    events, requested = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/new': _detail([f'{_fmt(when)} | 8 PM']),
    })
    assert len(events) == 1
    assert f'{HOME}/old' not in requested


@pytest.mark.unit
def test_unrecognised_and_empty_pages_yield_nothing(mock_geocoding_service):
    assert _run(MondayEveningConcertsScraper(), {HOME: '<html><body><p>Hi</p></body></html>'})[0] == []
    assert _run(MondayEveningConcertsScraper(), {})[0] == []


@pytest.mark.unit
def test_title_with_inline_italic_stays_on_one_line(mock_geocoding_service):
    when = datetime.now() + timedelta(days=50)
    home = _home(_home_entry(
        '/t', _fmt(when), 'Zipper Concert Hall',
        'STEVEN TAKASUGI <br>“PIANO CONCERTO (<em>Sinfonietta Version</em>)”',
    ))
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/t': _detail([f'{_fmt(when)} | 8 PM']),
    })
    assert events[0].title == 'Steven Takasugi: Piano Concerto (Sinfonietta Version)'


@pytest.mark.unit
def test_date_without_time_today_is_not_dropped(mock_geocoding_service):
    today = datetime.now()
    home = _home(_home_entry(
        '/t', _fmt(today), 'Zipper Concert Hall', _title_html('A COMPOSER', 'TODAY WORK'),
    ))
    events, _ = _run(MondayEveningConcertsScraper(), {
        HOME: home, f'{HOME}/t': _detail([_fmt(today)]),
    })
    assert len(events) == 1
    assert events[0].event_date == today.replace(hour=0, minute=0, second=0, microsecond=0)

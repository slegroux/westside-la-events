"""
Unit tests for the Pepperdine Center for the Arts scraper.

Fully offline: fetch_page and prefetch_pages are replaced with a hand-built
events table and show pages. Dates are generated relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.pepperdine_arts import PepperdineArtsScraper

LISTING = PepperdineArtsScraper.EVENTS_URL


def _day(dt):
    return f"{dt.strftime('%A')}, {dt.strftime('%B')} {dt.day}"


def _at(days):
    return datetime.now() + timedelta(days=days)


def _row(slug, title, date_line, last_day, tags='Pepperdine Music'):
    return f'''
    <tr>
      <td><a href="/events/season/{slug}.htm"><img src="/t/{slug}.png" alt=""></a></td>
      <td><div class="heading h3"><a class="linkarrow" href="/events/season/{slug}.htm">{title}</a></div>
          <p><strong><p>{date_line}</p></strong></p></td>
      <td>{tags}</td>
      <td><div class="button"><a href="/events/season/{slug}.htm">Learn More</a></div></td>
      <td>{last_day.strftime('%Y%m%d')}</td>
      <td>{(last_day + timedelta(days=1)).strftime('%Y%m%d')}</td>
    </tr>'''


def _listing(*rows):
    return f'<html><body><table>{"".join(rows)}</table></body></html>'


def _show(title, venue='Smothers Theatre', tickets='$30.50–$58', description=None):
    description = description or (
        'A long enough description of the evening, with plenty of words to pass the length filter.'
    )
    ticket_row = (
        f'<div class="ticket-row"><div class="heading h4">Tickets</div><p><span class="large">{tickets}</span></p></div>'
        if tickets else ''
    )
    venue_row = (
        f'<div class="venue-row"><div class="heading h4">Venue</div><p><span class="large">{venue}</span></p></div>'
        if venue else ''
    )
    return f'''<html><body>
      <div class="widget w-image full"><img src="/images/{title}.jpg" alt=""/></div>
      <div class="widget twothirds left"><h1>{title}</h1>
        <p><span class="largest">some date • 7:30 PM</span></p>
        <p>{description}</p></div>
      <div class="widget third right">{ticket_row}{venue_row}</div>
    </body></html>'''


def _url(slug):
    return f'https://arts.pepperdine.edu/events/season/{slug}.htm'


def _run(pages):
    scraper = PepperdineArtsScraper()
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


@pytest.mark.unit
def test_parses_show_with_detail_page(mock_geocoding_service):
    when = _at(10)
    line = f"{_day(when)}, {when.year} • 7:30 PM"
    pages = {
        LISTING: _listing(_row('mavis', 'Mavis Staples', line, when, tags='Singer/Songwriter/Folk')),
        _url('mavis'): _show('Mavis Staples'),
    }

    (e,) = _run(pages)

    assert e.title == 'Mavis Staples'
    assert e.event_date == when.replace(hour=19, minute=30, second=0, microsecond=0)
    assert e.url == f"{_url('mavis')}#{when.date().isoformat()}"
    assert e.venue_name == 'Smothers Theatre'
    assert e.address == '24255 Pacific Coast Highway, Malibu, CA 90263'
    assert e.price == 30.5 and not e.is_free
    assert e.category == 'Music'
    assert e.image_url == 'https://arts.pepperdine.edu/images/Mavis Staples.jpg'
    assert e.description.startswith('A long enough description')
    assert e.region == 'westside'


@pytest.mark.unit
def test_ranges_lists_and_multiple_showtimes_expand_per_day(mock_geocoding_service):
    """Each stated day is its own event, starting at that day's first showtime."""
    a, b, c = _at(10), _at(11), _at(14)
    line = (
        f"{_day(a)}–{_day(b)}, {a.year} • 7:30 PM | "
        f"{_day(c)}, {c.year} • 2 PM and 7:30 PM"
    )
    pages = {
        LISTING: _listing(_row('play', 'The Play', line, c, tags='Student Productions, Pepperdine Theatre')),
        _url('play'): _show('The Play', venue='Lindhurst Theatre', tickets='$18'),
    }

    events = _run(pages)

    assert [e.event_date.date() for e in events] == [a.date(), b.date(), c.date()]
    assert [e.event_date.hour for e in events] == [19, 19, 14]
    assert len({e.url for e in events}) == 3
    assert 'Showtimes: 2:00 PM, 7:30 PM.' in events[2].description
    assert 'Showtimes' not in events[0].description
    assert events[0].price == 18.0 and events[0].category == 'Theater'

    # "A and B" lists two days, not the span between them.
    d1, d2 = _at(20), _at(23)
    line = f"{_day(d1)} and {_day(d2)}, {d1.year} • 8 PM"
    pages = {LISTING: _listing(_row('two', 'Two Nights', line, d2)), _url('two'): _show('Two Nights')}
    assert [e.event_date.date() for e in _run(pages)] == [d1.date(), d2.date()]


@pytest.mark.unit
def test_past_shows_are_not_fetched_or_returned(mock_geocoding_service):
    past, future = _at(-5), _at(6)
    pages = {
        LISTING: _listing(
            _row('old', 'Old Show', f"{_day(past)}, {past.year} • 7:30 PM", past),
            _row('new', 'New Show', f"{_day(future)}, {future.year} • 7:30 PM", future),
        ),
        _url('new'): _show('New Show'),
    }
    fetched = []
    scraper = PepperdineArtsScraper()
    scraper.fetch_page = lambda url, retry=3: fetched.append(url) or pages.get(url)
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None

    events = scraper.scrape()

    assert [e.title for e in events] == ['New Show']
    assert _url('old') not in fetched


@pytest.mark.unit
def test_a_run_already_under_way_keeps_only_remaining_days(mock_geocoding_service):
    start, end = _at(-2), _at(2)
    line = f"{_day(start)}–{_day(end)}, {end.year} • 7 PM"
    pages = {LISTING: _listing(_row('run', 'Long Run', line, end)), _url('run'): _show('Long Run')}

    events = _run(pages)

    assert [e.event_date.date() for e in events] == [_at(0).date(), _at(1).date(), end.date()]


@pytest.mark.unit
def test_off_campus_shows_are_skipped(mock_geocoding_service):
    when = _at(9)
    line = f"{_day(when)}, {when.year} • 7:30 PM"
    pages = {
        LISTING: _listing(_row('away', 'Away Game', line, when), _row('home', 'Home Game', line, when)),
        _url('away'): _show('Away Game', venue='Walt Disney Concert Hall'),
        _url('home'): _show('Home Game', venue='Raitt Recital Hall'),
    }

    assert [e.title for e in _run(pages)] == ['Home Game']


@pytest.mark.unit
def test_free_and_unknown_pricing(mock_geocoding_service):
    when = _at(9)
    line = f"{_day(when)}, {when.year} • 7:30 PM"
    pages = {
        LISTING: _listing(_row('free', 'Free Recital', line, when), _row('none', 'No Price', line, when)),
        _url('free'): _show('Free Recital',
                            tickets='Show is free and open to the public, advance registration is not required.'),
        _url('none'): _show('No Price', tickets=None),
    }

    free, unknown = _run(pages)

    assert free.is_free and free.price is None
    assert not unknown.is_free and unknown.price is None and unknown.price_note == ''


@pytest.mark.unit
def test_dateless_rows_and_unrecognised_pages_yield_nothing(mock_geocoding_service):
    when = _at(9)
    pages = {
        LISTING: _listing(_row('x', 'No Time Given', f"{_day(when)}, {when.year}", when)),
        _url('x'): _show('No Time Given'),
    }
    assert _run(pages) == []
    assert _run({}) == []
    assert _run({LISTING: '<html><body>Nothing here</body></html>'}) == []

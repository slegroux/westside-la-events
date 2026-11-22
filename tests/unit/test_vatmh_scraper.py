"""
Unit tests for the Villa Aurora & Thomas Mann House scraper.

Fully offline: fetch_page and prefetch_pages are replaced with hand-built copies
of the Contao program list (div.kalenderliste > div.event). Dates are generated
relative to today. Like the real page, the <time datetime> attribute carries a
wrong Berlin offset that the scraper must ignore.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.vatmh import VATMHScraper

VILLA = 'Villa Aurora (520 Paseo Miramar, Pacific Palisades, CA 90272)'


def _day(dt):
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def _card(slug, title, location, when=None, time_text=None, range_text=None, body='A talk.'):
    """One list entry. time_text e.g. '7:30 pm' or '3:00 pm–7:00 pm'."""
    time_html = (
        f'<div class="time"><strong>Time:</strong> '
        f'<time datetime="{time_text}"> {time_text}</time></div>' if time_text else ''
    )
    range_html = f'<div class="date-vonbis">{range_text}</div>' if range_text else ''
    date_html = (
        f'<span class="day">Tu, </span><span class="date firstdate">{_day(when)}</span>'
        if when else ''
    )
    return f"""
<div class="event  layout_teaser upcoming featured cal_8">
<div class="event-image"><figure><a href="/en/eventreader/{slug}.html"><picture>
<img src="/assets/images/x/{slug}.png" width="200" height="140" alt=""></picture></a></figure></div>
<div class="event-info"><div class="datum-uhrzeit">{date_html}{time_html}{range_html}</div>
<div class="location"><strong>Location:</strong> {location}</div>
<div class="online">ONLINE</div></div>
<div class="event-text ce_text block">
<h3><a href="/en/eventreader/{slug}.html" title="{title}">{title}</a></h3>
<h4>{body}</h4></div>
</div>"""


def _page(*cards):
    return ('<html><body><div class="mod_eventlist block"><div class="kalenderliste">'
            + ''.join(cards) + '</div></div></body></html>')


def _future(days=10):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _run(listing, details=None):
    """Serve the listing page; details maps event URL -> page text."""
    details = details or {}
    scraper = VATMHScraper()
    scraper.fetch_page = lambda url, retry=3: (
        listing if url == VATMHScraper.EVENTS_URL else details.get(url, '<html></html>')
    )
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


@pytest.mark.unit
def test_parses_house_event_with_time_range(mock_geocoding_service):
    """Visible local date and time are used, not the Berlin-offset attribute."""
    day = _future()
    events = _run(_page(_card('meet', 'Meet The Artists', VILLA, day, '3:00 pm–7:00 pm',
                              body='Open House and Reception.')))

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Meet The Artists'
    assert e.event_date == day.replace(hour=15)
    assert e.end_date == day.replace(hour=19)
    assert e.venue_name == 'Villa Aurora'
    assert e.address == '520 Paseo Miramar, Pacific Palisades, CA 90272'
    assert e.url == 'https://www.vatmh.org/en/eventreader/meet.html'
    assert e.image_url == 'https://www.vatmh.org/assets/images/x/meet.png'
    assert e.description == 'Open House and Reception.'
    assert e.price is None and not e.is_free and e.price_note == ''
    assert e.region == 'westside'


@pytest.mark.unit
def test_single_time_and_date_only_events(mock_geocoding_service):
    """One time -> no end; no time at all -> a midnight (date-only) event."""
    day = _future()
    events = _run(_page(
        _card('chat', 'Fireside Chat', VILLA, day, '7:30 pm'),
        _card('house', 'Open House', 'Thomas Mann House', day + timedelta(days=1)),
    ))

    chat, house = events
    assert chat.event_date == day.replace(hour=19, minute=30) and chat.end_date is None
    assert house.event_date == day + timedelta(days=1) and house.end_date is None
    assert house.venue_name == 'Thomas Mann House'
    assert house.address == '1550 San Remo Dr, Pacific Palisades, CA 90272'


@pytest.mark.unit
def test_events_outside_la_are_dropped(mock_geocoding_service):
    """Germany (or anywhere without an LA/CA location) is dropped; CA partners stay."""
    day = _future()
    events = _run(_page(
        _card('cottbus', 'Art in the City - Cottbus', 'Cottbus', day),
        _card('tiger', 'Exhibition Murmuration', 'Tiger Strikes Asteroid', day),
        _card('laemmle', 'Screening', 'Laemmle Monica Film Center (1332 2nd St, Santa Monica, CA 90401)',
              day, '2:00 pm–4:00 pm'),
    ))

    assert [e.title for e in events] == ['Screening']
    assert events[0].venue_name == 'Laemmle Monica Film Center'
    assert events[0].address == '1332 2nd St, Santa Monica, CA 90401'


@pytest.mark.unit
def test_multi_day_run_keeps_start_and_ends_on_last_day(mock_geocoding_service):
    """An exhibition runs start -> last day; one that already ended is dropped."""
    start, end = _future(-3), _future(4)
    ended = _future(-20), _future(-10)
    events = _run(_page(
        _card('show', 'Exhibition', VILLA, start, range_text=f'{_day(start)}–{_day(end)}'),
        _card('old', 'Old Exhibition', VILLA, ended[0],
              range_text=f'{_day(ended[0])},–{_day(ended[1])},'),
    ))

    assert [e.title for e in events] == ['Exhibition']
    assert events[0].event_date == start
    assert events[0].end_date == end.replace(hour=23, minute=59)


@pytest.mark.unit
def test_skips_past_undated_and_invitation_only(mock_geocoding_service):
    day = _future()
    invite = _card('invite', 'Roundtable', VILLA, day)
    events = _run(
        _page(
            _card('past', 'Old Talk', VILLA, _future(-5), '7:00 pm'),
            _card('nodate', 'No Date', VILLA),
            invite,
            _card('open', 'Public Talk', VILLA, day, '6:00 pm'),
        ),
        details={'https://www.vatmh.org/en/eventreader/invite.html':
                 '<p>Language: English・By Invitation Only</p>'},
    )

    assert [e.title for e in events] == ['Public Talk']


@pytest.mark.unit
def test_category_ignores_description_and_defaults_to_education(mock_geocoding_service):
    day = _future()
    events = _run(_page(
        _card('talk', 'Fireside Chat', VILLA, day, '7:00 pm',
              body='The Family Oppenheim, a film about exile.'),
        _card('film', 'Screening and Q&A', VILLA, day + timedelta(days=1), '7:00 pm'),
    ))

    assert [e.category for e in events] == ['Education', 'Film']


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert _run('<html><body>Just a moment...</body></html>') == []
    scraper = VATMHScraper()
    scraper.fetch_page = lambda url, retry=3: None
    assert scraper.scrape() == []


@pytest.mark.unit
def test_date_only_event_today_is_not_dropped(mock_geocoding_service):
    """No time is stored as midnight; it must stay listed for its own day."""
    today = _future(0)
    events = _run(_page(
        _card('open-today', 'Open House', 'Thomas Mann House', today),
        _card('yesterday', 'Old Open House', 'Thomas Mann House', _future(-1)),
    ))

    assert [e.title for e in events] == ['Open House']
    assert events[0].event_date == today

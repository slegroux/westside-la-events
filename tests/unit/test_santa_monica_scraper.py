"""
Unit tests for the City of Santa Monica events scraper (santamonica.gov/events).

Fully offline: fetch_page is replaced with hand-built copies of the events grid
(single-quoted card hrefs, as on the real site) and of program detail pages.
Dates are generated relative to today.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.santa_monica import SantaMonicaScraper

BASE = 'https://www.santamonica.gov'
LISTING = f'{BASE}/events'
CHALLENGE = '<html><title>Pardon Our Interruption</title></html>'


def _stamp(dt):
    return dt.strftime('%Y%m%d%H%M')


def _card(event_id, title, start, lines, image='https://cdn.example/pic.jpg'):
    """One grid card; lines are the text rows of div.description."""
    rows = ''.join(f'<div>{line}</div>' for line in lines)
    return f"""
<div class="col-md-4"><a href='/events/{event_id}/{_stamp(start)}' class="card card--hover">
<div class="card__container"><div class="image-wrapper"><div>
<img src="{image}" role="presentation"></div></div>
<div class="card-body"><div class="card-title d-flex eventTitle">
   {title}
</div><div class="description">{rows}</div></div></div></a></div>"""


def _page(*cards):
    return ('<html><body><div id="grid-view"><div class="row">' + ''.join(cards)
            + '</div></div></body></html>')


def _when(days=3, hour=10, minute=30):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def _day(dt):
    return f"{dt.strftime('%A')}, {dt.strftime('%b')} {dt.day}, {dt.year}"


def _ld(obj):
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


def _detail(name, street, lat, lng, description='<p>Stories for toddlers.</p>'):
    org = {'@type': 'Organization', 'name': 'City of Santa Monica'}
    event = {
        '@type': 'Event', 'name': 'x', 'description': description,
        'location': {
            '@type': 'Library', 'name': name,
            'address': {'@type': 'PostalAddress', 'streetAddress': street,
                        'addressLocality': 'Santa Monica', 'postalCode': '90405',
                        'addressRegion': 'CA'},
            'geo': {'@type': 'GeoCoordinates', 'Latitude': lat, 'Longitude': lng},
        },
    }
    return f'<html><head>{_ld(org)}{_ld(event)}</head></html>'


def _detail_fetches(scraper):
    return [u for u in scraper.fetched if '/events/' in u]


def _scraper(pages, details=None, **limits):
    """Serve grid pages by URL; details maps program URL -> page (default none)."""
    scraper = SantaMonicaScraper()
    scraper.fetched = []
    for name, value in limits.items():
        setattr(scraper, name, value)

    def fetch_page(url, retry=3):
        scraper.fetched.append(url)
        if url in pages:
            return pages[url]
        return (details or {}).get(url)

    scraper.fetch_page = fetch_page
    return scraper


@pytest.mark.unit
def test_parses_card_start_from_link_and_end_from_text(mock_geocoding_service):
    """Start comes from the link stamp, end from the card's time range."""
    start = _when()
    page = _page(_card('abc', 'Baby Time', start,
                       [_day(start), '10:30 AM - 11:00 AM']))

    events = _scraper({LISTING: page}, MAX_DETAILS=0).scrape()

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Baby Time'
    assert e.event_date == start
    assert e.end_date == start.replace(hour=11, minute=0)
    assert e.url == f'{BASE}/events/abc/{_stamp(start)}'
    assert e.image_url == 'https://cdn.example/pic.jpg'
    assert e.source == 'Santa Monica'
    # The grid carries no venue: a generic location, in the Westside box.
    assert e.venue_name == 'City of Santa Monica'
    assert e.address == 'Santa Monica, CA'
    assert e.price is None and not e.is_free and e.price_note == ''
    assert e.region == 'westside'


@pytest.mark.unit
def test_multi_day_run_and_open_ended_events(mock_geocoding_service):
    """'to <date> <time>' sets the run's end; 'until concluded' states none."""
    started = _when(days=-2, hour=11, minute=0)
    ends = _when(days=20, hour=21, minute=0)
    soon = _when(days=2, hour=19, minute=0)
    page = _page(
        _card('run', 'Swiss Winter Village', started,
              [f"{started.strftime('%a')}, {started.strftime('%b')} {started.day}, {started.year} 11:00 AM",
               f"to {ends.strftime('%a')}, {ends.strftime('%b')} {ends.day}, {ends.year} 9:00 PM"]),
        _card('open', 'Neighborhood Walk', soon, [_day(soon), '7:00 PM until concluded']),
    )

    run, walk = _scraper({LISTING: page}, MAX_DETAILS=0).scrape()

    assert run.event_date == started and run.end_date == ends
    assert walk.event_date == soon and walk.end_date is None


@pytest.mark.unit
def test_skips_cancelled_meetings_past_and_duplicates(mock_geocoding_service):
    """Cancelled programs, government meetings, past events and repeats drop."""
    when = _when()
    page = _page(
        _card('keep', 'Storytime', when, [_day(when), '10:30 AM - 11:00 AM']),
        _card('keep', 'Storytime', when, [_day(when), '10:30 AM - 11:00 AM']),
        _card('canc', 'Citizenship Class', _when(4), [_day(_when(4)), 'Event Cancelled']),
        _card('mtg1', 'Planning Commission', _when(5), [_day(_when(5)), '6:00 PM until concluded']),
        _card('mtg2', 'City Council Meeting', _when(6), [_day(_when(6)), '5:30 PM until concluded']),
        _card('old', 'Old Class', _when(-3), [_day(_when(-3)), '10:30 AM - 11:00 AM']),
    )

    events = _scraper({LISTING: page}, MAX_DETAILS=0).scrape()

    assert [e.title for e in events] == ['Storytime']


@pytest.mark.unit
def test_pages_through_grid_and_stops_at_empty_page(mock_geocoding_service):
    """Page N is ?pagenum=N; paging ends at the first page with no cards."""
    a, b = _when(2), _when(3)
    scraper = _scraper({
        LISTING: _page(_card('a', 'First', a, [_day(a)])),
        f'{LISTING}?pagenum=2': _page(_card('b', 'Second', b, [_day(b)])),
        f'{LISTING}?pagenum=3': '<html><body></body></html>',
    }, MAX_DETAILS=0)

    events = scraper.scrape()

    assert [e.title for e in events] == ['First', 'Second']
    assert scraper.fetched == [LISTING, f'{LISTING}?pagenum=2', f'{LISTING}?pagenum=3']


@pytest.mark.unit
def test_page_cap_and_time_budget(mock_geocoding_service):
    when = _when()
    pages = {LISTING: _page(_card('a', 'First', when, [_day(when)])),
             f'{LISTING}?pagenum=2': _page(_card('b', 'Second', when, [_day(when)]))}

    capped = _scraper(pages, MAX_DETAILS=0, MAX_PAGES=1)
    assert len(capped.scrape()) == 1 and capped.fetched == [LISTING]

    out_of_time = _scraper(pages, MAX_DETAILS=0, PAGE_BUDGET_SECONDS=-1)
    assert out_of_time.scrape() == [] and out_of_time.fetched == []


@pytest.mark.unit
def test_challenge_page_ends_paging_but_keeps_earlier_events(mock_geocoding_service):
    """The site's interstitial is never worked around: stop and keep what we have."""
    when = _when()
    scraper = _scraper({
        LISTING: _page(_card('a', 'First', when, [_day(when)])),
        f'{LISTING}?pagenum=2': CHALLENGE,
        f'{LISTING}?pagenum=3': _page(_card('c', 'Never read', when, [_day(when)])),
    }, MAX_DETAILS=0)

    events = scraper.scrape()

    assert [e.title for e in events] == ['First']
    assert f'{LISTING}?pagenum=3' not in scraper.fetched
    assert _scraper({LISTING: CHALLENGE}).scrape() == []


@pytest.mark.unit
def test_detail_page_supplies_venue_once_per_program(mock_geocoding_service):
    """A recurring program is fetched once and every occurrence gets its venue."""
    first, second = _when(2), _when(9)
    page = _page(
        _card('toddler', 'Toddler Tuesdays', first, [_day(first), '10:30 AM - 11:00 AM']),
        _card('toddler', 'Toddler Tuesdays', second, [_day(second), '10:30 AM - 11:00 AM']),
        _card('solo', 'Pop-up Market', _when(3), [_day(_when(3))]),
    )
    detail = _detail('Fairview Branch Library', '2101 Ocean Park Blvd', 34.01472, -118.46356)
    scraper = _scraper({LISTING: page},
                       details={f'{BASE}/events/toddler/{_stamp(first)}': detail})

    events = scraper.scrape()

    toddler = [e for e in events if e.title == 'Toddler Tuesdays']
    assert len(toddler) == 2
    for e in toddler:
        assert e.venue_name == 'Fairview Branch Library'
        assert e.address == '2101 Ocean Park Blvd, Santa Monica, CA 90405'
        assert (e.latitude, e.longitude) == (34.01472, -118.46356)
        assert e.description == 'Stories for toddlers.'
    # A program whose page has no Event JSON-LD keeps the generic location.
    market = next(e for e in events if e.title == 'Pop-up Market')
    assert market.venue_name == 'City of Santa Monica'
    assert len(_detail_fetches(scraper)) == 2  # one per distinct program, not per occurrence


@pytest.mark.unit
def test_detail_fetching_is_capped_and_stops_at_challenge(mock_geocoding_service):
    when = _when()
    page = _page(*[_card(f'p{i}', f'Program {i}', when + timedelta(hours=i), [_day(when)])
                   for i in range(4)])

    capped = _scraper({LISTING: page}, MAX_DETAILS=2)
    assert len(capped.scrape()) == 4
    assert len(_detail_fetches(capped)) == 2

    blocked = _scraper({LISTING: page},
                       details={f'{BASE}/events/p0/{_stamp(when)}': CHALLENGE})
    assert len(blocked.scrape()) == 4  # still listed, with the generic venue
    assert len(_detail_fetches(blocked)) == 1  # then it stopped


@pytest.mark.unit
def test_empty_or_failed_fetch_yields_nothing(mock_geocoding_service):
    assert _scraper({}).scrape() == []
    assert _scraper({LISTING: '<html><body>Nothing here</body></html>'}).scrape() == []

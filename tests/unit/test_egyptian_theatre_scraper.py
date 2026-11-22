"""
Unit tests for the American Cinematheque scrapers (Aero, Egyptian, Los Feliz 3).

They share one parser parameterised by the WordPress `event_location` term,
so the Egyptian Theatre carries the parser tests and the Aero checks that
refactoring it left its behaviour alone. Fully offline: the reachability check
(fetch_page) and the REST call (session.get) are stubbed with trimmed payloads.
Dates are relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.aero_theater import (
    AeroTheaterScraper,
    EgyptianTheatreScraper,
    LosFeliz3Scraper,
)


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _item(title, when, pricing='$12.00 (member) ; $17.00 (general admission)', **extra):
    return {
        'title': {'rendered': title},
        'link': f"https://www.americancinematheque.com/now-showing/{title.lower().replace(' ', '-')}-{when:%m-%d-%Y}/",
        'content': {'rendered': '<p>A <b>great</b> film.</p>'},
        'acf': {'event_hero': {
            'dates': when.strftime('%a %b %d, %Y').upper(),
            'times': when.strftime('%I:%M %p').lstrip('0'),
            'pricing': pricing,
            'image_url': 'https://img.example/poster.jpg',
        }},
        **extra,
    }


def _run(scraper, pages):
    """Serve `pages` (list of payloads) from session.get; return events + the calls."""
    calls = []

    def get(url, params=None, timeout=None):
        calls.append(params)
        page = params['page']
        return _Resp(pages[page - 1] if page <= len(pages) else [])

    scraper.fetch_page = lambda url, retry=3: '<html></html>'
    scraper.session.get = get
    return scraper.scrape(), calls


def _future(days=5, hour=19):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=30, second=0, microsecond=0
    )


@pytest.mark.unit
def test_egyptian_parses_api_item(mock_geocoding_service):
    when = _future()
    events, calls = _run(EgyptianTheatreScraper(), [[_item('FAT CITY', when)]])

    assert calls[0] == {'per_page': 50, 'page': 1, 'event_location': 55,
                        '_fields': 'title,link,content,acf'}  # no slow _embed
    assert len(events) == 1
    e = events[0]
    assert e.source == 'Egyptian Theatre'
    assert e.title == 'FAT CITY'
    assert e.event_date == when
    assert e.price == 12.0 and not e.is_free and e.price_note == ''
    assert e.category == 'Film'
    assert e.description == 'A great film.'
    assert e.image_url == 'https://img.example/poster.jpg'
    assert e.venue_name == 'Egyptian Theatre'
    assert e.address == '6712 Hollywood Blvd, Los Angeles, CA 90028'
    # Constants are used as-is, so no geocoding.
    assert (e.latitude, e.longitude) == (34.1016, -118.3409)
    # Hollywood is outside the Westside box: shown in the beyond tab.
    assert e.region == 'beyond'


@pytest.mark.unit
def test_unknown_price_leaves_note_empty_and_free_is_free(mock_geocoding_service):
    when = _future()
    events, _ = _run(EgyptianTheatreScraper(), [[
        _item('NO PRICE', when, pricing=''),
        _item('FREE ONE', when + timedelta(days=1), pricing='Free (members-only)'),
    ]])

    no_price, free = events
    assert no_price.price is None and not no_price.is_free and no_price.price_note == ''
    assert free.is_free and free.price == 0.0


@pytest.mark.unit
def test_past_and_undated_items_are_dropped(mock_geocoding_service):
    when = _future()
    undated = _item('NO DATE', when)
    undated['acf'] = {'event_hero': {}}
    events, _ = _run(EgyptianTheatreScraper(), [[
        _item('OLD ONE', datetime.now() - timedelta(days=9)),
        undated,
        _item('TEST EVENT', when),  # CMS placeholder
        _item('KEEPER', when),
    ]])

    assert [e.title for e in events] == ['KEEPER']


@pytest.mark.unit
def test_empty_and_failing_api_yield_nothing(mock_geocoding_service):
    assert _run(EgyptianTheatreScraper(), [[]])[0] == []

    s = EgyptianTheatreScraper()
    s.fetch_page = lambda url, retry=3: '<html></html>'
    s.session.get = lambda url, params=None, timeout=None: _Resp(None, status=500)
    assert s.scrape() == []

    s = EgyptianTheatreScraper()
    s.fetch_page = lambda url, retry=3: None  # site unreachable
    assert s.scrape() == []


@pytest.mark.unit
def test_pages_until_short_page_and_respects_cap(mock_geocoding_service):
    full = [_item(f'FILM {i}', _future(days=2 + i)) for i in range(50)]
    events, calls = _run(EgyptianTheatreScraper(), [full, full, full, full])
    assert [c['page'] for c in calls] == [1, 2, 3]  # MAX_PAGES = 3
    assert all(c['per_page'] == 50 for c in calls)

    events, calls = _run(EgyptianTheatreScraper(), [full, [_item('LAST', _future())]])
    assert [c['page'] for c in calls] == [1, 2]  # short second page ends paging
    assert len(events) == 51


@pytest.mark.unit
def test_time_budget_stops_paging(mock_geocoding_service):
    s = EgyptianTheatreScraper()
    s.SCRAPE_BUDGET_SECONDS = 0
    events, calls = _run(s, [[_item('X', _future())]])
    assert calls == [] and events == []


@pytest.mark.unit
def test_los_feliz_uses_its_own_location_and_venue(mock_geocoding_service):
    when = _future()
    events, calls = _run(LosFeliz3Scraper(), [[_item('COLD WAR', when)]])

    assert calls[0]['event_location'] == 102
    e = events[0]
    assert e.source == 'Los Feliz 3'
    assert e.venue_name == 'Los Feliz 3 Cinema'
    assert e.address == '1822 N Vermont Ave, Los Angeles, CA 90027'
    assert e.region == 'beyond' and e.price_note == ''


@pytest.mark.unit
def test_aero_behaviour_is_unchanged(mock_geocoding_service):
    """The Aero keeps location 54, its geocoded venue, default region and "TBD"."""
    when = _future()
    events, calls = _run(AeroTheaterScraper(), [[_item('WILDWOOD', when, pricing='')]])

    assert calls[0] == {'per_page': 50, 'page': 1, 'event_location': 54, '_embed': 1}
    assert AeroTheaterScraper().source_name == 'Aero Theater'
    e = events[0]
    assert e.venue_name == 'Aero Theatre'
    assert e.address == '1328 Montana Ave, Santa Monica, CA 90403'
    assert e.region == 'westside'
    assert e.price_note == 'TBD'
    # Geocoded from the address (mocked as Santa Monica), not from constants.
    assert (e.latitude, e.longitude) == (34.0194, -118.4912)

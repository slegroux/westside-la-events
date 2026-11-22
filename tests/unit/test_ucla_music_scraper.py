"""
Unit tests for the UCLA School of Music scraper (shared Tribe parser).

Fully offline: fetch_json is replaced with hand-built Tribe API pages shaped
like the live payload. Dates are generated relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.ucla_music import UCLAMusicScraper
from src.utils.geo_filter import is_in_coverage_area


def _stamp(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def _day(offset, hour=20):
    return (datetime.now() + timedelta(days=offset)).replace(
        hour=hour, minute=0, second=0, microsecond=0)


def _event(eid, title, start, room='Schoenberg Hall', categories=('Classical',),
           event_type='Public Event', **extra):
    fields = {'_ecp_custom_6': {'label': 'Additional Event Info', 'value': 'Live Stream'}}
    if event_type:
        fields['_ecp_custom_5'] = {'label': 'Event Type', 'value': event_type}
    return {
        'id': eid,
        'title': title,
        'description': '<p>A concert.</p>',
        'excerpt': '',
        'start_date': _stamp(start),
        'end_date': _stamp(start + timedelta(hours=2)),
        'url': f'https://schoolofmusic.ucla.edu/event/{eid}/',
        'cost': 'Free',
        'all_day': False,
        'image': f'https://schoolofmusic.ucla.edu/img/{eid}.jpg',
        'categories': [{'name': c} for c in categories],
        # Live payloads carry only the room name, no address or coordinates.
        'venue': {'venue': room, 'province': 'CA'},
        'custom_fields': fields,
        **extra,
    }


def _scraper(monkeypatch, pages):
    """Serve each list in `pages` as one API page."""
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    s = UCLAMusicScraper()
    served = iter(pages)

    def fetch_json(*a, **k):
        events = next(served, [])
        return {'total_pages': len(pages), 'events': events}

    s.fetch_json = fetch_json
    return s


@pytest.mark.unit
def test_parses_free_public_concert(monkeypatch, mock_geocoding_service):
    when = _day(5)
    s = _scraper(monkeypatch, [[_event(
        'symphony', 'UCLA Symphony: Dvo&#345;&#225;k &#038; Bernstein', when)]])

    [e] = s.scrape()

    assert e.title == 'UCLA Symphony: Dvořák & Bernstein'
    assert e.event_date == when and e.end_date == when + timedelta(hours=2)
    assert e.venue_name == 'Schoenberg Hall'
    assert e.address == '445 Charles E Young Dr E, Los Angeles, CA 90095'
    assert (e.latitude, e.longitude) == (34.0707483, -118.4401261)
    assert e.region == 'westside'
    assert e.category == 'Music'
    assert e.is_free and e.price is None and e.price_note == 'Free'
    assert e.description == 'A concert.'
    assert e.url == 'https://schoolofmusic.ucla.edu/event/symphony/'
    assert e.image_url == 'https://schoolofmusic.ucla.edu/img/symphony.jpg'


@pytest.mark.unit
def test_drops_masterclasses_non_public_and_past(monkeypatch, mock_geocoding_service):
    s = _scraper(monkeypatch, [[
        _event('past', 'Old Concert', _day(-3)),
        _event('class', 'Flute Studio Guest Artist', _day(3), categories=('Classical', 'Masterclass')),
        _event('titled', 'Jessica Petrasek, Flute &#8211; Masterclass', _day(4), categories=()),
        _event('closed', 'Studio Jury', _day(5), event_type='Faculty Only'),
        _event('open', 'Faculty Recital', _day(6)),
        # The Event Type field is optional: a concert without it is still public.
        _event('untyped', 'Fall Jazzfest, Concert 1', _day(7), event_type='', categories=('Jazz',)),
    ]])

    assert [e.title for e in s.scrape()] == ['Faculty Recital', 'Fall Jazzfest, Concert 1']


@pytest.mark.unit
def test_bare_rooms_use_school_coordinates_and_st_pauls_is_pinned(monkeypatch, mock_geocoding_service):
    s = _scraper(monkeypatch, [[
        _event('lani', 'Woodwind Chamber Concert', _day(3), room='Lani Hall'),
        _event('choral', 'UCLA Choral Studies Fall Concert', _day(4),
               room='St. Paul the Apostle Catholic Church'),
    ]])

    lani, choral = s.scrape()

    assert lani.venue_name == 'Lani Hall'
    assert (lani.latitude, lani.longitude) == (34.0707483, -118.4401261)
    assert choral.venue_name == 'St. Paul the Apostle Catholic Church'
    assert choral.address == '10750 Ohio Ave, Los Angeles, CA 90024'
    assert (choral.latitude, choral.longitude) == (34.0559659, -118.43745)


@pytest.mark.unit
def test_venue_record_with_its_own_coordinates_wins_over_default(monkeypatch, mock_geocoding_service):
    # Several rooms at once arrive as a list of full venue records.
    rooms = [{'venue': 'Recording Studio', 'address': '445 Charles E Young Dr E',
              'city': 'Los Angeles', 'state': 'CA', 'geo_lat': 34.0747581, 'geo_lng': -118.4382436},
             {'venue': 'Lani Hall', 'address': '445 Charles E Young Dr E',
              'city': 'Los Angeles', 'state': 'CA', 'geo_lat': 34.0707483, 'geo_lng': -118.4401261}]
    s = _scraper(monkeypatch, [[_event('conf', 'Gender Amplified', _day(4), room=None, venue=rooms)]])

    [e] = s.scrape()

    assert e.venue_name == 'Recording Studio'
    assert (e.latitude, e.longitude) == (34.0747581, -118.4382436)
    assert e.address == '445 Charles E Young Dr E, Los Angeles, CA'


@pytest.mark.unit
def test_empty_custom_fields_list_and_missing_venue_do_not_crash(monkeypatch, mock_geocoding_service):
    # Tribe serialises "no custom fields" as [] and "no venue" as [].
    s = _scraper(monkeypatch, [[_event('bare', 'Riddims of Knowing', _day(4), custom_fields=[], venue=[])]])

    [e] = s.scrape()

    assert e.venue_name == 'Schoenberg Hall'
    assert (e.latitude, e.longitude) == (34.0707483, -118.4401261)


@pytest.mark.unit
def test_lectures_are_education_and_multiday_end_is_kept(monkeypatch, mock_geocoding_service):
    start = _day(4, 16)
    s = _scraper(monkeypatch, [[
        _event('talk', 'Jon Platt on the Future of the Music Business', _day(3),
               categories=('Lectures and Symposia',)),
        _event('wind', 'Wind Ensemble Residency', start, end_date=_stamp(start + timedelta(days=1, hours=2))),
    ]])

    talk, wind = s.scrape()

    assert talk.category == 'Education'
    assert wind.end_date == start + timedelta(days=1, hours=2)


@pytest.mark.unit
def test_follows_paging_and_stops_when_exhausted(monkeypatch, mock_geocoding_service):
    s = _scraper(monkeypatch, [
        [_event('one', 'Concert One', _day(3))],
        [_event('two', 'Concert Two', _day(4))],
    ])

    assert [e.title for e in s.scrape()] == ['Concert One', 'Concert Two']


@pytest.mark.unit
def test_empty_page_returns_nothing(monkeypatch, mock_geocoding_service):
    assert _scraper(monkeypatch, [[]]).scrape() == []
    s = _scraper(monkeypatch, [[]])
    s.fetch_json = lambda *a, **k: None
    assert s.scrape() == []


@pytest.mark.unit
def test_pinned_coordinates_are_in_the_coverage_area():
    assert is_in_coverage_area(UCLAMusicScraper.VENUE_LAT, UCLAMusicScraper.VENUE_LNG)
    for _needle, _addr, lat, lng in UCLAMusicScraper.VENUE_OVERRIDES:
        assert is_in_coverage_area(lat, lng)

"""
Unit tests for the Tockify-backed scrapers (Philosophical Research Society and
The World Stage).

Fully offline: fetch_json is replaced with hand-built copies of Tockify's
ngevent response. Times are generated from LA-local datetimes via zoneinfo, so
nothing depends on PST/PDT.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.tockify import (
    PhilosophicalResearchSocietyScraper,
    WorldStageScraper,
)

LA = ZoneInfo('America/Los_Angeles')


def _future(days=10, hour=19):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def _when(local):
    """Tockify's {millis, tzid} pair for a naive LA-local datetime."""
    aware = local.replace(tzinfo=LA)
    return {'millis': int(aware.timestamp() * 1000), 'tzid': 'America/Los_Angeles'}


def _item(title, local, uid='1', kind='singleton', desc='', status='scheduled',
          all_day=False, **content):
    return {
        'eid': {'uid': uid, 'seq': 0, 'tid': _when(local)['millis'], 'rid': 0},
        'when': {
            'start': _when(local),
            'end': _when(local + timedelta(hours=2)),
            'allDay': all_day,
        },
        'content': {
            'summary': {'text': title},
            'description': {'text': desc},
            **content,
        },
        'status': {'name': status},
        'kind': kind,
    }


def _run(scraper, items, has_next=False):
    calls = []

    def fetch_json(url, json_body=None, headers=None, method='POST', retry=2):
        calls.append((url, method))
        return {'events': items, 'metaData': {'hasNext': has_next}}

    scraper.fetch_json = fetch_json
    events = scraper.scrape()
    return events, calls


def _loc(lat=34.1131212, lng=-118.2776505):
    return {'latitude': lat, 'longitude': lng}


@pytest.mark.unit
def test_request_is_bounded_to_a_window():
    """The API call carries startms/endms, spanning the configured window."""
    scraper = PhilosophicalResearchSocietyScraper()
    _, calls = _run(scraper, [])
    url, method = calls[0]
    assert method == 'GET'
    assert 'calname=eventbrite' in url
    params = dict(p.split('=') for p in url.split('?')[1].split('&'))
    span_days = (int(params['endms']) - int(params['startms'])) / 86400000
    assert span_days == scraper.WINDOW_DAYS
    assert 60 <= scraper.WINDOW_DAYS <= 90


@pytest.mark.unit
def test_prs_parses_event_with_local_time_and_region():
    when = _future(hour=19)
    item = _item(
        'Erik Davis Talk', when, uid='42',
        desc='A talk on psychedelic Christianity.',
        place='PRS Auditorium',
        address='3910 Los Feliz Blvd, Los Angeles, CA 90027, USA',
        location=_loc(),
        customButtonLink='https://www.eventbrite.com/e/x-tickets-1?aff=a',
    )
    events, _ = _run(PhilosophicalResearchSocietyScraper(), [item])
    assert len(events) == 1
    e = events[0]
    assert e.title == 'Erik Davis Talk'
    assert e.event_date == when  # naive LA-local, DST-safe
    assert e.end_date == when + timedelta(hours=2)
    assert e.venue_name == 'Philosophical Research Society'
    assert e.region == 'beyond'
    assert (e.latitude, e.longitude) == (34.1131212, -118.2776505)
    assert e.price is None and e.price_note == ''
    # The ticket link serves every occurrence of a recurring item, so the
    # URL is made unique per occurrence with a fragment.
    assert e.url == (
        'https://www.eventbrite.com/e/x-tickets-1?aff=a#'
        + when.strftime('%Y-%m-%dT%H:%M')
    )


@pytest.mark.unit
def test_recurring_occurrences_are_kept_and_not_invented():
    """Each API occurrence becomes one event with its own URL; nothing extra."""
    base = _future(days=5)
    items = [
        _item('Reading Group', base + timedelta(days=7 * i), uid='9', kind='repeat',
              customButtonLink='https://tickets.example/rg')
        for i in range(3)
    ]
    events, _ = _run(PhilosophicalResearchSocietyScraper(), items)
    assert len(events) == 3
    assert len({e.url for e in events}) == 3


@pytest.mark.unit
def test_detail_url_when_no_ticket_link():
    when = _future()
    events, _ = _run(WorldStageScraper(), [_item('Show', when, uid='820')])
    tid = int(when.replace(tzinfo=LA).timestamp() * 1000)
    assert events[0].url == f'https://tockify.com/the.world.stage/detail/820/{tid}'


@pytest.mark.unit
def test_online_only_without_location_is_skipped():
    when = _future()
    online = _item('ONLINE: Peace Class', when, uid='1', desc='A free weekly gathering.')
    online_desc = _item('Class Series', when, uid='2', desc='Register to get the zoom link.')
    in_person = _item('Salon', when, uid='3', desc='Held in the lecture room.')
    events, _ = _run(PhilosophicalResearchSocietyScraper(), [online, online_desc, in_person])
    assert [e.title for e in events] == ['Salon']


@pytest.mark.unit
def test_online_word_with_a_location_is_kept():
    when = _future()
    item = _item('Hybrid Talk', when, desc='Also streamed online.', location=_loc())
    events, _ = _run(PhilosophicalResearchSocietyScraper(), [item])
    assert len(events) == 1


@pytest.mark.unit
def test_other_address_becomes_its_own_venue():
    when = _future()
    item = _item(
        'Off-site Screening', when, place='Egyptian Theatre',
        address='6712 Hollywood Blvd, Los Angeles, CA 90028, USA',
        location=_loc(34.1017, -118.3407),
    )
    events, _ = _run(PhilosophicalResearchSocietyScraper(), [item])
    assert events[0].venue_name == 'Egyptian Theatre'
    assert (events[0].latitude, events[0].longitude) == (34.1017, -118.3407)


@pytest.mark.unit
def test_past_cancelled_and_undated_items_are_dropped():
    past = _item('Gone', datetime.now() - timedelta(days=3), uid='1')
    cancelled = _item('Cancelled Show', _future(), uid='2', status='cancelled')
    undated = _item('No Time', _future(), uid='3')
    undated['when']['start'] = {}
    ok = _item('Fine', _future(), uid='4')
    events, _ = _run(WorldStageScraper(), [past, cancelled, undated, ok])
    assert [e.title for e in events] == ['Fine']


@pytest.mark.unit
def test_empty_and_unrecognised_responses_yield_nothing():
    assert _run(WorldStageScraper(), [])[0] == []
    scraper = WorldStageScraper()
    scraper.fetch_json = lambda *a, **k: None
    assert scraper.scrape() == []
    scraper.fetch_json = lambda *a, **k: {'unexpected': True}
    assert scraper.scrape() == []


@pytest.mark.unit
def test_truncated_description_ends_on_a_word_boundary():
    text = ('word ' * 100).strip()[:400]
    events, _ = _run(WorldStageScraper(), [_item('Show', _future(), desc=text)])
    assert events[0].description.endswith('…')
    assert len(events[0].description) <= 401


@pytest.mark.unit
def test_world_stage_is_curated_into_beyond_with_venue_coords():
    events, _ = _run(WorldStageScraper(), [_item('Show', _future())])
    e = events[0]
    assert e.region == 'beyond'
    assert e.venue_name == 'The World Stage'
    assert e.address == '4321 Degnan Blvd, Los Angeles, CA 90008'
    assert (e.latitude, e.longitude) == (34.0053013, -118.3317536)


@pytest.mark.unit
def test_world_stage_children_workshop_dropped_other_workshops_marked_education():
    when = _future()
    kids = _item(
        'Trap Drum Workshop', when, uid='4',
        desc='A hands-on workshop designed especially for children. For children age 2 to young adults. Admission: $5 Suggested Donation',
    )
    adult = _item(
        'World Stage Big Band', when, uid='574', kind='repeat',
        desc='Coordinated by Billy McCoy, this workshop goes through the decades of jazz. Admission: $5 Suggested Donation',
    )
    jam = _item(
        'The Billy Higgins Instrumental Jam Session', when, uid='9', kind='repeat',
        desc='INSTRUMENTALISTS ONLY. Admission: $5 Suggested Donation',
    )
    show = _item('Saxophonist Rickey Woodard', when, uid='821', desc='$20 Admission in Person')
    events, _ = _run(WorldStageScraper(), [kids, adult, jam, show])
    by_title = {e.title: e for e in events}
    assert 'Trap Drum Workshop' not in by_title
    assert by_title['World Stage Big Band'].category == 'Education'
    assert by_title['The Billy Higgins Instrumental Jam Session'].category == 'Music'
    assert by_title['Saxophonist Rickey Woodard'].category == 'Music'


@pytest.mark.unit
def test_world_stage_price_parse():
    when = _future()
    donation = _item('Jam', when, desc='Admission: $5 Suggested Donation')
    show = _item('Show', when, uid='2', desc='$20 Admission in Person')
    nothing = _item('Quiet', when, uid='3', desc='Hosted by someone.')
    events, _ = _run(WorldStageScraper(), [donation, show, nothing])
    by_title = {e.title: e for e in events}
    assert (by_title['Jam'].price, by_title['Jam'].price_note) == (5.0, 'Suggested donation')
    assert (by_title['Show'].price, by_title['Show'].price_note) == (20.0, '')
    assert (by_title['Quiet'].price, by_title['Quiet'].price_note) == (None, '')

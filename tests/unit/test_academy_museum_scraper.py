"""
Unit tests for the Academy Museum scraper.

Fully offline: fetch_page is replaced with a hand-built page that carries the
Next.js flight payload (``self.__next_f.push``) with a cfProgramsKeyedByTkId
map. Dates are generated relative to today.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.academy_museum import AcademyMuseumScraper


def _rich(text):
    return {'json': {'nodeType': 'document', 'data': {}, 'content': [
        {'nodeType': 'paragraph', 'data': {}, 'content': [
            {'nodeType': 'text', 'value': text, 'marks': [], 'data': {}}]}]}}


def _title(*runs):
    """A title made of several inline text runs (italic film name + ' in 35mm')."""
    return {'json': {'nodeType': 'document', 'data': {}, 'content': [
        {'nodeType': 'paragraph', 'data': {}, 'content': [
            {'nodeType': 'text', 'value': r, 'marks': [], 'data': {}} for r in runs]}]}}


def _iso(day):
    return day.strftime('%Y-%m-%dT00:00:00.000Z')


def _program(pid, title, start, end=None, types=('Screenings',), **extra):
    return {
        '__typename': 'ProgramEvent',
        'sys': {'id': pid},
        'slug': f'{pid}-slug',
        'programTitle': title if isinstance(title, dict) else _rich(title),
        'programTagline': None,
        'filmDescription1': _rich('A long description of the film.'),
        'activeStartDate': _iso(start),
        'activeEndDate': _iso(end or start),
        'hideFromCalendar': False,
        'membersOnly': False,
        'nonTicketedProgram': False,
        'type': 'Film',
        'programTypesCollection': {'items': [{'sys': {'id': 'x'}, 'name': n} for n in types]},
        'image': {'url': f'https://img.example/{pid}.jpg'},
        **extra,
    }


def _page(programs):
    payload = {'cfProgramsKeyedByTkId': {p['sys']['id']: p for p in programs}, 'cfCategories': []}
    # Compact separators, as Next.js emits them.
    flight = '5:' + json.dumps(['$', '$L20', None, payload], separators=(',', ':')) + '\n'
    # The flight stream arrives as several pushes; split mid-payload on purpose.
    half = len(flight) // 2
    scripts = ''.join(
        f'<script>self.__next_f.push({json.dumps([1, chunk])})</script>'
        for chunk in (flight[:half], flight[half:])
    )
    return f'<html><body>{scripts}</body></html>'


def _run(html):
    scraper = AcademyMuseumScraper()
    scraper.fetch_page = lambda url, retry=3: html
    return scraper.scrape()


def _day(offset):
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=offset)


@pytest.mark.unit
def test_parses_dated_screening(mock_geocoding_service):
    when = _day(10)
    events = _run(_page([_program('p1', _title('Stromboli ', 'in 35mm'), when)]))

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Stromboli in 35mm'
    assert e.event_date == when  # date-only: midnight placeholder, no tz shift
    assert e.url == 'https://www.academymuseum.org/en/programs/detail/p1-slug'
    assert e.category == 'Film'
    assert e.image_url == 'https://img.example/p1.jpg'
    assert e.description == 'A long description of the film.'
    assert e.price is None and not e.is_free and e.price_note == ''
    assert e.venue_name == 'Academy Museum of Motion Pictures'
    # Miracle Mile is inside the Westside box: default region, not 'beyond'.
    assert e.region == 'westside'


@pytest.mark.unit
def test_drops_past_ranges_hidden_and_members_only(mock_geocoding_service):
    programs = [
        _program('past', 'Yesterday film', _day(-1)),
        _program('today', 'Tonight film', _day(0)),
        _program('range', 'Ongoing tours', _day(-5), _day(60)),
        _program('hidden', 'Hidden', _day(3), hideFromCalendar=True),
        _program('members', 'Members only', _day(4), membersOnly=True),
        _program('ok', 'Open screening', _day(5)),
    ]

    events = _run(_page(programs))

    assert sorted(e.title for e in events) == ['Open screening', 'Tonight film']


@pytest.mark.unit
def test_free_tag_and_non_screening_category(mock_geocoding_service):
    programs = [
        _program('free', 'Bessie', _day(7), types=('Screenings', 'Free')),
        _program('tour', 'Sculpture Garden Walk', _day(8), types=('Tours', 'In-Gallery'), type='Education',
                 filmDescription1=_rich('Stroll the galleries with a guide.')),
    ]

    free, tour = sorted(_run(_page(programs)), key=lambda e: e.event_date)

    assert free.is_free and free.category == 'Film'
    assert tour.category != 'Film'  # not tagged Film just because the venue is a film museum


@pytest.mark.unit
@pytest.mark.parametrize('html', [
    '<html><body><p>nothing here</p></body></html>',
    '<html><body><script>self.__next_f.push([1,"5:[\\"$\\",null,{\\"somethingElse\\":{}}]"])</script></body></html>',
    '<html><body><script>self.__next_f.push([1,"5:{\\"cfProgramsKeyedByTkId\\":[1,2]}"])</script></body></html>',
    '<html><body><script>self.__next_f.push([1,"5:{\\"cfProgramsKeyedByTkId\\":{broken"])</script></body></html>',
    None,
])
def test_changed_page_shape_fails_soft(mock_geocoding_service, html):
    assert _run(html) == []


@pytest.mark.unit
def test_bad_program_does_not_sink_the_rest(mock_geocoding_service):
    good = _program('good', 'Good film', _day(3))
    bad = _program('bad', 'Bad dates', _day(3))
    bad['activeStartDate'] = 'not-a-date'
    untitled = _program('blank', '', _day(3))

    events = _run(_page([bad, untitled, good]))

    assert [e.title for e in events] == ['Good film']

"""
Unit tests for the Brain Dead Studios scraper (shared Filmbot parser; see
test_vidiots_scraper.py for the parse rules). What is specific here: the
Fairfax venue sits inside the Westside box, so it keeps the default region, and
today's showings only appear on the homepage, so two pages are merged.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.scrapers.filmbot import BrainDeadStudiosScraper
from src.utils.geo_filter import is_in_coverage_area

BASE = 'https://studios.wearebraindead.com'


def _iso(dt):
    return dt.replace(tzinfo=ZoneInfo('America/Los_Angeles')).isoformat()


def _movie(slug, name):
    return {'@type': 'Movie', '@id': f'{BASE}/movies/{slug}/#movie', 'name': name,
            'url': f'{BASE}/movies/{slug}/', 'description': 'A cult film.',
            'image': f'https://img.example/{slug}.jpg', 'duration': 'PT1H33M'}


def _show(slug, name, start, purchase):
    return {
        '@type': 'ScreeningEvent',
        'name': f'{name} - {start:%m/%d/%y} @ {start:%I:%M %p}',
        'startDate': _iso(start),
        'url': f'{BASE}/purchase/{purchase}/',
        'workPresented': {'@id': f'{BASE}/movies/{slug}/#movie'},
        'offers': [{'name': 'New Standard', 'price': '13',
                    'availability': 'https://schema.org/InStock'}],
    }


def _page(*nodes):
    graph = {'@context': 'https://schema.org', '@graph': list(nodes)}
    return f'<script type="application/ld+json">{json.dumps(graph)}</script>'


def _run(pages):
    scraper = BrainDeadStudiosScraper()
    fetched = []

    def fetch_page(url, retry=3):
        fetched.append(url)
        return pages.get(url)

    scraper.fetch_page = fetch_page
    return scraper.scrape(), fetched


def _later_today():
    # Always after "now" and before midnight, whatever time the test runs.
    now = datetime.now()
    return now.replace(hour=23, minute=30, second=0, microsecond=0) if now.hour < 23 else None


@pytest.mark.unit
def test_default_region_because_fairfax_is_inside_the_box(mock_geocoding_service):
    assert is_in_coverage_area(BrainDeadStudiosScraper.LATITUDE, BrainDeadStudiosScraper.LONGITUDE)
    assert BrainDeadStudiosScraper.REGION == 'westside'

    when = (datetime.now() + timedelta(days=2)).replace(hour=19, minute=30, second=0, microsecond=0)
    page = _page(_movie('repo-man', 'Repo Man'), _show('repo-man', 'Repo Man', when, 'a1'))

    events, _ = _run({f'{BASE}/coming-soon/': page})

    (e,) = events
    assert e.source == 'Brain Dead Studios'
    assert e.region == 'westside'
    assert e.title == 'Repo Man' and e.event_date == when
    assert e.venue_name == 'Brain Dead Studios'
    assert e.address == '611 N Fairfax Ave, Los Angeles, CA 90036'
    assert e.price == 13.0
    assert e.url == f'{BASE}/movies/repo-man/#{when:%Y-%m-%d}'


@pytest.mark.unit
def test_homepage_adds_todays_showings_without_duplicating(mock_geocoding_service):
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    tonight = _later_today()
    coming = _page(_movie('tampopo', 'Tampopo'), _show('tampopo', 'Tampopo', tomorrow, 't1'))
    nodes = [_movie('tampopo', 'Tampopo'), _show('tampopo', 'Tampopo', tomorrow, 't1')]  # repeated
    if tonight:
        nodes += [_movie('zodiac', 'Zodiac'), _show('zodiac', 'Zodiac', tonight, 'z1')]
    home = _page(*nodes)

    events, fetched = _run({f'{BASE}/coming-soon/': coming, f'{BASE}/': home})

    assert fetched == [f'{BASE}/coming-soon/', f'{BASE}/']
    expected = ['Tampopo'] + (['Zodiac'] if tonight else [])
    assert sorted(e.title for e in events) == sorted(expected)


@pytest.mark.unit
def test_one_page_failing_keeps_the_other(mock_geocoding_service):
    when = (datetime.now() + timedelta(days=2)).replace(hour=19, minute=0, second=0, microsecond=0)
    home = _page(_movie('repo-man', 'Repo Man'), _show('repo-man', 'Repo Man', when, 'a1'))

    events, _ = _run({f'{BASE}/': home})  # /coming-soon/ unreachable

    assert [e.title for e in events] == ['Repo Man']
    assert _run({})[0] == []

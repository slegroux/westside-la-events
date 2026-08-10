"""
Unit tests for the Boulevard Music scraper (The Events Calendar REST API).

Offline: BaseScraper.fetch_json is stubbed with a crafted Tribe payload, so no
network access. Covers past-event filtering, the three pricing shapes the shop
uses (dollar amount, free, blank), HTML stripping, category mapping, and the
fixed-venue constants that stand in for the API's empty venue record.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.boulevard_music import BoulevardMusicScraper


def _stamp(dt):
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def _payload():
    """One past event and four upcoming ones, in a single API page."""
    tonight = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    past = tonight - timedelta(days=6)
    soon = tonight + timedelta(days=5)
    free = tonight + timedelta(days=9)
    blank = tonight + timedelta(days=12)
    workshop = tonight + timedelta(days=15)

    def event(eid, title, start, cost, categories=('Live Music',), description=''):
        return {
            'id': eid,
            'title': title,
            'description': description,
            'excerpt': '',
            'start_date': _stamp(start),
            'end_date': _stamp(start + timedelta(hours=2)),
            'url': f'https://www.boulevardmusic.com/event/{eid}/',
            'cost': cost,
            'timezone': 'America/Los_Angeles',
            'all_day': False,
            'venue': [],
            'image': {'url': f'https://www.boulevardmusic.com/img/{eid}.jpeg'},
            'categories': [{'name': c} for c in categories],
        }

    return {
        'total_pages': 1,
        'events': [
            event('past-show', 'LAST WEEK&#8217;S SHOW', past, '$20'),
            event('stout-trio', 'JONATHAN STOUT TRIO', soon, '$28',
                  description='<p>Swing guitar &amp; vocals.</p><img src="x.jpg">'),
            event('open-mic', 'OPEN MIC NIGHT', free, 'Free'),
            event('tba-show', 'TBA SHOW', blank, ''),
            event('guitar-workshop', 'FINGERSTYLE WORKSHOP', workshop, '$45',
                  categories=('Workshop',)),
        ],
    }


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    s = BoulevardMusicScraper()
    s.fetch_json = lambda *a, **k: _payload()   # stub the network call
    return s


@pytest.mark.unit
@pytest.mark.scraper
class TestBoulevardMusicScraper:
    def test_filters_past_and_returns_upcoming(self, scraper):
        titles = [e.title for e in scraper.scrape()]
        # Past dropped (matched on the prefix: the source's curly apostrophe
        # survives unescaping, so an exact literal here would be brittle).
        assert not any(t.startswith('LAST WEEK') for t in titles)
        assert titles == [
            'JONATHAN STOUT TRIO',
            'OPEN MIC NIGHT',
            'TBA SHOW',
            'FINGERSTYLE WORKSHOP',
        ]

    def test_fixed_venue_and_coordinates(self, scraper):
        # The API carries no venue record, so these come from the scraper.
        e = scraper.scrape()[0]
        assert e.venue_name == 'Boulevard Music'
        assert e.address == '4316 Sepulveda Blvd, Culver City, CA 90230'
        assert (e.latitude, e.longitude) == (34.0043483, -118.4092163)

    def test_paid_event_pricing(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'JONATHAN STOUT TRIO')
        assert e.price == 28.0
        assert e.is_free is False
        assert e.price_note == '$28'

    def test_free_event_pricing(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'OPEN MIC NIGHT')
        assert e.is_free is True
        assert e.price is None
        assert e.price_note == 'Free'

    def test_blank_cost_leaves_price_note_empty(self, scraper):
        # Project convention: unknown price renders no badge, so no "TBD".
        e = next(x for x in scraper.scrape() if x.title == 'TBA SHOW')
        assert e.price is None
        assert e.is_free is False
        assert e.price_note == ''

    def test_description_html_is_stripped_and_unescaped(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'JONATHAN STOUT TRIO')
        assert e.description == 'Swing guitar & vocals.'
        assert '<' not in e.description

    def test_category_defaults_to_music_and_maps_workshops(self, scraper):
        by_title = {e.title: e for e in scraper.scrape()}
        assert by_title['JONATHAN STOUT TRIO'].category == 'Music'
        assert by_title['FINGERSTYLE WORKSHOP'].category == 'Education'

    def test_event_url_and_image_come_from_payload(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'JONATHAN STOUT TRIO')
        assert e.url == 'https://www.boulevardmusic.com/event/stout-trio/'
        assert e.image_url == 'https://www.boulevardmusic.com/img/stout-trio.jpeg'

    def test_end_date_kept_when_after_start(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'JONATHAN STOUT TRIO')
        assert e.end_date == e.event_date + timedelta(hours=2)

    def test_empty_response_returns_empty_list(self, scraper):
        scraper.fetch_json = lambda *a, **k: None
        assert scraper.scrape() == []

    def test_stops_paging_when_page_has_no_events(self, scraper):
        scraper.fetch_json = lambda *a, **k: {'total_pages': 9, 'events': []}
        assert scraper.scrape() == []


@pytest.mark.unit
class TestCostParsing:
    @pytest.fixture
    def s(self, monkeypatch, mock_geocoding_service):
        monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
        return BoulevardMusicScraper()

    @pytest.mark.parametrize('cost,expected', [
        ('$28', (28.0, False, '$28')),
        ('$28.50', (28.5, False, '$28.50')),
        ('$25 - $30', (25.0, False, '$25 - $30')),   # advertised low end
        ('Free', (None, True, 'Free')),
        ('0', (None, True, 'Free')),
        ('', (None, False, '')),
        (None, (None, False, '')),
        ('Donations welcome', (None, False, 'Donations welcome')),
    ])
    def test_cost_shapes(self, s, cost, expected):
        assert s._parse_cost(cost) == expected

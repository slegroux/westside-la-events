"""
Unit tests for the TRiP Santa Monica scraper.

Offline: fetch_page_js is stubbed with fixture HTML shaped like the rendered
Weekly Shows page (a flat Wix DOM where headings and body copy are siblings
rather than nested per-show containers).

The venue runs standing weekly nights with no end date, so these tests pin the
two things most likely to regress: which of several times on the page is taken
as the start, and that occurrences land on the weekday named in the heading.
"""
from datetime import date, datetime, timedelta

import pytest

from src.scrapers.tripp import TrippScraper


WEEKLY_SHOWS_HTML = """
<html><body>
  <h2>WEEKLY EVENTS &amp; SHOWS</h2>

  <h5>Friday TRIVIA Night</h5>
  <p>20 Questions Trivia is the Pub Quiz like no other. 21 and over.</p>
  <h6>When:</h6>
  <p>Every Friday night @ 7pm</p>

  <h5>Monday Community Art &amp; Open Mic</h5>
  <p>Come hang out with incredible artists and upcoming musicians.</p>
  <p>7:15pm signup, 8pm start.</p>
  <p>$10 for 10 minutes,</p>
</body></html>
"""


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    s = TrippScraper()
    s.fetch_page_js = lambda *a, **k: WEEKLY_SHOWS_HTML
    return s


@pytest.mark.unit
@pytest.mark.scraper
class TestTrippScraper:
    def test_finds_both_weekly_shows(self, scraper):
        titles = {e.title for e in scraper.scrape()}
        assert titles == {'Friday TRIVIA Night', 'Monday Community Art & Open Mic'}

    def test_projects_a_bounded_horizon(self, scraper):
        events = scraper.scrape()
        # Two standing nights, WEEKS_AHEAD occurrences each -- never unbounded.
        assert len(events) == 2 * scraper.WEEKS_AHEAD

    def test_occurrences_land_on_the_named_weekday(self, scraper):
        friday = [e for e in scraper.scrape() if e.title.startswith('Friday')]
        assert all(e.event_date.weekday() == 4 for e in friday)
        monday = [e for e in scraper.scrape() if e.title.startswith('Monday')]
        assert all(e.event_date.weekday() == 0 for e in monday)

    def test_occurrences_are_weekly_and_start_today_or_later(self, scraper):
        dates = sorted(e.event_date for e in scraper.scrape()
                       if e.title.startswith('Friday'))
        assert dates[0].date() >= date.today()
        assert all((b - a) == timedelta(weeks=1) for a, b in zip(dates, dates[1:]))

    def test_at_time_is_used_for_trivia(self, scraper):
        e = next(x for x in scraper.scrape() if x.title.startswith('Friday'))
        assert (e.event_date.hour, e.event_date.minute) == (19, 0)   # "@ 7pm"

    def test_explicit_start_beats_signup_time(self, scraper):
        # "7:15pm signup, 8pm start" -- the show is 8pm, not the signup at 7:15.
        e = next(x for x in scraper.scrape() if x.title.startswith('Monday'))
        assert (e.event_date.hour, e.event_date.minute) == (20, 0)

    def test_venue_address_and_coordinates(self, scraper):
        # Regression guard: this was previously 1431 3rd Street Promenade,
        # which is a different venue entirely.
        e = scraper.scrape()[0]
        assert e.venue_name == 'TRiP Santa Monica'
        assert e.address == '2101 Lincoln Blvd, Santa Monica, CA 90405'
        assert (e.latitude, e.longitude) == (34.0025873, -118.4703697)

    def test_categories(self, scraper):
        by_title = {e.title: e for e in scraper.scrape()}
        assert by_title['Friday TRIVIA Night'].category == 'Community'
        assert by_title['Monday Community Art & Open Mic'].category == 'Music'

    def test_occurrences_get_distinct_urls(self, scraper):
        urls = [e.url for e in scraper.scrape() if e.title.startswith('Friday')]
        assert len(set(urls)) == len(urls)
        assert all('#' in u for u in urls)

    def test_render_failure_returns_empty(self, scraper):
        scraper.fetch_page_js = lambda *a, **k: None
        assert scraper.scrape() == []

    def test_page_with_no_weekday_headings_yields_nothing(self, scraper):
        scraper.fetch_page_js = lambda *a, **k: '<html><body><h5>Coming soon</h5></body></html>'
        assert scraper.scrape() == []


@pytest.mark.unit
class TestTrippStartTimeParsing:
    @pytest.fixture
    def s(self, monkeypatch, mock_geocoding_service):
        monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
        return TrippScraper()

    @pytest.mark.parametrize('text,expected', [
        ('Every Friday night @ 7pm', (19, 0)),
        ('7:15pm signup, 8pm start.', (20, 0)),
        ('doors 9:30pm', (21, 30)),
        ('11am brunch set', (11, 0)),
        ('no time given', (20, 0)),          # evening default
    ])
    def test_start_time(self, s, text, expected):
        assert s._parse_start(text) == expected

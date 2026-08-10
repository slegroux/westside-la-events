"""
Unit tests for The Culver Steps scraper.

Offline: fetch_page is stubbed with fixture HTML built in the shape of the real
WPBakery happenings grid, so no network access.

The source writes dates without years ("Wednesdays, July 8 - August 26") and the
scraper recovers the year from the stated weekday, so fixtures are *generated*
from dates relative to today rather than hardcoded. Hardcoded month/day text
would drift out of the weekday-anchored window and the suite would rot.
"""
from datetime import date, datetime, timedelta

import pytest

from src.scrapers.culver_steps import CulverStepsScraper


def _card(title, blurb, slug, img='https://theculversteps.com/img/x.png'):
    return f"""
    <div class="col span_4 element events">
      <div class="inner-wrap">
        <a href="/directory/{slug}/"><img src="{img}"/></a>
        <div class="work-meta"><h4>{title}</h4><p>{blurb}</p></div>
      </div>
    </div>
    """


def _detail(title, body):
    return f"""
    <html><body><div class="container-wrap">
      <p>Back to Happenings</p><h1>{title}</h1><p>{body}</p>
      <h5>Where</h5><p>Upper Plaza</p>
      <p>Become an Insider! Sign up for exclusive deals.</p>
    </div></body></html>
    """


# --- generated schedule text -------------------------------------------------
# A weekly series two weeks out, running four occurrences.
SERIES_START = date.today() + timedelta(days=14)
SERIES_END = SERIES_START + timedelta(days=21)
SERIES_WEEKDAY = SERIES_START.strftime('%A')
SERIES_BLURB = (
    f"{SERIES_WEEKDAY}s, {SERIES_START:%B} {SERIES_START.day} - "
    f"{SERIES_END:%B} {SERIES_END.day} at 10:00am"
)

# A one-off ten days out.
ONE_OFF = date.today() + timedelta(days=10)
ONE_OFF_BLURB = (
    f"Join us for the block party on {ONE_OFF:%A}, {ONE_OFF:%B} {ONE_OFF.day}th from 5-8pm"
)

# A one-off that already happened.
PAST_DAY = date.today() - timedelta(days=6)
PAST_BLURB = f"{PAST_DAY:%A}, {PAST_DAY:%B} {PAST_DAY.day}th at 7pm"


LISTING_HTML = f"""
<html><body><div class="portfolio-wrap"><div class="row portfolio-items no-masonry">
  {_card('PLAY at the Steps', SERIES_BLURB, 'play-at-the-steps')}
  {_card('Culver Block Party', ONE_OFF_BLURB, 'culver-block-party')}
  {_card('Sunset Yoga on the Steps', 'Tuesdays at 6:30pm', 'sunset-yoga')}
  {_card('Last Month&#8217;s Concert', PAST_BLURB, 'last-concert')}
</div></div></body></html>
"""

DETAILS = {
    'https://theculversteps.com/directory/play-at-the-steps/': _detail(
        'PLAY at the Steps',
        'Sing. Dance. PLAY at The Steps! LoveBug and Me Music leads a fun-filled hour.',
    ),
    'https://theculversteps.com/directory/culver-block-party/': _detail(
        'Culver Block Party', 'Food trucks and neighbours on the plaza.'),
    # No date range anywhere -- neither the card nor the detail page bounds it.
    'https://theculversteps.com/directory/sunset-yoga/': _detail(
        'Sunset Yoga on the Steps', 'A free CorePower class above our iconic steps.'),
    'https://theculversteps.com/directory/last-concert/': _detail(
        'Last Month&#8217;s Concert', 'That was fun.'),
}


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    s = CulverStepsScraper()
    s.prefetch_pages = lambda *a, **k: None
    s.fetch_page = lambda url, **k: (
        LISTING_HTML if url == s.LISTING_URL else DETAILS.get(url)
    )
    return s


@pytest.mark.unit
@pytest.mark.scraper
class TestCulverStepsScraper:
    def test_weekly_series_expands_per_occurrence(self, scraper):
        dates = [e.event_date for e in scraper.scrape() if e.title == 'PLAY at the Steps']
        assert len(dates) == 4                                  # 3 weeks inclusive
        assert dates[0].date() == SERIES_START
        assert dates[-1].date() == SERIES_END
        assert all(d.hour == 10 and d.minute == 0 for d in dates)
        assert all((b - a).days == 7 for a, b in zip(dates, dates[1:]))

    def test_single_occurrence_with_time_range(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'Culver Block Party')
        # "5-8pm": the leading hour inherits the trailing meridiem.
        assert e.event_date == datetime(ONE_OFF.year, ONE_OFF.month, ONE_OFF.day, 17, 0)
        assert e.end_date == datetime(ONE_OFF.year, ONE_OFF.month, ONE_OFF.day, 20, 0)

    def test_unbounded_series_is_skipped(self, scraper):
        # "Tuesdays at 6:30pm" has no end date; projecting it forward would
        # invent events once the season quietly ends.
        titles = [e.title for e in scraper.scrape()]
        assert 'Sunset Yoga on the Steps' not in titles

    def test_past_event_is_skipped(self, scraper):
        titles = [e.title for e in scraper.scrape()]
        assert not any(t.startswith('Last Month') for t in titles)

    def test_fixed_venue_and_coordinates(self, scraper):
        e = scraper.scrape()[0]
        assert e.venue_name == 'The Culver Steps'
        assert e.address == '9300 Culver Blvd, Culver City, CA 90232'
        assert (e.latitude, e.longitude) == (34.0244516, -118.3933641)

    def test_all_events_are_free(self, scraper):
        events = scraper.scrape()
        assert events
        assert all(e.is_free and e.price_note == 'Free' for e in events)

    def test_occurrences_get_distinct_urls(self, scraper):
        events = [e for e in scraper.scrape() if e.title == 'PLAY at the Steps']
        urls = [e.url for e in events]
        assert len(set(urls)) == len(urls)          # dedup must not merge them
        assert urls[0].endswith(f'#{SERIES_START:%Y-%m-%d}')

    def test_description_drops_repeated_heading_and_boilerplate(self, scraper):
        e = next(x for x in scraper.scrape() if x.title == 'PLAY at the Steps')
        assert e.description.startswith('Sing. Dance.')
        assert 'Become an Insider' not in e.description
        assert 'Upper Plaza' not in e.description

    def test_image_url_is_absolute(self, scraper):
        e = scraper.scrape()[0]
        assert e.image_url == 'https://theculversteps.com/img/x.png'

    def test_listing_fetch_failure_returns_empty(self, scraper):
        scraper.fetch_page = lambda *a, **k: None
        assert scraper.scrape() == []


@pytest.mark.unit
class TestCulverStepsParsing:
    @pytest.fixture
    def s(self, monkeypatch, mock_geocoding_service):
        monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
        return CulverStepsScraper()

    @pytest.mark.parametrize('text,expected', [
        ('from 5-8pm', ((17, 0), (20, 0))),         # meridiem inherited
        ('7pm - 9pm', ((19, 0), (21, 0))),
        ('at 6:30pm', ((18, 30), None)),
        ('at 10:00am', ((10, 0), None)),
        ('no time here', ((0, 0), None)),
    ])
    def test_time_parsing(self, s, text, expected):
        assert s._parse_times(text) == expected

    def test_classify_prefers_title_over_description(self, s):
        # The blurb names a band; the title says it is a kids' event.
        assert s._classify('PLAY at the Steps', 'LoveBug and Me Music') == 'Family'
        assert s._classify('Summer Sunset Concert Series', 'family fun') == 'Music'
        assert s._classify('Sunset Yoga on the Steps', '') == 'Wellness'
        assert s._classify('Community Mixer', '') == 'Community'

    def test_classify_ignores_substring_matches(self, s):
        # "play" must not fire on "displays".
        assert s._classify('Art Walk', 'The gallery displays local work') == 'Community'

    def test_series_expansion_is_capped(self, s, monkeypatch):
        # A multi-year range must not expand without bound.
        start = date.today() + timedelta(days=7)
        end = start + timedelta(days=365 * 2)
        text = (f'{start:%A}s, {start:%B} {start.day} - {end:%B} {end.day} at 9am')
        occurrences = s._parse_schedule(text)
        assert len(occurrences) <= s.MAX_OCCURRENCES

    def test_unparseable_text_yields_nothing(self, s):
        assert s._parse_schedule('Coming soon! Follow us for updates.') == []

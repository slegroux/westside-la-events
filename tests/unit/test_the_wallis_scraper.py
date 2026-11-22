"""
Unit tests for The Wallis scraper.

Fully offline: fetch_page and prefetch_pages are replaced with a hand-built
season grid and show pages (JSON-LD offers, one per performance). Dates are
generated relative to today.
"""
import json
from datetime import datetime, timedelta

import pytest

from src.scrapers.the_wallis import TheWallisScraper

SEASON = TheWallisScraper.DEFAULT_SEASON_URL
HOME = TheWallisScraper.BASE_URL + '/'


def _d(dt):
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def _card(slug, title, start=None, end=None, cat='THEATER'):
    dates = ''
    if start:
        dates = _d(start) + (f' - {_d(end)}' if end else '')
    return f'''
    <div class="home-listing-item"><div class="show-card">
      <a href="https://thewallis.org/show-details/{slug}" aria-label="{title}">
        <img alt="{title}" data-src="https://img.example/{slug}.webp" src="https://img.example/{slug}.webp"/>
      </a>
      <div class="show-cat"><span>{cat}</span></div>
      <h3>{title}<span>{dates}</span></h3>
      <a href="https://thewallis.org/show-details/{slug}" class="read-more">More Info</a>
    </div></div>'''


def _season(*cards):
    return f'<html><body><div class="row">{"".join(cards)}</div></body></html>'


def _show_page(*performances, sold_out=False):
    """performances: naive datetimes; JSON-LD offers carry availabilityStarts."""
    offers = [{
        '@type': 'Offer',
        'availability': 'https://schema.org/SoldOut' if sold_out else 'https://schema.org/InStock',
        'availabilityStarts': p.strftime('%Y-%m-%d %H:%M:%S'),
        'url': 'https://tickets.example/1',
    } for p in performances]
    ld = {'@type': 'TheaterEvent', 'name': 'x', 'offers': offers}
    return (
        '<html><head>'
        '<meta name="description" content="A new play about the stars."/>'
        f'<script type="application/ld+json">{json.dumps(ld)}</script>'
        '</head></html>'
    )


def _at(days, hour=19, minute=30):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)


def _run(pages):
    scraper = TheWallisScraper()
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()


def _url(slug):
    return f'https://thewallis.org/show-details/{slug}'


@pytest.mark.unit
def test_run_becomes_one_event_per_performance_day(mock_geocoding_service):
    """Performance times come from the show page, not the card's date range."""
    matinee, evening, next_day = _at(10, 14, 30), _at(10, 19, 30), _at(11, 19, 30)
    pages = {
        SEASON: _season(_card('radio-galaxy', 'RADIO GALAXY', _at(10), _at(12))),
        _url('radio-galaxy'): _show_page(evening, matinee, next_day),
    }

    events = _run(pages)

    assert [e.event_date for e in events] == [matinee, next_day]
    first = events[0]
    assert first.title == 'RADIO GALAXY'
    assert first.url == f"{_url('radio-galaxy')}#{matinee.date().isoformat()}"
    assert events[1].url.endswith('#' + next_day.date().isoformat())
    assert 'Showtimes: 2:30 PM, 7:30 PM.' in first.description
    assert first.description.startswith('A new play about the stars.')
    assert first.category == 'Theater'
    assert first.image_url == 'https://img.example/radio-galaxy.webp'
    assert first.venue_name == 'The Wallis'
    assert first.price is None and first.price_note == ''
    assert first.region == 'westside'
    assert abs(first.latitude - 34.0722705) < 1e-6


@pytest.mark.unit
def test_past_performances_and_undated_cards_are_dropped(mock_geocoding_service):
    """A run already under way keeps only its remaining days; undated cards are skipped."""
    pages = {
        SEASON: _season(
            _card('running', 'RUNNING SHOW', _at(-5), _at(5)),
            _card('series', 'FILM SERIES'),
        ),
        _url('running'): _show_page(_at(-2), _at(3)),
        _url('series'): _show_page(_at(8)),
    }

    events = _run(pages)

    assert [e.title for e in events] == ['RUNNING SHOW']
    assert events[0].event_date == _at(3)


@pytest.mark.unit
def test_card_range_is_the_fallback_when_the_page_lists_no_performances(mock_geocoding_service):
    """Like Broad Stage: range start is the event date and range end the end date."""
    start, end = _at(20), _at(22)
    pages = {
        SEASON: _season(
            _card('no-times', 'NO TIMES YET', start, end, cat='DANCE'),
            _card('over', 'ALREADY OPEN', _at(-3), _at(4)),
        ),
        _url('no-times'): '<html><head></head></html>',
        _url('over'): '<html><head></head></html>',
    }

    events = _run(pages)

    assert [e.title for e in events] == ['NO TIMES YET']
    e = events[0]
    assert e.event_date.date() == start.date() and e.end_date.date() == end.date()
    assert e.url == _url('no-times')
    assert e.category == 'Theater'


@pytest.mark.unit
def test_sold_out_performance_days_and_family_category(mock_geocoding_service):
    pages = {
        SEASON: _season(_card('fam', 'FAMILY FEST', _at(9), cat='FAMILY')),
        _url('fam'): _show_page(_at(9, 11, 0), sold_out=True),
    }

    (event,) = _run(pages)

    assert event.price is None and event.price_note == 'Sold out'
    assert event.category == 'Family'


@pytest.mark.unit
def test_empty_or_unrecognised_page_yields_nothing(mock_geocoding_service):
    assert _run({}) == []
    assert _run({SEASON: '<html><body>Not found</body></html>'}) == []


@pytest.mark.unit
def test_season_slug_follows_the_home_page_nav(mock_geocoding_service):
    """When the site rolls to the next season, the new landing page is used."""
    new_season = 'https://www.thewallis.org/season2728'
    pages = {
        HOME: '<a href="/season2627">old</a><a href="/season2728">new</a>',
        new_season: _season(_card('next', 'NEXT YEAR SHOW', _at(30), _at(31))),
        _url('next'): _show_page(_at(30)),
    }

    events = _run(pages)

    assert [e.title for e in events] == ['NEXT YEAR SHOW']


@pytest.mark.unit
def test_showtimes_that_already_started_today_are_dropped(mock_geocoding_service, monkeypatch):
    real_now = datetime.now()
    fixed = real_now.replace(hour=15, minute=0, second=0, microsecond=0)

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed

    monkeypatch.setattr('src.scrapers.the_wallis.datetime', FixedClock)
    matinee, evening = fixed.replace(hour=13), fixed.replace(hour=20)
    pages = {
        SEASON: _season(_card('today', 'TODAY SHOW', _at(-1), _at(1))),
        _url('today'): _show_page(matinee, evening),
    }

    (event,) = _run(pages)

    assert event.event_date == evening
    assert 'Showtimes: 8:00 PM.' in event.description

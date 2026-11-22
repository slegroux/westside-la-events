"""
Unit tests for the New Beverly Cinema scraper.

Fully offline: fetch_page returns a hand-built copy of the thenewbev.com
schedule markup (month sections of event cards). Dates are relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.new_beverly import NewBeverlyScraper
from src.utils.geo_filter import is_in_coverage_area


def _card(when, title, times, label=None, link_text='More Info / Buy Tickets', slug=None):
    slug = slug or f"{when:%B-%d}".lower().replace('-0', '-') + '-' + title.lower().replace(' ', '-')
    clocks = ' / '.join(f'<time class="event-card__time">{t}</time>' for t in times)
    label_tag = f'<i class="event-card__label" aria-label="{label}"></i>' if label else ''
    return f'''
    <article class="event-card">
      <a href="https://thenewbev.com/program/{slug}/">
        <figure class="event-card__img"><img src="https://thenewbev.com/img/{slug}.jpg" alt=""></figure>
        <div class="event-card__date">
          <span class="event-card__day">{when:%a},</span>
          <span class="event-card__month">{when:%B}</span>
          <span class="event-card__numb">{when.day}</span>
        </div>
        <div class="event-card__info">
          {label_tag}{clocks}
          <h4 class="event-card__title">
            {title}
          </h4>
          <footer class="event-card__footer"><span class="event-card__link">{link_text}</span></footer>
        </div>
      </a>
    </article>'''


def _month(when, *cards):
    return f'''<section class="calendar-month">
      <section class="heading"><h2>{when:%B %Y}</h2></section>
      <section class="events"><div class="events__grid">{''.join(cards)}</div></section>
    </section>'''


def _run(html):
    scraper = NewBeverlyScraper()
    scraper.fetch_page = lambda url, retry=3: html
    return scraper.scrape()


def _day(days):
    return (datetime.now() + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)


@pytest.mark.unit
def test_parses_a_card(mock_geocoding_service):
    when = _day(3)
    events = _run(_month(when, _card(when, 'Zodiac', ['7:00 pm'], slug='zodiac-test')))

    (e,) = events
    assert e.source == 'New Beverly Cinema'
    assert e.title == 'Zodiac'
    assert e.event_date == when.replace(hour=19)
    assert e.url == 'https://thenewbev.com/program/zodiac-test/'
    assert e.image_url == 'https://thenewbev.com/img/zodiac-test.jpg'
    assert e.category == 'Film'
    assert e.description == 'Showtimes - 7:00pm.'
    assert e.price is None and not e.is_free and e.price_note == ''
    assert e.venue_name == 'New Beverly Cinema'
    assert e.address == '7165 Beverly Blvd, Los Angeles, CA 90036'
    assert (e.latitude, e.longitude) == (NewBeverlyScraper.LATITUDE, NewBeverlyScraper.LONGITUDE)


@pytest.mark.unit
def test_default_region_because_fairfax_is_inside_the_box(mock_geocoding_service):
    assert is_in_coverage_area(NewBeverlyScraper.LATITUDE, NewBeverlyScraper.LONGITUDE)
    when = _day(3)
    (e,) = _run(_month(when, _card(when, 'Zodiac', ['7:00 pm'])))
    assert e.region == 'westside'


@pytest.mark.unit
def test_double_feature_keeps_every_showtime_and_label(mock_geocoding_service):
    when = _day(4)
    card = _card(when, 'Paper Moon / <br>Nickelodeon', ['7:30 pm', '9:40 pm'], label='Special Event')

    (e,) = _run(_month(when, card))

    assert e.title == 'Paper Moon / Nickelodeon'
    assert e.event_date == when.replace(hour=19, minute=30)
    assert e.description == 'Special Event. Showtimes - 7:30pm, 9:40pm.'


@pytest.mark.unit
def test_sold_out_online_is_noted_not_priced(mock_geocoding_service):
    when = _day(2)
    card = _card(when, 'Zodiac', ['7:00 pm'], link_text='Sold Out Online / Some Tix At Door')

    (e,) = _run(_month(when, card))

    assert e.price is None and e.price_note == 'Sold out online (some tickets at door)'
    assert 'Sold out online' in e.description


@pytest.mark.unit
def test_same_film_on_consecutive_days_keeps_distinct_urls(mock_geocoding_service):
    d1, d2 = _day(2), _day(3)
    # One section per card so each carries its own month heading.
    month = (_month(d1, _card(d1, 'Fantastic Mr. Fox', ['2:00 pm'], label='Kiddie Matinee'))
             + _month(d2, _card(d2, 'Fantastic Mr. Fox', ['2:00 pm'], label='Kiddie Matinee')))

    e1, e2 = _run(month)

    assert e1.url != e2.url
    assert e1.event_date.date() != e2.event_date.date()


@pytest.mark.unit
def test_year_comes_from_the_month_heading(mock_geocoding_service):
    when = _day(40)
    (e,) = _run(_month(when, _card(when, 'Future Film', ['8:00 pm'])))
    assert (e.event_date.year, e.event_date.month, e.event_date.day) == (when.year, when.month, when.day)


@pytest.mark.unit
def test_past_unreadable_and_timeless_cards_are_dropped(mock_geocoding_service):
    when = _day(3)
    past = _day(-2)
    cards = [
        _card(when, 'Keeper', ['7:00 pm']),
        _card(when, 'No Time', []),
        _card(when, 'Bad Time', ['TBA']),
    ]
    html = _month(past, _card(past, 'Old Film', ['7:00 pm'])) + _month(when, *cards)

    events = _run(html)

    assert [e.title for e in events] == ['Keeper']


@pytest.mark.unit
def test_unrecognised_or_empty_page_yields_nothing(mock_geocoding_service):
    assert _run('<html><body><p>Closed for renovation</p></body></html>') == []
    assert _run(None) == []
    # A month section with no parseable heading is skipped.
    assert _run('<section class="calendar-month"><h2>Soon</h2>'
                + _card(_day(2), 'X', ['7:00 pm']) + '</section>') == []

"""
Regression tests for Fairmont Miramar date handling.

The events page marks standing programming "WEEKLY" without naming a day. The
scraper used to anchor those series to the run date, which put Oktoberfest on
whatever evening the scrape happened to run and drifted from run to run --
prod accumulated 14 bogus Oktoberfest dates that way. Dates must come from the
source or not exist.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from src.scrapers.fairmont_miramar import FairmontMiramarScraper


def _card(title, description, frequency='WEEKLY', time_text='5:00PM', booking_href=None):
    booking = f'<a href="{booking_href}">Book Now</a>' if booking_href else ''
    return BeautifulSoup(
        f'''
        <div class="event-cards__card">
          <h3 class="event-cards__title">{title}</h3>
          <div class="event-cards__event-type">Special Events</div>
          <div class="event-cards__description">{description}</div>
          <div class="event-cards__frequency-flag">{frequency}</div>
          <div class="event-cards__icon-wrapper">Front Drive</div>
          <div class="event-cards__icon-wrapper">{frequency}</div>
          <div class="event-cards__icon-wrapper">{time_text}</div>
          {booking}
          <a href="https://www.fairmont-miramar.com/events/x/">View Details</a>
        </div>
        ''',
        'lxml',
    ).find('div', class_='event-cards__card')


@pytest.mark.unit
class TestNoFabricatedDates:
    def test_weekly_without_a_day_produces_nothing(self):
        """The exact Oktoberfest failure: WEEKLY, no day, no dated link."""
        scraper = FairmontMiramarScraper()
        card = _card(
            'Oktoberfest at The Miramar',
            'Step into Bavarian spirit at The Miramar in Santa Monica!',
        )
        assert scraper._parse_card(card) == []

    def test_weekly_dates_returns_empty_without_a_weekday(self):
        scraper = FairmontMiramarScraper()
        assert scraper._weekly_dates('no day named here', 'Some Event', '5:00PM') == []

    def test_result_never_depends_on_the_day_the_scrape_runs(self):
        """Same input, different run days, same output -- previously it drifted."""
        scraper = FairmontMiramarScraper()
        card = _card('Afternoon Tea', 'Savory sandwiches and scones.')

        outputs = []
        for offset in range(7):
            fake_now = datetime(2026, 8, 24, 9, 0) + timedelta(days=offset)
            with patch('src.scrapers.fairmont_miramar.datetime') as dt:
                dt.now.return_value = fake_now
                dt.side_effect = lambda *a, **k: datetime(*a, **k)
                outputs.append([d for d, _ in scraper._weekly_dates(
                    card.find(class_='event-cards__description').get_text(),
                    'Afternoon Tea', '12:00PM',
                )])

        assert all(o == [] for o in outputs)


@pytest.mark.unit
class TestLegitimateDatesStillWork:
    def test_named_weekday_still_expands(self):
        scraper = FairmontMiramarScraper()
        dates = scraper._weekly_dates(
            'Join us every Thursday for live music.', 'Madi Rindge', '7:00PM'
        )
        assert len(dates) == 4
        for moment, _ in dates:
            assert moment.weekday() == 3  # Thursday
            assert (moment.hour, moment.minute) == (19, 0)

    def test_booking_link_date_is_preferred_over_inference(self):
        """Oktoberfest's real date lives on the linked Eventbrite listing."""
        scraper = FairmontMiramarScraper()
        card = _card(
            'Oktoberfest at The Miramar',
            'Step into Bavarian spirit!',
            booking_href='https://www.eventbrite.com/e/oktoberfest-tickets-123',
        )

        eventbrite_html = (
            '<script type="application/ld+json">'
            '{"@type": "SocialEvent", "startDate": "2026-10-08T17:00:00-07:00"}'
            '</script>'
        )
        with patch.object(scraper, 'fetch_page', return_value=eventbrite_html):
            found = scraper._booking_date(card)

        assert found is not None
        assert (found.year, found.month, found.day) == (2026, 10, 8)

    def test_booking_date_accepts_event_subtypes(self):
        """Eventbrite tags listings SocialEvent/MusicEvent, not bare Event."""
        scraper = FairmontMiramarScraper()
        card = _card('X', 'Y', booking_href='https://www.eventbrite.com/e/x-1')

        for schema_type in ('Event', 'SocialEvent', 'MusicEvent'):
            html = (
                '<script type="application/ld+json">'
                f'{{"@type": "{schema_type}", "startDate": "2026-10-08T17:00:00-07:00"}}'
                '</script>'
            )
            with patch.object(scraper, 'fetch_page', return_value=html):
                assert scraper._booking_date(card) is not None, schema_type

    def test_opentable_links_are_not_treated_as_dated(self):
        scraper = FairmontMiramarScraper()
        card = _card('Afternoon Tea', 'Scones.',
                     booking_href='https://www.opentable.com/r/afternoon-tea')
        assert scraper._booking_date(card) is None

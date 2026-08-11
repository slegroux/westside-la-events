"""
Unit tests for Eventbrite recurring-series normalization.

Eventbrite flattens a recurring series into one listing whose startDate is the
first occurrence and endDate the last, with no eventSchedule/subEvent to say
otherwise. Stored verbatim that becomes a months-long "event", and the site's
multi-day rule (which exists so exhibitions show on every day they are open)
then displays it every single day.

These tests pin the discrimination that matters: a weekly series is expanded
onto its weekday, while genuine multi-day events are left alone.
"""
from datetime import date, datetime, timedelta

import pytest

from src.data.models import Event
from src.scrapers.eventbrite import EventbriteScraper


@pytest.fixture
def scraper(monkeypatch, mock_geocoding_service):
    monkeypatch.setenv('SCRAPER_DISABLE_LOGOS', 'true')
    return EventbriteScraper()


def _event(title, start, end, url='https://www.eventbrite.com/e/thing-123'):
    return Event(title=title, event_date=start, end_date=end, url=url)


def _next_weekday(weekday: int) -> date:
    today = date.today()
    return today + timedelta(days=(weekday - today.weekday()) % 7)


@pytest.mark.unit
@pytest.mark.scraper
class TestRecurringExpansion:
    def test_weekly_series_expands_onto_its_weekday(self, scraper):
        # The reported bug: "Every Saturday 8PM" stored as a 140-day span.
        saturday = _next_weekday(5)
        start = datetime.combine(saturday, datetime.min.time()).replace(hour=20)
        end = start + timedelta(days=140)

        occurrences = scraper._expand_recurring(
            _event('"Marina Nights" Every Saturday 8PM / Coco Beach', start, end)
        )

        assert len(occurrences) > 1
        assert all(o.event_date.weekday() == 5 for o in occurrences)
        assert all(o.event_date.hour == 20 for o in occurrences)

    def test_expanded_occurrences_drop_the_series_end(self, scraper):
        # The series end is not any single night's end, and Eventbrite gives no
        # per-occurrence duration -- leaving it set is what caused the bug.
        saturday = _next_weekday(5)
        start = datetime.combine(saturday, datetime.min.time()).replace(hour=20)
        occurrences = scraper._expand_recurring(
            _event('Marina Nights Every Saturday', start, start + timedelta(days=140))
        )
        assert all(o.end_date is None for o in occurrences)

    def test_occurrences_are_weekly_and_distinctly_addressable(self, scraper):
        friday = _next_weekday(4)
        start = datetime.combine(friday, datetime.min.time()).replace(hour=21)
        occurrences = scraper._expand_recurring(
            _event('Fridays at the Club', start, start + timedelta(days=90))
        )
        dates = [o.event_date for o in occurrences]
        assert all((b - a) == timedelta(weeks=1) for a, b in zip(dates, dates[1:]))
        assert len({o.url for o in occurrences}) == len(occurrences)

    def test_expansion_is_bounded_by_the_horizon(self, scraper):
        saturday = _next_weekday(5)
        start = datetime.combine(saturday, datetime.min.time()).replace(hour=20)
        # A series running for years must not expand for years.
        occurrences = scraper._expand_recurring(
            _event('Every Saturday Forever', start, start + timedelta(days=1000))
        )
        assert len(occurrences) <= scraper.RECURRENCE_HORIZON_WEEKS

    def test_expansion_stops_at_series_end(self, scraper):
        saturday = _next_weekday(5)
        start = datetime.combine(saturday, datetime.min.time()).replace(hour=20)
        end = start + timedelta(days=14)          # only ~3 Saturdays
        occurrences = scraper._expand_recurring(
            _event('Every Saturday Briefly', start, end)
        )
        assert all(o.event_date.date() <= end.date() for o in occurrences)
        assert len(occurrences) == 3

    def test_past_occurrences_are_not_emitted(self, scraper):
        # A series that began months ago starts from today, not from its start.
        saturday = _next_weekday(5) - timedelta(weeks=10)
        start = datetime.combine(saturday, datetime.min.time()).replace(hour=20)
        occurrences = scraper._expand_recurring(
            _event('Every Saturday Long Running', start, start + timedelta(days=200))
        )
        assert all(o.event_date.date() >= date.today() for o in occurrences)


@pytest.mark.unit
@pytest.mark.scraper
class TestNonRecurringLeftAlone:
    def test_genuine_multiday_festival_is_untouched(self, scraper):
        # A festival weekend really does run continuously -- keep its span.
        start = datetime(2026, 3, 28, 11, 0)
        end = datetime(2026, 3, 29, 19, 0)          # ~1.3 days
        result = scraper._expand_recurring(_event('Vegan Street Fair 2026', start, end))
        assert len(result) == 1
        assert result[0].end_date == end

    def test_single_day_event_is_untouched(self, scraper):
        start = datetime(2026, 9, 1, 20, 0)
        end = datetime(2026, 9, 1, 23, 0)
        result = scraper._expand_recurring(_event('One Night Only', start, end))
        assert len(result) == 1
        assert result[0].end_date == end

    def test_long_span_without_stated_cadence_loses_its_end(self, scraper):
        # Undecodable cadence: better to show it once than to blanket months.
        start = datetime(2026, 8, 10, 21, 0)
        result = scraper._expand_recurring(
            _event('Friendo', start, start + timedelta(days=790))
        )
        assert len(result) == 1
        assert result[0].end_date is None
        assert result[0].event_date == start

    def test_event_without_end_date_is_untouched(self, scraper):
        start = datetime(2026, 9, 1, 20, 0)
        result = scraper._expand_recurring(_event('No End Given', start, None))
        assert len(result) == 1
        assert result[0].end_date is None


@pytest.mark.unit
class TestWeekdayDetection:
    @pytest.mark.parametrize('title,expected', [
        ('"Marina Nights" Every Saturday 8PM', 5),
        ('Every Friday Live Jazz', 4),
        ('Trivia Tuesdays', 1),
        ('SUNDAYS at the Beach', 6),
        ('every wednesday karaoke', 2),
        ('Mondays', 0),
        ('A Fast & Furious Legacy', None),
        ('', None),
    ])
    def test_weekday_from_title(self, title, expected):
        assert EventbriteScraper._recurring_weekday(title) == expected

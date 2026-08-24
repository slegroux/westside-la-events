"""
Tests for year inference and the scrapers that were fabricating dates.

Sources publish a month and day with no year. Guessing that year wrongly turned
listings that had already happened into future events: Arcana's blog archive
produced 14 "upcoming" events that were all last year's book signings, and The
Bungalow put a Thursday listing on a 2027 Friday.
"""
from datetime import datetime

import pytest

from src.utils.dates import named_weekday, resolve_year

NOW = datetime(2026, 8, 24, 12, 0)  # a Monday


@pytest.mark.unit
class TestNamedWeekday:
    def test_reads_a_single_weekday(self):
        assert named_weekday('Please join us this Saturday, December 13th') == 5

    def test_ignores_ambiguity(self):
        assert named_weekday('Open Monday through Friday') is None

    def test_handles_plurals(self):
        assert named_weekday('FIRST THURSDAYS - 5PM') == 3

    def test_no_weekday(self):
        assert named_weekday('December 13th, 4-6PM') is None
        assert named_weekday('') is None


@pytest.mark.unit
class TestResolveYear:
    def test_weekday_checksum_rejects_a_stale_listing(self):
        """"Saturday 9/27" is a 2025 Saturday; 2026-09-27 is a Sunday."""
        assert resolve_year(9, 27, weekday=5, now=NOW) is None

    def test_weekday_checksum_accepts_a_matching_year(self):
        # 2026-11-26 is a Thursday.
        resolved = resolve_year(11, 26, weekday=3, now=NOW)
        assert resolved == datetime(2026, 11, 26)

    def test_weekday_checksum_can_reach_next_year(self):
        # 2027-01-02 is a Saturday; 2026-01-02 has already passed.
        resolved = resolve_year(1, 2, weekday=5, now=NOW)
        assert resolved is not None
        assert resolved.year == 2027
        assert resolved.weekday() == 5

    def test_past_date_without_a_weekday_is_not_rolled_forward(self):
        """The resurrection bug: a past date must not become next year's."""
        assert resolve_year(7, 25, weekday=None, now=NOW) is None

    def test_future_date_without_a_weekday_is_kept(self):
        assert resolve_year(12, 5, weekday=None, now=NOW) == datetime(2026, 12, 5)

    def test_time_is_preserved(self):
        resolved = resolve_year(12, 5, weekday=None, hour=17, minute=30, now=NOW)
        assert (resolved.hour, resolved.minute) == (17, 30)

    def test_impossible_date_returns_none(self):
        assert resolve_year(2, 30, weekday=None, now=NOW) is None

    def test_never_returns_a_date_in_the_past(self):
        for month in range(1, 13):
            resolved = resolve_year(month, 15, weekday=None, now=NOW)
            if resolved is not None:
                assert resolved >= NOW.replace(hour=0, minute=0)

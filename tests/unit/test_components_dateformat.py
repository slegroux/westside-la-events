"""
Unit tests for the _format_event_date helper in src.web.components.
"""
import pytest
from datetime import datetime

from src.data.models import Event
from src.web.components import _format_event_date


@pytest.mark.unit
class TestFormatEventDate:
    """Test _format_event_date rendering of single-day, multi-day, and missing dates."""

    def test_single_day_event(self):
        """Only event_date set -> weekday + date + time, matching the code's strftime."""
        start = datetime(2026, 5, 29, 19, 0)  # Fri, 7:00 PM
        event = Event(title='Single', event_date=start)

        result = _format_event_date(event)

        expected = start.strftime("%a, %b %d, %Y at %I:%M %p")
        assert result == expected
        assert result == 'Fri, May 29, 2026 at 07:00 PM'

    def test_same_year_multi_day_range(self):
        """end_date on a later day in the same year -> compact range, start has NO year."""
        start = datetime(2026, 5, 29, 19, 0)
        end = datetime(2026, 5, 30, 22, 0)
        event = Event(title='Multi', event_date=start, end_date=end)

        result = _format_event_date(event)

        expected = f'{start.strftime("%b %d")} – {end.strftime("%b %d, %Y")}'
        assert result == expected
        assert result == 'May 29 – May 30, 2026'

    def test_cross_year_multi_day_range(self):
        """Span crosses a year boundary -> start INCLUDES its year for clarity."""
        start = datetime(2025, 12, 29, 19, 0)
        end = datetime(2026, 1, 2, 22, 0)
        event = Event(title='Cross-year', event_date=start, end_date=end)

        result = _format_event_date(event)

        expected = f'{start.strftime("%b %d, %Y")} – {end.strftime("%b %d, %Y")}'
        assert result == expected
        assert result == 'Dec 29, 2025 – Jan 02, 2026'

    def test_no_event_date(self):
        """Missing event_date -> 'Date TBA'."""
        event = Event(title='No date')

        assert _format_event_date(event) == 'Date TBA'

    def test_end_date_same_day_renders_single(self):
        """end_date on the SAME calendar day does not produce a range (uses single-day format)."""
        start = datetime(2026, 5, 29, 19, 0)
        end = datetime(2026, 5, 29, 21, 0)  # same date, later time
        event = Event(title='Same day end', event_date=start, end_date=end)

        result = _format_event_date(event)

        # end.date() is not > start.date(), so it falls through to single-day rendering.
        assert result == start.strftime("%a, %b %d, %Y at %I:%M %p")
        assert '–' not in result

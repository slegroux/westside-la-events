"""
Unit tests for the iCalendar (.ics) generation utilities in src/utils/calendar.py.
"""
import pytest
from datetime import datetime, timedelta

from src.data.models import Event
from src.utils.calendar import generate_ics, get_ics_filename


@pytest.mark.unit
class TestGenerateICS:
    """Test generate_ics() output structure and formatting."""

    def test_returns_string(self, sample_event):
        """generate_ics returns a string."""
        ics = generate_ics(sample_event)
        assert isinstance(ics, str)

    def test_vcalendar_wrapper(self, sample_event):
        """Output begins/ends with VCALENDAR markers."""
        ics = generate_ics(sample_event)
        assert ics.startswith('BEGIN:VCALENDAR')
        assert ics.endswith('END:VCALENDAR')

    def test_vevent_present(self, sample_event):
        """Output contains a VEVENT block."""
        ics = generate_ics(sample_event)
        assert 'BEGIN:VEVENT' in ics
        assert 'END:VEVENT' in ics
        # VEVENT must be nested inside VCALENDAR
        assert ics.index('BEGIN:VCALENDAR') < ics.index('BEGIN:VEVENT')
        assert ics.index('END:VEVENT') < ics.index('END:VCALENDAR')

    def test_required_calendar_headers(self, sample_event):
        """RFC 5545 calendar-level properties are present."""
        ics = generate_ics(sample_event)
        assert 'VERSION:2.0' in ics
        assert 'PRODID:-//Westside LA Events//NONSGML Event//EN' in ics
        assert 'CALSCALE:GREGORIAN' in ics
        assert 'METHOD:PUBLISH' in ics

    def test_crlf_line_endings(self, sample_event):
        """Lines are joined with CRLF as required by RFC 5545."""
        ics = generate_ics(sample_event)
        # Every line break must be a CRLF, never a bare LF.
        assert '\r\n' in ics
        # No bare LF (every \n is preceded by \r).
        assert ics.replace('\r\n', '') .find('\n') == -1

    def test_dtstart_dtend_format(self, sample_event):
        """DTSTART/DTEND match the event dates in YYYYMMDDTHHMMSS format."""
        ics = generate_ics(sample_event)
        expected_start = sample_event.event_date.strftime('%Y%m%dT%H%M%S')
        expected_end = sample_event.end_date.strftime('%Y%m%dT%H%M%S')
        assert f'DTSTART:{expected_start}' in ics
        assert f'DTEND:{expected_end}' in ics

    def test_dtstart_has_no_timezone_suffix(self, sample_event):
        """Formatted dates contain no timezone 'Z' suffix (naive local time)."""
        ics = generate_ics(sample_event)
        for line in ics.split('\r\n'):
            if line.startswith('DTSTART:') or line.startswith('DTEND:'):
                value = line.split(':', 1)[1]
                assert not value.endswith('Z')
                # Format is exactly 15 chars: 8 date + T + 6 time
                assert len(value) == 15
                assert value[8] == 'T'

    def test_dtend_defaults_to_two_hours_when_no_end_date(self):
        """When end_date is missing, DTEND is 2 hours after DTSTART."""
        start = datetime(2026, 6, 1, 19, 30, 0)
        event = Event(
            title="No End Event",
            event_date=start,
            source="test",
            url="https://example.com/e",
        )
        ics = generate_ics(event)
        expected_end = (start + timedelta(hours=2)).strftime('%Y%m%dT%H%M%S')
        assert f'DTSTART:{start.strftime("%Y%m%dT%H%M%S")}' in ics
        assert f'DTEND:{expected_end}' in ics

    def test_dtstamp_present(self, sample_event):
        """DTSTAMP property is present and well-formed."""
        ics = generate_ics(sample_event)
        stamp_lines = [l for l in ics.split('\r\n') if l.startswith('DTSTAMP:')]
        assert len(stamp_lines) == 1
        value = stamp_lines[0].split(':', 1)[1]
        assert len(value) == 15
        assert value[8] == 'T'

    def test_uid_present(self, sample_event):
        """UID uses the event id and the westsidelaevents.com domain."""
        sample_event.id = 42
        ics = generate_ics(sample_event)
        assert 'UID:42@westsidelaevents.com' in ics

    def test_summary_location_description_present(self, sample_event):
        """SUMMARY, LOCATION, and DESCRIPTION fields are present."""
        ics = generate_ics(sample_event)
        # sample_event has plain ASCII values with no special chars in these.
        assert f'SUMMARY:{sample_event.title}' in ics
        assert 'DESCRIPTION:' in ics
        assert 'LOCATION:' in ics

    def test_location_combines_venue_and_address(self, sample_event):
        """LOCATION combines venue and address; the joining comma is escaped."""
        ics = generate_ics(sample_event)
        # Source joins venue + address with ', ', then escapes commas to '\,'.
        # sample_event.address itself contains commas, which are also escaped.
        location_line = [l for l in ics.split('\r\n') if l.startswith('LOCATION:')][0]
        location_value = location_line.split(':', 1)[1]
        assert sample_event.venue_name in location_value
        # The venue/address separator comma is escaped.
        assert '\\,' in location_value
        # No unescaped comma remains.
        assert ', ' not in location_value.replace('\\, ', '')

    def test_location_tba_when_no_venue_or_address(self):
        """When venue and address are empty, LOCATION is 'Location TBA'."""
        event = Event(
            title="Mystery Event",
            event_date=datetime(2026, 6, 1, 12, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        assert 'LOCATION:Location TBA' in ics

    def test_default_description_when_missing(self):
        """A missing description falls back to the default text."""
        event = Event(
            title="No Desc Event",
            description="",
            event_date=datetime(2026, 6, 1, 12, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        assert 'DESCRIPTION:No description available' in ics

    def test_status_and_sequence(self, sample_event):
        """STATUS and SEQUENCE trailer fields are present."""
        ics = generate_ics(sample_event)
        assert 'STATUS:CONFIRMED' in ics
        assert 'SEQUENCE:0' in ics

    def test_url_included_when_present(self, sample_event):
        """URL line is included when the event has a url."""
        ics = generate_ics(sample_event)
        assert f'URL:{sample_event.url}' in ics

    def test_url_omitted_when_absent(self):
        """URL line is omitted when the event has no url."""
        event = Event(
            title="No URL Event",
            event_date=datetime(2026, 6, 1, 12, 0, 0),
            source="test",
            url="",
        )
        ics = generate_ics(event)
        assert 'URL:' not in ics

    def test_category_included_when_present(self, sample_event):
        """CATEGORIES line is included when category is set."""
        ics = generate_ics(sample_event)
        assert f'CATEGORIES:{sample_event.category}' in ics

    def test_category_omitted_when_absent(self):
        """CATEGORIES line is omitted when category is empty."""
        event = Event(
            title="No Category",
            event_date=datetime(2026, 6, 1, 12, 0, 0),
            source="test",
            category="",
        )
        ics = generate_ics(event)
        assert 'CATEGORIES:' not in ics

    def test_geo_included_when_coordinates_present(self, sample_event):
        """GEO line uses 'lat;lon' format when coordinates are present."""
        ics = generate_ics(sample_event)
        assert f'GEO:{sample_event.latitude};{sample_event.longitude}' in ics

    def test_geo_omitted_when_no_coordinates(self):
        """GEO line is omitted when coordinates are missing."""
        event = Event(
            title="No Geo Event",
            event_date=datetime(2026, 6, 1, 12, 0, 0),
            source="test",
            latitude=None,
            longitude=None,
        )
        ics = generate_ics(event)
        assert 'GEO:' not in ics


@pytest.mark.unit
class TestGenerateICSEscaping:
    """Test special-character escaping in generate_ics()."""

    def test_comma_escaped_in_title(self):
        """Commas in the title are escaped with a backslash."""
        event = Event(
            title="Jazz, Blues, and Soul",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        assert 'SUMMARY:Jazz\\, Blues\\, and Soul' in ics

    def test_semicolon_escaped_in_title(self):
        """Semicolons in the title are escaped with a backslash."""
        event = Event(
            title="Concert; Afterparty",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        assert 'SUMMARY:Concert\\; Afterparty' in ics

    def test_newline_escaped_in_description(self):
        """Newlines in description become literal backslash-n and CR is stripped."""
        event = Event(
            title="Multiline Event",
            description="Line one\nLine two\r\nLine three",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        # \n -> \\n, and \r is removed.
        description_line = [
            l for l in ics.split('\r\n') if l.startswith('DESCRIPTION:')
        ]
        assert len(description_line) == 1
        value = description_line[0].split(':', 1)[1]
        assert value == 'Line one\\nLine two\\nLine three'
        # The literal carriage return must not survive into the description value.
        assert '\r' not in value

    def test_comma_and_semicolon_escaped_in_description(self):
        """Commas and semicolons in description are escaped."""
        event = Event(
            title="Event",
            description="Tickets, drinks; snacks",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        assert 'DESCRIPTION:Tickets\\, drinks\\; snacks' in ics

    def test_comma_escaped_in_location(self):
        """Commas in venue/address are escaped in the LOCATION value."""
        event = Event(
            title="Event",
            venue_name="The Venue, Room 5",
            address="123 Main St, Santa Monica, CA",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        location_line = [
            l for l in ics.split('\r\n') if l.startswith('LOCATION:')
        ][0]
        value = location_line.split(':', 1)[1]
        # Every comma (including the venue/address join) is escaped.
        assert ',' not in value.replace('\\,', '')

    def test_description_backslash_not_escaped(self):
        """
        Documents ACTUAL behavior: a literal backslash in the description is
        NOT escaped. Per RFC 5545 the backslash should itself be escaped
        (and escaped first), so this is a latent escaping bug. The test pins
        current behavior rather than asserting RFC-correct behavior.
        """
        event = Event(
            title="Event",
            description=r"Path C:\temp",
            event_date=datetime(2026, 6, 1, 20, 0, 0),
            source="test",
        )
        ics = generate_ics(event)
        # The backslash passes through unescaped.
        assert 'DESCRIPTION:Path C:\\temp' in ics


@pytest.mark.unit
class TestGetICSFilename:
    """Test get_ics_filename() filename generation."""

    def test_basic_filename(self):
        """Title becomes a lowercase, hyphenated slug with date and .ics ext."""
        event = Event(
            title="Summer Jazz Festival",
            event_date=datetime(2026, 7, 4, 18, 0, 0),
            source="test",
        )
        assert get_ics_filename(event) == 'summer-jazz-festival-2026-07-04.ics'

    def test_ends_with_ics_extension(self, sample_event):
        """Filename always ends with the .ics extension."""
        assert get_ics_filename(sample_event).endswith('.ics')

    def test_date_appended(self):
        """The event date is appended in YYYY-MM-DD form."""
        event = Event(
            title="Event",
            event_date=datetime(2026, 1, 5, 9, 0, 0),
            source="test",
        )
        assert get_ics_filename(event) == 'event-2026-01-05.ics'

    def test_special_characters_stripped(self):
        """Punctuation is removed and not present in the slug."""
        event = Event(
            title="Art & Music: A \"Special\" Event!",
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        filename = get_ics_filename(event)
        # Only word chars, hyphens, and the date/extension remain.
        slug = filename.replace('-2026-03-10.ics', '')
        assert slug == 'art-music-a-special-event'
        for ch in '&:"!':
            assert ch not in filename

    def test_multiple_spaces_collapsed(self):
        """Runs of spaces/hyphens collapse to a single hyphen."""
        event = Event(
            title="Big    Show   Tonight",
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        assert get_ics_filename(event) == 'big-show-tonight-2026-03-10.ics'

    def test_leading_trailing_separators_stripped(self):
        """Leading/trailing hyphens introduced by punctuation are stripped."""
        event = Event(
            title="!!! Party !!!",
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        # Leading/trailing '!' become nothing, surrounding spaces collapse and
        # are stripped, leaving just 'party'.
        assert get_ics_filename(event) == 'party-2026-03-10.ics'

    def test_long_title_truncated_to_50_chars(self):
        """The slug portion is truncated to 50 characters."""
        long_title = "a" * 100
        event = Event(
            title=long_title,
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        filename = get_ics_filename(event)
        slug = filename.replace('-2026-03-10.ics', '')
        assert len(slug) == 50
        assert slug == 'a' * 50

    def test_lowercased(self):
        """The slug is lowercased."""
        event = Event(
            title="UPPER Case TITLE",
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        filename = get_ics_filename(event)
        slug = filename.replace('-2026-03-10.ics', '')
        assert slug == slug.lower()
        assert slug == 'upper-case-title'

    def test_underscores_preserved(self):
        """Underscores are word characters and survive the slug cleaning."""
        event = Event(
            title="my_event_name",
            event_date=datetime(2026, 3, 10, 12, 0, 0),
            source="test",
        )
        assert get_ics_filename(event) == 'my_event_name-2026-03-10.ics'

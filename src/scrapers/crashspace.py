"""
Scraper for CRASH Space (Los Angeles hackerspace) events.
Source: https://blog.crashspace.org/events/

The events page is a thin wrapper around a public Google Calendar, so this
reads that calendar's ICS feed directly. The feed carries the full history
(1700+ entries back to 2019) plus recurring rules for the weekly meetups, so
occurrences are expanded over a forward window rather than taken literally.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from .base import BaseScraper
from src.data.models import Event


LA_TZ = ZoneInfo('America/Los_Angeles')


class CrashSpaceScraper(BaseScraper):
    """Scraper for the CRASH Space public Google Calendar."""

    ICS_URL = (
        'https://calendar.google.com/calendar/ical/'
        'crashspacela%40gmail.com/public/basic.ics'
    )

    # CRASH Space's own address; the feed's LOCATION field is written a dozen
    # different ways ("Crash Space", "10526 Venice Blvd Culver City CA 90232"),
    # so the canonical address is used instead of geocoding each variant.
    VENUE_NAME = 'CRASH Space'
    ADDRESS = '10526 Venice Blvd, Culver City, CA 90232'

    # How far ahead recurring meetups are expanded.
    LOOKAHEAD_DAYS = 90

    def __init__(self):
        super().__init__('CRASH Space')
        self.base_url = 'https://blog.crashspace.org'
        self.events_url = f'{self.base_url}/events/'

    def scrape(self) -> List[Event]:
        """Read the ICS feed and emit upcoming occurrences."""
        self.log("Starting scrape...")
        events = []

        try:
            resp = self.session.get(self.ICS_URL, timeout=60)
            resp.raise_for_status()

            components = self._parse_ics(resp.text)
            self.log(f"Parsed {len(components)} calendar entries")

            window_start = datetime.now()
            window_end = window_start + timedelta(days=self.LOOKAHEAD_DAYS)

            for start, component in self._occurrences(components, window_start, window_end):
                try:
                    event = self._build_event(component, start)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error building event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    # -- ICS parsing --------------------------------------------------------

    def _parse_ics(self, text: str) -> List[Dict[str, str]]:
        """Parse VEVENT blocks into {property: raw value} dicts.

        Long ICS properties are wrapped onto continuation lines beginning with
        a space, so the text is unfolded before anything is matched.
        """
        unfolded = text.replace('\r\n', '\n').replace('\n ', '').replace('\n\t', '')

        components = []
        for block in re.findall(r'BEGIN:VEVENT\n(.*?)END:VEVENT', unfolded, re.S):
            component = {}
            for line in block.split('\n'):
                if ':' not in line:
                    continue
                name, _, value = line.partition(':')
                # Keep parameters (TZID, VALUE=DATE) attached to the key so the
                # datetime parser can read them.
                component[name.strip()] = value.strip()
            if component:
                components.append(component)
        return components

    def _get(self, component: Dict[str, str], prop: str):
        """Look up a property regardless of its parameters (e.g. DTSTART;TZID=...)."""
        for key, value in component.items():
            if key == prop or key.startswith(f'{prop};'):
                return key, value
        return None, None

    def _parse_dt(self, key: Optional[str], value: Optional[str]) -> Optional[datetime]:
        """Parse an ICS date/date-time into a naive LA-local datetime."""
        if not value:
            return None

        raw = value.split(',')[0].strip()

        try:
            if raw.endswith('Z'):
                aware = datetime.strptime(raw, '%Y%m%dT%H%M%SZ').replace(
                    tzinfo=ZoneInfo('UTC')
                )
                return aware.astimezone(LA_TZ).replace(tzinfo=None)
            if 'T' in raw:
                # Floating or TZID-qualified; Google emits LA-local times here.
                return datetime.strptime(raw, '%Y%m%dT%H%M%S')
            return datetime.strptime(raw, '%Y%m%d')
        except ValueError:
            return None

    # -- Recurrence ---------------------------------------------------------

    def _occurrences(self, components, window_start, window_end):
        """Yield (start, component) pairs falling inside the window.

        Handles the three shapes Google emits: one-off events, recurring
        masters with RRULE/EXDATE, and RECURRENCE-ID entries that override or
        cancel a single occurrence of a master.
        """
        overrides = set()
        for component in components:
            rec_key, rec_value = self._get(component, 'RECURRENCE-ID')
            if rec_value:
                uid = component.get('UID', '')
                moment = self._parse_dt(rec_key, rec_value)
                if moment:
                    overrides.add((uid, moment))

        results = []
        for component in components:
            start_key, start_value = self._get(component, 'DTSTART')
            start = self._parse_dt(start_key, start_value)
            if not start:
                continue

            _, rrule_value = self._get(component, 'RRULE')
            if not rrule_value:
                if window_start <= start <= window_end:
                    results.append((start, component))
                continue

            uid = component.get('UID', '')
            excluded = self._exception_dates(component)

            try:
                rule = rrulestr(rrule_value, dtstart=start)
                occurrences = rule.between(window_start, window_end, inc=True)
            except (ValueError, TypeError) as e:
                self.log(f"Skipping unparseable RRULE '{rrule_value}': {e}")
                continue

            for moment in occurrences:
                if moment in excluded:
                    continue
                # A RECURRENCE-ID entry elsewhere in the feed already carries
                # this occurrence (moved, edited, or cancelled).
                if (uid, moment) in overrides:
                    continue
                results.append((moment, component))

        results.sort(key=lambda pair: pair[0])
        return results

    def _exception_dates(self, component: Dict[str, str]) -> set:
        """Collect EXDATE values, which cancel individual occurrences."""
        excluded = set()
        for key, value in component.items():
            if key != 'EXDATE' and not key.startswith('EXDATE;'):
                continue
            for part in value.split(','):
                moment = self._parse_dt(key, part)
                if moment:
                    excluded.add(moment)
        return excluded

    # -- Event construction -------------------------------------------------

    def _build_event(self, component: Dict[str, str], start: datetime) -> Optional[Event]:
        title = self._unescape(component.get('SUMMARY', ''))
        if not title:
            return None

        description = self._unescape(component.get('DESCRIPTION', ''))
        # Descriptions are HTML fragments in this feed.
        description = re.sub(r'<[^>]+>', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip()

        end_key, end_value = self._get(component, 'DTEND')
        end = self._parse_dt(end_key, end_value)
        # DTEND belongs to the master occurrence; shift it by the same offset
        # so expanded occurrences keep their real duration.
        start_key, start_value = self._get(component, 'DTSTART')
        master_start = self._parse_dt(start_key, start_value)
        if end and master_start:
            end = start + (end - master_start)

        # Most feed entries carry no URL of their own. Falling back to the bare
        # events page gave every occurrence an identical URL, and dedup matches
        # on URL first -- so two different classes on the same day collapsed
        # into one. Qualify the fallback with the entry's UID and start time so
        # each occurrence is distinguishable.
        url = component.get('URL')
        if not url:
            uid = component.get('UID', '')
            fragment = f"{uid}-{start:%Y%m%dT%H%M}" if uid else f"{start:%Y%m%dT%H%M}"
            url = f"{self.events_url}#{fragment}"

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.ADDRESS,
            event_date=start,
            end_date=end,
            url=url,
            is_free=True,
            price_note='',
        )

    def _unescape(self, value: str) -> str:
        """Undo ICS escaping (\\, \\; \\n) in text properties."""
        if not value:
            return ''
        out = value.replace('\\n', ' ').replace('\\,', ',').replace('\\;', ';')
        return self.clean_text(out.replace('\\\\', '\\'))

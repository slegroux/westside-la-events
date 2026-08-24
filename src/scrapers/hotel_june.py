"""
Scraper for Hotel June West LA happenings.
Source: https://www.thehoteljune.com/west-los-angeles/happenings/

The page publishes schema.org Event objects in a JSON-LD @graph, with full
addresses. Most of the calendar is standing weekly programming at Caravan
Cantina, expressed as an eventSchedule with a byDay list and an open-ended
startDate in the past, so those are expanded forward instead of being taken as
single (long-expired) events.
"""
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional

from .base import BaseScraper, normalize_event_datetime
from src.data.models import Event


WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}


class HotelJuneScraper(BaseScraper):
    """Scraper for Hotel June West LA's happenings calendar."""

    DEFAULT_VENUE = 'Hotel June West LA'
    DEFAULT_ADDRESS = '8639 Lincoln Blvd, Los Angeles, CA 90045'

    # How far ahead standing weekly programming is expanded.
    LOOKAHEAD_DAYS = 60

    _LD_RE = re.compile(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
    )

    def __init__(self):
        super().__init__('Hotel June')
        self.base_url = 'https://www.thehoteljune.com'
        self.events_url = f'{self.base_url}/west-los-angeles/happenings/'

    def scrape(self) -> List[Event]:
        """Read the page's JSON-LD events."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch happenings page")
                return events

            nodes = self._event_nodes(html)
            self.log(f"Found {len(nodes)} event objects")

            for node in nodes:
                try:
                    events.extend(self._parse_node(node))
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _event_nodes(self, html: str) -> List[dict]:
        """Collect Event objects from every JSON-LD block on the page."""
        nodes = []
        for block in self._LD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            candidates = data.get('@graph') if isinstance(data, dict) else None
            if candidates is None:
                candidates = data if isinstance(data, list) else [data]
            for node in candidates:
                if isinstance(node, dict) and node.get('@type') == 'Event':
                    nodes.append(node)
        return nodes

    def _parse_node(self, node: dict) -> List[Event]:
        title = self.clean_text(node.get('name', ''))
        if not title:
            return []

        start = self._parse_timestamp(node.get('startDate'))
        if not start:
            return []
        end = self._parse_timestamp(node.get('endDate'))

        venue_name, address = self._location(node)
        if not address:
            # A listing with no street address is a neighborhood recommendation
            # (a citywide festival, say), not a hotel happening. Attributing it
            # to the hotel's own address would misplace it on the map.
            return []
        description = self.clean_text(node.get('description', ''))

        starts = self._schedule_starts(node, start, end)

        events = []
        for moment in starts:
            duration = (end - start) if (end and start and end > start) else None
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=moment,
                end_date=(moment + duration) if duration and len(starts) == 1 else None,
                url=node.get('@id') or self.events_url,
                price_note='',
            )
            if event:
                events.append(event)
        return events

    def _schedule_starts(self, node: dict, start: datetime,
                         end: Optional[datetime]) -> List[datetime]:
        """Work out which dates this event actually runs on.

        Standing weekly programming carries an eventSchedule byDay list and a
        startDate months in the past; those are expanded across the lookahead
        window. Everything else is a single dated event.
        """
        now = datetime.now()
        schedule = node.get('eventSchedule') or {}
        days = schedule.get('byDay') or []
        if isinstance(days, str):
            days = [days]

        weekdays = []
        for day in days:
            name = str(day).rsplit('/', 1)[-1].lower()
            if name in WEEKDAYS:
                weekdays.append(WEEKDAYS[name])

        if not weekdays:
            moment = normalize_event_datetime(start)
            # A one-off that has already finished (or started, for a run with
            # an end date) is stale listing copy, not an upcoming event.
            finished = normalize_event_datetime(end) if end else moment
            return [moment] if finished >= now else []

        hour, minute = self._schedule_time(schedule, start)
        window_end = now + timedelta(days=self.LOOKAHEAD_DAYS)
        series_end = normalize_event_datetime(end) if end else None

        occurrences = []
        day_cursor = now.date()
        while day_cursor <= window_end.date():
            if day_cursor.weekday() in weekdays:
                moment = datetime.combine(day_cursor, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
                if moment >= now and (series_end is None or moment <= series_end):
                    occurrences.append(moment)
            day_cursor += timedelta(days=1)
        return occurrences

    def _schedule_time(self, schedule: dict, start: datetime):
        """Start time for a recurring occurrence, preferring the schedule's."""
        raw = schedule.get('startTime')
        if raw:
            try:
                hour, _, minute = raw.partition(':')
                return int(hour), int(minute or 0)
            except ValueError:
                pass
        local = normalize_event_datetime(start)
        return local.hour, local.minute

    def _location(self, node: dict):
        """Venue name and address, falling back to the hotel itself."""
        location = node.get('location') or {}
        name = self.clean_text(location.get('name', '')) or self.DEFAULT_VENUE

        address = location.get('address') or {}
        if isinstance(address, dict):
            parts = [
                address.get('streetAddress'),
                address.get('addressLocality'),
                address.get('addressRegion'),
                address.get('postalCode'),
            ]
            joined = ', '.join(p for p in parts if p)
        else:
            joined = self.clean_text(str(address))

        # Some entries point at the city rather than a street address; the
        # caller drops those instead of guessing a location for them.
        if not joined or not any(char.isdigit() for char in joined):
            return name, ''
        return name, joined

    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

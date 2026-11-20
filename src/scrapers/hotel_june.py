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
from collections import Counter
from datetime import datetime, timedelta, timezone
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

    # The hotel's own coordinates (from its JSON-LD); every happening is on site.
    LATITUDE = 33.9587527
    LONGITUDE = -118.4187291

    # How far ahead standing weekly programming is expanded.
    LOOKAHEAD_DAYS = 60

    _LD_RE = re.compile(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
    )

    def __init__(self):
        super().__init__('Hotel June')
        self.base_url = 'https://www.thehoteljune.com'
        self.events_url = f'{self.base_url}/west-los-angeles/happenings/'
        self._graph = {}
        # How the page's timestamps relate to real LA time, measured per scrape
        # from the scheduled nodes (see _measure_clock_skew): None (the clock
        # digits are LA local time), 'utc' (a UTC clock), or a fixed timedelta.
        self._clock_mode = None

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
            self._measure_clock_skew(nodes)

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
        """Collect Event objects from every JSON-LD block on the page.

        Also indexes every node by @id: events refer to their venue by
        ``{"@id": ...}`` and the address lives on the referenced node.
        """
        nodes = []
        self._graph = {}
        for block in self._LD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            candidates = data.get('@graph') if isinstance(data, dict) else None
            if candidates is None:
                candidates = data if isinstance(data, list) else [data]
            for node in candidates:
                if not isinstance(node, dict):
                    continue
                if node.get('@id'):
                    self._graph.setdefault(node['@id'], node)
                if node.get('@type') == 'Event':
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

        image = node.get('image')
        starts = self._schedule_starts(node, start, end)
        duration = self._duration(node, start, end)

        events = []
        for moment in starts:
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=moment,
                end_date=(moment + duration) if duration else None,
                url=node.get('@id') or self.events_url,
                image_url=image if isinstance(image, str) else '',
                latitude=self.LATITUDE,
                longitude=self.LONGITUDE,
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

        # Every live series states its frequency; one that doesn't is skipped
        # rather than assumed weekly (never invent occurrences).
        frequency = str(schedule.get('repeatFrequency') or '').upper()
        if frequency not in ('P1W', 'P7D'):
            self.log(f"Skipping '{node.get('name')}': unsupported repeatFrequency {frequency or '(none)'}")
            return []

        hour, minute = self._schedule_time(schedule, start)
        window_end = now + timedelta(days=self.LOOKAHEAD_DAYS)
        # The node's own endDate is just the first occurrence's end; only the
        # schedule's endDate bounds the series.
        series_end = self._schedule_end(schedule)
        # The series does not exist before its own startDate (a local date).
        day_cursor = now.date()
        series_start = self._schedule_start(schedule)
        if series_start and series_start > day_cursor:
            day_cursor = series_start

        occurrences = []
        while day_cursor <= window_end.date():
            if day_cursor.weekday() in weekdays:
                moment = datetime.combine(day_cursor, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
                if moment >= now and (series_end is None or moment <= series_end):
                    occurrences.append(moment)
            day_cursor += timedelta(days=1)
        return occurrences

    @staticmethod
    def _schedule_start(schedule: dict):
        """First day of the schedule (a local date), if it has one."""
        raw = schedule.get('startDate')
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw)[:10]).date()
        except ValueError:
            return None

    def _schedule_end(self, schedule: dict) -> Optional[datetime]:
        """Last moment of the schedule's own endDate, if it has one."""
        raw = schedule.get('endDate')
        if not raw:
            return None
        try:
            last_day = datetime.fromisoformat(str(raw)[:10])
        except ValueError:
            return None
        return last_day + timedelta(days=1)

    def _duration(self, node: dict, start: datetime,
                  end: Optional[datetime]) -> Optional[timedelta]:
        """How long one occurrence runs, if the source says."""
        schedule = node.get('eventSchedule') or {}
        begin = self._clock(schedule.get('startTime'))
        finish = self._clock(schedule.get('endTime'))
        if schedule and begin and finish and finish > begin:
            return timedelta(hours=finish[0] - begin[0], minutes=finish[1] - begin[1])
        if not schedule and end and end > start:
            return end - start
        return None

    @staticmethod
    def _clock(raw: Optional[str]):
        """Parse 'HH:MM[:SS]' into (hour, minute), or None."""
        try:
            hour, _, rest = str(raw).partition(':')
            return int(hour), int(rest.partition(':')[0] or 0)
        except ValueError:
            return None

    def _schedule_time(self, schedule: dict, start: datetime):
        """Start time for a recurring occurrence, preferring the schedule's."""
        clock = self._clock(schedule.get('startTime'))
        if clock:
            return clock
        local = normalize_event_datetime(start)
        return local.hour, local.minute

    def _location(self, node: dict):
        """Venue name and address, falling back to the hotel itself."""
        location = node.get('location') or {}
        if isinstance(location, dict) and len(location) == 1 and '@id' in location:
            location = self._graph.get(location['@id'], {})
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

    def _measure_clock_skew(self, nodes: List[dict]) -> None:
        """Work out how this page's startDate stamps relate to real LA time.

        The site has stamped a UTC clock reading with a "-08:00" label (a 3 PM
        seating is "23:00:00-08:00"). It may fix the label, so the stated offset
        cannot be trusted either way. Scheduled nodes carry both the stamped
        startDate and the schedule's own local startTime, which gives the skew
        directly: 8 h (7 h in PDT) for the mislabelled page, 0 when they agree.
        With nothing to measure the skew is 0, i.e. the stamps are taken at
        their word.
        """
        votes = Counter()
        for node in nodes:
            schedule = node.get('eventSchedule') or {}
            clock = self._clock(schedule.get('startTime'))
            raw = node.get('startDate')
            stamp = self._stamp(raw)
            # A date-only stamp has no clock reading to compare.
            if not clock or not stamp or 'T' not in str(raw):
                continue
            wall, _ = stamp
            local_start = timedelta(hours=clock[0], minutes=clock[1])
            seen = timedelta(hours=wall.hour, minutes=wall.minute)
            skew = (seen - local_start + timedelta(hours=12)) % timedelta(days=1) \
                - timedelta(hours=12)
            as_utc = normalize_event_datetime(wall.replace(tzinfo=timezone.utc))
            if skew and timedelta(hours=as_utc.hour, minutes=as_utc.minute) == local_start:
                votes['utc'] += 1  # 8 h in PST and 7 h in PDT are one vote
            else:
                votes[skew] += 1

        self._clock_mode = None
        if not votes:
            return
        winner, count = votes.most_common(1)[0]
        # A lone odd node (a first occurrence the site mis-stamped) must not
        # move the whole page: only a clear majority changes anything.
        if winner and count * 2 > sum(votes.values()):
            self._clock_mode = winner
            self.log(f"Page timestamps measured as {winner if winner == 'utc' else f'{winner} ahead'}; correcting")

    @staticmethod
    def _stamp(value: Optional[str]):
        """(naive wall-clock reading, stated offset or None) of an ISO stamp."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
        return parsed.replace(tzinfo=None), parsed.tzinfo

    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        """Parse an event's startDate/endDate into a naive LA-local datetime.

        Corrects for the mode measured by _measure_clock_skew. A UTC clock
        reading is converted through the tz database, so a stamp in PDT lands
        7 h behind and one in PST 8 h. Any other measured skew is subtracted as
        is. With no skew the clock digits already are LA local time: the stated
        offset is ignored too, since a fixed "-08:00" label on a July stamp is
        as unreliable as the clock it came with.
        """
        stamp = self._stamp(value)
        if not stamp:
            return None
        wall, _ = stamp
        if self._clock_mode == 'utc':
            return normalize_event_datetime(wall.replace(tzinfo=timezone.utc))
        if self._clock_mode:
            return wall - self._clock_mode
        return wall

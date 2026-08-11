"""
Scraper for TRiP Santa Monica.
Source: https://www.tripsantamonica.com/trip-santa-monica-events

TRiP is a bar/music room at 2101 Lincoln Blvd running standing weekly nights
rather than a dated calendar. The site has two event pages and only one of them
is scrapable:

  * /calendar -- looks like the obvious target and is what this scraper used to
    read, but the calendar is not on the page at all. It is an
    eventscalendar.co widget inside an iframe, and that widget only loads data
    when handed a Wix-signed ``instance`` token. Neither the page HTML nor a
    direct fetch of the widget URL contains a single event, which is why this
    scraper returned 0 events for its whole life.
  * /trip-santa-monica-events ("Weekly Shows") -- real content, rendered into
    the DOM. Each show is an ``<h5>`` that begins with a weekday, followed by
    prose and a time ("Every Friday night @ 7pm", "7:15pm signup, 8pm start").

So we read the Weekly Shows page and expand each standing night into concrete
occurrences. The page is Wix and client-rendered, hence fetch_page_js.

Horizon: unlike a seasonal series, a bar's weekly night is open-ended by
definition -- there is no end date to find, and refusing to project one would
mean never listing this venue at all. We therefore emit a bounded WEEKS_AHEAD
window and let a later scrape extend it, rather than projecting indefinitely.
If the venue drops a night, stale occurrences age out within that window.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run dedup;
each occurrence carries a #YYYY-MM-DD URL fragment so same-titled nights on
different dates stay distinct.
"""
import re
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


_WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}


class TrippScraper(BaseScraper):
    """Scraper for TRiP Santa Monica's standing weekly shows."""

    BASE_URL = 'https://www.tripsantamonica.com'
    EVENTS_URL = f'{BASE_URL}/trip-santa-monica-events'

    # Single fixed venue. NB: this was previously recorded as "1431 3rd Street
    # Promenade", which is not this venue -- the site's own footer says 2101
    # Lincoln Blvd, so every event was being geocoded to the wrong place.
    VENUE_NAME = 'TRiP Santa Monica'
    VENUE_ADDRESS = '2101 Lincoln Blvd, Santa Monica, CA 90405'
    VENUE_LAT = 34.0025873
    VENUE_LNG = -118.4703697

    # How far ahead to project standing weekly nights.
    WEEKS_AHEAD = 8

    # A show heading starts with the weekday it runs on: "Friday TRIVIA Night".
    _HEADING_RE = re.compile(
        r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b\s*(.*)$',
        re.I,
    )
    # "@ 7pm", "8pm start", "7:15pm signup" -- prefer an explicit start.
    _START_RE = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*start', re.I)
    _AT_RE = re.compile(r'@\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?', re.I)
    _ANY_TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?', re.I)

    _CATEGORY_RULES = (
        ('trivia', 'Community'),
        ('quiz', 'Community'),
        ('open mic', 'Music'),
        ('music', 'Music'),
        ('jam', 'Music'),
        ('dj', 'Nightlife'),
        ('comedy', 'Comedy'),
        ('art', 'Art'),
    )

    def __init__(self):
        super().__init__(source_name='Tripp')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of TRiP Santa Monica...")
        events: List[Event] = []

        html = self.fetch_page_js(self.EVENTS_URL, timeout=45000)
        if not html:
            self.log("Failed to render the Weekly Shows page")
            return events

        shows = self._parse_shows(self.parse_html(html))
        self.log(f"Found {len(shows)} weekly show(s)")

        for weekday, title, description, start in shows:
            for occurrence in self._occurrences(weekday, start):
                event = self.create_event(
                    title=title,
                    description=description,
                    venue_name=self.VENUE_NAME,
                    address=self.VENUE_ADDRESS,
                    event_date=occurrence,
                    url=f'{self.EVENTS_URL}#{occurrence:%Y-%m-%d}',
                    category=self._classify(f'{title} {description}'),
                    latitude=self.VENUE_LAT,
                    longitude=self.VENUE_LNG,
                )
                if event:
                    events.append(event)

        self.log(f"Scraped {len(events)} occurrence(s) from {len(shows)} weekly show(s)")
        return events

    def _parse_shows(self, soup) -> List[Tuple[int, str, str, Tuple[int, int]]]:
        """Extract (weekday, title, description, start_time) per standing night.

        Headings and body copy are siblings in a flat Wix DOM rather than nested
        per-show containers, so a show owns every element after its heading up
        to the next weekday heading.
        """
        blocks = soup.find_all(['h2', 'h3', 'h4', 'h5', 'h6', 'p'])

        shows = []
        current = None      # (weekday, title, [text parts])
        for el in blocks:
            text = self.clean_text(el.get_text(' ', strip=True))
            if not text:
                continue

            match = self._HEADING_RE.match(text) if el.name.startswith('h') else None
            if match:
                if current:
                    shows.append(current)
                weekday = _WEEKDAYS[match.group(1).lower()]
                current = (weekday, text, [])
                continue

            if current is not None:
                current[2].append(text)

        if current:
            shows.append(current)

        parsed = []
        for weekday, title, parts in shows:
            description = self.clean_text(' '.join(parts))
            parsed.append((weekday, title, description, self._parse_start(description)))
        return parsed

    def _parse_start(self, text: str) -> Tuple[int, int]:
        """Pick the show's start time.

        "7:15pm signup, 8pm start" has two times and the later one is the show;
        an explicit "start" wins, then an "@ 7pm", then the first time present.
        """
        for pattern in (self._START_RE, self._AT_RE, self._ANY_TIME_RE):
            match = pattern.search(text)
            if match:
                hour = int(match.group(1)) % 12
                if match.group(3).lower() == 'p':
                    hour += 12
                return hour, int(match.group(2) or 0)
        return 20, 0    # evening default for a night-time venue

    def _occurrences(self, weekday: int, start: Tuple[int, int]) -> List[datetime]:
        """Next WEEKS_AHEAD occurrences of a weekday, starting today."""
        today = date.today()
        first = today + timedelta(days=(weekday - today.weekday()) % 7)
        return [
            datetime(day.year, day.month, day.day, start[0], start[1])
            for day in (first + timedelta(weeks=w) for w in range(self.WEEKS_AHEAD))
        ]

    def _classify(self, text: str) -> str:
        low = text.lower()
        for keyword, category in self._CATEGORY_RULES:
            if keyword in low:
                return category
        return 'Nightlife'

"""
Scraper for the Academy Museum of Motion Pictures (Miracle Mile).
Source: https://www.academymuseum.org/en/calendar

The calendar is a Next.js app whose server-rendered flight data
(``self.__next_f.push``) carries every program as ``cfProgramsKeyedByTkId``.
Showtimes are loaded client-side from the ticketing system and are NOT in the
payload, so each program only has a date (``activeStartDate`` / ``activeEndDate``,
midnight UTC). A program with one date is stored as a date-only event (00:00,
which the UI renders without a time). Programs spanning a date range (ongoing
tours, multi-week workshops, members-only offers) are skipped: their dates are
a window, not an occurrence, and the real days live only in prose.

This payload shape is fragile. Any change makes the scraper log and return
nothing rather than guess.

The museum (6067 Wilshire Blvd) is inside the Westside coverage box, so events
use the default region.
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event
from src.utils.categories import classify_event


class AcademyMuseumScraper(BaseScraper):
    """Scraper for the Academy Museum calendar (Next.js flight payload)."""

    VENUE_NAME = 'Academy Museum of Motion Pictures'
    VENUE_ADDRESS = '6067 Wilshire Blvd, Los Angeles, CA 90036'
    VENUE_LAT = 34.0628
    VENUE_LNG = -118.3591

    CALENDAR_URL = 'https://www.academymuseum.org/en/calendar'
    PROGRAM_URL = 'https://www.academymuseum.org/en/programs/detail/{slug}'

    PAYLOAD_KEY = '"cfProgramsKeyedByTkId":'
    DESCRIPTION_LIMIT = 600

    def __init__(self):
        super().__init__('Academy Museum')
        self.base_url = 'https://www.academymuseum.org'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Academy Museum calendar...")
        try:
            return self._scrape()
        except Exception as e:  # fragile source: never break the run
            self.log(f"Unexpected error, returning no events: {e}")
            return []

    def _scrape(self) -> List[Event]:
        html = self.fetch_page(self.CALENDAR_URL)
        if not html:
            self.log("Failed to fetch calendar page")
            return []

        programs = self._extract_programs(html)
        if not programs:
            self.log("No program payload found; page shape may have changed")
            return []
        self.log(f"Found {len(programs)} program(s) in payload")

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        events: List[Event] = []
        ranged = 0
        for raw in programs:
            if not isinstance(raw, dict):
                continue
            try:
                start, single_day = self._dates(raw)
                if start is None:
                    continue
                if not single_day:
                    ranged += 1
                    continue
                if start < today:
                    continue
                event = self._build_event(raw, start)
            except Exception as e:
                self.log(f"  x error parsing program: {e}")
                continue
            if event:
                events.append(event)

        self.log(f"Scraped {len(events)} dated program(s); skipped {ranged} date-range program(s)")
        return events

    # -- payload ---------------------------------------------------------

    def _extract_programs(self, html: str) -> List[dict]:
        """Programs from the page's Next.js flight data ([] if the shape differs)."""
        soup = self.parse_html(html)
        chunks = []
        for script in soup.find_all('script'):
            text = script.string or ''
            match = re.match(r'\s*self\.__next_f\.push\((\[.*\])\)\s*;?\s*$', text, re.DOTALL)
            if not match:
                continue
            try:
                part = json.loads(match.group(1))
            except ValueError:
                continue
            if len(part) > 1 and isinstance(part[1], str):
                chunks.append(part[1])
        flight = ''.join(chunks)

        idx = flight.find(self.PAYLOAD_KEY)
        if idx < 0:
            return []
        try:
            keyed, _ = json.JSONDecoder().raw_decode(flight, idx + len(self.PAYLOAD_KEY))
        except ValueError:
            return []
        if not isinstance(keyed, dict):
            return []
        return list(keyed.values())

    @staticmethod
    def _rich_text(node) -> str:
        """Plain text of a Contentful rich-text node (or a {'json': node} field)."""
        if isinstance(node, dict) and 'json' in node:
            node = node['json']
        if not isinstance(node, dict):
            return ''
        if node.get('nodeType') == 'text':
            return node.get('value') or ''
        children = [AcademyMuseumScraper._rich_text(c) for c in node.get('content') or []]
        # Paragraph/list blocks sit side by side; inline runs join as written.
        return (' ' if node.get('nodeType') == 'document' else '').join(children)

    @staticmethod
    def _dates(raw: dict):
        """(start midnight, single_day) from the program's active dates, or (None, False).

        The values are midnight UTC but denote a calendar date, so the date
        part is taken as written (no timezone shift).
        """
        try:
            start = datetime.strptime(str(raw.get('activeStartDate'))[:10], '%Y-%m-%d')
            end = datetime.strptime(str(raw.get('activeEndDate'))[:10], '%Y-%m-%d')
        except ValueError:
            return None, False
        return start, start == end

    def _build_event(self, raw: dict, start: datetime) -> Optional[Event]:
        if raw.get('hideFromCalendar') or raw.get('membersOnly'):
            return None
        title = self.clean_text(self._rich_text(raw.get('programTitle')) or self._rich_text(raw.get('title')))
        slug = raw.get('slug')
        if not title or not slug:
            return None

        type_names = [
            t.get('name', '') for t in (raw.get('programTypesCollection') or {}).get('items') or []
            if isinstance(t, dict)
        ]
        tagline = self.clean_text(self._rich_text(raw.get('programTagline')))
        body = self.clean_text(self._rich_text(raw.get('filmDescription1')))
        description = (tagline or body)[:self.DESCRIPTION_LIMIT]

        if 'Screenings' in type_names:
            category = 'Film'
        else:
            # Classify without the venue name: "Motion Pictures" tags everything Film.
            category = classify_event(title, description, '')

        image = raw.get('image') if isinstance(raw.get('image'), dict) else {}

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=start,
            url=self.PROGRAM_URL.format(slug=slug),
            image_url=image.get('url') or '',
            category=category,
            is_free='Free' in type_names,
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

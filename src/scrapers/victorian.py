"""
Scraper for The Victorian (Santa Monica).
Source: https://www.thevictorian.com/what-s-on

The page is a Wix site listing "Weekly Happenings" as one block per night:
a day heading, the night's name, and a run of service/DJ times. Those blocks
are read directly and expanded across the lookahead window.

This previously shipped a hardcoded schedule that was never checked against the
site, and it was wrong in every particular -- it advertised comedy nights on
Monday and Wednesday, when the venue is closed Sunday through Wednesday. Only
what the page actually says is published now; if the page stops parsing, the
scraper returns nothing rather than falling back to an assumed schedule.
"""
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event

WEEKDAYS = {
    'MONDAY': 0, 'TUESDAY': 1, 'WEDNESDAY': 2, 'THURSDAY': 3,
    'FRIDAY': 4, 'SATURDAY': 5, 'SUNDAY': 6,
}

# "5pm", "8:00 pm", "10:30-11:30pm" -> first time is the night's start.
_TIME_RE = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', re.IGNORECASE)


class VictorianScraper(BaseScraper):
    """Scraper for The Victorian's weekly happenings."""

    VENUE_NAME = 'The Victorian'
    ADDRESS = '2640 Main St, Santa Monica, CA 90405'

    LOOKAHEAD_DAYS = 56

    def __init__(self):
        super().__init__('The Victorian')
        self.base_url = 'https://www.thevictorian.com'
        self.events_url = f'{self.base_url}/what-s-on'
        self.venue_name = self.VENUE_NAME
        self.venue_address = self.ADDRESS

    def scrape(self) -> List[Event]:
        """Read the weekly happenings and expand them forward."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch what's-on page")
                return events

            nights = self._parse_nights(html)
            if not nights:
                self.log("No weekly happenings found on the page")
                return events

            self.log(f"Found {len(nights)} weekly happenings")

            for night in nights:
                for moment in self._weekly_occurrences(
                    night['weekday'], night['hour'], night['minute']
                ):
                    event = self.create_event(
                        title=night['title'],
                        description=night['description'],
                        venue_name=self.VENUE_NAME,
                        address=self.ADDRESS,
                        event_date=moment,
                        url=self.events_url,
                        category=night['category'],
                        price_note='',
                    )
                    if event:
                        events.append(event)

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_nights(self, html: str) -> List[dict]:
        """Read each night's block from the Weekly Happenings section.

        Wix splits a block across sibling rich-text elements that share an
        `__item-<id>` suffix on their ids, so those are grouped back together.
        """
        soup = self.parse_html(html)

        groups = {}
        order = []
        for element in soup.select('[data-testid="richTextElement"]'):
            match = re.search(r'__item-(\w+)$', element.get('id', ''))
            if not match:
                continue
            key = match.group(1)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(element)

        nights = []
        for key in order:
            texts = [
                self.clean_text(el.get_text(' '))
                for el in groups[key]
                if el.get_text(strip=True)
            ]
            weekday = None
            for text in texts:
                if text.upper() in WEEKDAYS:
                    weekday = WEEKDAYS[text.upper()]
                    break
            if weekday is None:
                continue

            remaining = [t for t in texts if t.upper() not in WEEKDAYS]
            if not remaining:
                continue

            title = remaining[0]
            description = ' '.join(remaining[1:]).strip()
            hour, minute = self._start_time(description)

            nights.append({
                'weekday': weekday,
                'title': title,
                'description': description,
                'hour': hour,
                'minute': minute,
                'category': self._category(title, description),
            })
        return nights

    def _start_time(self, description: str) -> tuple:
        """The night's first published time; 8 PM when none is given."""
        match = _TIME_RE.search(description or '')
        if not match:
            return 20, 0
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        meridiem = match.group(3).lower()
        if meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
        return hour, minute

    def _category(self, title: str, description: str) -> str:
        text = f'{title} {description}'.lower()
        if 'salsa' in text or 'bachata' in text or 'dancing' in text:
            return 'Dance'
        if 'comedy' in text:
            return 'Comedy'
        if 'dj' in text or 'music' in text:
            return 'Music'
        return 'Nightlife'

    def _weekly_occurrences(self, weekday: int, hour: int, minute: int) -> List[datetime]:
        now = datetime.now()
        occurrences = []
        cursor = now.date()
        end = (now + timedelta(days=self.LOOKAHEAD_DAYS)).date()
        while cursor <= end:
            if cursor.weekday() == weekday:
                moment = datetime.combine(cursor, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
                if moment >= now:
                    occurrences.append(moment)
            cursor += timedelta(days=1)
        return occurrences

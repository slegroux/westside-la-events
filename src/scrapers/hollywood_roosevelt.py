"""
Scraper for The Hollywood Roosevelt's calendar.
Source: https://www.thehollywoodroosevelt.com/happenings/

This is a "beyond the Westside" source: Hollywood is outside the coverage box,
so REGION opts it into the separate tab and its events are validated against
LA County instead.

The calendar publishes cadence, not dates -- each card carries a weekday badge
("FRI") and a frequency ("Weekly", "Biweekly", "Monthly"). Weekly cards can be
expanded exactly. Biweekly and monthly ones have no published anchor date, and
the linked Eventbrite pages only expose the series' overall span, so guessing
which weeks they land on would put wrong dates on the site. Those are skipped
and counted in the log instead.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


WEEKDAY_ABBR = {
    'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6,
}


class HollywoodRooseveltScraper(BaseScraper):
    """Scraper for The Hollywood Roosevelt hotel's recurring programming."""

    REGION = 'beyond'

    VENUE_NAME = 'The Hollywood Roosevelt'
    ADDRESS = '7000 Hollywood Blvd, Los Angeles, CA 90028'

    LOOKAHEAD_DAYS = 60

    # "Every Friday · 8 PM - Late · 21+"
    _TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b', re.IGNORECASE)

    def __init__(self):
        super().__init__('The Hollywood Roosevelt')
        self.base_url = 'https://www.thehollywoodroosevelt.com'
        self.events_url = f'{self.base_url}/happenings/'

    def scrape(self) -> List[Event]:
        """Expand the calendar's weekly programming."""
        self.log("Starting scrape...")
        events = []
        skipped = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch happenings page")
                return events

            soup = self.parse_html(html)
            cards = soup.select('.happening-card, .happening-card--featured')
            self.log(f"Found {len(cards)} calendar cards")

            for card in cards:
                try:
                    parsed, skip_reason = self._parse_card(card)
                    events.extend(parsed)
                    if skip_reason:
                        skipped.append(skip_reason)
                except Exception as e:
                    self.log(f"Error parsing card: {e}")
                    continue

            if skipped:
                # Surfaced rather than silently dropped: these are real events
                # whose dates the source simply doesn't publish.
                self.log(
                    f"Skipped {len(skipped)} card(s) with no resolvable dates: "
                    + '; '.join(skipped)
                )

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_card(self, card) -> Tuple[List[Event], Optional[str]]:
        """Expand one card; returns (events, reason it was skipped)."""
        title_elem = card.find('h2')
        title = self.clean_text(title_elem.get_text()) if title_elem else ''
        if not title:
            return [], None

        day_elem = card.select_one('.badge-day')
        freq_elem = card.select_one('.badge-month')
        day_text = self.clean_text(day_elem.get_text()).lower() if day_elem else ''
        frequency = self.clean_text(freq_elem.get_text()).lower() if freq_elem else ''

        weekday = WEEKDAY_ABBR.get(day_text[:3])
        if weekday is None:
            return [], f"{title} (no weekday)"

        # Only a weekly cadence pins an event to specific dates. Anything else
        # needs an anchor the source doesn't give.
        if 'week' not in frequency or frequency.startswith('bi'):
            return [], f"{title} ({frequency or 'unknown cadence'})"

        details_elem = card.select_one('.happening-details')
        details = self.clean_text(details_elem.get_text(' ')) if details_elem else ''
        hour, minute = self._parse_time(details)

        desc_elem = card.select_one('.content')
        description = self.clean_text(desc_elem.get_text(' ')) if desc_elem else ''
        if details:
            description = f'{description} ({details})'.strip()

        room_elem = card.select_one('.happening-venue-tag')
        room = self.clean_text(room_elem.get_text()) if room_elem else ''
        venue_name = f'{self.VENUE_NAME} — {room}' if room else self.VENUE_NAME

        link = card.select_one('a.happening-ticket')
        url = link['href'] if link and link.get('href') else self.events_url

        image_url = ''
        img = card.find('img')
        if img and img.get('src'):
            image_url = img['src']

        events = []
        for moment in self._weekly_occurrences(weekday, hour, minute):
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=self.ADDRESS,
                event_date=moment,
                url=url,
                image_url=image_url,
                price_note='',
            )
            if event:
                events.append(event)
        return events, None

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

    def _parse_time(self, details: str) -> Tuple[int, int]:
        """Read the start time from the details line; defaults to 8 PM."""
        match = self._TIME_RE.search(details or '')
        if not match:
            return 20, 0
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if match.group(3).lower() == 'pm' and hour != 12:
            hour += 12
        elif match.group(3).lower() == 'am' and hour == 12:
            hour = 0
        return hour, minute

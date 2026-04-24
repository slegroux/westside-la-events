"""
Scraper for The Bungalow Santa Monica events.
Source: https://thebungalow.com/santa-monica/happenings/
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class BungalowSMScraper(BaseScraper):
    """Scraper for The Bungalow Santa Monica events."""

    def __init__(self):
        super().__init__('The Bungalow Santa Monica')
        self.base_url = 'https://thebungalow.com'
        self.events_url = f'{self.base_url}/santa-monica/happenings/'
        self.venue_name = 'The Bungalow Santa Monica'
        self.address = '101 Wilshire Blvd, Santa Monica, CA 90401'
        self.latitude = 34.0195
        self.longitude = -118.4912

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events = []

        html = self.fetch_page(self.events_url)
        if not html:
            self.log("Failed to fetch events page")
            return events

        soup = self.parse_html(html)

        # Only grab the upcoming events block (not block-events-past)
        upcoming_block = soup.find('div', class_=lambda c: c and 'block-events' in c and 'past' not in c)
        if not upcoming_block:
            self.log("Could not find upcoming events block")
            return events

        # Upcoming block: events sit directly in .container (no events-container wrapper)
        container = upcoming_block.find('div', class_='container')
        if not container:
            self.log("Could not find container")
            return events

        event_items = container.find_all('div', class_='event')
        self.log(f"Found {len(event_items)} event items")

        for item in event_items:
            try:
                event = self._parse_event(item)
                if event:
                    events.append(event)
            except Exception as e:
                self.log(f"Error parsing event: {e}")
                continue

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _parse_event(self, item) -> Optional[Event]:
        content_div = item.find('div', class_=lambda c: c and 'basis-9' in c)
        if not content_div:
            return None

        # Title
        title_elem = content_div.find('p', class_='h2')
        if not title_elem:
            return None
        title = self.clean_text(title_elem.get_text())
        if not title:
            return None

        # Date/time — first <p> in the content div (before the h2)
        date_str = ''
        for p in content_div.find_all('p'):
            if p == title_elem:
                break
            text = self.clean_text(p.get_text())
            if text:
                date_str = text
                break

        event_date = self._parse_date(date_str)
        if event_date is None:
            return None  # Skip events we can't date (e.g. "Summer Thursdays")

        # Skip past events
        if event_date < datetime.now():
            return None

        # Description
        desc_div = content_div.find('div', class_=lambda c: c and 'max-w' in c)
        description = self.clean_text(desc_div.get_text(' ')) if desc_div else ''

        # Image
        image_url = ''
        img_div = item.find('div', class_=lambda c: c and 'basis-4' in c)
        if img_div:
            img = img_div.find('img')
            if img:
                image_url = img.get('src', '') or img.get('data-src', '')

        # Price — look for keywords in description
        is_free, price, price_note = self._parse_price(description)

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.address,
            event_date=event_date,
            url=self.events_url,
            image_url=image_url,
            category='Nightlife',
            price=price,
            is_free=is_free,
            price_note=price_note,
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None

        # Handle recurring: "Every Thursday | 7PM" or "Thursdays | 7PM" → next upcoming occurrence
        recurring_match = re.match(r'(?:Every\s+)?(\w+?)s?\s*\|\s*(\d+(?::\d+)?(?:am|pm)?)', date_str, re.I)
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        if recurring_match and recurring_match.group(1).lower() in days:
            day_name = recurring_match.group(1)
            time_str = recurring_match.group(2)
            return self._next_weekday(day_name, time_str)

        # Normalize: strip pipe and clean up time part
        # e.g. "Thursday, May 7 | 5pm" → "May 7 5pm"
        normalized = re.sub(r'\s*\|\s*', ' ', date_str)
        # Remove day-of-week prefix
        normalized = re.sub(r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*', '', normalized, flags=re.I)
        # Remove time range end: "5pm-1am" → "5pm"
        normalized = re.sub(r'(\d+(?::\d+)?(?:am|pm))-\d+(?::\d+)?(?:am|pm)', r'\1', normalized, flags=re.I)

        try:
            dt = date_parser.parse(normalized, fuzzy=True)
            # Bump to next year if the date is in the past
            if dt < datetime.now():
                dt = dt.replace(year=dt.year + 1)
            # If still past, give up
            if dt < datetime.now():
                return None
            return dt
        except Exception:
            return None

    def _next_weekday(self, day_name: str, time_str: str) -> Optional[datetime]:
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target = days.index(day_name.lower())
        today = datetime.now()
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7  # always return next occurrence, not today
        next_day = today + timedelta(days=days_ahead)
        try:
            time_dt = date_parser.parse(time_str)
            return next_day.replace(hour=time_dt.hour, minute=time_dt.minute, second=0, microsecond=0)
        except Exception:
            return next_day.replace(hour=19, minute=0, second=0, microsecond=0)

    def _parse_price(self, description: str):
        text = description.lower()
        # Look for dollar amounts
        dollar_match = re.search(r'\$(\d+)', description)
        if dollar_match:
            amount = float(dollar_match.group(1))
            return False, amount, f'${dollar_match.group(1)}'
        if re.search(r'\bfree\b', text):
            return True, 0.0, 'Free'
        return False, None, 'TBD'

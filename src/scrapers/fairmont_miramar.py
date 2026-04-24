"""
Scraper for Fairmont Miramar Hotel Santa Monica events.
Source: https://www.fairmont-miramar.com/explore/events-calendar/

Fairmont Miramar is a landmark oceanfront hotel in Santa Monica offering
live music, jazz nights, afternoon tea, holiday events, and seasonal experiences.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event

API_URL = 'https://www.fairmont-miramar.com/wp-json/verb/v1/events/filter'
EVENTS_PAGE = 'https://www.fairmont-miramar.com/explore/events-calendar/'

DAYS_OF_WEEK = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}


class FairmontMiramarScraper(BaseScraper):
    """Scraper for Fairmont Miramar Hotel events calendar."""

    def __init__(self):
        super().__init__('Fairmont Miramar')
        self.base_url = 'https://www.fairmont-miramar.com'
        self.venue_name = 'Fairmont Miramar Hotel'
        self.venue_address = '101 Wilshire Blvd, Santa Monica, CA 90401'
        self.session.headers.update({
            'Referer': EVENTS_PAGE,
        })

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events = []
        page = 1

        while True:
            self.log(f"Fetching page {page}...")
            resp_data = self._fetch_page(page)
            if not resp_data:
                break

            html = resp_data.get('content', '')
            if not html or 'no events matching' in html.lower():
                break

            soup = BeautifulSoup(html, 'lxml')
            cards = soup.find_all('div', class_='event-cards__card')
            if not cards:
                break

            for card in cards:
                try:
                    parsed = self._parse_card(card)
                    events.extend(parsed)
                except Exception as e:
                    self.log(f"Error parsing card: {e}")

            self.log(f"Page {page}: {len(cards)} cards, {len(events)} events so far")

            if not resp_data.get('load_more'):
                break
            page += 1

        self.log(f"Scraped {len(events)} events")
        return events

    def _fetch_page(self, page_no: int) -> Optional[dict]:
        try:
            resp = self.session.get(
                API_URL,
                params={
                    'element': 'h2',
                    'posts_per_page': 20,
                    'paged': page_no,
                },
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log(f"Error fetching page {page_no}: {e}")
            return None

    def _parse_card(self, card) -> List[Event]:
        title_el = card.find(class_='event-cards__title')
        if not title_el:
            return []
        title = title_el.get_text(strip=True)
        if not title:
            return []

        # Category / event type
        cat_el = card.find(class_='event-cards__event-type')
        raw_category = cat_el.get_text(strip=True) if cat_el else ''

        # Description
        desc_el = card.find(class_='event-cards__description')
        description = desc_el.get_text(strip=True) if desc_el else ''
        if not description:
            description = f"{raw_category} at {self.venue_name}"

        # Frequency flag
        freq_el = card.find(class_='event-cards__frequency-flag')
        frequency = freq_el.get_text(strip=True).upper() if freq_el else ''

        # Icons: [0]=location, [1]=date/frequency, [2]=time
        icons = card.find_all('div', class_='event-cards__icon-wrapper')
        icon_texts = [ic.get_text(strip=True) for ic in icons]
        venue_sub = icon_texts[0] if len(icon_texts) > 0 else ''
        date_text = icon_texts[1] if len(icon_texts) > 1 else ''
        time_text = icon_texts[2] if len(icon_texts) > 2 else ''

        # Link
        link_el = card.find('a', href=True)
        url = link_el['href'] if link_el else EVENTS_PAGE

        # Image (lazy-loaded via data-src)
        img_el = card.find('img')
        image_url = ''
        if img_el:
            image_url = img_el.get('data-src') or img_el.get('src', '')
            if image_url and image_url.startswith('data:'):
                image_url = ''

        category = self._map_category(raw_category, title, description)
        venue_display = f"{venue_sub} — {self.venue_name}" if venue_sub else self.venue_name

        is_weekly = 'WEEKLY' in frequency or 'WEEKLY' in date_text.upper()

        if is_weekly:
            # Generate next 4 occurrences based on day-of-week in description
            dates = self._weekly_dates(description, title, time_text)
        else:
            # Specific date like "May 08" or "Oct 02"
            dt = self._parse_specific_date(date_text, time_text)
            dates = [(dt, None)] if dt else []

        results = []
        for event_date, end_date in dates:
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue_display,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                category=category,
                price_note='TBD',
            )
            if event:
                results.append(event)
        return results

    def _parse_specific_date(self, date_text: str, time_text: str) -> Optional[datetime]:
        """Parse a date like 'May 08' or 'Oct 02' with an optional time."""
        if not date_text or date_text.upper() in ('WEEKLY', 'MONTHLY', 'DAILY'):
            return None
        try:
            now = datetime.now()
            combined = f"{date_text} {now.year} {time_text}".strip()
            dt = date_parser.parse(combined, fuzzy=True)
            # If parsed date is in the past, try next year
            if dt < now - timedelta(days=1):
                dt = dt.replace(year=now.year + 1)
            return dt
        except Exception:
            return None

    def _weekly_dates(self, description: str, title: str, time_text: str) -> List[Tuple]:
        """Generate next 4 weekly occurrences based on day-of-week found in description/title."""
        text = f"{description} {title}".lower()
        target_weekday = None
        for day_name, weekday in DAYS_OF_WEEK.items():
            if day_name in text:
                target_weekday = weekday
                break

        now = datetime.now()
        # Parse time
        hour, minute = 20, 0  # default 8 PM
        if time_text:
            try:
                t = date_parser.parse(time_text)
                hour, minute = t.hour, t.minute
            except Exception:
                pass

        if target_weekday is None:
            # No day found — just return next 4 weekly slots starting today
            dates = []
            d = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if d < now:
                d += timedelta(days=1)
            for _ in range(4):
                dates.append((d, None))
                d += timedelta(weeks=1)
            return dates

        # Advance to next occurrence of target_weekday
        days_ahead = (target_weekday - now.weekday()) % 7
        if days_ahead == 0 and now.hour >= hour:
            days_ahead = 7
        next_date = now + timedelta(days=days_ahead)
        next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

        return [(next_date + timedelta(weeks=i), None) for i in range(4)]

    def _map_category(self, raw: str, title: str, description: str) -> str:
        combined = f"{raw} {title} {description}".lower()
        if any(k in combined for k in ['jazz', 'piano', 'live music', 'concert', 'music', 'band', 'orchestra']):
            return 'Music'
        if any(k in combined for k in ['tea', 'brunch', 'dining', 'food', 'culinary', 'sushi', 'cocktail', 'wine', 'beer', 'oktoberfest', 'luau']):
            return 'Food'
        if any(k in combined for k in ['art', 'exhibit', 'gallery']):
            return 'Arts'
        if any(k in combined for k in ['yoga', 'fitness', 'wellness', 'meditation', 'swim']):
            return 'Wellness'
        if any(k in combined for k in ['family', 'kid', 'children', 'mermaid', 'magic']):
            return 'Family'
        return 'Other'

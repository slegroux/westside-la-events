"""
Scraper for The Broad Stage events.
Source: https://www.thebroadstage.org/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class BroadStageScraper(BaseScraper):
    """Scraper for The Broad Stage events."""

    def __init__(self):
        super().__init__('The Broad Stage')
        self.base_url = 'https://broadstage.org'
        self.events_url = f'{self.base_url}/2526-season/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Broad Stage website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the events page (may require JavaScript)
            html = self.fetch_page_js(self.events_url, wait_selector='.event-card, .event-item, article')
            if not html:
                # Try without JS
                html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find all show items — each is a div.inner with p.heading (date) + h3 (title) + a (link)
            event_items = [
                d for d in soup.find_all('div', class_='inner')
                if d.find('p', class_='heading') and d.find('h3')
            ]

            self.log(f"Found {len(event_items)} event items")

            seen_urls = set()
            for item in event_items:
                try:
                    link = item.find('a', href=True)
                    if not link:
                        continue
                    url = self.normalize_url(link['href'], self.base_url)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    event = self._parse_event(item, url)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item, url: str) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data
            url: Event detail URL

        Returns:
            Event object or None
        """
        # Extract title
        title_elem = item.find(['h1', 'h2', 'h3', 'h4'])
        if not title_elem:
            title_elem = item.find('a', href=True)

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())

        # Extract description
        description = ""
        desc_elem = item.find('p', class_=lambda x: x and 'desc' in str(x).lower())
        if not desc_elem:
            desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time from p.heading (e.g. "February 27, 2026" or "April 18-19, 2026")
        event_date = None
        date_elem = item.find('p', class_='heading')
        if date_elem:
            date_str = self.clean_text(date_elem.get_text())
            # Handle date ranges like "April 18-19, 2026" — use start date
            date_str = re.sub(r'(\d+)-\d+,', r'\1,', date_str)
            try:
                event_date = date_parser.parse(date_str, fuzzy=True)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Venue info - The Broad Stage in Santa Monica
        venue_name = "The Broad Stage"
        address = "1310 11th St, Santa Monica, CA 90401"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - performing arts venue
        category = "Theater"

        # Price info
        is_free = False
        price = None
        price_note = "TBD"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

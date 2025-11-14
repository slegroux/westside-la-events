"""
Scraper for McCabe's Guitar Shop concerts.
Source: https://www.mccabes.com/concerts-landing/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class McCabesScraper(BaseScraper):
    """Scraper for McCabe's Guitar Shop concerts."""

    def __init__(self):
        super().__init__("McCabe's Guitar Shop")
        self.base_url = 'https://www.mccabes.com'
        self.events_url = f'{self.base_url}/concerts-landing/'

    def scrape(self) -> List[Event]:
        """
        Scrape concerts from McCabe's Guitar Shop website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the concerts page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch concerts page")
                return events

            soup = self.parse_html(html)

            # Find all concert items using FooEvents classes
            concert_container = soup.find('div', class_='fooevents-event-listing-list-container')

            if concert_container:
                concert_items = concert_container.find_all('div', class_=re.compile(r'fooevents-event-listing-list-item'))
            else:
                # Alternative selector - try event cards
                concert_items = soup.find_all(['div', 'article'], class_=re.compile(r'event', re.IGNORECASE))

            self.log(f"Found {len(concert_items)} concert items")

            for item in concert_items:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing concert: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} concerts")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single concert item.

        Args:
            item: BeautifulSoup element containing concert data

        Returns:
            Event object or None
        """
        # Extract title from h3 element
        title_elem = item.find('h3')
        if not title_elem:
            title_elem = item.find(['h2', 'h4'])

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())

        # Extract URL from link
        url = self.events_url
        link = item.find('a', href=True)
        if link:
            url = self.normalize_url(link['href'], self.base_url)

        # Extract description
        description = ""
        desc_elem = item.find('p') or item.find('div', class_=re.compile(r'desc|content', re.IGNORECASE))
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time from fooevents-event-listing-list-datetime
        event_date = None
        date_elem = item.find('div', class_='fooevents-event-listing-list-datetime')
        if not date_elem:
            date_elem = item.find(['time', 'span'], class_=re.compile(r'date|time', re.IGNORECASE))

        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            # Format is like "Fri Nov 14 2025 | 8pm"
            date_str = date_str.replace('|', '').strip()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Check if sold out
        is_sold_out = False
        if item.find(text=re.compile(r'sold out', re.IGNORECASE)):
            is_sold_out = True

        # Venue info - McCabe's in Santa Monica
        venue_name = "McCabe's Guitar Shop"
        address = "3101 Pico Blvd, Santa Monica, CA 90405"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - music concerts
        category = "Music & Concerts"

        # Price info
        is_free = False
        price = None
        price_note = "Sold out" if is_sold_out else "Check website for ticket prices"

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

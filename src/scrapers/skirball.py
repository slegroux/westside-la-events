"""
Scraper for Skirball Cultural Center events.
Source: https://www.skirball.org/programs/public-programs
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class SkirballScraper(BaseScraper):
    """Scraper for Skirball Cultural Center events."""

    def __init__(self):
        super().__init__('Skirball Cultural Center')
        self.base_url = 'https://www.skirball.org'
        self.events_url = f'{self.base_url}/programs/public-programs'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Skirball Cultural Center website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the events page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find all event items - they're in list items or article elements
            event_items = soup.find_all('li', class_=lambda x: x and ('audience' in x or 'category' in x))

            if not event_items:
                # Try alternative selector - event links in h3
                event_items = soup.find_all('h3')

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

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object or None
        """
        # Extract title from h3 > a element
        title_elem = item.find('h3')
        if not title_elem:
            return None

        link_elem = title_elem.find('a', href=True)
        if not link_elem:
            return None

        title = self.clean_text(link_elem.get_text())
        url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract description from p element
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time - appears as text after title
        event_date = None
        # Look for date patterns like "Thursday, November 20, 6:30 pm"
        text_content = item.get_text()
        try:
            # Try to find date pattern
            import re
            date_pattern = r'([A-Z][a-z]+day),?\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{1,2}:\d{2}\s*[ap]m)?'
            date_match = re.search(date_pattern, text_content)
            if date_match:
                date_str = f"{date_match.group(2)} {date_match.group(3)} {datetime.now().year}"
                if date_match.group(4):
                    date_str += f" {date_match.group(4)}"
                event_date = date_parser.parse(date_str)
        except Exception as e:
            self.log(f"Error parsing date: {e}")

        # Extract category from class or text
        category = ""
        # Check for category keywords in the item's classes or nearby text
        item_classes = ' '.join(item.get('class', [])).lower()
        if 'film' in item_classes or 'film' in text_content.lower():
            category = 'Film & Screenings'
        elif 'music' in item_classes or 'music' in text_content.lower():
            category = 'Music & Concerts'
        elif 'performance' in item_classes or 'performance' in text_content.lower():
            category = 'Performing Arts'
        elif 'family' in item_classes or 'kids' in text_content.lower():
            category = 'Family & Kids'

        # Venue info - Skirball Cultural Center in Brentwood
        venue_name = "Skirball Cultural Center"
        address = "2701 N Sepulveda Blvd, Los Angeles, CA 90049"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - varies by event
        is_free = False
        price = None
        price_note = "Check website for pricing"

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

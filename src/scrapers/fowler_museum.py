"""
Scraper for UCLA Fowler Museum events.
Source: https://fowler.ucla.edu/events/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class FowlerMuseumScraper(BaseScraper):
    """Scraper for UCLA Fowler Museum events."""

    def __init__(self):
        super().__init__('UCLA Fowler Museum')
        self.base_url = 'https://fowler.ucla.edu'
        self.events_url = f'{self.base_url}/events/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from UCLA Fowler Museum website.

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

            # Find all event items - typically in article or div elements
            event_items = soup.find_all(['article', 'div'], class_=re.compile(r'event', re.IGNORECASE))

            if not event_items:
                # Try finding event links
                event_links = soup.find_all('a', href=re.compile(r'/events/[a-z0-9-]+'))
                # Get unique parent containers
                event_items = []
                seen = set()
                for link in event_links:
                    parent = link.find_parent(['article', 'div', 'section'])
                    if parent and id(parent) not in seen:
                        seen.add(id(parent))
                        event_items.append(parent)

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
        # Extract title from h2 or h3 element
        title_elem = item.find(['h2', 'h3'], class_=re.compile(r'title|event', re.IGNORECASE))
        if not title_elem:
            title_elem = item.find(['h2', 'h3'])

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())

        # Extract URL
        link = item.find('a', href=re.compile(r'/events/'))
        if not link:
            return None

        url = self.normalize_url(link['href'], self.base_url)

        # Extract description
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time - format like "Sat Nov 15, 2025" and "2:00 pm - 4:30 pm"
        event_date = None
        end_date = None

        # Look for time elements or date-related text
        date_elem = item.find('time')
        if not date_elem:
            # Try finding date patterns in text
            text_content = item.get_text()
            date_match = re.search(r'([A-Z][a-z]{2})\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})', text_content)
            if date_match:
                date_str = f"{date_match.group(2)} {date_match.group(3)}, {date_match.group(4)}"

                # Look for time
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', text_content, re.IGNORECASE)
                if time_match:
                    date_str += f" {time_match.group(1)}"

                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Error parsing date '{date_str}': {e}")
        else:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Extract category from event metadata
        category = ""
        # Look for category indicators
        text_lower = item.get_text().lower()
        if 'talk' in text_lower or 'lecture' in text_lower:
            category = 'Education'
        elif 'screening' in text_lower or 'film' in text_lower:
            category = 'Film'
        elif 'exhibition' in text_lower:
            category = 'Art'
        elif 'performance' in text_lower:
            category = 'Theater'
        elif 'workshop' in text_lower:
            category = 'Education'

        # Venue info - UCLA Fowler Museum
        venue_name = "UCLA Fowler Museum"
        address = "308 Charles E Young Dr N, Los Angeles, CA 90095"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - typically free or check website
        is_free = 'free' in item.get_text().lower()
        price = None
        price_note = "Free admission" if is_free else "TBD"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

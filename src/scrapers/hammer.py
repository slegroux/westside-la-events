"""
Scraper for Hammer Museum events.
Source: https://hammer.ucla.edu/programs-events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class HammerScraper(BaseScraper):
    """Scraper for Hammer Museum events."""

    def __init__(self):
        super().__init__('Hammer Museum')
        self.base_url = 'https://hammer.ucla.edu'
        self.events_url = f'{self.base_url}/programs-events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Hammer Museum website.

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

            # Find all event items
            # Hammer uses article elements or linked cards for events
            event_items = soup.find_all('article', class_=lambda x: x and 'program' in x.lower())

            if not event_items:
                # Try alternative selector - event links
                event_items = soup.find_all('a', href=lambda x: x and '/programs-events/' in x)

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
        # Extract title
        title_elem = item.find(['h2', 'h3', 'h4'])
        if not title_elem:
            title_elem = item.find('a')
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract description
        desc_elem = item.find('p') or item.find('div', class_=lambda x: x and 'description' in x.lower())
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date/time
        event_date = None
        date_elem = item.find('time')
        if not date_elem:
            date_elem = item.find(class_=lambda x: x and 'date' in x.lower())

        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Venue info - Hammer Museum
        venue_name = "Hammer Museum"
        address = "10899 Wilshire Blvd, Los Angeles, CA 90024"

        # Extract URL
        link_elem = item if item.name == 'a' else item.find('a', href=True)
        url = ""
        if link_elem and link_elem.has_attr('href'):
            url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            # Drupal uses srcset, try data-src, src
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - Hammer Museum events are typically free
        is_free = True
        price = None
        price_note = "Free admission; timed tickets recommended"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

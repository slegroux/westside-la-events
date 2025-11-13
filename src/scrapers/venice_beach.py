"""
Scraper for Venice Beach events.
Source: https://www.visitveniceca.com/calendar-2/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class VeniceBeachScraper(BaseScraper):
    """Scraper for Venice Beach events."""

    def __init__(self):
        super().__init__('Venice Beach Events')
        self.base_url = 'https://www.visitveniceca.com'
        self.events_url = f'{self.base_url}/calendar-2/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Visit Venice CA website.

        Uses WordPress Events Manager plugin with AJAX loading.

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

            # Events Manager plugin uses specific classes
            # Look for event list items
            event_items = soup.find_all('li', class_=lambda x: x and 'event' in x.lower())

            if not event_items:
                # Try alternative selectors
                event_items = soup.find_all('div', class_=lambda x: x and 'event-item' in x.lower())

            if not event_items:
                # Try finding event articles
                event_items = soup.find_all('article', class_=lambda x: x and 'event' in x.lower())

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
        title_elem = item.find(['h2', 'h3', 'h4', 'h5'])
        if not title_elem:
            # Try finding event title class
            title_elem = item.find(class_=lambda x: x and 'event-title' in x.lower())
        if not title_elem:
            title_elem = item.find('a')

        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event":
            return None

        # Extract description
        desc_elem = item.find('p') or item.find('div', class_=lambda x: x and ('description' in x.lower() or 'excerpt' in x.lower()))
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date/time
        event_date = None

        # Look for time element
        date_elem = item.find('time')
        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date from time element '{date_str}': {e}")

        # If no time element, look for date classes
        if not event_date:
            date_elem = item.find(class_=lambda x: x and 'date' in x.lower())
            if date_elem:
                date_str = date_elem.get_text()
                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Error parsing date from class '{date_str}': {e}")

        # Extract venue/location
        venue_name = ""
        address = "Venice Beach, CA"

        location_elem = item.find(class_=lambda x: x and ('location' in x.lower() or 'venue' in x.lower()))
        if location_elem:
            venue_name = self.clean_text(location_elem.get_text())
            if venue_name:
                address = f"{venue_name}, Venice, CA"

        # Extract URL
        link_elem = item if item.name == 'a' else item.find('a', href=True)
        url = ""
        if link_elem and link_elem.has_attr('href'):
            url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - assume free unless otherwise specified
        is_free = True
        price = None
        price_note = ""

        # Check for price info in text
        text_content = f"{title} {description}".lower()
        if '$' in text_content and 'free' not in text_content:
            is_free = False
            price_note = "Check website for pricing"

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

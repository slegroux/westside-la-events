"""
Scraper for West Hollywood city events.
Source: https://www.weho.org/city-government/calendar
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class WestHollywoodScraper(BaseScraper):
    """Scraper for West Hollywood city events."""

    def __init__(self):
        super().__init__('West Hollywood')
        self.base_url = 'https://www.weho.org'
        self.events_url = f'{self.base_url}/city-government/calendar'

    def scrape(self) -> List[Event]:
        """
        Scrape events from West Hollywood city calendar.

        Uses Playwright for JavaScript rendering since the site blocks regular requests.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Use Playwright to fetch the page since it returns 403 for regular requests
            html = self.fetch_page_js(self.events_url, wait_selector='div.calendar, article, .event')
            if not html:
                self.log("Failed to fetch events page with Playwright")
                return events

            soup = self.parse_html(html)

            # Find all event items
            # West Hollywood uses various selectors for calendar events
            event_items = soup.find_all('article')

            if not event_items:
                # Try alternative selectors
                event_items = soup.find_all('div', class_=lambda x: x and 'event' in x.lower())

            if not event_items:
                # Try finding event links
                event_items = soup.find_all('a', href=lambda x: x and '/calendar/' in x or x and '/event' in x)

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
        title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'h5'])
        if not title_elem:
            # Try finding event title class
            title_elem = item.find(class_=lambda x: x and 'title' in x.lower())
        if not title_elem and item.name == 'a':
            title_elem = item

        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event" or len(title) < 3:
            return None

        # Extract description
        desc_elem = item.find('p') or item.find('div', class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower()))
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
        venue_name = "West Hollywood"
        address = "West Hollywood, CA"

        location_elem = item.find(class_=lambda x: x and ('location' in x.lower() or 'venue' in x.lower()))
        if location_elem:
            location_text = self.clean_text(location_elem.get_text())
            if location_text:
                venue_name = location_text
                address = f"{location_text}, West Hollywood, CA"

        # Extract URL
        if item.name == 'a' and item.has_attr('href'):
            url = self.normalize_url(item['href'], self.base_url)
        else:
            link_elem = item.find('a', href=True)
            url = self.normalize_url(link_elem['href'], self.base_url) if link_elem else ""

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - West Hollywood city events are typically free
        is_free = True
        price = None
        price_note = "Free community event"

        # Check for paid events in text
        text_content = f"{title} {description}".lower()
        if '$' in text_content or 'ticket' in text_content:
            is_free = False
            price_note = None  # Display as $TBD
        elif 'free' in text_content:
            price_note = "Free event"

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

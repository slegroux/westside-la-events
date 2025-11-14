"""
Scraper for Culver City events.
Source: https://www.culvercity.gov/Events-directory
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class CulverCityScraper(BaseScraper):
    """Scraper for Culver City events."""

    def __init__(self):
        super().__init__('Culver City')
        self.base_url = 'https://www.culvercity.gov'
        self.events_url = f'{self.base_url}/Events-directory'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Culver City Events Directory.

        Uses ASP.NET with Telerik controls for event management.

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

            # Find all event cards/links
            # Culver City displays events as anchor tags with event info
            event_items = soup.find_all('a', href=lambda x: x and '/Events-directory/' in x)

            # Alternative: look for event containers
            if not event_items:
                event_items = soup.find_all('div', class_=lambda x: x and 'event' in x.lower())

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
        # If item is a link, extract info from it and children
        if item.name == 'a':
            # Title is typically in the link text or a child heading
            title_elem = item.find(['h2', 'h3', 'h4', 'h5'])
            if not title_elem:
                # Title might be direct text content
                title = self.clean_text(item.get_text())
            else:
                title = self.clean_text(title_elem.get_text())
        else:
            # Extract title from child elements
            title_elem = item.find(['h2', 'h3', 'h4', 'h5'])
            title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event" or len(title) < 3:
            return None

        # Extract description
        # Look for summary or description elements
        desc_elem = None
        if item.name == 'a':
            # Description might be in sibling or parent container
            parent = item.find_parent('div')
            if parent:
                desc_elem = parent.find('p') or parent.find('div', class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower()))
        else:
            desc_elem = item.find('p') or item.find('div', class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower()))

        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date/time
        event_date = None

        # Look for date element in item or parent
        date_elem = item.find(class_=lambda x: x and 'date' in x.lower())
        if not date_elem and item.name == 'a':
            parent = item.find_parent('div')
            if parent:
                date_elem = parent.find(class_=lambda x: x and 'date' in x.lower())

        if not date_elem:
            date_elem = item.find('time')

        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Venue info
        venue_name = "Culver City"
        address = "Culver City, CA"

        # Check for specific location in text
        location_elem = item.find(class_=lambda x: x and 'location' in x.lower())
        if not location_elem and item.name == 'a':
            parent = item.find_parent('div')
            if parent:
                location_elem = parent.find(class_=lambda x: x and 'location' in x.lower())

        if location_elem:
            location_text = self.clean_text(location_elem.get_text())
            if location_text:
                venue_name = location_text
                address = f"{location_text}, Culver City, CA"

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

        # Price info - Culver City events are typically free
        is_free = True
        price = None
        price_note = "Free community event"

        # Check for paid events in text
        text_content = f"{title} {description}".lower()
        if '$' in text_content or 'admission' in text_content:
            is_free = False
            price_note = None  # Display as $TBD

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

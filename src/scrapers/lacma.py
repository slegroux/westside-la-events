"""
Scraper for LACMA (Los Angeles County Museum of Art) events.
Source: https://www.lacma.org/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class LACMAScraper(BaseScraper):
    """Scraper for LACMA events."""

    def __init__(self):
        super().__init__('LACMA')
        self.base_url = 'https://www.lacma.org'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from LACMA website.

        LACMA uses a Drupal Views system with AJAX loading capabilities.

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
            # LACMA uses views-row classes for event listings
            event_items = soup.find_all('div', class_=lambda x: x and 'views-row' in x)

            if not event_items:
                # Alternative: look for article or event-specific elements
                event_items = soup.find_all('article')

            if not event_items:
                # Try finding event links
                event_items = soup.find_all('a', href=lambda x: x and '/event/' in x)

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
            # Try finding the link text
            link_elem = item.find('a')
            title_elem = link_elem
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event":
            return None

        # Extract description
        desc_elem = item.find('p') or item.find('div', class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower()))
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date/time
        event_date = None

        # Look for time element first
        date_elem = item.find('time')
        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date from time element '{date_str}': {e}")

        # If no time element, look for date classes or spans
        if not event_date:
            date_elem = item.find(class_=lambda x: x and 'date' in x.lower())
            if date_elem:
                date_str = date_elem.get_text()
                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Error parsing date from class '{date_str}': {e}")

        # Extract location/venue
        venue_name = "LACMA"
        address = "5905 Wilshire Blvd, Los Angeles, CA 90036"

        # Check if it's an online or off-site event
        location_elem = item.find(class_=lambda x: x and 'location' in x.lower())
        if location_elem:
            location_text = self.clean_text(location_elem.get_text())
            if location_text and 'online' in location_text.lower():
                venue_name = "LACMA (Online)"
                address = "Online"
            elif location_text and location_text.lower() not in ['lacma', 'los angeles county museum of art']:
                venue_name = location_text
                address = f"{location_text}, Los Angeles, CA"

        # Extract URL
        link_elem = item if item.name == 'a' else item.find('a', href=True)
        url = ""
        if link_elem and link_elem.has_attr('href'):
            url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            # Try different src attributes (Drupal can use data-src, srcset, etc.)
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info
        # LACMA general admission is required for most events
        is_free = False
        price = None
        price_note = "Museum admission required"

        # Check for free events in text
        text_content = f"{title} {description}".lower()
        if 'free' in text_content or 'no admission' in text_content:
            is_free = True
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

"""
Scraper for Santa Monica city events.
Source: https://www.smgov.net/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class SantaMonicaScraper(BaseScraper):
    """Scraper for Santa Monica events."""

    def __init__(self):
        super().__init__('Santa Monica')
        self.base_url = 'https://www.smgov.net'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Santa Monica website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Note: The actual parsing logic will depend on the website structure
            # This is a template that needs to be adjusted after inspecting the site
            event_items = soup.find_all('div', class_='event-item')  # Adjust selector

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

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object
        """
        # Extract title
        title_elem = item.find('h3') or item.find('h2') or item.find('a', class_='title')
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract description
        desc_elem = item.find('p', class_='description') or item.find('div', class_='description')
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date
        date_elem = item.find('time') or item.find('span', class_='date')
        event_date = None
        if date_elem:
            date_str = date_elem.get('datetime') or date_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception:
                pass

        # Extract venue
        venue_elem = item.find('span', class_='venue') or item.find('div', class_='location')
        venue_name = self.clean_text(venue_elem.get_text()) if venue_elem else ""

        # Extract address
        address_elem = item.find('span', class_='address')
        address = self.clean_text(address_elem.get_text()) if address_elem else ""
        if not address and venue_name:
            address = f"{venue_name}, Santa Monica, CA"

        # Extract URL
        link_elem = item.find('a', href=True)
        url = self.normalize_url(link_elem['href'], self.base_url) if link_elem else ""

        # Extract image
        img_elem = item.find('img', src=True)
        image_url = self.normalize_url(img_elem['src'], self.base_url) if img_elem else ""

        # Extract price information
        is_free = False
        price = None

        # Check for free events in title or description
        price_text = f"{title} {description}"
        if 'free' in price_text.lower() or 'no cost' in price_text.lower():
            is_free = True
        else:
            # Try to extract price
            import re
            price_match = re.search(r'\$(\d+(?:\.\d{2})?)', price_text)
            if price_match:
                try:
                    price = float(price_match.group(1))
                except ValueError:
                    pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            price=price,
            is_free=is_free
        )

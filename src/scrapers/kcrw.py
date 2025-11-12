"""
Scraper for KCRW events.
Source: https://www.kcrw.com/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class KCRWScraper(BaseScraper):
    """Scraper for KCRW events."""

    def __init__(self):
        super().__init__('KCRW')
        self.base_url = 'https://www.kcrw.com'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from KCRW website.

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

            # KCRW uses CSS modules with unique class names
            # Event cards have class starting with EventCard_cardContainer__
            event_items = soup.find_all('div', class_=lambda x: x and 'EventCard_cardContainer__' in x)

            if not event_items:
                self.log("No event cards found on page")
                return events

            self.log(f"Found {len(event_items)} event cards")

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
        # Extract title - in EventCard_cardTitle__
        title_elem = item.find('p', class_=lambda x: x and 'EventCard_cardTitle__' in x)
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract date - in EventCard_date__
        date_elem = item.find('div', class_=lambda x: x and 'EventCard_date__' in x)
        event_date = None
        if date_elem:
            # Date is split into month and day
            date_parts = [s.strip() for s in date_elem.stripped_strings]
            if len(date_parts) >= 2:
                # Construct date string like "Nov 14" and add current year
                from datetime import datetime
                current_year = datetime.now().year
                date_str = f"{date_parts[0]} {date_parts[1]} {current_year}"
                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Failed to parse date '{date_str}': {e}")

        # Extract venue - in small-text class
        venue_elem = item.find('p', class_='small-text')
        venue_name = ""
        address = ""
        if venue_elem:
            # Format is typically "Venue Name, City, State"
            full_location = self.clean_text(venue_elem.get_text())
            parts = [p.strip() for p in full_location.split(',')]
            if parts:
                venue_name = parts[0]
                address = full_location

        # Extract category/tags
        tags = item.find_all('div', class_=lambda x: x and 'Tag_tag__' in x)
        category = None
        if tags:
            # Use first meaningful tag as category
            tag_texts = [tag.get_text(strip=True) for tag in tags]
            # Skip generic tags like "Featured"
            for tag in tag_texts:
                if tag.lower() not in ['featured', 'kcrw presents']:
                    category = tag
                    break

        # Extract URL - parent <a> tag wraps the card
        parent_link = item.find_parent('a')
        url = ""
        if parent_link and parent_link.get('href'):
            url = self.normalize_url(parent_link['href'], self.base_url)

        # Extract image
        img_elem = item.find('img')
        image_url = ""
        if img_elem:
            src = img_elem.get('src', '')
            if src:
                image_url = src  # Already full URL from Contentful CDN

        # Fetch description from detail page
        description = self._fetch_event_description(url) if url else ""

        # Extract price information from title or description
        is_free = False
        price = None

        # Check for free events
        price_text = f"{title} {description}"
        if 'free' in price_text.lower() or 'no cover' in price_text.lower():
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
            category=category,
            price=price,
            is_free=is_free
        )

    def _fetch_event_description(self, event_url: str) -> str:
        """
        Fetch event description from the detail page.

        Args:
            event_url: URL of the event detail page

        Returns:
            Event description text
        """
        try:
            self.log(f"Fetching description from {event_url}")
            html = self.fetch_page(event_url)
            if not html:
                return ""

            soup = self.parse_html(html)

            # Extract description paragraphs
            # Strategy: Get first few substantial paragraphs before the donation message
            paragraphs = soup.find_all('p')
            description_parts = []

            for p in paragraphs:
                text = self.clean_text(p.get_text())

                # Skip short paragraphs and footer content
                if len(text) < 50:
                    continue
                if any(keyword in text.lower() for keyword in ['donate to kcrw', 'copyright', 'kcrw member']):
                    break  # Stop at footer content

                # Add this paragraph to description
                description_parts.append(text)

                # Usually descriptions are 1-3 paragraphs
                if len(description_parts) >= 3:
                    break

            return ' '.join(description_parts)

        except Exception as e:
            self.log(f"Error fetching description: {e}")
            return ""

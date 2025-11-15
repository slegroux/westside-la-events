"""
Scraper for Old Town Music Hall events.
Source: https://prod5.agileticketing.net/websales/pages/list.aspx?epguid=046f24e9-20f3-4095-9ab6-2596f53377e0&
"""
from datetime import datetime, timezone
from typing import List, Optional
import json
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class OldTownMusicHallScraper(BaseScraper):
    """Scraper for Old Town Music Hall events."""

    def __init__(self):
        super().__init__('Old Town Music Hall')
        self.base_url = 'https://prod5.agileticketing.net'
        self.events_url = f'{self.base_url}/websales/pages/list.aspx?epguid=046f24e9-20f3-4095-9ab6-2596f53377e0&'
        # Venue information (from the JSON-LD data)
        self.venue_name = 'Old Town Music Hall'
        self.venue_address = '140 Richmond Street, El Segundo, CA 90245'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Old Town Music Hall Agile Ticketing page.

        This scraper extracts events from JSON-LD structured data embedded
        in the Agile Ticketing event listing page, and also extracts images
        from the HTML structure.

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

            # First, extract images from HTML (map event names to image URLs)
            image_map = self._extract_images_from_html(soup)

            # Extract JSON-LD structured data
            # Agile Ticketing embeds event data in script tags with type="application/ld+json"
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            if not json_ld_scripts:
                self.log("No JSON-LD structured data found on page")
                return events

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle both single events and arrays of events
                    if isinstance(data, list):
                        # Array of events
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Event':
                                event_name = item.get('name', '')
                                event = self._parse_json_ld_event(item, image_map.get(event_name))
                                if event:
                                    events.append(event)
                    elif isinstance(data, dict):
                        if data.get('@type') == 'Event':
                            # Single event
                            event_name = data.get('name', '')
                            event = self._parse_json_ld_event(data, image_map.get(event_name))
                            if event:
                                events.append(event)

                except (json.JSONDecodeError, Exception) as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _extract_images_from_html(self, soup) -> dict:
        """
        Extract event images from the HTML structure.

        The Agile Ticketing page has images in the HTML but not in JSON-LD.
        We need to map event names to their image URLs.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Dictionary mapping event names to image URLs
        """
        image_map = {}

        try:
            # Find all event items in the list
            items = soup.find_all('div', class_='Item')

            for item in items:
                # Extract event name from the Name element
                name_elem = item.find('h3', class_='Name')
                if not name_elem:
                    continue
                event_name = name_elem.get_text(strip=True)

                # Extract image URL from ImageBox
                image_box = item.find('div', class_='ImageBox')
                if image_box:
                    img = image_box.find('img')
                    if img:
                        # Get full-size image if available, otherwise use thumbnail
                        image_url = img.get('full-src') or img.get('src')
                        if image_url:
                            # Ensure it's a full URL
                            if not image_url.startswith('http'):
                                image_url = f"{self.base_url}{image_url}"
                            image_map[event_name] = image_url

        except Exception as e:
            self.log(f"Error extracting images: {e}")

        return image_map

    def _parse_json_ld_event(self, data: dict, image_url: Optional[str] = None) -> Optional[Event]:
        """
        Parse a JSON-LD event object.

        Args:
            data: JSON-LD event dictionary
            image_url: Image URL extracted from HTML (optional)

        Returns:
            Event object or None
        """
        try:
            # Extract title
            title = data.get('name', 'Untitled Event')

            # Extract dates
            event_date = None
            end_date = None

            start_date_str = data.get('startDate')
            if start_date_str:
                try:
                    event_date = date_parser.parse(start_date_str)
                except Exception as e:
                    self.log(f"Failed to parse start date '{start_date_str}': {e}")

            # Note: Agile Ticketing JSON-LD typically doesn't include endDate
            # Events are usually single showings with specific start times

            # Extract venue information
            venue_name = self.venue_name
            address = self.venue_address

            location = data.get('location', {})
            if isinstance(location, dict):
                # Override with specific venue info if available
                if location.get('name'):
                    venue_name = location.get('name', venue_name)

                # Extract address
                addr_obj = location.get('address', {})
                if isinstance(addr_obj, dict):
                    street = addr_obj.get('streetAddress', '')
                    city = addr_obj.get('addressLocality', '')
                    state = addr_obj.get('addressRegion', '')
                    postal = addr_obj.get('postalCode', '')

                    # Build address string
                    address_parts = []
                    if street:
                        address_parts.append(street)
                    if city:
                        address_parts.append(city)
                    if state:
                        address_parts.append(state)
                    if postal:
                        address_parts.append(postal)

                    if address_parts:
                        address = ', '.join(address_parts)

            # Extract URL from offers
            url = ""
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                offer_url = offers.get('url', '')
                if offer_url:
                    url = offer_url
                    # Ensure it's a full URL
                    if url and not url.startswith('http'):
                        url = f"{self.base_url}{url}"

            # Use image URL from HTML if provided
            if not image_url:
                image_url = ""

            # No description in JSON-LD for Agile Ticketing
            description = ""

            # Extract price information
            price = None
            is_free = False
            price_note = "TBD"

            # Determine category based on title and venue
            # Old Town Music Hall shows classic movies and live music
            category = self._categorize_event(title)

            # Filter out past events
            if event_date:
                now = datetime.now(timezone.utc) if event_date.tzinfo else datetime.now()
                if event_date < now:
                    self.log(f"Skipping past event: {title}")
                    return None

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

        except Exception as e:
            self.log(f"Error parsing JSON-LD event: {e}")
            return None

    def _categorize_event(self, title: str) -> str:
        """
        Categorize event based on title.

        Old Town Music Hall hosts classic films and live music performances.

        Args:
            title: Event title

        Returns:
            Category string
        """
        title_lower = title.lower()

        # Check for live music indicators
        music_keywords = [
            'concert', 'band', 'orchestra', 'jazz', 'music',
            'parlor boys', 'celebration', 'organ', 'pianist'
        ]

        for keyword in music_keywords:
            if keyword in title_lower:
                return "Music"

        # Otherwise, likely a film screening (default for this venue)
        return "Film"

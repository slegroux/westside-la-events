"""
Scraper for Alliance Française de Los Angeles events.
Source: https://www.afdela.org/events/
"""
import json
import re
from datetime import datetime
from typing import List, Optional, Dict
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class AFdelaScraper(BaseScraper):
    """Scraper for Alliance Française de Los Angeles events."""

    def __init__(self):
        super().__init__('AFdela')
        self.base_url = 'https://www.afdela.org'
        self.events_url = f'{self.base_url}/events/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from AFdela website.
        Uses JSON-LD structured data for reliable parsing.

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

            # Extract all JSON-LD structured data from the page
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            self.log(f"Found {len(json_ld_scripts)} JSON-LD script tags")

            event_count = 0
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle both single events and arrays of events
                    events_data = []
                    if isinstance(data, list):
                        events_data = [item for item in data if item.get('@type') == 'Event']
                    elif data.get('@type') == 'Event':
                        events_data = [data]

                    # Parse each event
                    for event_data in events_data:
                        event_count += 1
                        self.log(f"Parsing event {event_count}: {event_data.get('name', 'Untitled')}")

                        event = self._parse_from_structured_data(event_data)
                        if event:
                            events.append(event)

                except json.JSONDecodeError as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue
                except Exception as e:
                    self.log(f"Error processing JSON-LD script: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_from_structured_data(self, data: Dict) -> Optional[Event]:
        """
        Parse event from JSON-LD structured data.

        Args:
            data: JSON-LD event data dictionary

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Title
            title = data.get('name', 'Untitled Event')

            # Description
            description = data.get('description', '')

            # Dates
            event_date = None
            end_date = None
            if data.get('startDate'):
                try:
                    event_date = date_parser.parse(data['startDate'])
                except Exception as e:
                    self.log(f"Error parsing start date: {e}")

            if data.get('endDate'):
                try:
                    end_date = date_parser.parse(data['endDate'])
                except Exception as e:
                    self.log(f"Error parsing end date: {e}")

            # Location/Venue
            location = data.get('location', {})
            venue_name = location.get('name', 'Alliance Française de Los Angeles')

            # Address
            address_data = location.get('address', {})
            address = self._parse_address(address_data, venue_name)

            # Event URL
            url = data.get('url', '')
            if url and not url.startswith('http'):
                url = self.normalize_url(url, self.base_url)

            # Image
            image_url = data.get('image', '')
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else ''
            if image_url and not image_url.startswith('http'):
                image_url = self.normalize_url(image_url, self.base_url)

            # Price info
            offers = data.get('offers', {})
            is_free = False
            price = None

            if offers:
                # Handle both single offer and list of offers
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                price_text = offers.get('price', '')
                if price_text:
                    try:
                        # Handle various price formats
                        if isinstance(price_text, (int, float)):
                            price = float(price_text)
                        else:
                            # Remove currency symbols and whitespace
                            clean_price = str(price_text).replace('$', '').replace('£', '').replace('€', '').strip()
                            if clean_price:
                                price = float(clean_price)
                    except (ValueError, TypeError):
                        self.log(f"Could not parse price: {price_text}")

                # Check if free
                if 'free' in str(offers).lower() or price == 0:
                    is_free = True

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing event data: {e}")
            return None

    def _parse_address(self, address_data: Dict, venue_name: str) -> str:
        """
        Parse address from JSON-LD address data.

        Args:
            address_data: Address data from JSON-LD
            venue_name: Venue name as fallback

        Returns:
            Formatted address string
        """
        if isinstance(address_data, str):
            return address_data

        if isinstance(address_data, dict):
            street = address_data.get('streetAddress', '')
            city = address_data.get('addressLocality', '')
            state = address_data.get('addressRegion', 'CA')
            postal = address_data.get('postalCode', '')

            # Build full address
            address_parts = [p for p in [street, city, state, postal] if p]
            if address_parts:
                return ', '.join(address_parts)

        # Fallback to venue name with LA
        return f"{venue_name}, Los Angeles, CA" if venue_name else "Los Angeles, CA"

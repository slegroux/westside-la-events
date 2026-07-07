"""
Scraper for The Casual Creative events.
Source: https://luma.com/thecasualcreative?k=c

The Casual Creative hosts pop-up experiences and workshops in Los Angeles
that inspire creative play and artistic participation.
"""
import json
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class CasualCreativeScraper(BaseScraper):
    """Scraper for The Casual Creative events on Luma."""

    def __init__(self):
        super().__init__('The Casual Creative')
        self.base_url = 'https://luma.com'
        self.events_url = f'{self.base_url}/thecasualcreative?k=c'

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Casual Creative's Luma page.

        Luma provides structured JSON-LD data in an Organization object with
        an events array. This is the primary data source.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Try regular HTTP request first (Luma provides JSON-LD in initial HTML)
            html = self.fetch_page(self.events_url)

            # If regular HTTP fails, try JavaScript rendering as fallback
            if not html:
                self.log("Regular HTTP failed, trying JavaScript rendering...")
                html = self.fetch_page_js(
                    self.events_url,
                    wait_selector='[class*="content-card"]',
                    timeout=45000
                )

            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Extract all JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            if not json_ld_scripts:
                self.log("No JSON-LD data found")
                return events

            self.log(f"Found {len(json_ld_scripts)} JSON-LD scripts")

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle Organization with events array (Luma's structure)
                    if data.get('@type') == 'Organization' and 'events' in data:
                        event_list = data.get('events', [])
                        self.log(f"Found Organization with {len(event_list)} events in events array")
                        for event_data in event_list:
                            if event_data.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(event_data)
                                if event:
                                    events.append(event)

                    # Handle single event
                    elif data.get('@type') == 'Event':
                        event = self._parse_event_from_json_ld(data)
                        if event:
                            events.append(event)

                    # Handle event list (ItemList)
                    elif data.get('@type') == 'ItemList':
                        items = data.get('itemListElement', [])
                        for item in items:
                            event_data = item.get('item', {})
                            if event_data.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(event_data)
                                if event:
                                    events.append(event)

                    # Handle list of events (array at root)
                    elif isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(item)
                                if event:
                                    events.append(event)

                except json.JSONDecodeError as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue
                except Exception as e:
                    self.log(f"Error processing JSON-LD: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event_from_json_ld(self, data: dict) -> Optional[Event]:
        """
        Parse event from JSON-LD structured data.

        Args:
            data: Event data from JSON-LD

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Title
            title = data.get('name', '').strip()
            if not title:
                return None

            # Description
            description = data.get('description', '').strip()

            # URL
            url = data.get('url', '') or data.get('@id', '')
            # Normalize Luma URLs
            if url and not url.startswith('http'):
                url = self.normalize_url(url, self.base_url)

            # Dates
            event_date = None
            end_date = None

            start_str = data.get('startDate')
            if start_str:
                try:
                    event_date = date_parser.parse(start_str)
                except Exception as e:
                    self.log(f"Failed to parse start date '{start_str}': {e}")

            end_str = data.get('endDate')
            if end_str:
                try:
                    end_date = date_parser.parse(end_str)
                except Exception as e:
                    self.log(f"Failed to parse end date '{end_str}': {e}")

            # Location/Venue
            location = data.get('location', {})
            venue_name = ''
            address = ''
            latitude = None
            longitude = None

            if isinstance(location, dict):
                venue_name = location.get('name', '').strip()

                # Address
                address_data = location.get('address', {})
                if isinstance(address_data, dict):
                    street = address_data.get('streetAddress', '')
                    city = address_data.get('addressLocality', '')
                    state = address_data.get('addressRegion', '')
                    postal = address_data.get('postalCode', '')

                    # Build proper address (skip if streetAddress is just venue name)
                    if street and street != venue_name:
                        address_parts = [p for p in [street, city, state, postal] if p]
                        address = ', '.join(address_parts)
                    elif city or state:
                        address_parts = [p for p in [city, state, postal] if p]
                        address = ', '.join(address_parts) if address_parts else ''
                elif isinstance(address_data, str):
                    address = address_data

                # Coordinates
                geo = location.get('geo', {})
                if isinstance(geo, dict):
                    try:
                        latitude = float(geo.get('latitude'))
                        longitude = float(geo.get('longitude'))
                    except (ValueError, TypeError):
                        pass
            elif isinstance(location, str):
                # Sometimes location is just a string
                venue_name = location

            # If no proper address but we have venue name and coordinates, use venue + city
            if (not address or address == venue_name) and venue_name:
                address = f"{venue_name}, Los Angeles, CA"

            # Image
            image_url = ''
            image_data = data.get('image')
            if image_data:
                if isinstance(image_data, str):
                    image_url = image_data
                elif isinstance(image_data, list) and len(image_data) > 0:
                    image_url = image_data[0] if isinstance(image_data[0], str) else image_data[0].get('url', '')
                elif isinstance(image_data, dict):
                    image_url = image_data.get('url', '')

            # Price information
            offers = data.get('offers', {})
            price = None
            is_free = False
            price_note = ''

            if isinstance(offers, dict):
                price_str = offers.get('price', '')
                if price_str:
                    try:
                        price = float(price_str)
                        if price == 0:
                            is_free = True
                    except (ValueError, TypeError):
                        pass

                # Check availability for free status
                if 'free' in str(offers).lower() or price == 0:
                    is_free = True
                    price = None

                # Get price note from name
                offer_name = offers.get('name', '')
                if offer_name and offer_name != title:
                    price_note = offer_name

            elif isinstance(offers, list):
                # Sometimes offers is an array - take the first/cheapest
                for offer in offers:
                    if isinstance(offer, dict):
                        price_str = offer.get('price', '')
                        if price_str:
                            try:
                                test_price = float(price_str)
                                if price is None or test_price < price:
                                    price = test_price
                                if price == 0:
                                    is_free = True
                            except (ValueError, TypeError):
                                pass

            # Organizer information
            organizer = data.get('organizer', {})
            if isinstance(organizer, dict):
                organizer_name = organizer.get('name', '')
                if organizer_name and organizer_name not in description:
                    if description:
                        description = f"{description}\n\nOrganized by {organizer_name}"
                    else:
                        description = f"Organized by {organizer_name}"

            # Category will be auto-classified
            category = None

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
                price_note=price_note,
                latitude=latitude,
                longitude=longitude
            )

        except Exception as e:
            self.log(f"Error parsing JSON-LD event: {e}")
            return None

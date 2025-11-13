"""
Scraper for LA Tech Events from Luma.
Source: https://luma.com/latechevents?k=c

Scrapes tech community events from the LA Tech Events Luma page.
"""
import json
import re
from datetime import datetime
from typing import List, Optional, Dict
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class LATechEventsScraper(BaseScraper):
    """Scraper for LA Tech Events from Luma."""

    def __init__(self):
        super().__init__("LA Tech Events")
        self.url = 'https://luma.com/latechevents?k=c'

    def scrape(self) -> List[Event]:
        """
        Scrape tech events from the Luma page.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from Luma LA Tech Events...")
        events = []

        try:
            # Fetch the page
            html = self.fetch_page(self.url)
            if not html:
                self.log("Failed to fetch page")
                return events

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Look for JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Check if this is event data
                    if isinstance(data, dict):
                        # Single event
                        if data.get('@type') == 'Event':
                            event = self._parse_json_ld_event(data)
                            if event:
                                events.append(event)
                                self.log(f"Found event: {event.title}")

                        # Check for events array
                        elif 'events' in data and isinstance(data['events'], list):
                            for event_data in data['events']:
                                if event_data.get('@type') == 'Event':
                                    event = self._parse_json_ld_event(event_data)
                                    if event:
                                        events.append(event)
                                        self.log(f"Found event: {event.title}")

                    # Handle array of events
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Event':
                                event = self._parse_json_ld_event(item)
                                if event:
                                    events.append(event)
                                    self.log(f"Found event: {event.title}")

                except json.JSONDecodeError as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue
                except Exception as e:
                    self.log(f"Error processing JSON-LD script: {e}")
                    continue

            self.log(f"Total: {len(events)} events scraped")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_json_ld_event(self, event_data: Dict) -> Optional[Event]:
        """
        Parse event from JSON-LD structured data.

        Args:
            event_data: Event dictionary from JSON-LD

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract title
            title = event_data.get('name', '').strip()
            if not title:
                self.log("No title found, skipping event")
                return None

            # Extract description
            description = event_data.get('description', '').strip()
            if not description:
                description = f"Tech event: {title}"

            # Truncate long descriptions
            if len(description) > 500:
                description = description[:497] + "..."

            # Extract dates
            event_date = None
            end_date = None

            start_date_str = event_data.get('startDate')
            if start_date_str:
                try:
                    event_date = date_parser.parse(start_date_str)
                except Exception as e:
                    self.log(f"Error parsing start date '{start_date_str}': {e}")

            end_date_str = event_data.get('endDate')
            if end_date_str:
                try:
                    end_date = date_parser.parse(end_date_str)
                except Exception as e:
                    self.log(f"Error parsing end date '{end_date_str}': {e}")

            # Extract location information
            venue_name = ''
            address = ''
            latitude = None
            longitude = None

            location_data = event_data.get('location', {})
            if isinstance(location_data, dict):
                # Get venue name
                venue_name = location_data.get('name', '').strip()

                # Get address
                address_data = location_data.get('address', {})
                if isinstance(address_data, dict):
                    street = address_data.get('streetAddress', '')
                    city = address_data.get('addressLocality', '')
                    state = address_data.get('addressRegion', '')
                    postal = address_data.get('postalCode', '')

                    # Check if street address is just the venue name (not a real address)
                    # If so, don't use it - we'll reverse geocode later
                    if street and street != venue_name:
                        # Build address string with real street address
                        address_parts = [p for p in [street, city, state, postal] if p]
                        address = ', '.join(address_parts)
                    elif city or state or postal:
                        # Build address without street (just city/state/zip)
                        address_parts = [p for p in [city, state, postal] if p]
                        address = ', '.join(address_parts) if address_parts else ''
                elif isinstance(address_data, str):
                    address = address_data.strip()

                # Get coordinates from geo data
                geo_data = location_data.get('geo', {})
                if isinstance(geo_data, dict):
                    try:
                        latitude = float(geo_data.get('latitude', 0))
                        longitude = float(geo_data.get('longitude', 0))
                    except (ValueError, TypeError):
                        pass

                # Special handling for venues with coordinates but no complete street address
                # Use reverse geocoding to get the full address
                # Check if address lacks street info (e.g., just "Los Angeles, California")
                has_street_address = address and any(char.isdigit() for char in address.split(',')[0] if address)
                if venue_name and latitude and longitude and not has_street_address:
                    # Try to get address from geocoding service using coordinates
                    try:
                        from src.utils.geocoding import get_geocoding_service
                        geocoder = get_geocoding_service()

                        # Try reverse geocoding with coordinates
                        reverse_address = geocoder.reverse_geocode(latitude, longitude)
                        if reverse_address:
                            address = reverse_address
                            self.log(f"Reverse geocoded {venue_name}: {address}")
                        else:
                            # Fallback: try geocoding venue name + city
                            coords = geocoder.geocode(f"{venue_name}, Los Angeles, CA")
                            if coords:
                                # Get the address that was geocoded
                                address = f"{venue_name}, Los Angeles, CA"
                                self.log(f"Geocoded {venue_name}")
                    except Exception as e:
                        self.log(f"Error geocoding {venue_name}: {e}")
                        # Keep using the coordinates we have from JSON-LD

            # Extract event URL
            event_url = event_data.get('url', '') or event_data.get('@id', '')
            if not event_url:
                event_url = self.url  # Fallback to main page

            # Extract image URL
            image_url = ''
            image_data = event_data.get('image')
            if isinstance(image_data, str):
                image_url = image_data
            elif isinstance(image_data, list) and image_data:
                image_url = image_data[0] if isinstance(image_data[0], str) else ''
            elif isinstance(image_data, dict):
                image_url = image_data.get('url', '')

            # Extract price information
            price = None
            is_free = False

            offers = event_data.get('offers', {})
            if isinstance(offers, dict):
                price_str = offers.get('price')
                if price_str is not None:
                    try:
                        price = float(price_str)
                        is_free = (price == 0)
                    except (ValueError, TypeError):
                        pass

                # Check availability
                availability = offers.get('availability', '')
                if 'free' in str(availability).lower():
                    is_free = True
                    price = 0.0
            elif isinstance(offers, list):
                # Take first offer
                if offers:
                    first_offer = offers[0]
                    if isinstance(first_offer, dict):
                        price_str = first_offer.get('price')
                        if price_str is not None:
                            try:
                                price = float(price_str)
                                is_free = (price == 0)
                            except (ValueError, TypeError):
                                pass

            # Create event with tech category
            # If we have coordinates from JSON-LD, create Event directly
            # Otherwise use create_event which will geocode the address
            if latitude and longitude:
                # Import what we need for manual event creation
                from src.utils.geo_filter import validate_event_location

                # Validate location - filter out events outside Westside/Malibu
                is_valid, reason = validate_event_location(
                    latitude=latitude,
                    longitude=longitude,
                    address=address,
                    venue_name=venue_name
                )

                if not is_valid:
                    self.log(f"Skipping non-Westside event: '{title}' at {venue_name or address} ({reason})")
                    return None

                # Create Event directly with coordinates
                return Event(
                    title=title.strip(),
                    description=description.strip(),
                    venue_name=venue_name.strip(),
                    address=address.strip(),
                    latitude=latitude,
                    longitude=longitude,
                    event_date=event_date,
                    end_date=end_date,
                    category='Tech',
                    source=self.source_name,
                    url=event_url.strip(),
                    image_url=image_url.strip(),
                    source_logo_url=self.source_logo_url or "",
                    price=price,
                    is_free=is_free
                )
            else:
                # No coordinates, use create_event to geocode address
                return self.create_event(
                    title=title,
                    description=description,
                    venue_name=venue_name,
                    address=address,
                    event_date=event_date,
                    end_date=end_date,
                    url=event_url,
                    image_url=image_url,
                    category='Tech',  # Set as Tech category
                    price=price,
                    is_free=is_free
                )

        except Exception as e:
            self.log(f"Error parsing JSON-LD event: {e}")
            return None

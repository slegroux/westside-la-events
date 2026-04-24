"""
Scraper for Sounds Like LA events.
Source: https://soundslikela.org/calendar/
"""
from datetime import datetime, timezone
from typing import List, Optional
import json
import re
import zoneinfo
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class SoundsLikeLAScraper(BaseScraper):
    """Scraper for Sounds Like LA events."""

    def __init__(self):
        super().__init__('Sounds Like LA')
        self.base_url = 'https://soundslikela.org'
        self.events_url = f'{self.base_url}/calendar/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Sounds Like LA website.

        This scraper extracts events from JSON-LD structured data embedded
        in the WordPress site using The Events Calendar plugin.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the calendar page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Extract JSON-LD structured data
            # The Events Calendar embeds event data in script tags with type="application/ld+json"
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            if not json_ld_scripts:
                self.log("No JSON-LD structured data found on page")
                return events

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle both single events and ItemList
                    if isinstance(data, dict):
                        if data.get('@type') == 'Event':
                            # Single event
                            event = self._parse_json_ld_event(data)
                            if event:
                                events.append(event)
                        elif data.get('@type') == 'ItemList' and 'itemListElement' in data:
                            # List of events
                            for item in data['itemListElement']:
                                if isinstance(item, dict) and item.get('@type') == 'Event':
                                    event = self._parse_json_ld_event(item)
                                    if event:
                                        events.append(event)
                    elif isinstance(data, list):
                        # Array of events
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Event':
                                event = self._parse_json_ld_event(item)
                                if event:
                                    events.append(event)

                except (json.JSONDecodeError, Exception) as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue

            # Fallback: Try to fetch from the REST API endpoint
            if not events:
                self.log("No events found in JSON-LD, trying REST API...")
                api_events = self._fetch_from_api()
                events.extend(api_events)

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_json_ld_event(self, data: dict) -> Optional[Event]:
        """
        Parse a JSON-LD event object.

        Args:
            data: JSON-LD event dictionary

        Returns:
            Event object or None
        """
        try:
            # Extract title
            title = data.get('name', 'Untitled Event')

            # Extract description
            description = data.get('description', '')

            # Extract dates
            event_date = None
            end_date = None

            start_date_str = data.get('startDate')
            if start_date_str:
                try:
                    event_date = date_parser.parse(start_date_str)
                except Exception as e:
                    self.log(f"Failed to parse start date '{start_date_str}': {e}")

            end_date_str = data.get('endDate')
            if end_date_str:
                try:
                    end_date = date_parser.parse(end_date_str)
                except Exception as e:
                    self.log(f"Failed to parse end date '{end_date_str}': {e}")

            # Extract venue information
            venue_name = ""
            address = ""

            location = data.get('location', {})
            if isinstance(location, dict):
                venue_name = location.get('name', '')

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

                    address = ', '.join(address_parts)

            # Extract URL
            url = data.get('url', '')
            if url and not url.startswith('http'):
                url = f"{self.base_url}{url}"

            # Extract image
            image_url = ""
            image_data = data.get('image')
            if isinstance(image_data, str):
                image_url = image_data
            elif isinstance(image_data, dict):
                image_url = image_data.get('url', '')
            elif isinstance(image_data, list) and image_data:
                # Take first image if it's an array
                if isinstance(image_data[0], str):
                    image_url = image_data[0]
                elif isinstance(image_data[0], dict):
                    image_url = image_data[0].get('url', '')

            # Extract price information
            offers = data.get('offers', {})
            price = None
            is_free = False
            price_note = ""

            if isinstance(offers, dict):
                price_str = offers.get('price')
                if price_str:
                    try:
                        # Handle price as string or number
                        if isinstance(price_str, str):
                            # Extract numeric value
                            price_match = re.search(r'[\d.]+', price_str)
                            if price_match:
                                price = float(price_match.group())
                        else:
                            price = float(price_str)
                    except (ValueError, TypeError):
                        pass

                # Check if free
                price_currency = offers.get('priceCurrency', '')
                if price == 0 or str(price_str).lower() == 'free':
                    is_free = True
                    price = None

                # Extract availability/URL for tickets
                availability = offers.get('availability', '')
                offer_url = offers.get('url', '')
                if offer_url:
                    price_note = "Tickets available online"

            # Determine category (Sounds Like LA focuses on music events)
            category = "Music"

            # Look for performer info to refine category
            performer = data.get('performer', {})
            if isinstance(performer, dict):
                performer_type = performer.get('@type', '')
                if performer_type == 'MusicGroup':
                    category = "Music"
                elif performer_type == 'PerformingGroup':
                    category = "Performance"

            # Filter out past events
            # Make datetime.now() timezone-aware if event_date is timezone-aware
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

    def _fetch_from_api(self) -> List[Event]:
        """
        Fetch events from the WordPress REST API as a fallback.

        Returns:
            List of Event objects
        """
        events = []

        try:
            # The Events Calendar REST API endpoint
            api_url = f"{self.base_url}/wp-json/tribe/events/v1/events"

            # Add parameters for upcoming events
            params = {
                'per_page': 50,
                'start_date': datetime.now(zoneinfo.ZoneInfo('America/Los_Angeles')).strftime('%Y-%m-%d'),
                'order': 'asc',
                'orderby': 'event_date'
            }

            self.log(f"Fetching from API: {api_url}")

            response = self.session.get(api_url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Parse events from API response
                api_events = data.get('events', [])

                for event_data in api_events:
                    event = self._parse_api_event(event_data)
                    if event:
                        events.append(event)

                self.log(f"Fetched {len(events)} events from API")
            else:
                self.log(f"API request failed with status {response.status_code}")

        except Exception as e:
            self.log(f"Error fetching from API: {e}")

        return events

    def _parse_api_event(self, data: dict) -> Optional[Event]:
        """
        Parse an event from the WordPress REST API response.

        Args:
            data: API event dictionary

        Returns:
            Event object or None
        """
        try:
            # Extract title
            title = data.get('title', 'Untitled Event')

            # Extract description
            description = data.get('description', '')
            # Clean HTML tags if present
            if description:
                description = re.sub(r'<[^>]+>', '', description)

            # Extract dates
            event_date = None
            end_date = None

            start_date_str = data.get('start_date')
            if start_date_str:
                try:
                    event_date = date_parser.parse(start_date_str)
                except Exception as e:
                    self.log(f"Failed to parse start date: {e}")

            end_date_str = data.get('end_date')
            if end_date_str:
                try:
                    end_date = date_parser.parse(end_date_str)
                except Exception as e:
                    self.log(f"Failed to parse end date: {e}")

            # Extract venue
            venue_name = ""
            address = ""
            venue_data = data.get('venue', {})
            if venue_data:
                venue_name = venue_data.get('venue', '')
                address = venue_data.get('address', '')

            # Extract URL
            url = data.get('url', '')

            # Extract image
            image_url = data.get('image', {}).get('url', '') if isinstance(data.get('image'), dict) else ''

            # Extract cost
            price = None
            is_free = False
            cost_str = data.get('cost', '')

            if cost_str:
                if 'free' in cost_str.lower():
                    is_free = True
                else:
                    price_match = re.search(r'\$?(\d+(?:\.\d{2})?)', cost_str)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                        except ValueError:
                            pass

            # Category
            category = "Music"
            categories = data.get('categories', [])
            if categories and isinstance(categories, list):
                # Use first category
                if categories[0].get('name'):
                    category = categories[0]['name']

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
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing API event: {e}")
            return None

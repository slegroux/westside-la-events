"""
Scraper for Aviator Nation events via Eventbrite.
Sources:
- Aviator Nation Venice: https://www.eventbrite.com/o/aviator-nation-77562713843
- Aviator Nation La Jolla: https://www.eventbrite.com/o/aviator-nation-la-jolla-81542951833

Note: Aviator Nation uses Eventbrite for most event ticketing.
Venice location hosts comedy shows and other events.
"""
from datetime import datetime
from typing import List, Optional
import json
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class AviatorNationScraper(BaseScraper):
    """Scraper for Aviator Nation events via Eventbrite."""

    def __init__(self):
        super().__init__('Aviator Nation')
        self.base_url = 'https://www.eventbrite.com'
        # Aviator Nation organizer pages on Eventbrite
        self.organizer_urls = [
            'https://www.eventbrite.com/o/aviator-nation-77562713843',  # Venice
            'https://www.eventbrite.com/o/aviator-nation-la-jolla-81542951833',  # La Jolla
        ]

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aviator Nation's Eventbrite organizer pages.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from Eventbrite organizer pages...")
        events = []

        for organizer_url in self.organizer_urls:
            organizer_name = self._extract_organizer_name(organizer_url)
            self.log(f"Scraping {organizer_name}...")
            events.extend(self._scrape_organizer_page(organizer_url))

        self.log(f"Successfully scraped {len(events)} total events")
        return events

    def _extract_organizer_name(self, url: str) -> str:
        """Extract organizer name from URL for logging."""
        if 'la-jolla' in url:
            return 'Aviator Nation La Jolla'
        return 'Aviator Nation Venice'

    def _scrape_organizer_page(self, url: str) -> List[Event]:
        """
        Scrape an Aviator Nation organizer page by extracting event data
        from window.__SERVER_DATA__.

        Args:
            url: Organizer page URL

        Returns:
            List of Event objects
        """
        events = []

        try:
            html = self.fetch_page(url)
            if not html:
                self.log(f"Failed to fetch organizer page: {url}")
                return events

            # Extract window.__SERVER_DATA__
            match = re.search(r'window\.__SERVER_DATA__\s*=\s*(\{.*?\});?\s*(?:window\.|</script>)', html, re.DOTALL)
            if not match:
                self.log(f"No window.__SERVER_DATA__ found on page")
                return events

            # Parse the JavaScript object as JSON
            try:
                json_str = match.group(1)
                # Remove trailing commas that aren't valid JSON
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.log(f"Failed to parse SERVER_DATA: {e}")
                return events

            # Extract events from the data structure
            # Events can be in multiple locations: upcoming_events, past_events, etc.
            view_data = data.get('view_data', {})
            events_data = view_data.get('events', {})

            # Get both upcoming and past events (we want all of them)
            upcoming_events = events_data.get('upcoming_events', [])
            past_events = events_data.get('past_events', [])

            all_events = upcoming_events + past_events
            self.log(f"Found {len(upcoming_events)} upcoming and {len(past_events)} past events")

            # Parse each event
            for i, event_data in enumerate(all_events, 1):
                try:
                    event = self._parse_event_from_organizer_data(event_data)
                    if event:
                        events.append(event)
                        self.log(f"  [{i}/{len(all_events)}] ✓ {event.title}")
                except Exception as e:
                    self.log(f"  [{i}/{len(all_events)}] ✗ Error: {e}")
                    continue

            self.log(f"Scraped {len(events)} events from organizer page")

        except Exception as e:
            self.log(f"Error during organizer page scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event_from_organizer_data(self, data: dict) -> Optional[Event]:
        """
        Parse event from organizer page's event list format.
        This is a simpler format than the full event page data.

        Args:
            data: Event data from organizer page

        Returns:
            Event object or None if parsing fails
        """
        # Title (can be a string or dict with 'text' key)
        title_data = data.get('name', '')
        if isinstance(title_data, dict):
            title = title_data.get('text', '')
        else:
            title = title_data

        if not title:
            return None

        # Description (may not be available in list view)
        description_data = data.get('summary', '') or data.get('description', '')
        if isinstance(description_data, dict):
            description = description_data.get('text', '')
        else:
            description = description_data

        # URL - build from event ID
        event_id = data.get('id', '')
        url = data.get('url', '')
        if not url and event_id:
            url = f"{self.base_url}/e/{event_id}"

        # Dates
        event_date = None
        end_date = None

        start_data = data.get('start', {})
        if start_data:
            try:
                start_str = start_data.get('local') or start_data.get('utc')
                if start_str:
                    event_date = date_parser.parse(start_str)
            except:
                pass

        end_data = data.get('end', {})
        if end_data:
            try:
                end_str = end_data.get('local') or end_data.get('utc')
                if end_str:
                    end_date = date_parser.parse(end_str)
            except:
                pass

        # Venue - try to get from primary_venue
        venue_name = ''
        address = ''

        venue = data.get('primary_venue', {})
        if venue:
            venue_name = venue.get('name', '')
            venue_address = venue.get('address', {})
            if venue_address:
                street = venue_address.get('address_1', '')
                city = venue_address.get('city', '')
                state = venue_address.get('region', '')
                postal = venue_address.get('postal_code', '')
                address_parts = [p for p in [street, city, state, postal] if p]
                address = ', '.join(address_parts) if address_parts else ''

        # Check venue_id to determine location
        venue_id = data.get('venue_id', '')

        # If no venue found, try to infer from title or use default
        if not venue_name:
            if 'venice' in title.lower() or 'aviator nation' in title.lower():
                venue_name = 'Aviator Nation Venice'
                address = '1224 Abbot Kinney Blvd, Venice, CA 90291'
            elif 'la jolla' in title.lower():
                venue_name = 'Aviator Nation La Jolla'
                address = '909 Prospect St, La Jolla, CA 92037'
            else:
                # Default to Venice (most common)
                venue_name = 'Aviator Nation Venice'
                address = '1224 Abbot Kinney Blvd, Venice, CA 90291'

        # Image
        image_url = ''
        if 'logo_id' in data or 'logo' in data:
            logo_data = data.get('logo', {})
            if isinstance(logo_data, dict):
                image_url = logo_data.get('url', '') or logo_data.get('original', {}).get('url', '')

        # Price
        is_free = data.get('is_free', False)
        price = None

        # Some events may have ticket_availability in the list view
        ticket_availability = data.get('ticket_availability', {})
        if ticket_availability:
            min_price = ticket_availability.get('minimum_ticket_price', {})
            if min_price:
                try:
                    price_value = min_price.get('major_value')
                    if price_value is not None:
                        price = float(price_value)
                        if price == 0:
                            is_free = True
                except:
                    pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=None,  # Will be auto-classified by create_event
            price=price,
            is_free=is_free
        )

    def _scrape_event_page(self, url: str) -> Optional[Event]:
        """
        Scrape a single event page using window.__SERVER_DATA__.

        Args:
            url: Event page URL

        Returns:
            Event object or None if parsing fails
        """
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            # Try to extract window.__SERVER_DATA__
            match = re.search(r'window\.__SERVER_DATA__\s*=\s*(\{[^;]*\});?\s*(?:window\.|</script>)', html, re.DOTALL)
            if not match:
                return None

            # Parse the JavaScript object as JSON
            try:
                json_str = match.group(1)
                # Remove trailing commas that aren't valid JSON
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.log(f"Failed to parse SERVER_DATA for {url}: {e}")
                return None

            # Navigate to event data in SERVER_DATA structure
            event_data = data.get('event', {})
            if not event_data:
                event_data = data.get('listing', {})

            if not event_data:
                return None

            return self._parse_event_from_server_data(event_data)

        except Exception as e:
            self.log(f"Error scraping event page {url}: {e}")
            return None

    def _parse_event_from_server_data(self, data: dict) -> Optional[Event]:
        """
        Parse event from window.__SERVER_DATA__ format.

        Args:
            data: Event data from __SERVER_DATA__

        Returns:
            Event object or None if parsing fails
        """
        # Title
        title_data = data.get('name', '')
        if isinstance(title_data, dict):
            title = title_data.get('text', '')
        else:
            title = title_data

        if not title:
            return None

        # Description
        description = data.get('summary', '') or data.get('description', '')

        # URL - build from event ID
        event_id = data.get('id', '')
        url = f"{self.base_url}/e/{event_id}" if event_id else data.get('url', '')

        # Dates
        event_date = None
        end_date = None

        start_data = data.get('start', {})
        if start_data:
            try:
                start_str = start_data.get('local') or start_data.get('utc')
                if start_str:
                    event_date = date_parser.parse(start_str)
            except:
                pass

        end_data = data.get('end', {})
        if end_data:
            try:
                end_str = end_data.get('local') or end_data.get('utc')
                if end_str:
                    end_date = date_parser.parse(end_str)
            except:
                pass

        # Venue
        venue_name = ''
        address = ''

        venue = data.get('primary_venue', {})
        if venue:
            venue_name = venue.get('name', '')

            venue_address = venue.get('address', {})
            if venue_address:
                street = venue_address.get('address_1', '')
                city = venue_address.get('city', '')
                state = venue_address.get('region', '')
                postal = venue_address.get('postal_code', '')

                address_parts = [p for p in [street, city, state, postal] if p]
                address = ', '.join(address_parts) if address_parts else ''

        # If no venue found, use Aviator Nation Venice Beach as default
        # (most events are at this location)
        if not venue_name:
            venue_name = 'Aviator Nation Venice'
            address = '1224 Abbot Kinney Blvd, Venice, CA 90291'

        # Image
        image_url = ''
        image_data = data.get('image', {})
        if image_data:
            image_url = image_data.get('url', '') or image_data.get('original', {}).get('url', '')

        # Price
        is_free = data.get('is_free', False)
        price = None

        ticket_availability = data.get('ticket_availability', {})
        if ticket_availability:
            min_price = ticket_availability.get('minimum_ticket_price', {})
            if min_price:
                try:
                    price_value = min_price.get('major_value')
                    if price_value is not None:
                        price = float(price_value)
                        if price == 0:
                            is_free = True
                except:
                    pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=None,  # Will be auto-classified by create_event
            price=price,
            is_free=is_free
        )

    def scrape_bandsintown_attempt(self) -> List[Event]:
        """
        Original attempt to scrape from Bandsintown API (non-functional).
        Kept for reference - may work with proper authentication.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape via Bandsintown API...")
        events = []

        try:
            # Fetch events from Bandsintown API
            # NOTE: This endpoint requires authentication or uses client-side rendering
            api_url = f"{self.bandsintown_api}?venueId={self.bandsintown_venue_id}"

            response = self.session.get(
                api_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
            )

            if response.status_code != 200:
                self.log(f"API returned status code {response.status_code}")
                return events

            data = response.json()

            # Bandsintown returns events in a specific format
            if not data or not isinstance(data, list):
                self.log(f"No events found or unexpected data format")
                return events

            self.log(f"Found {len(data)} events from Bandsintown API")

            for i, event_data in enumerate(data, 1):
                try:
                    event = self._parse_event(event_data)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(data)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, event_data: dict) -> Optional[Event]:
        """
        Parse a single event from Bandsintown API data.

        Args:
            event_data: Dictionary containing event data from Bandsintown API

        Returns:
            Event object or None if parsing fails
        """
        # Extract artist information
        artist_name = ''
        if 'artist' in event_data:
            if isinstance(event_data['artist'], dict):
                artist_name = event_data['artist'].get('name', '')
            elif isinstance(event_data['artist'], str):
                artist_name = event_data['artist']
        elif 'artistName' in event_data:
            artist_name = event_data['artistName']
        elif 'lineup' in event_data and event_data['lineup']:
            # Sometimes lineup is an array of artist names
            if isinstance(event_data['lineup'], list) and len(event_data['lineup']) > 0:
                artist_name = event_data['lineup'][0]

        if not artist_name:
            self.log("No artist name found, skipping event")
            return None

        # Create title from artist name
        title = artist_name

        # Extract date/time
        event_date = None
        date_str = event_data.get('datetime', event_data.get('date', ''))
        if date_str:
            try:
                # Bandsintown datetime format: "2025-11-15T20:00:00"
                event_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception as e:
                self.log(f"Could not parse date '{date_str}': {e}")

        # Extract event URL
        event_url = event_data.get('url', event_data.get('ticketUrl', self.bandsintown_api_url))

        # Extract image URL
        image_url = ''
        if 'artist' in event_data and isinstance(event_data['artist'], dict):
            image_url = event_data['artist'].get('image', event_data['artist'].get('imageUrl', ''))
        elif 'image' in event_data:
            image_url = event_data['image']
        elif 'imageUrl' in event_data:
            image_url = event_data['imageUrl']

        # Extract description
        description = event_data.get('description', '')
        if not description:
            description = f"{artist_name} live at {self.venue_name}"

            # Add additional artists if there's a lineup
            if 'lineup' in event_data and isinstance(event_data['lineup'], list):
                if len(event_data['lineup']) > 1:
                    other_artists = event_data['lineup'][1:]
                    description += f" with {', '.join(other_artists)}"

        # Check if event is on sale, sold out, etc.
        is_free = False
        offers = event_data.get('offers', [])
        if offers and isinstance(offers, list):
            for offer in offers:
                if offer.get('status', '').lower() == 'free':
                    is_free = True
                    break

        # Try to extract price
        price = None
        if offers and isinstance(offers, list) and len(offers) > 0:
            price_str = offers[0].get('price', offers[0].get('minPrice', ''))
            if price_str:
                try:
                    price = float(price_str)
                except:
                    pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=None,
            url=event_url,
            image_url=image_url,
            category='Music',  # Aviator Nation is primarily a music venue
            price=price,
            is_free=is_free
        )

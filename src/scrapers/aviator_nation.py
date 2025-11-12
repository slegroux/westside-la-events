"""
Scraper for Aviator Nation Dreamland events in Malibu.
Source: https://aviatornationdreamland.com/pages/event-calendar-custom

Note: Aviator Nation uses Bandsintown for event ticketing and listings.
Bandsintown venue ID: 10320209

IMPLEMENTATION NOTE:
Bandsintown's API requires authentication or uses client-side rendering that's difficult
to scrape directly. Alternative approaches:
1. Use Eventbrite scraper (many Aviator Nation events are on Eventbrite)
2. Scrape from Songkick (https://www.songkick.com/venues/4473685-aviator-nation-dreamland)
3. Implement Playwright-based scraping for Bandsintown page

Current implementation returns empty list - needs enhancement.
"""
from datetime import datetime
from typing import List, Optional
import json

from .base import BaseScraper
from src.data.models import Event


class AviatorNationScraper(BaseScraper):
    """Scraper for Aviator Nation Dreamland events via Bandsintown."""

    def __init__(self):
        super().__init__('Aviator Nation Dreamland')
        self.base_url = 'https://aviatornationdreamland.com'
        self.bandsintown_venue_id = '10320209'
        self.bandsintown_api_url = 'https://www.bandsintown.com/v/10320209-aviator-nation-dreamland'
        self.bandsintown_api = 'https://www.bandsintown.com/api/venue-events'
        self.venue_name = 'Aviator Nation Dreamland'
        self.venue_address = '22969 Pacific Coast Hwy, Malibu, CA 90265'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aviator Nation.

        NOTE: Current implementation incomplete - Bandsintown requires client-side rendering.
        Aviator Nation events can be found via:
        - Eventbrite scraper (organizer: Aviator Nation Dreamland)
        - Songkick API
        - Direct Bandsintown page scraping with Playwright

        Returns:
            Empty list (implementation incomplete)
        """
        self.log("Scraper incomplete - Aviator Nation events available via Eventbrite")
        self.log("Search Eventbrite for organizer: 'Aviator Nation Dreamland'")
        return []

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
            category='music',  # Aviator Nation is primarily a music venue
            price=price,
            is_free=is_free
        )

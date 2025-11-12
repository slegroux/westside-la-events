"""
Scraper for Gnarwhal Coffee events in Santa Monica.
Source: https://www.gnarwhalcoffee.com/events

Gnarwhal Coffee uses Squarespace for their website with an events collection.
This scraper uses the Squarespace API to fetch events by month.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class GnarwhalScraper(BaseScraper):
    """Scraper for Gnarwhal Coffee events via Squarespace API."""

    def __init__(self):
        super().__init__('Gnarwhal Coffee')
        self.base_url = 'https://www.gnarwhalcoffee.com'
        self.events_url = f'{self.base_url}/events'
        self.api_url = f'{self.base_url}/api/open/GetItemsByMonth'
        self.collection_id = '685469328f26260258e0e914'  # Events collection ID
        self.venue_name = 'Gnarwhal Coffee'
        self.venue_address = '3101 Main Street, Santa Monica, CA 90405'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Gnarwhal Coffee via Squarespace API.

        The API requires month in format MM-YY (e.g., "11-25" for November 2025).
        We'll fetch events for the current month and next 3 months.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape via Squarespace API...")
        events = []

        try:
            # Get current date
            current_date = datetime.now()

            # Fetch events for current month and next 3 months
            for month_offset in range(4):
                target_date = current_date + timedelta(days=30 * month_offset)
                month_str = target_date.strftime('%m-%y')  # Format: MM-YY

                self.log(f"Fetching events for {target_date.strftime('%B %Y')} ({month_str})...")

                url = f"{self.api_url}?collectionId={self.collection_id}&month={month_str}"

                response = self.session.get(url, headers={'User-Agent': 'Mozilla/5.0'})

                if response.status_code != 200:
                    self.log(f"API returned status code {response.status_code} for {month_str}")
                    continue

                month_events = response.json()

                if not isinstance(month_events, list):
                    self.log(f"Unexpected data format for {month_str}")
                    continue

                self.log(f"Found {len(month_events)} events in {target_date.strftime('%B %Y')}")

                for event_data in month_events:
                    try:
                        event = self._parse_event(event_data)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

            self.log(f"Successfully scraped {len(events)} total events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, data: dict) -> Optional[Event]:
        """
        Parse a single event from Squarespace API data.

        Squarespace events typically have structure:
        {
            "id": "...",
            "title": "Event Title",
            "body": "<p>Description HTML</p>",
            "startDate": 1234567890000,  # Unix timestamp in milliseconds
            "endDate": 1234567890000,
            "location": {"addressTitle": "Venue Name", ...},
            "assetUrl": "https://...",  # Image URL
            ...
        }

        Args:
            data: Event data from Squarespace API

        Returns:
            Event object or None if parsing fails
        """
        # Title
        title = data.get('title', '')
        if not title:
            return None

        # Description - Squarespace stores HTML in 'body'
        description = data.get('body', '')
        # Strip HTML tags for plain text description
        if description:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(description, 'html.parser')
            description = soup.get_text(strip=True)

        # Dates - Squarespace uses Unix timestamps in milliseconds
        event_date = None
        end_date = None

        start_timestamp = data.get('startDate')
        if start_timestamp:
            try:
                # Convert milliseconds to seconds
                event_date = datetime.fromtimestamp(start_timestamp / 1000)
            except Exception as e:
                self.log(f"Could not parse start date {start_timestamp}: {e}")

        end_timestamp = data.get('endDate')
        if end_timestamp:
            try:
                end_date = datetime.fromtimestamp(end_timestamp / 1000)
            except Exception as e:
                self.log(f"Could not parse end date {end_timestamp}: {e}")

        # URL - build from event ID
        event_id = data.get('id', '')
        url = f"{self.events_url}/{event_id}" if event_id else self.events_url

        # Also check for fullUrl
        if 'fullUrl' in data:
            url = f"{self.base_url}{data['fullUrl']}"

        # Image URL
        image_url = data.get('assetUrl', '')

        # Location - Squarespace events can have location data
        location = data.get('location', {})
        venue_name = self.venue_name
        address = self.venue_address

        if location:
            # Check if event is at a different location
            location_title = location.get('addressTitle', '')
            if location_title and location_title.lower() != 'gnarwhal':
                venue_name = location_title

                # Build address from location data
                address_line1 = location.get('addressLine1', '')
                address_line2 = location.get('addressLine2', '')
                city = location.get('addressCountry', '')  # Squarespace field names vary

                address_parts = [p for p in [address_line1, address_line2, city] if p]
                if address_parts:
                    address = ', '.join(address_parts)

        # Price info - check if mentioned in title or description
        is_free = False
        price = None

        # Check for free events
        if 'free' in title.lower() or 'free' in description.lower():
            is_free = True
        else:
            # Try to extract price from description or title
            import re
            price_text = f"{title} {description}"
            price_match = re.search(r'\$(\d+(?:\.\d{2})?)', price_text)
            if price_match:
                try:
                    price = float(price_match.group(1))
                except ValueError:
                    pass

        return self.create_event(
            title=title,
            description=description or f"Event at {self.venue_name}",
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category='',  # Will be auto-classified by create_event
            price=price,
            is_free=is_free
        )

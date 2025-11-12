"""
Scraper for Meetup events in Los Angeles.
Source: https://www.meetup.com/find/events/?location=us--ca--los-angeles
"""
import json
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class MeetupScraper(BaseScraper):
    """Scraper for Meetup events (no API key required)."""

    def __init__(self):
        super().__init__('Meetup')
        self.base_url = 'https://www.meetup.com'
        self.events_url = f'{self.base_url}/find/events/?location=us--ca--los-angeles'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Meetup LA page.
        Extracts event data from Apollo GraphQL state embedded in Next.js page.

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

            # Extract Next.js data which contains Apollo GraphQL state
            next_data_script = soup.find('script', id='__NEXT_DATA__')
            if not next_data_script:
                self.log("No __NEXT_DATA__ found")
                return events

            next_data = json.loads(next_data_script.string)
            apollo_state = next_data.get('props', {}).get('pageProps', {}).get('__APOLLO_STATE__', {})

            if not apollo_state:
                self.log("No Apollo state found")
                return events

            # Extract event objects from Apollo state
            event_keys = [k for k in apollo_state.keys()
                         if k.startswith('Event:') and k.count(':') == 1]

            self.log(f"Found {len(event_keys)} events in Apollo state")

            for event_key in event_keys:
                try:
                    event_data = apollo_state[event_key]
                    event = self._parse_event_from_apollo(event_data, apollo_state)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event {event_key}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event_from_apollo(self, event_data: dict, apollo_state: dict) -> Optional[Event]:
        """
        Parse event from Apollo GraphQL state.

        Args:
            event_data: Event object from Apollo state
            apollo_state: Full Apollo state for resolving references

        Returns:
            Event object or None if parsing fails
        """
        # Title
        title = event_data.get('title', '')
        if not title:
            return None

        # Description
        description = event_data.get('description', '')

        # URL
        url = event_data.get('eventUrl', '')

        # Date
        event_date = None
        date_str = event_data.get('dateTime')
        if date_str:
            try:
                event_date = date_parser.parse(date_str)
            except:
                pass

        # Group info (for location context)
        group_ref = event_data.get('group', {}).get('__ref')
        group_name = ''
        if group_ref and group_ref in apollo_state:
            group = apollo_state[group_ref]
            group_name = group.get('name', '')

        # Venue/Location - Meetup events often don't have structured venue data
        # Try to extract from description or use "Los Angeles, CA" as default
        venue_name = ""
        address = "Los Angeles, CA"  # Default

        # Some events might have location in the title
        if '@' in title:
            # Example: "Event @ Venue Name"
            parts = title.split('@')
            if len(parts) > 1:
                venue_name = parts[-1].strip()
                address = f"{venue_name}, Los Angeles, CA"

        # Image
        image_url = ""
        photo_ref = event_data.get('featuredEventPhoto', {}).get('__ref')
        if photo_ref and photo_ref in apollo_state:
            photo = apollo_state[photo_ref]
            base_url = photo.get('baseUrl', '')
            photo_id = photo.get('id', '')
            if base_url and photo_id:
                # Meetup image URLs are typically: baseUrl + photo_id + '.jpeg'
                image_url = f"{base_url}{photo_id}.jpeg"

        # Price - check if event has fees
        fee_settings = event_data.get('feeSettings')
        is_free = fee_settings is None
        price = None
        if fee_settings:
            # Fee settings exist, event likely has a cost
            # Would need to parse fee_settings structure if available
            is_free = False

        # RSVP count (could be useful)
        rsvp_data = event_data.get('rsvps', {})
        attendee_count = rsvp_data.get('totalCount', 0)

        # Category - will be auto-classified
        category = None

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=None,  # Meetup typically doesn't provide end date in listing
            url=url,
            image_url=image_url,
            category=category,  # Will be auto-classified
            price=price,
            is_free=is_free
        )

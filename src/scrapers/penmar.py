"""
Scraper for The Penmar events via Eventbrite.
Source: https://www.eventbrite.com/o/world-of-sound-productions-34157573931

The Penmar hosts regular events including:
- Sunset Vibes Silent Disco (monthly, Saturdays at 6pm)
- Sunset Sessions (weekly, Fridays 6pm-9pm)

Events are organized by World of Sound Productions and hosted at
The Penmar Golf Course (Clubhouse at 1233 Rose Ave, Venice, CA 90291).
"""
from datetime import datetime
from typing import List, Optional
import json
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class PenmarScraper(BaseScraper):
    """Scraper for The Penmar events via Eventbrite."""

    def __init__(self):
        super().__init__('The Penmar')
        self.base_url = 'https://www.eventbrite.com'
        # World of Sound Productions organizer page
        self.organizer_url = 'https://www.eventbrite.com/o/world-of-sound-productions-34157573931'
        self.venue_name = 'The Penmar'
        self.venue_address = '1233 Rose Ave, Venice, CA 90291'

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Penmar via World of Sound Productions Eventbrite.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from Eventbrite organizer page...")
        events = []

        try:
            events = self._scrape_organizer_page()
            self.log(f"Successfully scraped {len(events)} total events")
        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_organizer_page(self) -> List[Event]:
        """
        Scrape the World of Sound Productions organizer page by extracting
        event data from the Next.js __NEXT_DATA__ payload.

        Returns:
            List of Event objects
        """
        events = []

        try:
            html = self.fetch_page(self.organizer_url)
            if not html:
                self.log(f"Failed to fetch organizer page: {self.organizer_url}")
                return events

            # Eventbrite organizer pages are now Next.js apps. Event listings
            # live in the __NEXT_DATA__ JSON blob at props.pageProps.upcomingEvents.
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                html, re.DOTALL,
            )
            if not match:
                self.log("No __NEXT_DATA__ found on page")
                return events

            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError as e:
                self.log(f"Failed to parse __NEXT_DATA__: {e}")
                return events

            page_props = data.get('props', {}).get('pageProps', {})
            upcoming_events = page_props.get('upcomingEvents', []) or []

            all_events = list(upcoming_events)
            self.log(f"Found {len(upcoming_events)} upcoming events")

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

        # If no description, create one based on event details
        if not description:
            if 'silent disco' in title.lower():
                description = (
                    f"Sunset Vibes Silent Disco at The Penmar Golf Course featuring multiple stages "
                    f"with DJs and live performances. Dance under the stars with headphones at this "
                    f"unique outdoor music experience. All ages welcome. Full bar and restaurant available."
                )
            elif 'sunset session' in title.lower():
                description = (
                    f"Live music performance at The Penmar's weekly Sunset Sessions. "
                    f"Enjoy great music, food, drinks, and stunning sunset views every Friday evening."
                )
            else:
                description = f"Event at {self.venue_name} in Venice Beach."

        # URL - build from event ID
        event_id = data.get('id') or data.get('eventbrite_event_id') or ''
        url = data.get('url', '')
        if not url and event_id:
            url = f"{self.base_url}/e/{event_id}"

        # Dates - new __NEXT_DATA__ format uses split start_date/start_time strings,
        # legacy format used nested start/end dicts with 'local'/'utc'.
        event_date = None
        end_date = None

        start_data = data.get('start', {})
        if isinstance(start_data, dict) and (start_data.get('local') or start_data.get('utc')):
            try:
                event_date = date_parser.parse(start_data.get('local') or start_data.get('utc'))
            except Exception:
                pass
        elif data.get('start_date'):
            try:
                start_str = f"{data['start_date']}T{data.get('start_time') or '00:00:00'}"
                event_date = date_parser.parse(start_str)
            except Exception:
                pass

        end_data = data.get('end', {})
        if isinstance(end_data, dict) and (end_data.get('local') or end_data.get('utc')):
            try:
                end_date = date_parser.parse(end_data.get('local') or end_data.get('utc'))
            except Exception:
                pass
        elif data.get('end_date'):
            try:
                end_str = f"{data['end_date']}T{data.get('end_time') or '00:00:00'}"
                end_date = date_parser.parse(end_str)
            except Exception:
                pass

        # Venue - extract from title or use from event data
        venue_name = self.venue_name
        address = self.venue_address

        # Try to determine venue from title
        title_lower = title.lower()
        if 'penmar' in title_lower:
            venue_name = 'The Penmar'
            address = '1233 Rose Ave, Venice, CA 90291'
        elif 'waterfront' in title_lower:
            venue_name = 'The Waterfront Venice'
            address = '205 Ocean Front Walk, Venice, CA 90291'
        elif 'vista' in title_lower or 'hermosa' in title_lower:
            # Events at other locations (Hermosa Beach)
            venue_name = 'Vista at Hermosa Beach'
            address = 'Hermosa Beach, CA'
        else:
            # Try to extract venue from event data
            venue = data.get('primary_venue', {})
            if venue:
                venue_name_from_data = venue.get('name', '')
                if venue_name_from_data:
                    venue_name = venue_name_from_data

                venue_address = venue.get('address', {})
                if venue_address:
                    street = venue_address.get('address_1', '')
                    city = venue_address.get('city', '')
                    state = venue_address.get('region', '')
                    postal = venue_address.get('postal_code', '')
                    address_parts = [p for p in [street, city, state, postal] if p]
                    if address_parts:
                        address = ', '.join(address_parts)

        # Image - new __NEXT_DATA__ uses 'image', legacy used 'logo'
        image_url = ''
        image_data = data.get('image') or data.get('logo')
        if isinstance(image_data, dict):
            image_url = (
                image_data.get('url', '')
                or (image_data.get('original') or {}).get('url', '')
            )
        elif isinstance(image_data, str):
            image_url = image_data

        # Price
        is_free = data.get('is_free', False)
        price = None

        # Try to extract price from ticket_availability
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

        # Determine category - most Penmar events are music
        category = 'Music'
        if 'silent disco' in title.lower():
            category = 'Music'
        elif 'comedy' in title.lower():
            category = 'Comedy'
        elif 'trivia' in title.lower() or 'bingo' in title.lower():
            category = 'Other'

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

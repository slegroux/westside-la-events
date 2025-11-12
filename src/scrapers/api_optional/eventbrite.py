"""
Scraper for Eventbrite events using the official API.
Documentation: https://www.eventbrite.com/platform/api
"""
from datetime import datetime, timedelta
from typing import List
import requests

from .base import BaseScraper
from src.data.models import Event
import config


class EventbriteScraper(BaseScraper):
    """Scraper for Eventbrite events using API."""

    def __init__(self, api_token: str = None):
        super().__init__('Eventbrite')
        self.api_token = api_token or config.EVENTBRITE_API_TOKEN
        self.api_base = 'https://www.eventbriteapi.com/v3'

        if self.api_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_token}'
            })

    def scrape(self) -> List[Event]:
        """
        Scrape events from Eventbrite API.

        Returns:
            List of Event objects
        """
        self.log("Starting Eventbrite API scrape...")

        if not self.api_token:
            self.log("Error: EVENTBRITE_API_TOKEN not configured")
            return []

        events = []

        try:
            # Search for events in LA area
            # Eventbrite uses latitude/longitude with radius
            params = {
                'location.latitude': config.MAP_CENTER['lat'],
                'location.longitude': config.MAP_CENTER['lng'],
                'location.within': '15mi',  # 15 mile radius
                'start_date.range_start': datetime.now().isoformat(),
                'start_date.range_end': (datetime.now() + timedelta(days=90)).isoformat(),
                'expand': 'venue,category',
                'page_size': 50
            }

            page = 1
            has_more_pages = True

            while has_more_pages and page <= 5:  # Limit to 5 pages
                params['page'] = page

                response = self.session.get(
                    f'{self.api_base}/events/search/',
                    params=params,
                    timeout=config.SCRAPER_CONFIG['timeout_seconds']
                )

                if response.status_code != 200:
                    self.log(f"Error: API returned status {response.status_code}")
                    break

                data = response.json()

                for event_data in data.get('events', []):
                    try:
                        event = self._parse_event(event_data)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

                # Check for more pages
                pagination = data.get('pagination', {})
                has_more_pages = pagination.get('has_more_items', False)
                page += 1

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, data: dict) -> Event:
        """
        Parse a single event from API response.

        Args:
            data: Event data from API

        Returns:
            Event object
        """
        # Extract basic info
        title = data.get('name', {}).get('text', 'Untitled Event')
        description = data.get('description', {}).get('text', '')
        url = data.get('url', '')
        image_url = data.get('logo', {}).get('url', '')

        # Extract dates
        start = data.get('start', {})
        end = data.get('end', {})

        event_date = None
        if start.get('utc'):
            try:
                event_date = datetime.fromisoformat(start['utc'].replace('Z', '+00:00'))
            except Exception:
                pass

        end_date = None
        if end.get('utc'):
            try:
                end_date = datetime.fromisoformat(end['utc'].replace('Z', '+00:00'))
            except Exception:
                pass

        # Extract venue info
        venue = data.get('venue', {})
        venue_name = venue.get('name', '')

        # Build address
        address_parts = []
        if venue.get('address'):
            addr = venue['address']
            if addr.get('address_1'):
                address_parts.append(addr['address_1'])
            if addr.get('city'):
                address_parts.append(addr['city'])
            if addr.get('region'):
                address_parts.append(addr['region'])

        address = ', '.join(address_parts) if address_parts else ''

        # Get coordinates
        latitude = venue.get('latitude')
        longitude = venue.get('longitude')

        # Convert to float if they're strings
        if latitude and isinstance(latitude, str):
            latitude = float(latitude)
        if longitude and isinstance(longitude, str):
            longitude = float(longitude)

        # Extract category
        category_data = data.get('category', {})
        category = category_data.get('name', '') if category_data else ''

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category
        )

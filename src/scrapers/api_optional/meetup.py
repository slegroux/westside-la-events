"""
Scraper for Meetup events.
Can use either GraphQL API or web scraping depending on API availability.
"""
from datetime import datetime, timedelta
from typing import List
import requests

from .base import BaseScraper
from src.data.models import Event
import config


class MeetupScraper(BaseScraper):
    """Scraper for Meetup events."""

    def __init__(self):
        super().__init__('Meetup')
        self.base_url = 'https://www.meetup.com'
        # Meetup's GraphQL endpoint (may require authentication)
        self.graphql_url = 'https://www.meetup.com/gql'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Meetup.

        Returns:
            List of Event objects
        """
        self.log("Starting Meetup scrape...")
        events = []

        try:
            # Try using their public API endpoint first
            events = self._scrape_from_api()

            if not events:
                self.log("API scraping failed, trying web scraping...")
                events = self._scrape_from_web()

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _scrape_from_api(self) -> List[Event]:
        """
        Attempt to scrape using Meetup's API/GraphQL.

        Returns:
            List of Event objects
        """
        events = []

        try:
            # Search for events in LA area
            # This is a simplified query - actual GraphQL query may differ
            query = """
            query($lat: Float!, $lon: Float!, $radius: Int!) {
                rankedEvents(filter: {
                    lat: $lat
                    lon: $lon
                    radius: $radius
                    startDateRange: "today"
                }) {
                    edges {
                        node {
                            id
                            title
                            description
                            dateTime
                            endTime
                            eventUrl
                            venue {
                                name
                                address
                                city
                                state
                                lat
                                lng
                            }
                            group {
                                name
                            }
                            featuredEventPhoto {
                                source
                            }
                        }
                    }
                }
            }
            """

            variables = {
                'lat': config.MAP_CENTER['lat'],
                'lon': config.MAP_CENTER['lng'],
                'radius': 15  # miles
            }

            response = self.session.post(
                self.graphql_url,
                json={'query': query, 'variables': variables},
                timeout=config.SCRAPER_CONFIG['timeout_seconds']
            )

            if response.status_code == 200:
                data = response.json()
                edges = data.get('data', {}).get('rankedEvents', {}).get('edges', [])

                for edge in edges:
                    node = edge.get('node', {})
                    event = self._parse_api_event(node)
                    if event:
                        events.append(event)

        except Exception as e:
            self.log(f"API scraping error: {e}")

        return events

    def _scrape_from_web(self) -> List[Event]:
        """
        Scrape events from Meetup web pages.

        Returns:
            List of Event objects
        """
        events = []

        try:
            # Try scraping from LA events page
            url = f'{self.base_url}/find/events/?allMeetups=false&radius=15&userFreeform=Los+Angeles%2C+CA'

            html = self.fetch_page(url)
            if not html:
                return events

            soup = self.parse_html(html)

            # Note: Actual selectors will depend on Meetup's current HTML structure
            # This is a template that needs adjustment
            event_cards = soup.find_all('div', {'data-testid': 'event-card'})

            for card in event_cards:
                try:
                    event = self._parse_web_event(card)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event card: {e}")
                    continue

        except Exception as e:
            self.log(f"Web scraping error: {e}")

        return events

    def _parse_api_event(self, node: dict) -> Event:
        """Parse event from API response."""
        title = node.get('title', 'Untitled Event')
        description = node.get('description', '')
        url = node.get('eventUrl', '')
        image_url = node.get('featuredEventPhoto', {}).get('source', '')

        # Parse dates
        event_date = None
        if node.get('dateTime'):
            try:
                event_date = datetime.fromisoformat(node['dateTime'].replace('Z', '+00:00'))
            except Exception:
                pass

        end_date = None
        if node.get('endTime'):
            try:
                end_date = datetime.fromisoformat(node['endTime'].replace('Z', '+00:00'))
            except Exception:
                pass

        # Venue info
        venue = node.get('venue', {})
        venue_name = venue.get('name', '') or node.get('group', {}).get('name', '')

        address_parts = []
        if venue.get('address'):
            address_parts.append(venue['address'])
        if venue.get('city'):
            address_parts.append(venue['city'])
        if venue.get('state'):
            address_parts.append(venue['state'])

        address = ', '.join(address_parts) if address_parts else ''

        latitude = venue.get('lat')
        longitude = venue.get('lng')

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url
        )

    def _parse_web_event(self, card) -> Event:
        """Parse event from web page HTML."""
        # This is a template - actual implementation depends on HTML structure
        title_elem = card.find('h3') or card.find('h2')
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        desc_elem = card.find('p', class_='description')
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        link_elem = card.find('a', href=True)
        url = self.normalize_url(link_elem['href'], self.base_url) if link_elem else ""

        # More parsing would go here...

        return self.create_event(
            title=title,
            description=description,
            url=url
        )

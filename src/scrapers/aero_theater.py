"""
Scraper for Aero Theater (American Cinematheque) events.
Source: https://www.americancinematheque.com/wp-json/wp/v2/event

Note: This site uses WordPress REST API. We fetch events directly from the
event API (not the product API) which includes images via _embed parameter.
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re
import requests

from .base import BaseScraper
from src.data.models import Event


class AeroTheaterScraper(BaseScraper):
    """Scraper for Aero Theater events."""

    def __init__(self):
        super().__init__('Aero Theater')
        self.base_url = 'https://www.americancinematheque.com'
        self.api_url = f'{self.base_url}/wp-json/wp/v2/event'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aero Theater using WordPress REST API.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch events from API (paginated)
            page = 1
            per_page = 50  # Use smaller page size since _embed is slower

            while True:
                params = {
                    'per_page': per_page,
                    'page': page,
                    'event_location': 54,  # Aero Theatre location ID for event API
                    '_embed': 1  # Include embedded media data (images)
                }

                self.log(f"Fetching page {page} from API...")
                response = requests.get(self.api_url, params=params, timeout=120)

                if response.status_code != 200:
                    self.log(f"API returned status {response.status_code}")
                    break

                event_data = response.json()

                if not event_data:
                    break

                self.log(f"Found {len(event_data)} events on page {page}")

                for item in event_data:
                    try:
                        event = self._parse_event(item)
                        if event:
                            events.append(event)
                            self.log(f"Parsed: {event.title}")
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

                # Check if there are more pages
                if len(event_data) < per_page:
                    break

                page += 1

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, event: dict) -> Optional[Event]:
        """
        Parse an event from the WordPress API response.

        Args:
            event: Dictionary containing event data from API

        Returns:
            Event object or None
        """
        try:
            # Extract title
            raw_title = event.get('title', {}).get('rendered', '')
            if not raw_title:
                return None

            # Clean up HTML entities
            import html
            from bs4 import BeautifulSoup
            title = html.unescape(BeautifulSoup(raw_title, 'html.parser').get_text())

            # Extract ACF (Advanced Custom Fields) data
            acf_data = event.get('acf', {})

            # Extract date and time - MUST have a date to be a valid event
            # The API provides date in YYYYMMDD format and time as separate field
            event_date = None

            # Get date and time from ACF fields
            date_str = acf_data.get('event_start_date', '')  # Format: YYYYMMDD (e.g., "20251116")
            time_str = acf_data.get('event_start_time', '')  # Format: "11:00 am"

            if date_str:
                try:
                    # Combine date and time for accurate parsing
                    if time_str:
                        # Parse YYYYMMDD format and combine with time
                        combined = f"{date_str} {time_str}"
                        event_date = date_parser.parse(combined)
                    else:
                        # Parse just the date in YYYYMMDD format
                        event_date = datetime.strptime(date_str, '%Y%m%d')
                except Exception as e:
                    self.log(f"Error parsing date '{date_str}' with time '{time_str}': {e}")
                    pass

            # Fallback: try event_date field
            if not event_date:
                date_str = acf_data.get('event_date', '')
                if date_str:
                    try:
                        event_date = date_parser.parse(date_str)
                    except:
                        pass

            # Fallback: try post date
            if not event_date:
                date_str = event.get('date', '')
                if date_str:
                    try:
                        event_date = date_parser.parse(date_str)
                    except:
                        pass

            if not event_date:
                self.log(f"No date found for event: {title}")
                return None

            # Skip past events (older than yesterday)
            if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                return None

            # Extract description
            description = ""
            content = event.get('content', {}).get('rendered', '')
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                description = self.clean_text(soup.get_text())

            # Extract URL
            url = event.get('link', '')

            # Extract image from ACF event_card_image field (primary) or embedded data (fallback)
            image_url = ""
            try:
                # Try ACF event_card_image first (this is what American Cinematheque uses)
                event_card_image = acf_data.get('event_card_image', {})
                if isinstance(event_card_image, dict) and 'url' in event_card_image:
                    image_url = event_card_image['url']

                # Fallback to embedded featured media if no ACF image
                if not image_url:
                    embedded = event.get('_embedded', {})
                    featured_media = embedded.get('wp:featuredmedia', [])
                    if featured_media and len(featured_media) > 0:
                        image_url = featured_media[0].get('source_url', '')
            except Exception as e:
                self.log(f"Error extracting image: {e}")
                pass

            # Extract price info
            is_free = acf_data.get('event_free', False) or acf_data.get('product_free_event', False)
            price = 0.0 if is_free else None

            # Venue details
            venue_name = "Aero Theatre"
            address = "1328 Montana Ave, Santa Monica, CA 90403"

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=None,
                url=url,
                image_url=image_url,
                category="Film",
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing event: {e}")
            return None

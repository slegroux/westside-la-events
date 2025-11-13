"""
Scraper for UCLA community events.
Source: https://community.ucla.edu
"""
import json
import re
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class UCLAScraper(BaseScraper):
    """Scraper for UCLA community events."""

    def __init__(self):
        super().__init__('UCLA')
        self.base_url = 'https://community.ucla.edu'

    def scrape(self) -> List[Event]:
        """
        Scrape events from UCLA community events calendar.

        The site loads event data dynamically via JavaScript, so we need Playwright.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Use Playwright since events are loaded dynamically
            html = self.fetch_page_js(self.base_url, wait_selector='.event-cards-home, .eventlist-events')
            if not html:
                self.log("Failed to fetch events page")
                return events

            # Extract JSON data from the HTML
            # Look for pattern: {"dates":[...]}
            json_match = re.search(r'\{"dates":\[.*?\]\}', html, re.DOTALL)
            if not json_match:
                self.log("Could not find JSON data in page, trying alternate approach...")
                # Try scraping rendered HTML instead
                soup = self.parse_html(html)
                return self._scrape_from_html(soup)

            json_str = json_match.group(0)
            data = json.loads(json_str)

            # Process events from each date group
            for date_group in data.get('dates', []):
                for event_data in date_group.get('events', []):
                    try:
                        event = self._parse_event(event_data)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, event_data: dict) -> Event:
        """
        Parse a single event from JSON data.

        Args:
            event_data: Dict containing event data

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract nested data object
            data = event_data.get('data', {})

            # Extract title
            title = data.get('title', 'Untitled Event')

            # Extract description
            description = data.get('description', '')

            # Extract date/time
            event_date = None
            start_str = data.get('start')
            if start_str:
                try:
                    event_date = date_parser.parse(start_str)
                except Exception:
                    pass

            # Calculate end date
            end_date = None
            duration = data.get('duration')
            if event_date and duration:
                from datetime import timedelta
                try:
                    # Duration is in seconds
                    end_date = event_date + timedelta(seconds=int(duration))
                except Exception:
                    pass

            # Extract location info
            locations = data.get('locations', [])
            venue_name = ''
            address = ''

            if locations:
                location = locations[0]
                venue_name = location.get('name', '')

                # Build address from components
                address_parts = []
                if location.get('address'):
                    address_parts.append(location['address'])
                if location.get('city'):
                    address_parts.append(location['city'])
                if location.get('state'):
                    address_parts.append(location['state'])
                if location.get('zip'):
                    address_parts.append(location['zip'])
                address = ', '.join(address_parts)

            # Check for virtual locations
            virtual_locations = data.get('virtualLocations', [])
            if virtual_locations and not venue_name:
                venue_name = 'Virtual Event'
                address = 'Online'

            # Extract URL - check buttons for RSVP/website links
            url = ''
            buttons = event_data.get('buttons', [])
            for button in buttons:
                if button.get('url'):
                    url = button['url']
                    break

            # Extract image
            image_url = data.get('image', '')

            # Extract price info
            is_free = True  # Default to free for UCLA events
            price = None
            price_note = ''

            # Check labels for pricing hints
            labels = event_data.get('labels', {})
            if isinstance(labels, dict):
                # Look for cost-related categories
                for key, value in labels.items():
                    if 'cost' in key.lower() or 'price' in key.lower():
                        if 'free' not in str(value).lower():
                            is_free = False
                            price_note = str(value)

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                price=price,
                is_free=is_free,
                price_note=price_note
            )

        except Exception as e:
            self.log(f"Error parsing event data: {e}")
            return None

    def _scrape_from_html(self, soup) -> List[Event]:
        """
        Fallback method to scrape from rendered HTML when JSON parsing fails.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of Event objects
        """
        events = []

        # Find event cards
        event_items = soup.find_all('article', class_=lambda x: x and 'event' in x.lower())
        if not event_items:
            event_items = soup.find_all('div', class_=lambda x: x and 'event-card' in x.lower())
        if not event_items:
            event_items = soup.find_all('a', href=lambda x: x and '/events/' in x or x and '/event/' in x)

        self.log(f"Found {len(event_items)} events via HTML parsing")

        for item in event_items:
            try:
                # Extract title
                title_elem = item.find(['h1', 'h2', 'h3', 'h4'])
                if not title_elem:
                    title_elem = item.find(class_=lambda x: x and 'title' in x.lower())
                title = self.clean_text(title_elem.get_text()) if title_elem else None

                if not title:
                    continue

                # Extract other fields
                desc_elem = item.find('p') or item.find(class_=lambda x: x and 'description' in x.lower())
                description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

                # Date
                date_elem = item.find('time')
                if not date_elem:
                    date_elem = item.find(class_=lambda x: x and 'date' in x.lower())
                event_date = None
                if date_elem:
                    try:
                        date_str = date_elem.get('datetime', '') or date_elem.get_text()
                        event_date = date_parser.parse(date_str)
                    except:
                        pass

                # URL
                url = ""
                if item.name == 'a':
                    url = item.get('href', '')
                else:
                    link = item.find('a', href=True)
                    if link:
                        url = link['href']
                if url and not url.startswith('http'):
                    url = f"{self.base_url}{url}"

                # Image
                img_elem = item.find('img')
                image_url = ""
                if img_elem:
                    image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
                    if image_url and not image_url.startswith('http'):
                        image_url = f"{self.base_url}{image_url}"

                event = self.create_event(
                    title=title,
                    description=description,
                    venue_name="UCLA",
                    address="Los Angeles, CA 90095",
                    event_date=event_date,
                    url=url,
                    image_url=image_url,
                    is_free=True
                )

                if event:
                    events.append(event)

            except Exception as e:
                self.log(f"Error parsing HTML event: {e}")
                continue

        return events

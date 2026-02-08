"""
Scraper for M.I.'s Westside Comedy Theater events.
Sources:
- https://westsidecomedy.com/ (current/near-term events)
- https://www.eventbrite.com/o/mis-westside-comedy-theater-107617136371 (far-future events)

Scrapes both the main website and Eventbrite to get complete event coverage.
"""
import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class WestsideComedyScraper(BaseScraper):
    """Scraper for M.I.'s Westside Comedy Theater events."""

    def __init__(self):
        super().__init__("M.I.'s Westside Comedy Theater")
        self.website_url = 'https://westsidecomedy.com/'
        self.eventbrite_url = 'https://www.eventbrite.com/o/mis-westside-comedy-theater-107617136371'
        self.venue_name = "M.I.'s Westside Comedy Theater"
        self.venue_address = '1323-A 3rd St Promenade, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape events from both westsidecomedy.com and Eventbrite.

        Returns:
            List of Event objects from both sources
        """
        events = []

        # Scrape current events from main website
        website_events = self._scrape_website()
        events.extend(website_events)

        # Scrape future events from Eventbrite
        eventbrite_events = self._scrape_eventbrite()
        events.extend(eventbrite_events)

        self.log(f"Total: {len(events)} events ({len(website_events)} from website, {len(eventbrite_events)} from Eventbrite)")
        return events

    def _scrape_website(self) -> List[Event]:
        """
        Scrape events from westsidecomedy.com homepage.

        The website embeds Eventbrite events, so we extract event IDs and fetch
        them directly from Eventbrite API which is faster and more reliable.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from westsidecomedy.com...")
        events = []

        try:
            html = self.fetch_page(self.website_url)
            if not html:
                self.log("Failed to fetch website page")
                return events

            # Extract event IDs from URLs in the HTML
            # Format: https://westsidecomedy.com/single-event/e/1799258694189
            # These are Eventbrite event IDs
            event_ids = set(re.findall(r'single-event/e/(\d+)', html))
            self.log(f"Found {len(event_ids)} unique event IDs on website")

            # Prefetch all Eventbrite event pages concurrently
            if event_ids:
                eb_urls = [f'https://www.eventbrite.com/e/{eid}' for eid in sorted(event_ids)]
                self.prefetch_pages(eb_urls)

            for i, event_id in enumerate(sorted(event_ids), 1):
                try:
                    # Fetch directly from Eventbrite using the event ID
                    # This gives us westsidecomedy.com URL but Eventbrite data
                    event = self._fetch_eventbrite_event_by_id(event_id)
                    if event:
                        events.append(event)
                        self.log(f"Website event {i}/{len(event_ids)}: {event.title}")
                except Exception as e:
                    self.log(f"Error fetching event {event_id}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during website scrape: {e}")

        return events

    def _fetch_eventbrite_event_by_id(self, event_id: str) -> Optional[Event]:
        """
        Fetch event details from Eventbrite using event ID.

        Args:
            event_id: Eventbrite event ID (numeric string)

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Construct Eventbrite event URL
            eventbrite_url = f'https://www.eventbrite.com/e/{event_id}'

            # Fetch the page
            html = self.fetch_page(eventbrite_url)
            if not html:
                return None

            # Extract event data from embedded JSON
            event_data = self._extract_eventbrite_event_data(html)
            if event_data:
                # Enhance event data with description and image from HTML meta tags
                soup = BeautifulSoup(html, 'html.parser')

                # Extract description from Open Graph or structured data
                if not event_data.get('summary') and not event_data.get('description'):
                    og_desc = soup.find('meta', property='og:description')
                    if og_desc and og_desc.get('content'):
                        event_data['summary'] = og_desc['content']

                # Extract image from Open Graph or structured data
                if not event_data.get('logo') and not event_data.get('image'):
                    og_image = soup.find('meta', property='og:image')
                    if og_image and og_image.get('content'):
                        event_data['logo'] = og_image['content']

                # Parse using Eventbrite parser but use westsidecomedy.com URL
                event = self._parse_eventbrite_event(event_data)
                if event:
                    # Override URL to point to westsidecomedy.com
                    event.url = f'https://westsidecomedy.com/single-event/e/{event_id}/'
                    return event

        except Exception as e:
            self.log(f"Error fetching Eventbrite event {event_id}: {e}")

        return None

    def _extract_eventbrite_event_data(self, html: str) -> Optional[Dict]:
        """
        Extract single event data from Eventbrite event page.

        Args:
            html: HTML content of Eventbrite event page

        Returns:
            Dictionary containing event data or None if not found
        """
        try:
            # Look for __NEXT_DATA__ which contains event information
            next_data_pattern = r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>'
            match = re.search(next_data_pattern, html, re.DOTALL)

            if match:
                data = json.loads(match.group(1))
                # Navigate to event data
                event_data = data.get('props', {}).get('pageProps', {}).get('event')
                if event_data:
                    return event_data

            # Fallback: Try window.__SERVER_DATA__ if __NEXT_DATA__ not found
            server_data = self._extract_server_data(html)
            if server_data:
                return server_data.get('event')

        except Exception as e:
            self.log(f"Error extracting event data: {e}")

        return None

    def _fetch_website_event_details(self, event_url: str) -> Optional[Event]:
        """
        Fetch and parse a single event from westsidecomedy.com event page.

        Uses Playwright since the pages are JavaScript-rendered.

        Args:
            event_url: URL to the event detail page

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Use Playwright to fetch JavaScript-rendered content
            html = self.fetch_page_js(event_url, wait_selector='h1', timeout=10000)
            if not html:
                self.log(f"Failed to fetch {event_url}")
                return None

            soup = BeautifulSoup(html, 'html.parser')

            # Extract title (may be in different elements)
            title = None
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)

            if not title:
                self.log(f"No title found for {event_url}")
                return None

            # Extract date/time from various possible locations
            event_date = None
            end_date = None

            # Try meta tags first
            start_meta = soup.find('meta', {'property': 'event:start_date'})
            end_meta = soup.find('meta', {'property': 'event:end_date'})

            if start_meta and start_meta.get('content'):
                try:
                    event_date = date_parser.parse(start_meta['content'])
                except Exception as e:
                    self.log(f"Error parsing start date from meta: {e}")

            if end_meta and end_meta.get('content'):
                try:
                    end_date = date_parser.parse(end_meta['content'])
                except Exception as e:
                    self.log(f"Error parsing end date from meta: {e}")

            # If no meta tags, try finding date in text
            if not event_date:
                # Look for date patterns in the page
                date_patterns = [
                    r'([A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d+,\s+\d{4}\s+at\s+\d+:\d+\s+[AP]M)',
                    r'([A-Z][a-z]+\s+\d+,\s+\d{4}\s+@\s+\d+:\d+\s+[ap]m)'
                ]
                for pattern in date_patterns:
                    match = re.search(pattern, html)
                    if match:
                        try:
                            event_date = date_parser.parse(match.group(1))
                            break
                        except:
                            continue

            # Extract description from page content
            description = ''

            # Try to find description in common locations
            desc_selectors = [
                ('div', {'class': 'tribe-events-single-event-description'}),
                ('div', {'class': 'event-description'}),
                ('div', {'class': 'description'}),
                ('p', {})
            ]

            for tag, attrs in desc_selectors:
                desc_elem = soup.find(tag, attrs)
                if desc_elem:
                    paragraphs = desc_elem.find_all('p') if tag == 'div' else [desc_elem]
                    desc_parts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                    if desc_parts:
                        description = ' '.join(desc_parts)
                        break

            if not description:
                description = f"Comedy show at {self.venue_name}"

            # Truncate long descriptions
            if len(description) > 500:
                description = description[:497] + "..."

            # Extract image URL
            image_url = ''
            # Try Open Graph image first
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image and og_image.get('content'):
                image_url = og_image['content']
            else:
                # Try finding first image in content
                img = soup.find('img')
                if img and img.get('src'):
                    image_url = img['src']

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=event_url,
                image_url=image_url,
                category='Comedy'
            )

        except Exception as e:
            self.log(f"Error parsing event page {event_url}: {e}")
            return None

    def _scrape_eventbrite(self) -> List[Event]:
        """
        Scrape events from Eventbrite organizer page.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from Eventbrite...")
        events = []

        try:
            # Fetch the Eventbrite organizer page
            html = self.fetch_page(self.eventbrite_url)
            if not html:
                self.log("Failed to fetch Eventbrite page")
                return events

            # Extract embedded JSON data from JavaScript
            event_data = self._extract_server_data(html)
            if not event_data:
                self.log("Failed to extract event data from page")
                return events

            # Get future events list
            future_events = event_data.get('view_data', {}).get('events', {}).get('future_events', [])
            self.log(f"Found {len(future_events)} future events on Eventbrite")

            for i, event_json in enumerate(future_events, 1):
                try:
                    event = self._parse_eventbrite_event(event_json)
                    if event:
                        events.append(event)
                        self.log(f"Eventbrite event {i}/{len(future_events)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing Eventbrite event {i}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during Eventbrite scrape: {e}")

        return events

    def _extract_server_data(self, html: str) -> Optional[Dict]:
        """
        Extract window.__SERVER_DATA__ JSON object from Eventbrite page.

        Args:
            html: Page HTML content

        Returns:
            Dictionary containing server data or None if not found
        """
        try:
            # Find the start of the server data
            start_marker = 'window.__SERVER_DATA__ = '
            start_pos = html.find(start_marker)
            if start_pos == -1:
                self.log("Could not find window.__SERVER_DATA__ in page")
                return None

            # Move past the marker
            start_pos += len(start_marker)

            # Find the end - look for the closing script tag
            # We need to balance braces to find the correct end
            brace_count = 0
            in_string = False
            escape_next = False
            end_pos = start_pos

            for i in range(start_pos, len(html)):
                char = html[i]

                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break

            if end_pos == start_pos:
                self.log("Could not find end of JSON data")
                return None

            json_str = html[start_pos:end_pos]
            data = json.loads(json_str)
            return data

        except Exception as e:
            self.log(f"Error extracting server data: {e}")
        return None

    def _parse_eventbrite_event(self, event_data: Dict) -> Optional[Event]:
        """
        Parse event from Eventbrite JSON data structure.

        Args:
            event_data: Event dictionary from Eventbrite's embedded data

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract basic info - name can be a string or dict
            name_field = event_data.get('name', '')
            if isinstance(name_field, dict):
                title = name_field.get('text', '')
            else:
                title = name_field

            if not title:
                return None

            # Event URL
            event_url = event_data.get('url', '')

            # Parse dates
            event_date = None
            end_date = None
            start_data = event_data.get('start', {})
            end_data = event_data.get('end', {})

            if start_data.get('local'):
                try:
                    event_date = date_parser.parse(start_data['local'])
                except Exception as e:
                    self.log(f"Error parsing start date: {e}")

            if end_data.get('local'):
                try:
                    end_date = date_parser.parse(end_data['local'])
                except Exception as e:
                    self.log(f"Error parsing end date: {e}")

            # Extract price information
            price = None
            is_free = False
            price_range = event_data.get('price_range', '')

            if price_range:
                if 'free' in price_range.lower():
                    is_free = True
                    price = 0.0
                else:
                    # Extract minimum price from range like "$14.82 - $25" or "$15"
                    price_match = re.search(r'\$(\d+(?:\.\d{2})?)', price_range)
                    if price_match:
                        price = float(price_match.group(1))

            # Extract description
            description = event_data.get('summary', '') or event_data.get('description', {}).get('text', '')
            if not description:
                description = f"Comedy show at {self.venue_name}"

            # Truncate long descriptions
            if len(description) > 500:
                description = description[:497] + "..."

            # Extract image URL (Eventbrite uses 'logo' or 'image' field)
            image_url = ''
            logo_data = event_data.get('logo') or event_data.get('image')
            if isinstance(logo_data, dict):
                # Try various image size keys
                for key in ['url', 'original', 'large', 'medium']:
                    if logo_data.get(key):
                        image_url = logo_data[key]
                        break
            elif isinstance(logo_data, str):
                image_url = logo_data

            # Venue information (use defaults if not in data)
            venue_name = self.venue_name
            address = self.venue_address

            # Try to get venue from data if available
            venue_data = event_data.get('venue', {})
            if venue_data:
                venue_name = venue_data.get('name', self.venue_name)
                venue_address = venue_data.get('address', {})
                if venue_address:
                    address_parts = [
                        venue_address.get('address_1', ''),
                        venue_address.get('city', ''),
                        venue_address.get('region', ''),
                        venue_address.get('postal_code', '')
                    ]
                    address = ', '.join([p for p in address_parts if p]) or self.venue_address

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=event_url,
                image_url=image_url,
                category='Comedy',
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing event from JSON: {e}")
            return None

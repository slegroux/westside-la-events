"""
Scraper for KINN events.
Source: https://luma.com/KINNevents

KINN hosts events focused on AI, technology, and community in Los Angeles.
Events are listed on their Luma page with structured JSON-LD data.
"""
import json
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class KinnScraper(BaseScraper):
    """Scraper for KINN events on Luma."""

    def __init__(self):
        super().__init__('KINN')
        self.base_url = 'https://luma.com'
        self.events_url = f'{self.base_url}/KINNevents'

    def scrape(self) -> List[Event]:
        """
        Scrape events from KINN's Luma page.

        Luma uses JavaScript to render content and provides structured JSON-LD data
        for events. Falls back to parsing event URLs from the HTML if JS rendering fails.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Try regular HTTP request first (Luma provides JSON-LD in initial HTML)
            html = self.fetch_page(self.events_url)

            # If regular HTTP fails, try JavaScript rendering as fallback
            if not html:
                self.log("Regular HTTP failed, trying JavaScript rendering...")
                html = self.fetch_page_js(
                    self.events_url,
                    wait_selector='[class*="content-card"]',
                    timeout=45000
                )

            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Extract all JSON-LD structured data
            json_ld_scripts = soup.find_all('script', type='application/ld+json')

            if not json_ld_scripts:
                self.log("No JSON-LD data found")
                return events

            self.log(f"Found {len(json_ld_scripts)} JSON-LD scripts")

            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle Organization with events array (Luma's structure)
                    if data.get('@type') == 'Organization' and 'events' in data:
                        event_list = data.get('events', [])
                        self.log(f"Found Organization with {len(event_list)} events in events array")
                        for event_data in event_list:
                            if event_data.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(event_data)
                                if event:
                                    events.append(event)

                    # Handle single event
                    elif data.get('@type') == 'Event':
                        event = self._parse_event_from_json_ld(data)
                        if event:
                            events.append(event)

                    # Handle event list (ItemList)
                    elif data.get('@type') == 'ItemList':
                        items = data.get('itemListElement', [])
                        for item in items:
                            event_data = item.get('item', {})
                            if event_data.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(event_data)
                                if event:
                                    events.append(event)

                    # Handle list of events (array at root)
                    elif isinstance(data, list):
                        for item in data:
                            if item.get('@type') == 'Event':
                                event = self._parse_event_from_json_ld(item)
                                if event:
                                    events.append(event)

                except json.JSONDecodeError as e:
                    self.log(f"Error parsing JSON-LD: {e}")
                    continue
                except Exception as e:
                    self.log(f"Error processing JSON-LD: {e}")
                    continue

            # If no JSON-LD events found, try parsing HTML directly
            if not events:
                events = self._scrape_from_html(soup)

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event_from_json_ld(self, data: dict) -> Optional[Event]:
        """
        Parse event from JSON-LD structured data.

        Args:
            data: Event data from JSON-LD

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Title
            title = data.get('name', '').strip()
            if not title:
                return None

            # Description
            description = data.get('description', '').strip()

            # URL
            url = data.get('url', '')
            # Normalize Luma URLs
            if url and not url.startswith('http'):
                url = self.normalize_url(url, self.base_url)

            # Dates
            event_date = None
            end_date = None

            start_str = data.get('startDate')
            if start_str:
                try:
                    event_date = date_parser.parse(start_str)
                except Exception as e:
                    self.log(f"Failed to parse start date '{start_str}': {e}")

            end_str = data.get('endDate')
            if end_str:
                try:
                    end_date = date_parser.parse(end_str)
                except Exception as e:
                    self.log(f"Failed to parse end date '{end_str}': {e}")

            # Location/Venue
            location = data.get('location', {})
            venue_name = ''
            address = ''
            latitude = None
            longitude = None

            if isinstance(location, dict):
                venue_name = location.get('name', '').strip()

                # Address
                address_data = location.get('address', {})
                if isinstance(address_data, dict):
                    street = address_data.get('streetAddress', '')
                    city = address_data.get('addressLocality', '')
                    state = address_data.get('addressRegion', '')
                    postal = address_data.get('postalCode', '')

                    address_parts = [p for p in [street, city, state, postal] if p]
                    address = ', '.join(address_parts)
                elif isinstance(address_data, str):
                    address = address_data

                # Coordinates
                geo = location.get('geo', {})
                if isinstance(geo, dict):
                    try:
                        latitude = float(geo.get('latitude'))
                        longitude = float(geo.get('longitude'))
                    except (ValueError, TypeError):
                        pass
            elif isinstance(location, str):
                # Sometimes location is just a string
                venue_name = location

            # If no proper address but we have venue name, construct basic address
            # Check if address is just the venue name (not a real street address)
            if not address or address == venue_name:
                # Use known address for The KINN
                if venue_name == "The KINN":
                    address = "1356 Abbot Kinney Blvd, Venice, CA 90291"
                elif venue_name:
                    address = f"{venue_name}, Los Angeles, CA"

            # Image
            image_url = ''
            image_data = data.get('image')
            if image_data:
                if isinstance(image_data, str):
                    image_url = image_data
                elif isinstance(image_data, list) and len(image_data) > 0:
                    image_url = image_data[0] if isinstance(image_data[0], str) else image_data[0].get('url', '')
                elif isinstance(image_data, dict):
                    image_url = image_data.get('url', '')

            # Price information
            offers = data.get('offers', {})
            price = None
            is_free = False
            price_note = ''

            if isinstance(offers, dict):
                price_str = offers.get('price', '')
                if price_str:
                    try:
                        price = float(price_str)
                        if price == 0:
                            is_free = True
                    except (ValueError, TypeError):
                        pass

                # Check availability for free status
                availability = offers.get('availability', '')
                price_currency = offers.get('priceCurrency', '')

                if 'free' in str(offers).lower() or price == 0:
                    is_free = True
                    price = None

                # Get price note from name or category
                offer_name = offers.get('name', '')
                if offer_name and offer_name != title:
                    price_note = offer_name

            elif isinstance(offers, list):
                # Sometimes offers is an array
                for offer in offers:
                    if isinstance(offer, dict):
                        price_str = offer.get('price', '')
                        if price_str:
                            try:
                                test_price = float(price_str)
                                if price is None or test_price < price:
                                    price = test_price
                                if price == 0:
                                    is_free = True
                            except (ValueError, TypeError):
                                pass

            # Organizer information (can be useful for description)
            organizer = data.get('organizer', {})
            if isinstance(organizer, dict):
                organizer_name = organizer.get('name', '')
                if organizer_name and organizer_name not in description:
                    if description:
                        description = f"{description}\n\nOrganized by {organizer_name}"
                    else:
                        description = f"Organized by {organizer_name}"

            # KINN events are typically tech/education focused
            category = None  # Let auto-classification handle it

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
                is_free=is_free,
                price_note=price_note
            )

        except Exception as e:
            self.log(f"Error parsing JSON-LD event: {e}")
            return None

    def _scrape_from_html(self, soup) -> List[Event]:
        """
        Fallback method to scrape events from HTML when JSON-LD is not available.
        Extracts event URLs and fetches each event page individually.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of Event objects
        """
        self.log("Attempting to scrape event URLs from HTML structure...")
        events = []

        try:
            # Look for event links in the HTML
            # Luma event URLs follow pattern: /event/evt-XXXXXXXXXXXX
            event_links = soup.find_all('a', href=re.compile(r'/event/evt-[a-zA-Z0-9-]+'))
            event_urls = set()

            for link in event_links:
                href = link.get('href', '')
                if href and '/event/evt-' in href:
                    # Build full URL
                    if href.startswith('http'):
                        event_url = href
                    else:
                        event_url = self.normalize_url(href, self.base_url)
                    event_urls.add(event_url)

            self.log(f"Found {len(event_urls)} unique event URLs in HTML")

            # Fetch each event page
            for i, event_url in enumerate(sorted(event_urls), 1):
                try:
                    self.log(f"Fetching event {i}/{len(event_urls)}: {event_url}")
                    event = self._fetch_event_details(event_url)
                    if event:
                        events.append(event)
                        self.log(f"  [{i}/{len(event_urls)}] ✓ {event.title}")
                except Exception as e:
                    self.log(f"  [{i}/{len(event_urls)}] ✗ Error: {e}")
                    continue

            # If no event URLs found, try parsing event cards directly
            if not events:
                self.log("No event URLs found, trying to parse cards directly...")
                event_cards = soup.find_all('div', class_=lambda x: x and 'content-card' in str(x))

                if not event_cards:
                    # Try alternate selector
                    event_cards = soup.find_all('a', class_=lambda x: x and 'event-link' in str(x))

                self.log(f"Found {len(event_cards)} event cards in HTML")

                for card in event_cards:
                    try:
                        # Extract event URL
                        url = ''
                        if card.name == 'a':
                            url = card.get('href', '')
                        else:
                            link = card.find('a', class_=lambda x: x and 'event-link' in str(x))
                            if link:
                                url = link.get('href', '')

                        if url:
                            url = self.normalize_url(url, self.base_url)

                        # Extract title
                        title_elem = card.find('div', class_=lambda x: x and 'title' in str(x))
                        title = self.clean_text(title_elem.get_text()) if title_elem else ''

                        if not title:
                            # Try h2, h3
                            for heading in ['h2', 'h3', 'h4']:
                                title_elem = card.find(heading)
                                if title_elem:
                                    title = self.clean_text(title_elem.get_text())
                                    break

                        if not title:
                            continue

                        # Extract description
                        desc_elem = card.find('div', class_=lambda x: x and 'desc' in str(x))
                        description = self.clean_text(desc_elem.get_text()) if desc_elem else ''

                        # Extract image
                        img_elem = card.find('img')
                        image_url = ''
                        if img_elem:
                            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
                            if image_url:
                                image_url = self.normalize_url(image_url, self.base_url)

                        # Extract date (look for time elements)
                        event_date = None
                        time_elem = card.find('time')
                        if time_elem:
                            datetime_attr = time_elem.get('datetime')
                            if datetime_attr:
                                try:
                                    event_date = date_parser.parse(datetime_attr)
                                except Exception:
                                    pass

                        # If we have a URL, try to fetch more details
                        if url:
                            self.log(f"Fetching details from: {url}")
                            event = self._fetch_event_details(url)
                            if event:
                                events.append(event)
                                continue

                        # Otherwise create event from card data
                        # KINN is located in Venice, CA - use specific address for better geolocation
                        event = self.create_event(
                            title=title,
                            description=description,
                            venue_name='The KINN',
                            address='1356 Abbot Kinney Blvd, Venice, CA 90291',  # KINN address in Venice
                            event_date=event_date,
                            url=url,
                            image_url=image_url
                        )

                        if event:
                            events.append(event)

                    except Exception as e:
                        self.log(f"Error parsing event card: {e}")
                        continue

        except Exception as e:
            self.log(f"Error scraping from HTML: {e}")

        return events

    def _fetch_event_details(self, event_url: str) -> Optional[Event]:
        """
        Fetch detailed event information from an individual event page.

        Args:
            event_url: URL of the event detail page

        Returns:
            Event object or None if fetch fails
        """
        try:
            html = self.fetch_page_js(
                event_url,
                wait_selector='script[type="application/ld+json"]',
                timeout=30000
            )

            if not html:
                return None

            soup = self.parse_html(html)

            # Look for JSON-LD on event page
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    data = json.loads(json_ld.string)
                    if data.get('@type') == 'Event':
                        return self._parse_event_from_json_ld(data)
                except Exception as e:
                    self.log(f"Error parsing JSON-LD from event page: {e}")

            return None

        except Exception as e:
            self.log(f"Error fetching event details from {event_url}: {e}")
            return None

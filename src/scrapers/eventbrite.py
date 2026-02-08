"""
Scraper for Eventbrite events in Los Angeles.
Source: https://www.eventbrite.com/d/ca--los-angeles/events/

This scraper catches events from multiple Westside LA venues including:
- Perry's Beach (Santa Monica) - electronic music events
- Aviator Nation Dreamland (Malibu) - events posted by various organizers
- M.I.'s Westside Comedy Theater (Santa Monica)
- Venice West (Venice)
- And many other venues that use Eventbrite for ticketing

Note: Events are automatically filtered to Westside/Malibu area by the base scraper's
geo_filter validation. Some venues with dedicated scrapers (like Beyond Baroque) are
handled separately.
"""
import json
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class EventbriteScraper(BaseScraper):
    """Scraper for Eventbrite events (no API key required)."""

    def __init__(self):
        super().__init__('Eventbrite')
        self.base_url = 'https://www.eventbrite.com'
        self.events_url = f'{self.base_url}/d/ca--los-angeles/events/'

        # Specific organizer/collection pages to scrape
        self.collection_urls = [
            'https://www.eventbrite.com/cc/santa-monica-beach-perrys-beach-events-4542063',
        ]

    def scrape(self) -> List[Event]:
        """
        Scrape events from Eventbrite LA page and specific organizer collections.
        Uses JSON-LD structured data for the general LA page and window.__SERVER_DATA__
        for collection pages.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        # Scrape general LA events page (JSON-LD format)
        events.extend(self._scrape_general_page())

        # Scrape specific organizer collection pages (SERVER_DATA format)
        for collection_url in self.collection_urls:
            events.extend(self._scrape_collection_page(collection_url))

        self.log(f"Successfully scraped {len(events)} total events")
        return events

    def _scrape_general_page(self) -> List[Event]:
        """
        Scrape the general LA events page by extracting event URLs and fetching
        individual event pages for accurate time data.

        Note: The list page JSON-LD only contains dates (2025-11-16) without times,
        so we must fetch individual event pages to get full timestamps (2025-11-16T14:00:00-08:00).

        Returns:
            List of Event objects
        """
        self.log("Scraping general LA events page...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Extract event URLs from the page
            event_urls = set()

            # Method 1: Extract from JSON-LD itemList to get URLs
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                data = json.loads(json_ld.string)
                if data.get('@type') == 'ItemList':
                    event_items = data.get('itemListElement', [])
                    for item in event_items:
                        event_data = item.get('item', {})
                        url = event_data.get('url', '')
                        if url:
                            event_urls.add(url.split('?')[0])  # Remove query params

            # Method 2: Also extract from href attributes as backup
            event_links = soup.find_all('a', href=re.compile(r'eventbrite\.com/e/[^/]+-tickets-\d+'))
            for link in event_links:
                href = link.get('href', '')
                if '/e/' in href and '-tickets-' in href:
                    if href.startswith('http'):
                        clean_url = href.split('?')[0]
                    elif href.startswith('/e/'):
                        clean_url = f"{self.base_url}{href.split('?')[0]}"
                    else:
                        continue
                    event_urls.add(clean_url)

            self.log(f"Found {len(event_urls)} unique event URLs in general page")

            # Prefetch all event pages concurrently
            if event_urls:
                self.prefetch_pages(sorted(event_urls))

            # Fetch each event page and extract full data with correct times
            for i, event_url in enumerate(sorted(event_urls), 1):
                try:
                    event = self._scrape_event_page(event_url)
                    if event:
                        events.append(event)
                        self.log(f"  [{i}/{len(event_urls)}] ✓ {event.title}")
                except Exception as e:
                    self.log(f"  [{i}/{len(event_urls)}] ✗ Error: {e}")
                    continue

            self.log(f"Scraped {len(events)} events from general page")

        except Exception as e:
            self.log(f"Error during general page scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_collection_page(self, url: str) -> List[Event]:
        """
        Scrape a specific organizer collection page by extracting event URLs
        and fetching JSON-LD data from each individual event page.

        Args:
            url: Collection page URL

        Returns:
            List of Event objects
        """
        organizer = url.split('/')[-1].split('-')[-1]
        self.log(f"Scraping collection page: {organizer}...")
        events = []

        try:
            # Check if this is an organizer profile page (/o/) that requires JS rendering
            if '/o/' in url:
                return self._scrape_organizer_profile_page(url)

            html = self.fetch_page(url)
            if not html:
                self.log(f"Failed to fetch collection page: {url}")
                return events

            soup = self.parse_html(html)

            # Extract event URLs from href attributes (both relative and absolute)
            event_links = soup.find_all('a', href=re.compile(r'eventbrite\.com/e/[^/]+-tickets-\d+'))
            event_urls = set()  # Use set to avoid duplicates

            for link in event_links:
                href = link.get('href', '')
                if '/e/' in href and '-tickets-' in href:
                    # Handle both relative and absolute URLs
                    if href.startswith('http'):
                        clean_url = href.split('?')[0]
                    elif href.startswith('/e/'):
                        clean_url = f"{self.base_url}{href.split('?')[0]}"
                    else:
                        continue
                    event_urls.add(clean_url)

            self.log(f"Found {len(event_urls)} unique event URLs in collection")

            # Prefetch all event pages concurrently
            if event_urls:
                self.prefetch_pages(sorted(event_urls))

            # Fetch each event page and extract JSON-LD data
            for i, event_url in enumerate(sorted(event_urls), 1):
                try:
                    event = self._scrape_event_page(event_url)
                    if event:
                        events.append(event)
                        self.log(f"  [{i}/{len(event_urls)}] ✓ {event.title}")
                except Exception as e:
                    self.log(f"  [{i}/{len(event_urls)}] ✗ Error: {e}")
                    continue

            self.log(f"Scraped {len(events)} events from collection page")

        except Exception as e:
            self.log(f"Error during collection page scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_organizer_profile_page(self, url: str) -> List[Event]:
        """
        Scrape an organizer profile page (/o/) using Playwright for JS rendering.
        These pages require JavaScript to load event links.

        Args:
            url: Organizer profile page URL

        Returns:
            List of Event objects
        """
        organizer = url.split('/')[-1]
        self.log(f"Scraping organizer profile page (JS): {organizer}...")
        events = []

        try:
            # Fetch page with JavaScript rendering
            html = self.fetch_page_js(url, wait_selector='a[href*="/e/"]', timeout=30000)
            if not html:
                self.log(f"Failed to fetch organizer page with JS: {url}")
                return events

            soup = self.parse_html(html)

            # Extract event URLs
            event_urls = set()
            all_links = soup.find_all('a', href=True)

            for link in all_links:
                href = link.get('href', '')
                if '/e/' in href and 'tickets' in href:
                    # Clean URL
                    clean_url = href.split('?')[0]
                    if clean_url.startswith('/'):
                        clean_url = f"{self.base_url}{clean_url}"
                    event_urls.add(clean_url)

            self.log(f"Found {len(event_urls)} unique event URLs in organizer profile")

            # Prefetch all event pages concurrently
            if event_urls:
                self.prefetch_pages(sorted(event_urls))

            # Fetch each event page and extract data
            for i, event_url in enumerate(sorted(event_urls), 1):
                try:
                    event = self._scrape_event_page(event_url)
                    if event:
                        events.append(event)
                        self.log(f"  [{i}/{len(event_urls)}] ✓ {event.title}")
                except Exception as e:
                    self.log(f"  [{i}/{len(event_urls)}] ✗ Error: {e}")
                    continue

            self.log(f"Scraped {len(events)} events from organizer profile page")

        except Exception as e:
            self.log(f"Error during organizer profile page scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_event_page(self, url: str) -> Optional[Event]:
        """
        Scrape a single event page using JSON-LD structured data or window.__SERVER_DATA__.
        Tries JSON-LD first as it has more complete venue information.

        Args:
            url: Event page URL

        Returns:
            Event object or None if parsing fails
        """
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            soup = self.parse_html(html)

            # First, try JSON-LD as it has complete venue information
            json_lds = soup.find_all('script', type='application/ld+json')
            for json_ld in json_lds:
                try:
                    data = json.loads(json_ld.string)
                    # Look for Event, Festival, or SocialEvent type in either dict or list
                    if isinstance(data, dict):
                        if data.get('@type') in ('Event', 'Festival', 'SocialEvent'):
                            event = self._parse_event_from_structured_data(data)
                            if event:
                                return event
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') in ('Event', 'Festival', 'SocialEvent'):
                                event = self._parse_event_from_structured_data(item)
                                if event:
                                    return event
                except:
                    continue

            # Fallback to window.__SERVER_DATA__ if JSON-LD doesn't work
            match = re.search(r'window\.__SERVER_DATA__\s*=\s*(\{[^;]*\});?\s*(?:window\.|</script>)', html, re.DOTALL)
            if not match:
                return None

            # Parse the JavaScript object as JSON
            try:
                # Clean up the JSON string
                json_str = match.group(1)
                # Replace common JavaScript patterns that aren't valid JSON
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)  # Remove trailing commas
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                self.log(f"Failed to parse SERVER_DATA for {url}: {e}")
                return None

            # Navigate to event data in SERVER_DATA structure
            event_data = data.get('event', {})
            if not event_data:
                # Try alternate structure
                event_data = data.get('listing', {})

            if not event_data:
                return None

            # Parse HTML to extract price if not in SERVER_DATA
            html_price = self._extract_price_from_html(soup)

            return self._parse_event_from_server_data(event_data, html_price)

        except Exception as e:
            self.log(f"Error scraping event page {url}: {e}")
            return None

    def _parse_event_from_structured_data(self, data: dict) -> Optional[Event]:
        """
        Parse event from JSON-LD structured data.

        Args:
            data: Event data from JSON-LD

        Returns:
            Event object or None if parsing fails
        """
        # Title
        title = data.get('name', '')
        if not title:
            return None

        # Description
        description = data.get('description', '')

        # URL
        url = data.get('url', '')

        # Dates
        event_date = None
        end_date = None

        start_str = data.get('startDate')
        if start_str:
            try:
                event_date = date_parser.parse(start_str)
            except:
                pass

        end_str = data.get('endDate')
        if end_str:
            try:
                end_date = date_parser.parse(end_str)
            except:
                pass

        # Location/Venue
        location = data.get('location', {})
        venue_name = location.get('name', '')

        # Address
        address_data = location.get('address', {})
        street = address_data.get('streetAddress', '')
        city = address_data.get('addressLocality', '')
        state = address_data.get('addressRegion', '')
        postal = address_data.get('postalCode', '')

        # Build full address
        address_parts = [p for p in [street, city, state, postal] if p]
        address = ', '.join(address_parts) if address_parts else f"{venue_name}, Los Angeles, CA"

        # Coordinates (Eventbrite provides them!)
        latitude = None
        longitude = None
        geo = location.get('geo', {})
        if geo:
            try:
                latitude = float(geo.get('latitude'))
                longitude = float(geo.get('longitude'))
            except:
                pass

        # Image
        image_url = data.get('image', '')

        # Price - check if free
        offers = data.get('offers', {})
        is_free = False
        price = None

        if isinstance(offers, dict):
            price_str = offers.get('price', '')
            if price_str:
                try:
                    price = float(price_str)
                except:
                    pass

            availability = offers.get('availability', '')
            if 'free' in str(offers).lower() or price == 0:
                is_free = True
        elif isinstance(offers, list) and offers:
            # Sometimes offers is a list
            first_offer = offers[0]
            price_str = first_offer.get('price', '')
            if price_str:
                try:
                    price = float(price_str)
                except:
                    pass
            if 'free' in str(first_offer).lower() or price == 0:
                is_free = True

        # Category - extract from performers or keywords if available
        category = None
        performers = data.get('performer', [])
        if performers:
            # Could use performer info to classify
            pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,  # Will be auto-classified by create_event
            price=price,
            is_free=is_free
        )

    def _extract_price_from_html(self, soup) -> Optional[float]:
        """
        Extract price from HTML when not available in SERVER_DATA.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Price as float or None if not found
        """
        try:
            # Look for price in the conversion bar or ticket selector
            # Pattern: "From $XX.XX" or "$XX.XX"
            price_text_pattern = re.compile(r'(?:From\s+)?\$(\d+\.?\d*)')

            # Search in common price display elements
            price_elements = soup.find_all(['div', 'span'], string=price_text_pattern)

            for elem in price_elements:
                text = elem.get_text()
                match = price_text_pattern.search(text)
                if match:
                    try:
                        price = float(match.group(1))
                        return price
                    except ValueError:
                        continue

            return None
        except Exception as e:
            self.log(f"Error extracting price from HTML: {e}")
            return None

    def _parse_event_from_server_data(self, data: dict, html_price: Optional[float] = None) -> Optional[Event]:
        """
        Parse event from window.__SERVER_DATA__ format (used in collection pages).

        Args:
            data: Event data from __SERVER_DATA__

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

        # Description
        description = data.get('summary', '') or data.get('description', '')

        # URL - build from event ID
        event_id = data.get('id', '')
        url = f"{self.base_url}/e/{event_id}" if event_id else data.get('url', '')

        # Dates
        event_date = None
        end_date = None

        start_data = data.get('start', {})
        if start_data:
            try:
                # SERVER_DATA format uses 'local' or 'utc' timestamps
                start_str = start_data.get('local') or start_data.get('utc')
                if start_str:
                    event_date = date_parser.parse(start_str)
            except:
                pass

        end_data = data.get('end', {})
        if end_data:
            try:
                end_str = end_data.get('local') or end_data.get('utc')
                if end_str:
                    end_date = date_parser.parse(end_str)
            except:
                pass

        # Venue
        venue_name = ''
        address = ''

        venue = data.get('primary_venue', {})
        if venue:
            venue_name = venue.get('name', '')

            venue_address = venue.get('address', {})
            if venue_address:
                street = venue_address.get('address_1', '')
                city = venue_address.get('city', '')
                state = venue_address.get('region', '')
                postal = venue_address.get('postal_code', '')

                address_parts = [p for p in [street, city, state, postal] if p]
                address = ', '.join(address_parts) if address_parts else ''

        # Extract venue from title if not found in venue field
        # (Perry's events often include venue name in title)
        if not venue_name and "perry" in title.lower():
            venue_name = "Perry's Beach"
            address = "930 Pacific Coast Highway, Santa Monica, CA 90403"

        # Fallback if no address found
        if not address and venue_name:
            address = f"{venue_name}, Santa Monica, CA"

        # Image
        image_url = ''
        image_data = data.get('image', {})
        if isinstance(image_data, dict) and image_data:
            image_url = image_data.get('url', '') or image_data.get('original', {}).get('url', '')

        # Use Perry's Beach collection image as fallback for Perry's events without images
        if not image_url and ("perry" in title.lower() or venue_name == "Perry's Beach"):
            image_url = 'https://img.evbuc.com/https%3A%2F%2Fcdn.evbuc.com%2Fimages%2F1165815693%2F2872939232171%2F1%2Foriginal.20251029-200910?w=512&auto=format%2Ccompress&q=75&sharp=10&rect=0%2C34%2C1191%2C435&s=3121f4932e02e60f7a30495e5421b9e6'

        # Price
        is_free = data.get('is_free', False)
        price = None

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

        # Fall back to HTML-extracted price if not found in SERVER_DATA
        if price is None and html_price is not None:
            price = html_price
            if price == 0:
                is_free = True

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=None,  # Will be auto-classified by create_event
            price=price,
            is_free=is_free
        )

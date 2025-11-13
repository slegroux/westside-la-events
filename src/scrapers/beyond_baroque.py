"""
Scraper for Beyond Baroque Literary Arts Center events.
Source: https://www.eventbrite.com/o/beyond-baroque-literary-arts-center-1685240682

Beyond Baroque is a Venice-based literary arts center founded in 1968, hosting poetry readings,
fiction workshops, book launches, and literary events.
"""
import json
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class BeyondBaroqueScraper(BaseScraper):
    """Scraper for Beyond Baroque Literary Arts Center events from Eventbrite."""

    def __init__(self):
        super().__init__('Beyond Baroque')
        self.organizer_url = 'https://www.eventbrite.com/o/beyond-baroque-literary-arts-center-1685240682'
        self.base_url = 'https://www.eventbrite.com'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Beyond Baroque's Eventbrite organizer page.
        Uses Playwright for JavaScript rendering as the page loads events dynamically.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape of Beyond Baroque events...")
        events = []

        try:
            # Fetch organizer page with JavaScript rendering
            html = self.fetch_page_js(self.organizer_url, wait_selector='a[href*="/e/"]', timeout=60000)
            if not html:
                self.log("Failed to fetch organizer page with JavaScript rendering")
                return events

            soup = self.parse_html(html)

            # Extract event URLs
            event_urls = set()
            all_links = soup.find_all('a', href=True)

            for link in all_links:
                href = link.get('href', '')
                if '/e/' in href and 'tickets' in href:
                    # Clean URL (remove query parameters)
                    clean_url = href.split('?')[0]
                    if clean_url.startswith('/'):
                        clean_url = f"{self.base_url}{clean_url}"
                    event_urls.add(clean_url)

            self.log(f"Found {len(event_urls)} unique event URLs")

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

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_event_page(self, url: str) -> Optional[Event]:
        """
        Scrape a single event page using JSON-LD structured data.
        Beyond Baroque events use JSON-LD with complete venue information.

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

            # Parse JSON-LD structured data
            json_lds = soup.find_all('script', type='application/ld+json')
            for json_ld in json_lds:
                try:
                    data = json.loads(json_ld.string)
                    # Look for Event or Festival type (Beyond Baroque uses both)
                    if isinstance(data, dict):
                        if data.get('@type') in ('Event', 'Festival'):
                            return self._parse_event_from_json_ld(data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') in ('Event', 'Festival'):
                                return self._parse_event_from_json_ld(item)
                except:
                    continue

            return None

        except Exception as e:
            self.log(f"Error scraping event page {url}: {e}")
            return None

    def _parse_event_from_json_ld(self, data: dict) -> Optional[Event]:
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
        venue_name = location.get('name', 'Beyond Baroque Literary Arts Center')

        # Address
        address_data = location.get('address', {})
        if isinstance(address_data, dict):
            street = address_data.get('streetAddress', '')
            city = address_data.get('addressLocality', '')
            state = address_data.get('addressRegion', '')
            postal = address_data.get('postalCode', '')

            # Build full address
            address_parts = [p for p in [street, city, state, postal] if p]
            address = ', '.join(address_parts) if address_parts else '681 Venice Blvd, Venice, CA 90291'
        else:
            # Fallback address
            address = '681 Venice Blvd, Venice, CA 90291'

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
                    if price == 0:
                        is_free = True
                except:
                    pass

            if 'free' in str(offers).lower():
                is_free = True
        elif isinstance(offers, list) and offers:
            # Sometimes offers is a list
            first_offer = offers[0]
            price_str = first_offer.get('price', '')
            if price_str:
                try:
                    price = float(price_str)
                    if price == 0:
                        is_free = True
                except:
                    pass
            if 'free' in str(first_offer).lower():
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

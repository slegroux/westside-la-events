"""
Scraper for Timeout LA events.
Source: https://www.timeout.com/los-angeles/things-to-do
"""
import json
import re
from datetime import datetime
from typing import List, Optional, Dict
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class TimeoutScraper(BaseScraper):
    """Scraper for Timeout LA events."""

    def __init__(self):
        super().__init__('Timeout LA')
        self.base_url = 'https://www.timeout.com'
        # Updated URL - the old "this-week" page no longer exists
        self.events_url = f'{self.base_url}/los-angeles/things-to-do/things-to-do-in-los-angeles-today'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Timeout LA website.
        Fetches detail pages to get complete information including exact addresses.

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

            # Parse event cards from article elements
            event_cards = soup.find_all('article', class_='tile')
            self.log(f"Found {len(event_cards)} event cards on listing page")

            # Collect all detail URLs and prefetch them concurrently
            card_urls = []
            for card in event_cards:
                link_elem = card.find('a', {'data-testid': 'tile-link_testID'})
                if link_elem and link_elem.get('href'):
                    card_urls.append(self.normalize_url(link_elem['href'], self.base_url))
            if card_urls:
                self.prefetch_pages(card_urls)

            for i, card in enumerate(event_cards, 1):
                try:
                    # Get URL from card
                    link_elem = card.find('a', {'data-testid': 'tile-link_testID'})
                    if not link_elem or not link_elem.get('href'):
                        self.log(f"Event {i}: No link found, skipping")
                        continue

                    event_url = self.normalize_url(link_elem['href'], self.base_url)

                    # Fetch detail page for complete data (hits prefetch cache)
                    self.log(f"Event {i}/{len(event_cards)}: Fetching {event_url}")
                    event = self._fetch_and_parse_detail(event_url, card)

                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _fetch_and_parse_detail(self, url: str, card) -> Optional[Event]:
        """
        Fetch event detail page and parse complete information.

        Args:
            url: Event detail page URL
            card: BeautifulSoup element from listing (fallback data)

        Returns:
            Event object with complete information
        """
        try:
            # Fetch detail page
            detail_html = self.fetch_page(url)
            if not detail_html:
                self.log(f"Failed to fetch detail page: {url}")
                return None

            detail_soup = self.parse_html(detail_html)

            # Try to extract structured data (JSON-LD) first - most reliable
            structured_data = self._extract_structured_data(detail_soup)

            if structured_data:
                return self._parse_from_structured_data(structured_data, url)
            else:
                # Fallback to parsing HTML
                self.log("No structured data found, parsing HTML")
                return self._parse_from_html(detail_soup, card, url)

        except Exception as e:
            self.log(f"Error fetching detail for {url}: {e}")
            return None

    def _extract_structured_data(self, soup) -> Optional[Dict]:
        """Extract JSON-LD structured data from page."""
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                if data.get('@type') == 'Event':
                    return data
            except Exception as e:
                self.log(f"Error parsing JSON-LD: {e}")
        return None

    def _parse_from_structured_data(self, data: Dict, url: str) -> Event:
        """Parse event from JSON-LD structured data."""
        # Title
        title = data.get('name', 'Untitled Event')

        # Description
        description = data.get('description', '')

        # Dates
        event_date = None
        end_date = None
        if data.get('startDate'):
            try:
                event_date = date_parser.parse(data['startDate'])
            except:
                pass
        if data.get('endDate'):
            try:
                end_date = date_parser.parse(data['endDate'])
            except:
                pass

        # Location/Venue
        location = data.get('location', {})
        venue_name = location.get('name', '')

        address_data = location.get('address', {})
        if isinstance(address_data, dict):
            street = address_data.get('streetAddress', '')
            city = address_data.get('addressLocality', '')
            postal = address_data.get('postalCode', '')
            state = 'CA'  # Default for LA events

            # Build full address
            address_parts = [p for p in [street, city, state, postal] if p]
            address = ', '.join(address_parts)
        else:
            address = str(address_data) if address_data else f"{venue_name}, Los Angeles, CA"

        # Image
        image_url = data.get('image', '')

        # Price info
        offers = data.get('offers', {})
        is_free = False
        price = None
        if offers:
            price_text = offers.get('price', '')
            if price_text:
                try:
                    # Remove currency symbols and whitespace before converting to float
                    clean_price = price_text.replace('$', '').replace('£', '').replace('€', '').strip()
                    price = float(clean_price)
                except:
                    pass
            if 'free' in str(offers).lower():
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
            price=price,
            is_free=is_free
        )

    def _extract_price_from_html(self, soup) -> Optional[Dict]:
        """
        Extract price information from HTML detail page.

        Looks for price in definition lists (<dt>Price:</dt><dd>value</dd>)
        and other common patterns.

        Args:
            soup: BeautifulSoup object of detail page

        Returns:
            Dict with 'price' (float or None) and 'is_free' (bool)
        """
        price = None
        is_free = False

        # Strategy 1: Look for definition list with "Price:" label
        dt_elements = soup.find_all('dt')
        for dt in dt_elements:
            dt_text = self.clean_text(dt.get_text()).lower()
            if 'price' in dt_text:
                # Found price label, get the corresponding value
                dd = dt.find_next_sibling('dd')
                if dd:
                    price_text = self.clean_text(dd.get_text())

                    # Check if free
                    if 'free' in price_text.lower():
                        is_free = True
                        price = 0.0
                    else:
                        # Try to extract numeric price
                        # Look for patterns like "$15", "$15.00", "15", etc.
                        price_match = re.search(r'\$?\s*(\d+(?:\.\d{2})?)', price_text)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                            except ValueError:
                                pass
                    break

        # Strategy 2: Look for any element containing "Price:" text
        if price is None:
            # Search for text containing "price:"
            for text_elem in soup.find_all(text=lambda t: t and 'price:' in t.lower()):
                parent = text_elem.parent
                if parent:
                    text_content = self.clean_text(parent.get_text())

                    if 'free' in text_content.lower():
                        is_free = True
                        price = 0.0
                    else:
                        # Extract price after "price:" label
                        price_match = re.search(r'price:\s*\$?\s*(\d+(?:\.\d{2})?)', text_content, re.IGNORECASE)
                        if price_match:
                            try:
                                price = float(price_match.group(1))
                            except ValueError:
                                pass
                    break

        return {'price': price, 'is_free': is_free} if (price is not None or is_free) else None

    def _parse_from_html(self, detail_soup, card, url: str) -> Event:
        """Fallback: Parse event from HTML when structured data not available."""
        # Extract title from card
        title_elem = card.find('h3', {'data-testid': 'tile-title_testID'})
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Try to find description on detail page
        description = ""
        desc_container = detail_soup.find('div', class_=lambda x: x and 'body' in str(x).lower())
        if desc_container:
            paragraphs = desc_container.find_all('p')
            if paragraphs:
                description = self.clean_text(paragraphs[0].get_text())

        # Extract venue name from detail page
        venue_elem = detail_soup.find(class_=lambda x: x and 'venueName' in str(x))
        venue_name = self.clean_text(venue_elem.get_text()) if venue_elem else ""

        # Address - try to find on page
        address = f"{venue_name}, Los Angeles, CA" if venue_name else "Los Angeles, CA"

        # Date from card
        event_date = None
        end_date = None
        time_elem = card.find('time')
        if time_elem:
            date_str = time_elem.get('datetime')
            if date_str:
                try:
                    time_text = time_elem.get_text()
                    parsed_date = date_parser.parse(date_str)
                    if 'until' in time_text.lower():
                        event_date = datetime.now()
                        end_date = parsed_date
                    else:
                        event_date = parsed_date
                except:
                    pass

        # Image
        img_elem = detail_soup.find('meta', property='og:image')
        image_url = img_elem.get('content', '') if img_elem else ""

        # Extract price information from detail page
        price = None
        is_free = False
        price_info = self._extract_price_from_html(detail_soup)
        if price_info:
            price = price_info.get('price')
            is_free = price_info.get('is_free', False)

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
            is_free=is_free
        )

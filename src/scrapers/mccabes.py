"""
Scraper for McCabe's Guitar Shop concerts.
Source: https://www.mccabes.com/concerts-landing/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class McCabesScraper(BaseScraper):
    """Scraper for McCabe's Guitar Shop concerts."""

    def __init__(self):
        super().__init__("McCabe's Guitar Shop")
        self.base_url = 'https://www.mccabes.com'
        self.events_url = f'{self.base_url}/concerts-landing/'

    def scrape(self) -> List[Event]:
        """
        Scrape concerts from McCabe's Guitar Shop website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the concerts page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch concerts page")
                return events

            soup = self.parse_html(html)

            # Find all concert items using FooEvents classes
            concert_container = soup.find('div', class_='fooevents-event-listing-list-container')

            if concert_container:
                concert_items = concert_container.find_all('div', class_=re.compile(r'fooevents-event-listing-list-item'))
            else:
                # Alternative selector: require event-class node to contain a date marker
                # (time element or month abbreviation) to avoid matching menus/headers/footers
                candidates = soup.find_all(['div', 'article'], class_=re.compile(r'event', re.IGNORECASE))
                concert_items = [
                    d for d in candidates
                    if d.find('time') or re.search(
                        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
                        d.get_text()
                    )
                ]

            self.log(f"Found {len(concert_items)} concert items")

            # Collect detail URLs and prefetch them concurrently
            # Cap detail pages to avoid timeout when site returns 503s
            MAX_DETAIL_PAGES = 30
            detail_urls = []
            for item in concert_items:
                link = item.find('a', href=True)
                if link:
                    detail_urls.append(self.normalize_url(link['href'], self.base_url))
            if len(detail_urls) > MAX_DETAIL_PAGES:
                self.log(f"Capping detail page fetches from {len(detail_urls)} to {MAX_DETAIL_PAGES}")
                detail_urls = detail_urls[:MAX_DETAIL_PAGES]
            if detail_urls:
                self.prefetch_pages(detail_urls, max_concurrent=5)

            for item in concert_items:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing concert: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} concerts")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single concert item.

        Args:
            item: BeautifulSoup element containing concert data

        Returns:
            Event object or None
        """
        # Extract title from h3 element
        title_elem = item.find('h3')
        if not title_elem:
            title_elem = item.find(['h2', 'h4'])

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())

        # Extract URL from link
        url = self.events_url
        link = item.find('a', href=True)
        if link:
            url = self.normalize_url(link['href'], self.base_url)

        # Extract description
        description = ""
        desc_elem = item.find('p') or item.find('div', class_=re.compile(r'desc|content', re.IGNORECASE))
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time from fooevents-shortcode-date
        event_date = None
        date_elem = item.find('p', class_='fooevents-shortcode-date')
        if not date_elem:
            date_elem = item.find('div', class_='fooevents-event-listing-list-datetime')
        if not date_elem:
            date_elem = item.find(['time', 'span'], class_=re.compile(r'date|time', re.IGNORECASE))

        if date_elem:
            date_str = date_elem.get('datetime', '') or date_elem.get_text()
            # Format is like "Fri Nov 14 2025 | 8pm"
            # Remove icon elements and clean up
            date_str = re.sub(r'<[^>]+>', '', str(date_str))  # Remove HTML tags
            date_str = date_str.replace('|', '').strip()
            # Fix non-standard day abbreviations
            date_str = date_str.replace('Tues ', 'Tue ')
            date_str = date_str.replace('Thurs ', 'Thu ')
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Check if sold out
        is_sold_out = False
        if item.find(text=re.compile(r'sold out', re.IGNORECASE)):
            is_sold_out = True

        # Venue info - McCabe's in Santa Monica
        venue_name = "McCabe's Guitar Shop"
        address = "3101 Pico Blvd, Santa Monica, CA 90405"

        # Extract image - check both img tags and CSS background-image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')

        # If no img tag, check for background-image in style attribute
        if not image_url:
            bg_div = item.find('div', style=re.compile(r'background-image'))
            if bg_div:
                style = bg_div.get('style', '')
                match = re.search(r'background-image:\s*url\((.*?)\)', style)
                if match:
                    image_url = match.group(1).strip('\'"')

        if image_url:
            image_url = self.normalize_url(image_url, self.base_url)

        # Category - music only (McCabe's is a music venue)
        category = "Music"

        # Price info - fetch from detail page
        is_free = False
        price = None
        price_note = "Sold out" if is_sold_out else None

        if not is_sold_out and url and url != self.events_url:
            # Fetch the detail page to get pricing
            price_info = self._extract_price_from_detail_page(url)
            if price_info:
                price = price_info.get('price')
                price_note = price_info.get('price_note')
                is_free = price_info.get('is_free', False)

        if price_note is None:
            price_note = "TBD"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

    def _extract_price_from_detail_page(self, url: str) -> dict:
        """
        Extract pricing information from an event detail page.

        Args:
            url: URL of the event detail page

        Returns:
            Dictionary with price, price_note, and is_free keys
        """
        try:
            # Use only 1 retry with short timeout to avoid burning time on 503s
            html = self.fetch_page(url, retry=1)
            if not html:
                return None

            soup = self.parse_html(html)

            # Look for WooCommerce price elements
            price_elem = soup.find('span', class_='woocommerce-Price-amount')
            if not price_elem:
                # Try alternative price selectors
                price_elem = soup.find('p', class_='price')

            if price_elem:
                # Extract price text
                price_text = self.clean_text(price_elem.get_text())
                # Parse price (e.g., "$25.00" or "$25")
                price_match = re.search(r'\$(\d+(?:\.\d{2})?)', price_text)
                if price_match:
                    price = float(price_match.group(1))

                    # Look for ticketing fee and total amount
                    # Search for patterns like "Ticketing Fee" followed by a price
                    fee_match = None
                    total_match = None

                    # Find fee amount in the page
                    page_text = soup.get_text()
                    fee_pattern = re.search(r'Ticketing Fee.*?\$(\d+(?:\.\d{2})?)', page_text, re.DOTALL | re.IGNORECASE)
                    if fee_pattern:
                        fee_match = float(fee_pattern.group(1))

                    # Find total amount
                    total_pattern = re.search(r'Total Payable Amount.*?\$(\d+(?:\.\d{2})?)', page_text, re.DOTALL | re.IGNORECASE)
                    if total_pattern:
                        total_match = float(total_pattern.group(1))

                    # Build price note with fee information if available
                    if fee_match and total_match:
                        return {
                            'price': price,
                            'price_note': f"${price:.2f} + ${fee_match:.2f} fee = ${total_match:.2f} total",
                            'is_free': False
                        }
                    elif fee_match:
                        total_calc = price + fee_match
                        return {
                            'price': price,
                            'price_note': f"${price:.2f} + ${fee_match:.2f} fee = ${total_calc:.2f} total",
                            'is_free': False
                        }
                    else:
                        return {
                            'price': price,
                            'price_note': f"${price:.2f}",
                            'is_free': False
                        }

            # Check for "free" indicators
            if soup.find(text=re.compile(r'\bfree\b', re.IGNORECASE)):
                return {
                    'price': 0.0,
                    'price_note': "Free",
                    'is_free': True
                }

        except Exception as e:
            self.log(f"Error extracting price from {url}: {e}")

        return None

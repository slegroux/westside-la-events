"""
Scraper for McCabe's Guitar Shop concerts.
Source: https://www.mccabes.com/concerts-landing/

Two requests in total, no per-event detail fetches (the site 503s a burst of
detail-page requests):
  1. The concerts landing page lists every upcoming concert with title, full
     date (including year), time, image and link.
  2. The WooCommerce Store API (one call) supplies the ticket price and stock
     status for each concert product, matched by permalink.
If the price call fails the events are still emitted, just without a price.
"""
from typing import Dict, List
from dateutil import parser as date_parser
import html as html_lib
import re

from .base import BaseScraper
from src.data.models import Event


class McCabesScraper(BaseScraper):
    """Scraper for McCabe's Guitar Shop concerts."""

    VENUE_NAME = "McCabe's Guitar Shop"
    ADDRESS = "3101 Pico Blvd, Santa Monica, CA 90405"
    VENUE_LAT = 34.0260256
    VENUE_LNG = -118.4576079

    def __init__(self):
        super().__init__("McCabe's Guitar Shop")
        self.base_url = 'https://www.mccabes.com'
        self.events_url = f'{self.base_url}/concerts-landing/'
        self.products_url = (
            f'{self.base_url}/wp-json/wc/store/v1/products'
            '?per_page=100&category=concert-tickets'
        )

    def scrape(self) -> List[Event]:
        """Scrape upcoming concerts from McCabe's Guitar Shop."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch concerts page")
                return events

            soup = self.parse_html(html)
            items = soup.find_all('div', class_='fooevents-calendar-list-item')
            self.log(f"Found {len(items)} concert items")

            products = self._fetch_products()

            for item in items:
                try:
                    event = self._parse_event(item, products)
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

    def _fetch_products(self) -> Dict[str, dict]:
        """Fetch concert products from the Store API, keyed by permalink."""
        data = self.fetch_json(self.products_url, method="GET")
        if not isinstance(data, list):
            self.log("Store API unavailable; events will have no price")
            return {}
        return {
            p['permalink'].rstrip('/'): p
            for p in data if isinstance(p, dict) and p.get('permalink')
        }

    def _parse_event(self, item, products: Dict[str, dict]) -> Event:
        """Parse one landing-page concert card, enriched with Store API data."""
        title_elem = item.find('h3')
        if not title_elem:
            return None
        title = self.clean_text(title_elem.get_text())

        link = title_elem.find('a', href=True) or item.find('a', href=True)
        url = self.normalize_url(link['href'], self.base_url) if link else self.events_url

        date_elem = item.find('p', class_='fooevents-shortcode-date')
        date_str = self.clean_text(date_elem.get_text()) if date_elem else ''
        # Format is like "Fri Nov 14 2025 | 8pm"
        date_str = date_str.replace('|', ' ')
        date_str = date_str.replace('Tues ', 'Tue ').replace('Thurs ', 'Thu ')
        try:
            event_date = date_parser.parse(date_str)
        except (ValueError, OverflowError):
            self.log(f"Skipping '{title}': unparseable date '{date_str}'")
            return None

        image_url = ""
        bg_div = item.find('div', style=re.compile(r'background-image'))
        if bg_div:
            match = re.search(r'background-image:\s*url\((.*?)\)', bg_div.get('style', ''))
            if match:
                image_url = self.normalize_url(match.group(1).strip('\'"'), self.base_url)

        # Price and availability come from the Store API product, if matched.
        product = products.get(url.rstrip('/'))
        price = None
        price_note = ""
        sold_out = bool(item.find(string=re.compile(r'sold out', re.IGNORECASE)))
        description = ""
        if product:
            if product.get('is_in_stock') is False:
                sold_out = True
            prices = product.get('prices') or {}
            raw = prices.get('price')
            if raw not in (None, ''):
                amount = int(raw) / (10 ** prices.get('currency_minor_unit', 2))
                if amount > 0:
                    price = amount
                    price_note = f"${amount:.2f}"
            description = self._description(product)
        if sold_out:
            price_note = "Sold out"

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.ADDRESS,
            event_date=event_date,
            url=url,
            image_url=image_url,
            category="Music",
            price=price,
            price_note=price_note,
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

    def _description(self, product: dict) -> str:
        """Blurb from the product's short description, minus the date heading."""
        short = product.get('short_description') or ''
        short = re.sub(r'<h3>.*?</h3>', '', short, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', short)
        return self.clean_text(html_lib.unescape(text))

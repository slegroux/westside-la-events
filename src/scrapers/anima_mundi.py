"""
Scraper for Anima Mundi Herbals (Venice apothecary) events.
Source: https://animamundiherbals.com/pages/event-calendar

Anima Mundi sells event tickets as Shopify products. The calendar page's own
widget is empty; the real listing is a product picker whose <option> tags carry
the product ids, which are then resolved against the shop's public
products.json.

Two things make this source awkward, and both are handled here:

  * Anima Mundi runs apothecaries in Venice, Brooklyn, Soho and Costa Rica off
    one catalog, and the only location signal is prose in the product body
    ("in our Venice garden"). Non-Venice events are dropped rather than
    geocoded, since the geo filter can't tell them apart.
  * Dates live in prose too, often several per product
    ("Monday, August 3rd, 17th and 31st at 9:15-9:45am"), so each product can
    expand into several events.
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
    'december': 12,
}


class AnimaMundiScraper(BaseScraper):
    """Scraper for Anima Mundi Herbals' Venice events."""

    VENUE_NAME = 'Anima Mundi Herbals'
    ADDRESS = '417 Rose Ave, Venice, CA'

    # Only events whose copy places them at the Venice location are kept.
    VENICE_MARKERS = ('venice',)
    OTHER_LOCATIONS = ('brooklyn', 'soho', 'costa rica')

    # Matches "August 3rd", "September 22nd", and bare follow-ons like "17th".
    _MONTH_RE = re.compile(
        r'\b(' + '|'.join(MONTHS) + r')\b|\b(\d{1,2})(?:st|nd|rd|th)\b',
        re.IGNORECASE,
    )
    # "9:15-9:45am", "7-9pm", "11-5pm", "at 7pm". The end hour is captured so a
    # range like "11-5pm" can be read as 11am-5pm rather than 11pm.
    _TIME_RE = re.compile(
        r'\b(\d{1,2})(?::(\d{2}))?\s*(?:(?:-|–|to)\s*(\d{1,2})(?::\d{2})?)?\s*(am|pm)\b',
        re.IGNORECASE,
    )

    PRODUCTS_URL = 'https://animamundiherbals.com/products.json'
    MAX_PRODUCT_PAGES = 5

    def __init__(self):
        super().__init__('Anima Mundi Herbals')
        self.base_url = 'https://animamundiherbals.com'
        self.events_url = f'{self.base_url}/pages/event-calendar'

    def scrape(self) -> List[Event]:
        """Scrape Venice events from the Shopify catalog."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch event calendar page")
                return events

            product_ids = self._listed_product_ids(html)
            self.log(f"Found {len(product_ids)} event products on the calendar")
            if not product_ids:
                return events

            catalog = self._fetch_catalog()
            self.log(f"Loaded {len(catalog)} catalog products")

            for product_id in product_ids:
                product = catalog.get(product_id)
                if not product:
                    continue
                try:
                    events.extend(self._parse_product(product))
                except Exception as e:
                    self.log(f"Error parsing product {product_id}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _listed_product_ids(self, html: str) -> List[int]:
        """Read product ids out of the calendar page's picker options."""
        ids = []
        for raw in re.findall(r'data-product-id\s*=\s*"(\d+)"', html):
            value = int(raw)
            if value not in ids:
                ids.append(value)
        return ids

    def _fetch_catalog(self) -> Dict[int, dict]:
        """Load the public Shopify catalog, keyed by product id."""
        catalog = {}
        for page in range(1, self.MAX_PRODUCT_PAGES + 1):
            resp = self.session.get(
                self.PRODUCTS_URL, params={'limit': 250, 'page': page}, timeout=45
            )
            resp.raise_for_status()
            try:
                products = resp.json().get('products', [])
            except json.JSONDecodeError:
                break
            if not products:
                break
            for product in products:
                catalog[product['id']] = product
        return catalog

    def _parse_product(self, product: dict) -> List[Event]:
        """Expand one ticket product into an Event per scheduled date."""
        title = self.clean_text(product.get('title', ''))
        if not title:
            return []

        body = self._plain_text(product.get('body_html') or '')
        if not self._is_venice(body):
            return []

        starts = self._parse_dates(body)
        if not starts:
            return []

        url = f"{self.base_url}/products/{product.get('handle', '')}"
        image_url = ''
        images = product.get('images') or []
        if images:
            image_url = images[0].get('src', '')

        price, is_free = self._parse_price(product)

        events = []
        for start in starts:
            event = self.create_event(
                title=title,
                description=body[:500],
                venue_name=self.VENUE_NAME,
                address=self.ADDRESS,
                event_date=start,
                url=url,
                image_url=image_url,
                price=price,
                is_free=is_free,
                price_note='',
            )
            if event:
                events.append(event)
        return events

    def _plain_text(self, body_html: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', body_html)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return re.sub(r'\s+', ' ', text).strip()

    def _is_venice(self, body: str) -> bool:
        """Whether the copy places this event at the Venice location.

        Some listings name several apothecaries; Venice has to be mentioned,
        and a listing that names only other cities is rejected.
        """
        lowered = body.lower()
        if not any(marker in lowered for marker in self.VENICE_MARKERS):
            return False
        return True

    def _parse_dates(self, body: str) -> List[datetime]:
        """Pull every scheduled date out of the product copy.

        Handles "Tuesday, September 22nd" as well as runs that share a month
        ("Monday, August 3rd, 17th and 31st"), where later ordinals inherit the
        most recently named month.
        """
        hour, minute = self._parse_time(body)

        found: List[Tuple[int, int]] = []
        current_month = None

        for match in self._MONTH_RE.finditer(body):
            month_name, day = match.group(1), match.group(2)
            if month_name:
                current_month = MONTHS[month_name.lower()]
                continue
            if current_month is None or not day:
                continue
            day_value = int(day)
            if 1 <= day_value <= 31:
                pair = (current_month, day_value)
                if pair not in found:
                    found.append(pair)

        today = datetime.now()
        dates = []
        for month, day in found:
            # Copy omits the year. Anima Mundi leaves finished series on the
            # calendar page, so a recently-passed month means a stale listing
            # (drop it as past), not next year's date. Only a month far enough
            # behind to look like a calendar wrap rolls forward.
            year = today.year
            if month < today.month and (today.month - month) >= 6:
                year += 1
            try:
                moment = datetime(year, month, day, hour, minute)
            except ValueError:
                continue
            if moment.date() >= today.date():
                dates.append(moment)
        return dates

    def _parse_time(self, body: str) -> Tuple[int, int]:
        """Best-effort start time; defaults to 19:00 when none is stated."""
        match = self._TIME_RE.search(body)
        if not match:
            return 19, 0
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        end_hour = int(match.group(3)) if match.group(3) else None
        meridiem = match.group(4).lower()

        # The am/pm marker trails the range and belongs to the END time. When
        # the start reads later than the end on a 12-hour clock ("11-5pm"), the
        # start is in the other half of the day.
        crosses_midday = (
            meridiem == 'pm' and end_hour is not None and hour > end_hour
        )
        if crosses_midday:
            pass  # start stays as an AM hour
        elif meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
        if not 0 <= hour <= 23:
            return 19, 0
        return hour, minute

    def _parse_price(self, product: dict) -> Tuple[Optional[float], bool]:
        variants = product.get('variants') or []
        prices = []
        for variant in variants:
            try:
                prices.append(float(variant.get('price')))
            except (TypeError, ValueError):
                continue
        if not prices:
            return None, False
        low = min(prices)
        return (None, True) if low == 0 else (low, False)

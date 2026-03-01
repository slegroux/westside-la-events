"""
Scraper for Visit Santa Monica events.
Source: https://www.santamonica.com/events/
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class SantaMonicaEventsScraper(BaseScraper):
    """Scraper for Visit Santa Monica events."""

    def __init__(self):
        super().__init__('Visit Santa Monica')
        self.base_url = 'https://www.santamonica.com'
        self.events_url = f'{self.base_url}/events/'

    def scrape(self) -> List[Event]:
        """Scrape events from santamonica.com."""
        self.log("Starting scrape...")
        events: List[Event] = []

        html = self.fetch_page(self.events_url)
        if not html:
            self.log("Failed to fetch events page")
            return events

        soup = self.parse_html(html)
        detail_urls = self._extract_event_urls(soup)

        # Fallback to JS-rendered HTML if server HTML has no event links.
        if not detail_urls:
            self.log("No event links found in static HTML, trying JS rendering...")
            html_js = self.fetch_page_js(
                self.events_url,
                wait_selector='a[href*="/event/"]',
                timeout=45000
            )
            if html_js:
                soup_js = self.parse_html(html_js)
                detail_urls = self._extract_event_urls(soup_js)

        if not detail_urls:
            self.log("No event detail URLs found")
            return events

        self.log(f"Found {len(detail_urls)} event detail URLs")
        self.prefetch_pages(sorted(detail_urls), max_concurrent=8)

        for url in sorted(detail_urls):
            try:
                event = self._parse_event_detail(url)
                if event:
                    events.append(event)
            except Exception as e:
                self.log(f"Error parsing event detail {url}: {e}")

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _extract_event_urls(self, soup) -> Set[str]:
        """Extract event detail URLs from listing page."""
        urls: Set[str] = set()

        for link in soup.select('a[href]'):
            href = (link.get('href') or '').strip()
            if not href:
                continue

            url = self.normalize_url(href, self.base_url)
            if '/event/' in url:
                # Remove hash/query noise for stable dedupe.
                clean = url.split('#', 1)[0].split('?', 1)[0]
                urls.add(clean)

        # Also attempt extraction from script payloads when links are embedded.
        if not urls:
            html_text = str(soup)
            matches = re.findall(r'https?://www\.santamonica\.com/event/[^"\'<\s]+', html_text)
            for match in matches:
                clean = match.split('#', 1)[0].split('?', 1)[0]
                urls.add(clean)

            relative_matches = re.findall(r'"/event/[^"]+"', html_text)
            for match in relative_matches:
                rel = match.strip('"')
                urls.add(self.normalize_url(rel, self.base_url))

        return urls

    def _parse_event_detail(self, url: str) -> Optional[Event]:
        """Parse a single event detail page."""
        html = self.fetch_page(url)
        if not html:
            return None

        soup = self.parse_html(html)
        data = self._extract_jsonld_event(soup)

        title = self.clean_text(data.get('name', '')) if data else ''
        if not title:
            title_elem = soup.find('h1')
            title = self.clean_text(title_elem.get_text()) if title_elem else ''
        if not title:
            return None

        description = ""
        if data and data.get('description'):
            description = self.clean_text(self._strip_html(data['description']))
        if not description:
            desc_meta = soup.find('meta', attrs={'name': 'description'})
            if desc_meta:
                description = self.clean_text(desc_meta.get('content', ''))

        event_date = self._parse_datetime(data.get('startDate') if data else None)
        end_date = self._parse_datetime(data.get('endDate') if data else None)

        if not event_date:
            time_elem = soup.find('time')
            if time_elem:
                event_date = self._parse_datetime(time_elem.get('datetime') or time_elem.get_text())

        location = data.get('location') if data else {}
        venue_name = self._extract_location_name(location)
        address = self._extract_address(location)

        if not address:
            address = "Santa Monica, CA"

        image_url = self._extract_image(data.get('image') if data else None)
        price, is_free, price_note = self._extract_pricing(data.get('offers') if data else None)

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

    def _extract_jsonld_event(self, soup) -> Dict[str, Any]:
        """Extract Event schema JSON-LD from a page."""
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            content = script.string or script.get_text() or ''
            if not content.strip():
                continue

            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                continue

            event = self._find_event_in_payload(payload)
            if event:
                return event

        return {}

    def _find_event_in_payload(self, payload: Any) -> Dict[str, Any]:
        """Find an Event object inside any JSON-LD payload structure."""
        if isinstance(payload, dict):
            node_type = payload.get('@type')
            if node_type == 'Event' or (isinstance(node_type, list) and 'Event' in node_type):
                return payload

            if '@graph' in payload:
                return self._find_event_in_payload(payload['@graph'])

            for value in payload.values():
                found = self._find_event_in_payload(value)
                if found:
                    return found

        if isinstance(payload, list):
            for item in payload:
                found = self._find_event_in_payload(item)
                if found:
                    return found

        return {}

    def _parse_datetime(self, value: Optional[str]):
        """Parse datetime string safely."""
        if not value:
            return None
        try:
            return date_parser.parse(value)
        except Exception:
            return None

    def _extract_location_name(self, location: Any) -> str:
        """Extract venue name from Event.location."""
        if isinstance(location, dict):
            return self.clean_text(location.get('name', ''))
        if isinstance(location, list) and location and isinstance(location[0], dict):
            return self.clean_text(location[0].get('name', ''))
        return ''

    def _extract_address(self, location: Any) -> str:
        """Extract venue address from Event.location."""
        if isinstance(location, list) and location:
            location = location[0]

        if not isinstance(location, dict):
            return ''

        address = location.get('address')
        if isinstance(address, str):
            return self.clean_text(address)

        if isinstance(address, dict):
            parts = [
                address.get('streetAddress', ''),
                address.get('addressLocality', ''),
                address.get('addressRegion', ''),
                address.get('postalCode', ''),
            ]
            return self.clean_text(', '.join([p for p in parts if p]))

        return ''

    def _extract_image(self, image_data: Any) -> str:
        """Extract image URL from Event.image."""
        if isinstance(image_data, str):
            return self.normalize_url(image_data, self.base_url)

        if isinstance(image_data, list) and image_data:
            first = image_data[0]
            if isinstance(first, str):
                return self.normalize_url(first, self.base_url)
            if isinstance(first, dict):
                return self.normalize_url(first.get('url', ''), self.base_url)

        if isinstance(image_data, dict):
            return self.normalize_url(image_data.get('url', ''), self.base_url)

        return ''

    def _extract_pricing(self, offers: Any) -> tuple[Optional[float], bool, str]:
        """Extract price and free/paid flags from Event.offers."""
        is_free = False
        price = None
        price_note = 'TBD'

        offer = offers[0] if isinstance(offers, list) and offers else offers

        if isinstance(offer, dict):
            raw_price = offer.get('price')
            if raw_price is not None:
                try:
                    price = float(raw_price)
                    is_free = price == 0.0
                except (TypeError, ValueError):
                    pass

            availability = str(offer.get('availability', '')).lower()
            if 'free' in availability:
                is_free = True

            category = str(offer.get('category', '')).lower()
            if 'free' in category:
                is_free = True

            if price is None and offer.get('priceCurrency'):
                price_note = f"Pricing in {offer.get('priceCurrency')}"

        return price, is_free, price_note

    def _strip_html(self, text: str) -> str:
        """Remove HTML tags from a description string."""
        if '<' not in text:
            return text
        return self.parse_html(text).get_text(' ', strip=True)

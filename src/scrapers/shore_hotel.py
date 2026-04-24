"""
Scraper for Shore Hotel Santa Monica events.
Source: https://www.shorehotel.com/events

Shore Hotel is an oceanfront hotel in Santa Monica that curates a local events
calendar covering concerts, farmers markets, festivals, theatre, and more in
the greater Westside area.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event

API_URL = 'https://www.shorehotel.com/api/eventcalendardetailapi/FilterEventList'
EVENTS_PAGE = 'https://www.shorehotel.com/events'
PLACEHOLDER_IMAGES = {
    '/resourcefiles/common-image/480-360.jpg',
    '/images_noindex/no-image-event.jpg',
}
SHORE_HOTEL_FALLBACK_IMAGE = '/static/logos/shore_hotel.jpg'


class ShoreHotelScraper(BaseScraper):
    """Scraper for Shore Hotel Santa Monica events calendar."""

    def __init__(self):
        super().__init__('Shore Hotel')
        self.base_url = 'https://www.shorehotel.com'
        self.venue_name = 'Shore Hotel'
        self.venue_address = '1515 Ocean Avenue, Santa Monica, CA 90401'
        self.session.headers.update({
            'Referer': EVENTS_PAGE,
            'X-Requested-With': 'XMLHttpRequest',
        })

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events = []
        today = datetime.now()
        end_date = today + timedelta(days=60)

        page = 1
        max_pages = 5  # up to 100 events (20 per page)

        while page <= max_pages:
            self.log(f"Fetching page {page}...")
            html = self._fetch_page(page, today, end_date)
            if not html or not html.strip():
                break

            soup = BeautifulSoup(html, 'lxml')
            cards = soup.find_all('div', class_='category-grid-img-list')
            if not cards:
                break

            for card in cards:
                try:
                    event = self._parse_card(card)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing card: {e}")

            self.log(f"Page {page}: {len(cards)} cards, {len(events)} total so far")
            page += 1

        self.log(f"Scraped {len(events)} events")
        return events

    def _fetch_page(self, page_no: int, start: datetime, end: datetime) -> Optional[str]:
        try:
            resp = self.session.post(
                API_URL,
                data={
                    'StartDate': start.strftime('%m/%d/%Y'),
                    'EndDate': end.strftime('%m/%d/%Y'),
                    'FormatKey': 'eventcommonlistblock',
                    'NumberOfEventsToFetch': 20,
                    'SearchValue': '',
                    'PageNo': page_no,
                    'ShowOnlyFeaturedEvents': 'false',
                    'ShowOnlyRecurrentEvents': 'false',
                    'ProfileAlias': '',
                },
                timeout=20,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.log(f"Error fetching page {page_no}: {e}")
            return None

    def _parse_card(self, card) -> Optional[Event]:
        # URL
        link = card.find('a', href=True)
        url = link['href'] if link else EVENTS_PAGE
        if url and not url.startswith('http'):
            url = self.base_url + url

        # Title
        h3 = card.find('h3')
        if not h3:
            return None
        title = h3.get_text(strip=True)
        if not title:
            return None

        # Category tag
        cat_tag = card.find('div', class_='category-tag')
        raw_category = cat_tag.get_text(strip=True) if cat_tag else ''

        # Date — parse from the visible text in .f-grid-date (HTML comment has full names)
        date_div = card.find('div', class_='f-grid-date')
        event_date, end_date = None, None
        if date_div:
            # Try the HTML comment first (has full month names like "April 23, 2026")
            comment = re.search(r'<!--\s*(.+?)\s*(?:<br\s*/?>)?\s*-->', str(date_div))
            date_text = comment.group(1).strip() if comment else date_div.get_text(strip=True)
            event_date, end_date = self._parse_date_range(date_text)

        # Address — format: "Venue Name, street, city, state, zip"
        addr_span = card.find('div', class_='f-grid-address')
        venue_name = ''
        address = ''
        if addr_span:
            # Collapse whitespace/newlines before splitting
            addr_text = ' '.join(addr_span.get_text().split())
            parts = [p.strip() for p in addr_text.split(',')]
            if len(parts) >= 2:
                venue_name = parts[0]
                # Rejoin remaining parts, normalise hyphenated city names
                remaining = ', '.join(parts[1:])
                remaining = re.sub(r'United States of America', '', remaining, flags=re.IGNORECASE)
                remaining = re.sub(r'United States', '', remaining, flags=re.IGNORECASE)
                remaining = re.sub(r'([A-Za-z]+)-([A-Za-z]+)', lambda m: m.group(1) + ' ' + m.group(2), remaining)
                # Collapse multiple commas/spaces left by removals
                remaining = re.sub(r',\s*,', ',', remaining)
                address = remaining.strip().strip(',')
            else:
                address = addr_text

        # Image — try card thumbnail first, fall back to event detail page
        img = card.find('img')
        image_url = ''
        if img:
            src = img.get('src', '')
            if src and not any(src.endswith(p.lstrip('/')) or p in src for p in PLACEHOLDER_IMAGES):
                image_url = src if src.startswith('http') else self.base_url + src
        if not image_url and url and url != EVENTS_PAGE:
            image_url = self._fetch_image_from_url(url)
        if not image_url:
            image_url = SHORE_HOTEL_FALLBACK_IMAGE

        category = self._map_category(raw_category, title)

        actual_venue = venue_name or self.venue_name
        # Prefer the parsed street address; fall back to venue name so the
        # geocoder can place the event correctly (e.g. "Hollywood Bowl" → outside
        # Westside → filtered out). Only use the hotel's own address when we
        # have zero location information from the card.
        if address:
            actual_address = address
        elif venue_name:
            actual_address = venue_name
        else:
            actual_address = self.venue_address

        return self.create_event(
            title=title,
            description='',
            venue_name=actual_venue,
            address=actual_address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,
            price_note='TBD',
        )

    def _fetch_image_from_url(self, url: str) -> str:
        """Fetch event image from the Shore Hotel event detail page."""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')

            # 1. og:image is the most reliable
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                src = og['content']
                if not any(p in src for p in PLACEHOLDER_IMAGES):
                    return src

            # 2. First large content image (skip icons and tiny thumbnails)
            for img in soup.find_all('img', src=True):
                src = img.get('src', '')
                if not src or any(p in src for p in PLACEHOLDER_IMAGES):
                    continue
                # Skip tiny images (logos, icons)
                w = img.get('width', '')
                h = img.get('height', '')
                try:
                    if int(w) < 200 or int(h) < 100:
                        continue
                except (ValueError, TypeError):
                    pass
                if src.startswith('http'):
                    return src
                if src.startswith('/'):
                    return self.base_url + src
        except Exception as e:
            self.log(f"Could not fetch image from {url}: {e}")
        return ''

    def _parse_date_range(self, text: str):
        """Return (start_datetime, end_datetime) from a string like 'April 23, 2026 - April 24, 2026'."""
        text = text.strip()
        # Split on ' - ' or '–'
        parts = re.split(r'\s*[–-]\s*', text, maxsplit=1)
        start, end = None, None
        try:
            start = date_parser.parse(parts[0], fuzzy=True)
        except Exception:
            pass
        if len(parts) > 1:
            try:
                end = date_parser.parse(parts[1], fuzzy=True)
            except Exception:
                pass
        return start, end

    def _map_category(self, raw: str, title: str) -> str:
        raw_lower = raw.lower()
        title_lower = title.lower()
        combined = raw_lower + ' ' + title_lower

        if any(k in combined for k in ['concert', 'music', 'jazz', 'band', 'twilight']):
            return 'Music'
        if any(k in combined for k in ['art', 'exhibit', 'gallery', 'museum']):
            return 'Arts'
        if any(k in combined for k in ['food', 'dining', 'farmer', 'market', 'culinary', 'wine', 'beer', 'tasting']):
            return 'Food'
        if any(k in combined for k in ['theatre', 'theater', 'play', 'comedy', 'improv', 'performance']):
            return 'Arts'
        if any(k in combined for k in ['sport', 'marathon', 'run', 'race', 'fitness']):
            return 'Sports'
        if any(k in combined for k in ['family', 'kid', 'child', 'children']):
            return 'Family'
        if any(k in combined for k in ['fair', 'festival', 'parade', 'celebration']):
            return 'Festival'
        return 'Other'

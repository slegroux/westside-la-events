"""
Scrapers for venue pages on Moments (momentsapp.no).

Moments aggregates community events and publishes clean schema.org JSON-LD:
the venue page carries an ItemList of event URLs, and each event page carries
an Event object with UTC timestamps and geo coordinates. That means no date
guessing and no geocoding round trip.

Currently used for Dr Paul Carlson Park in Culver City, which hosts recurring
free classes that no city calendar lists.
"""
import json
import re
from datetime import datetime
from typing import List, Optional

from .base import BaseScraper, normalize_event_datetime
from src.data.models import Event


class MomentsVenueScraper(BaseScraper):
    """Base scraper for a single Moments venue page.

    Subclasses set VENUE_SLUG and pass the source/venue display name.
    """

    BASE_URL = 'https://momentsapp.no'
    CITY = 'los-angeles'

    VENUE_SLUG: str = ''
    # Fallback address; Moments only publishes locality, so the street address
    # is supplied by the subclass where known.
    ADDRESS: str = ''

    # Safety rail against a venue page listing an unbounded backlog.
    MAX_EVENTS = 60

    _LD_RE = re.compile(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S
    )

    def __init__(self, source_name: str, venue_name: str):
        super().__init__(source_name)
        self.base_url = self.BASE_URL
        self.venue_name = venue_name
        self.events_url = f'{self.BASE_URL}/events/{self.CITY}/venue/{self.VENUE_SLUG}'

    def scrape(self) -> List[Event]:
        """Read the venue's event list, then each event's JSON-LD."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch venue page")
                return events

            urls = self._event_urls(html)
            self.log(f"Found {len(urls)} events listed at the venue")
            if not urls:
                return events

            urls = urls[:self.MAX_EVENTS]
            self.prefetch_pages(urls)

            for url in urls:
                try:
                    event = self._parse_event_page(url)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing {url}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _event_urls(self, html: str) -> List[str]:
        """Pull event detail URLs out of the venue page's ItemList."""
        urls = []
        for block in self._LD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            if data.get('@type') != 'ItemList':
                continue
            for entry in data.get('itemListElement', []):
                url = entry.get('item')
                if url and url not in urls:
                    urls.append(url)
        return urls

    def _parse_event_page(self, url: str) -> Optional[Event]:
        html = self.fetch_page(url)
        if not html:
            return None

        data = None
        for block in self._LD_RE.findall(html):
            try:
                candidate = json.loads(block)
            except json.JSONDecodeError:
                continue
            if candidate.get('@type') == 'Event':
                data = candidate
                break
        if not data:
            return None

        title = self.clean_text(data.get('name', ''))
        event_date = self._parse_timestamp(data.get('startDate'))
        if not title or not event_date:
            return None

        # Moments keeps finished events on the venue page. Compare in the
        # canonical naive LA-local form, since the feed's timestamps are UTC
        # aware and datetime.now() is naive.
        if normalize_event_datetime(event_date) < datetime.now():
            return None

        location = data.get('location') or {}
        geo = location.get('geo') or {}
        latitude = geo.get('latitude')
        longitude = geo.get('longitude')

        description = self.clean_text(data.get('description', ''))

        # Moments lists community classes that are typically free; only trust
        # an explicit offer, and otherwise leave pricing unstated.
        price, is_free = self._parse_offers(data.get('offers'))

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.ADDRESS,
            event_date=event_date,
            end_date=self._parse_timestamp(data.get('endDate')),
            url=data.get('url') or url,
            price=price,
            is_free=is_free,
            price_note='',
            latitude=latitude,
            longitude=longitude,
        )

    def _parse_offers(self, offers):
        """Read price from a schema.org Offer, if one is published."""
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            return None, False
        try:
            price = float(offers.get('price'))
        except (TypeError, ValueError):
            return None, False
        return (None, True) if price == 0 else (price, False)

    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        """Parse an ISO-8601 timestamp; create_event converts it to LA-local."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None


class CarlsonParkScraper(MomentsVenueScraper):
    """Dr Paul Carlson Park, Culver City -- free recurring community classes."""

    VENUE_SLUG = 'dr-paul-carlson-park'
    ADDRESS = 'Dr Paul Carlson Park, Braddock Dr, Culver City, CA'

    def __init__(self):
        super().__init__('Dr Paul Carlson Park', 'Dr Paul Carlson Park')

"""
Scraper for Harvelle's Santa Monica (blues, jazz and funk club, 1432 4th St).
Sources: https://santamonica.harvelles.com/ (full calendar) and
https://www.harvelles.com/ (a shorter list, used as a fallback).

Both pages run on the SeatEngine ticketing platform and embed the calendar as
schema.org JSON-LD. harvelles.com lists the sister Long Beach club as well, so
only events whose location is Santa Monica are kept. startDate is UTC ("Z");
create_event converts it to naive LA time. The JSON-LD carries no prices, so
price_note stays empty.
"""
import json
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class HarvellesScraper(BaseScraper):
    """Scraper for Harvelle's Santa Monica via SeatEngine JSON-LD."""

    VENUE_NAME = "Harvelle's Santa Monica"
    VENUE_ADDRESS = '1432 4th St, Santa Monica, CA 90401'
    VENUE_LAT = 34.0160
    VENUE_LNG = -118.4963

    # Most complete first; the second also lists Long Beach, which is filtered.
    LISTING_URLS = [
        'https://santamonica.harvelles.com/',
        'https://www.harvelles.com/',
    ]

    _LD_RE = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S
    )

    def __init__(self):
        super().__init__("Harvelle's")
        self.base_url = 'https://www.harvelles.com'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Harvelle's Santa Monica...")
        events: List[Event] = []

        items: List[dict] = []
        for url in self.LISTING_URLS:
            html = self.fetch_page(url)
            items = self._santa_monica_events(html) if html else []
            if items:
                break
            self.log(f"No Santa Monica events found at {url}")
        if not items:
            return events

        now = datetime.now()
        seen = set()
        for item in items:
            try:
                event = self._build_event(item)
            except Exception as e:
                self.log(f"  ✗ error parsing '{item.get('name', '')}': {e}")
                continue
            if not event or (event.end_date or event.event_date) < now:
                continue
            if event.url in seen:
                continue
            seen.add(event.url)
            events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _santa_monica_events(self, html: str) -> List[dict]:
        """Every Event object in the page's JSON-LD located in Santa Monica."""
        found: List[dict] = []

        def walk(node):
            if isinstance(node, dict):
                if node.get('@type') == 'Event' and self._in_santa_monica(node):
                    found.append(node)
                    return
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        for raw in self._LD_RE.findall(html):
            try:
                walk(json.loads(raw))
            except ValueError:
                continue
        return found

    @staticmethod
    def _in_santa_monica(event: dict) -> bool:
        location = event.get('location')
        if not isinstance(location, dict):
            return False
        address = location.get('address')
        address = address if isinstance(address, dict) else location
        return str(address.get('addressLocality', '')).strip().lower() == 'santa monica'

    def _build_event(self, item: dict) -> Optional[Event]:
        title = self.clean_text(item.get('name', ''))
        start = self._parse_dt(item.get('startDate'))
        if not title or not start:
            return None

        description = self.clean_text(
            BeautifulSoup(item.get('description') or '', 'html.parser').get_text(' ')
        )
        image = item.get('image') if isinstance(item.get('image'), str) else ''
        if not image.startswith('http') or 'missing' in image:
            image = ''  # SeatEngine's relative "headshot_missing" placeholder

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=start,
            url=item.get('url') or self.base_url,
            image_url=image,
            category='Music',
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

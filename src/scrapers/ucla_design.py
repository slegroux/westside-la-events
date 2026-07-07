"""
Scraper for UCLA Design Media Arts events.
Source: https://www.design.ucla.edu/events

The site is a Next.js app. The full event list is embedded in the page's
``__NEXT_DATA__`` JSON blob under ``props.pageProps.events`` — no HTML
scraping or JS rendering required. Image uploads are served from the
``/api/uploads/`` path (the bare ``/uploads/`` path 404s).
"""
from datetime import datetime
from typing import List, Optional
import json
import re

from dateutil import parser as date_parser

from .base import BaseScraper, LA_TZ
from src.data.models import Event


class UCLADesignScraper(BaseScraper):
    """Scraper for UCLA Design Media Arts events."""

    def __init__(self):
        super().__init__('UCLA Design Media Arts')
        self.base_url = 'https://www.design.ucla.edu'
        self.events_url = f'{self.base_url}/events'
        # UCLA Design Media Arts is housed in the Broad Art Center (Westwood).
        self.venue_name = 'UCLA Design Media Arts'
        self.venue_address = 'Broad Art Center, 240 Charles E. Young Dr, Los Angeles, CA 90095'

    def scrape(self) -> List[Event]:
        """
        Scrape events from the __NEXT_DATA__ blob on the events page.

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
            next_data = soup.find('script', id='__NEXT_DATA__')
            if not next_data or not next_data.string:
                self.log("No __NEXT_DATA__ found on page")
                return events

            data = json.loads(next_data.string)
            raw_events = data.get('props', {}).get('pageProps', {}).get('events', [])
            self.log(f"Found {len(raw_events)} events in page data")

            for item in raw_events:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                        self.log(f"Parsed: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, item: dict) -> Optional[Event]:
        """Parse a single event dict from props.pageProps.events."""
        title = (item.get('title') or '').strip()
        if not title:
            return None

        # Date — ISO 8601 with a Z suffix (UTC). create_event normalizes
        # aware datetimes to LA-local, so just hand it the parsed value.
        date_str = item.get('date')
        if not date_str:
            self.log(f"No date for event: {title}")
            return None
        try:
            event_date = date_parser.parse(date_str)
        except Exception as e:
            self.log(f"Failed to parse date '{date_str}' for '{title}': {e}")
            return None

        # Skip past events (compare on LA-local calendar date).
        local_date = event_date.astimezone(LA_TZ).date() if event_date.tzinfo else event_date.date()
        if local_date < datetime.now(LA_TZ).date():
            return None

        # Description is Markdown; strip the most common markers for readability.
        description = self.clean_text(re.sub(r'[#*•]+', ' ', item.get('description') or ''))

        # Canonical detail page; the `link` field is an optional external link.
        slug = item.get('slug')
        url = f"{self.base_url}/events/{slug}" if slug else (item.get('link') or self.events_url)

        # Image uploads live under /api/uploads/, not /uploads/.
        image_url = ""
        images = item.get('images') or []
        if images and isinstance(images[0], dict):
            raw = images[0].get('url') or ''
            if raw.startswith('http'):
                image_url = raw
            elif raw.startswith('/'):
                image_url = f"{self.base_url}/api{raw}"

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=None,
            url=url,
            image_url=image_url,
            category=self._categorize(item.get('type')),
            price=None,
            is_free=False,
            price_note="",
        )

    @staticmethod
    def _categorize(event_type: Optional[str]) -> str:
        """Map the venue's free-form `type` field onto a site category."""
        t = (event_type or '').strip().lower()
        if 'lecture' in t or 'town hall' in t or 'awards' in t:
            return "Education"
        if 'party' in t:
            return "Nightlife"
        # Exhibitions, performances, and untyped entries default to Art.
        return "Art"

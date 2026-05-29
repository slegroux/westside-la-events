"""
Scraper for LA Tech Events from Luma.
Source: https://luma.com/latechevents?k=c

Scrapes tech community events from the LA Tech Events Luma calendar.

Implementation note:
    The public Luma page used to embed events as JSON-LD <script> tags,
    but the current build (2026) ships only minimal page metadata in
    JSON-LD. The full event list is fetched client-side from Luma's
    public calendar API: https://api.lu.ma/calendar/get-items.

    We call that endpoint directly with the calendar's ``api_id``. It
    returns a structured ``entries`` list — each entry contains the
    event's start/end times, coordinates, full address, cover image,
    and a URL slug. This is far more stable than scraping the SPA's
    rendered DOM.
"""
import json
from typing import List, Optional, Dict
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event
from src.utils.geo_filter import validate_event_location


class LATechEventsScraper(BaseScraper):
    """Scraper for LA Tech Events from Luma."""

    # Calendar api_id for https://luma.com/latechevents
    CALENDAR_API_ID = 'cal-ftCm1tx0EOoXGtb'
    API_URL = 'https://api.lu.ma/calendar/get-items'

    def __init__(self):
        super().__init__("LA Tech Events")
        self.url = 'https://luma.com/latechevents?k=c'

    def scrape(self) -> List[Event]:
        """
        Scrape tech events from the Luma calendar API.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from Luma LA Tech Events...")
        events: List[Event] = []

        try:
            api_url = (
                f'{self.API_URL}?calendar_api_id={self.CALENDAR_API_ID}'
                f'&period=future&pagination_limit=100'
            )

            try:
                response = self.session.get(
                    api_url,
                    headers={'Accept': 'application/json'},
                    timeout=20,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                self.log(f"Failed to fetch Luma API: {e}")
                return events

            entries = data.get('entries') or []
            self.log(f"Luma API returned {len(entries)} entries")

            for entry in entries:
                try:
                    event_data = entry.get('event') or {}
                    if not event_data:
                        continue
                    event = self._parse_api_event(event_data)
                    if event:
                        events.append(event)
                        self.log(f"Found event: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing Luma entry: {e}")
                    continue

            self.log(f"Total: {len(events)} events scraped")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_api_event(self, event_data: Dict) -> Optional[Event]:
        """
        Parse a single event payload from the Luma calendar API.

        Args:
            event_data: ``event`` object from an ``entries[]`` item

        Returns:
            Event object, or None when parsing fails or the event is
            outside the coverage area.
        """
        # Title
        title = (event_data.get('name') or '').strip()
        if not title:
            return None

        # Description — Luma's public list endpoint doesn't include the
        # long description, just the name. Fall back to a stub so the
        # detail page still has something to show.
        description = f"Tech event: {title}"

        # Dates
        event_date = None
        end_date = None
        start_str = event_data.get('start_at')
        if start_str:
            try:
                event_date = date_parser.parse(start_str)
            except Exception as e:
                self.log(f"Error parsing start_at '{start_str}': {e}")
        end_str = event_data.get('end_at')
        if end_str:
            try:
                end_date = date_parser.parse(end_str)
            except Exception as e:
                self.log(f"Error parsing end_at '{end_str}': {e}")

        # Location
        venue_name = ''
        address = ''
        latitude = None
        longitude = None

        geo = event_data.get('geo_address_info') or {}
        if isinstance(geo, dict):
            # 'address' is typically the venue name (e.g. "The KINN").
            # 'full_address' is the canonical street address.
            venue_name = (geo.get('address') or '').strip()
            full_addr = (geo.get('full_address') or '').strip()
            if full_addr:
                address = full_addr
            else:
                # Build from parts if no full_address (obfuscated events)
                parts = [geo.get('short_address'), geo.get('city_state')]
                address = ', '.join(p for p in parts if p) or ''

        coord = event_data.get('coordinate') or {}
        if isinstance(coord, dict):
            try:
                lat = coord.get('latitude')
                lng = coord.get('longitude')
                if lat is not None and lng is not None:
                    latitude = float(lat)
                    longitude = float(lng)
            except (ValueError, TypeError):
                pass

        # URL — Luma uses short slugs under luma.com/<slug>
        slug = (event_data.get('url') or '').strip()
        event_url = f'https://luma.com/{slug}' if slug else self.url

        # Cover image
        image_url = (
            event_data.get('cover_url')
            or event_data.get('social_image_url')
            or ''
        )

        # Luma calendar events are RSVP-based; treat as free unless we
        # have explicit ticket info (the list endpoint doesn't include
        # offers). Leave price unset so downstream code can default it.

        if latitude is not None and longitude is not None:
            # We have coordinates — validate location ourselves so we
            # can skip geocoding entirely.
            is_valid, reason = validate_event_location(
                latitude=latitude,
                longitude=longitude,
                address=address,
                venue_name=venue_name,
            )
            if not is_valid:
                self.log(
                    f"Skipping non-Westside event: '{title}' at "
                    f"{venue_name or address} ({reason})"
                )
                return None

            return Event(
                title=title.strip(),
                description=description.strip(),
                venue_name=venue_name.strip(),
                address=address.strip(),
                latitude=latitude,
                longitude=longitude,
                event_date=event_date,
                end_date=end_date,
                category='Tech',
                source=self.source_name,
                url=event_url.strip(),
                image_url=image_url.strip(),
                source_logo_url=self.source_logo_url or "",
                price=None,
                is_free=False,
            )

        # No coordinates — let create_event geocode + validate.
        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=event_url,
            image_url=image_url,
            category='Tech',
        )

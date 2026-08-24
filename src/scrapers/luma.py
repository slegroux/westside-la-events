"""
Shared base for scrapers backed by a Luma (lu.ma) public calendar.

Luma's calendar API returns fully structured events -- name, UTC start/end,
resolved Google Places address and coordinates -- so subclasses only need to
declare which calendar to read. That avoids re-parsing HTML or JSON-LD per
source, and means events arrive already geocoded.
"""
from datetime import datetime
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class LumaCalendarScraper(BaseScraper):
    """Base scraper for a single public Luma calendar.

    Subclasses set CALENDAR_API_ID (found in the calendar page's __NEXT_DATA__
    payload under props.pageProps.initialData.data.calendar.api_id) and pass a
    source name plus the human-facing calendar URL.
    """

    API_URL = 'https://api.lu.ma/calendar/get-items'

    # Subclasses must override.
    CALENDAR_API_ID: str = ''

    # Fallback venue label when Luma has no resolved place for an event.
    DEFAULT_VENUE_NAME: str = ''

    def __init__(self, source_name: str, calendar_slug: str):
        super().__init__(source_name)
        self.base_url = 'https://luma.com'
        self.calendar_url = f'{self.base_url}/{calendar_slug}'

    def scrape(self) -> List[Event]:
        """Fetch upcoming events from the Luma calendar API."""
        self.log("Starting scrape...")
        events = []

        try:
            entries = self._fetch_entries()
            self.log(f"Found {len(entries)} calendar entries")

            for entry in entries:
                try:
                    event = self._parse_entry(entry)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing entry: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _fetch_entries(self) -> List[dict]:
        """Page through future calendar entries.

        Luma signals continuation with `has_more` plus a cursor, so follow it
        rather than assuming one response holds the whole calendar.
        """
        entries = []
        cursor = None

        # Bounded so a misbehaving cursor can't spin forever.
        for _ in range(10):
            params = {
                'calendar_api_id': self.CALENDAR_API_ID,
                'period': 'future',
                'pagination_limit': 50,
            }
            if cursor:
                params['pagination_cursor'] = cursor

            resp = self.session.get(self.API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            page = data.get('entries', []) or []
            entries.extend(page)

            if not data.get('has_more') or not page:
                break
            cursor = data.get('next_cursor') or page[-1].get('api_id')
            if not cursor:
                break

        return entries

    def _parse_entry(self, entry: dict) -> Optional[Event]:
        """Turn one Luma calendar entry into an Event."""
        event = entry.get('event') or {}

        title = (event.get('name') or '').strip()
        if not title:
            return None

        event_date = self._parse_timestamp(event.get('start_at'))
        if not event_date:
            return None

        # Online-only events have no physical location to place on the map.
        if event.get('location_type') == 'virtual':
            return None

        # Luma resolves venues through Google Places, so prefer its structured
        # address and coordinates over anything we'd geocode ourselves.
        geo = event.get('geo_address_info') or {}
        venue_name = (geo.get('address') or '').strip() or self.DEFAULT_VENUE_NAME
        address = (geo.get('full_address') or '').strip()

        coordinate = event.get('coordinate') or {}
        latitude = coordinate.get('latitude') if coordinate else None
        longitude = coordinate.get('longitude') if coordinate else None

        slug = event.get('url') or ''
        url = f'{self.base_url}/{slug}' if slug else self.calendar_url

        price, is_free, price_note = self._parse_ticket_info(entry.get('ticket_info'))

        return self.create_event(
            title=title,
            description='',
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=self._parse_timestamp(event.get('end_at')),
            url=url,
            image_url=event.get('cover_url') or '',
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=latitude,
            longitude=longitude,
        )

    def _parse_ticket_info(self, ticket_info):
        """Read price, free flag and sold-out note from Luma's ticket_info.

        Returns (price, is_free, price_note). Per project convention an unknown
        price leaves price_note empty rather than emitting a placeholder.
        """
        if not isinstance(ticket_info, dict):
            return None, False, ''

        is_free = bool(ticket_info.get('is_free'))
        price = None
        cents = (ticket_info.get('price') or {}).get('cents')
        if isinstance(cents, (int, float)):
            price = cents / 100.0
            if price == 0:
                is_free = True

        price_note = 'Sold out' if ticket_info.get('is_sold_out') else ''
        return price, is_free, price_note

    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        """Parse Luma's UTC ISO-8601 timestamps (e.g. 2026-08-21T01:30:00.000Z).

        create_event normalizes aware datetimes to LA-local, so keep the
        timezone attached rather than dropping it here.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

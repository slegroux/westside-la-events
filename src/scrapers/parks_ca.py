"""
Scraper for California State Parks events.
Source: https://events.parks.ca.gov/

The old parks.ca.gov/Events HTML listing now redirects to events.parks.ca.gov,
an ArcGIS Experience Builder app that renders everything client-side. It reads
two public ArcGIS feature-service layers, which we query directly (the same
requests the page makes):

- layer 0 (``CSP_Events_v1.2_Public``): one row per event series (title,
  description, park, cost, sign-up link, status)
- layer 1 (``events``): one row per occurrence (UTC epoch-ms start/end),
  linked to its series by ``parentglobalid``

Filters to LA/Westside parks (Angeles District parks matching ``target_parks``).
"""
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo
from urllib.parse import urlencode

from .base import BaseScraper
from src.data.models import Event

_LA = ZoneInfo('America/Los_Angeles')


class ParksCaliforniaScraper(BaseScraper):
    """Scraper for California State Parks events."""

    FEATURE_SERVER = (
        'https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/'
        'CSP_Events_v1.2_Public/FeatureServer'
    )

    def __init__(self):
        super().__init__('California State Parks')
        self.base_url = 'https://events.parks.ca.gov'
        self.events_url = f'{self.base_url}/'

        # Focus on LA/Westside area parks
        self.target_parks = [
            'Malibu Creek',
            'Malibu Lagoon',
            'Los Angeles State Historic Park',
            'Los Angeles SHP',
            'Kenneth Hahn',
            'Topanga State Park',
            'Will Rogers State Historic Park',
            'Will Rogers SHP',
            'Santa Monica Mountains'
        ]

    def _query(self, layer: int, where: str) -> List[dict]:
        """Return the attribute dicts of a feature-service query (all pages)."""
        rows: List[dict] = []
        offset = 0
        while True:
            params = urlencode({
                'where': where,
                'outFields': '*',
                'returnGeometry': 'false',
                'resultOffset': offset,
                'resultRecordCount': 1000,
                'f': 'json',
            })
            data = self.fetch_json(
                f'{self.FEATURE_SERVER}/{layer}/query?{params}', method='GET'
            )
            if not data or 'features' not in data:
                self.log(f"Feature query failed for layer {layer}")
                break
            batch = [f.get('attributes', {}) for f in data['features']]
            rows.extend(batch)
            if not data.get('exceededTransferLimit') or not batch:
                break
            offset += len(batch)
        return rows

    def scrape(self) -> List[Event]:
        """
        Scrape upcoming events at LA/Westside State Parks.

        Returns:
            List of Event objects (one per upcoming occurrence)
        """
        self.log("Starting scrape...")
        events: List[Event] = []

        try:
            series_rows = self._query(0, "district_pretty = 'Angeles District'")
            series: Dict[str, dict] = {}
            for row in series_rows:
                if not self._is_target_park(row.get('park_unit') or ''):
                    continue
                if (row.get('status') or '').lower() == 'cancelled':
                    continue
                series[(row.get('globalid') or '').strip('{}').lower()] = row
            self.log(f"Found {len(series)} event series at target parks "
                     f"(of {len(series_rows)} in Angeles District)")
            if not series:
                return events

            occurrences = self._query(1, "event_date_end >= CURRENT_TIMESTAMP")
            now = datetime.now()
            for occ in occurrences:
                parent = series.get((occ.get('parentglobalid') or '').strip('{}').lower())
                if not parent:
                    continue
                if 'cancel' in (occ.get('status') or '').lower() or occ.get('EventCancelled_text'):
                    continue
                try:
                    event = self._build_event(parent, occ, now)
                except Exception as e:
                    self.log(f"Error building event '{parent.get('event_title')}': {e}")
                    continue
                if event:
                    events.append(event)

            events.sort(key=lambda e: e.event_date)
            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    @staticmethod
    def _to_local(epoch_ms) -> Optional[datetime]:
        """UTC epoch milliseconds -> naive LA-local datetime."""
        if not epoch_ms:
            return None
        return datetime.fromtimestamp(epoch_ms / 1000, _LA).replace(tzinfo=None)

    def _build_event(self, parent: dict, occ: dict, now: datetime) -> Optional[Event]:
        start = self._to_local(occ.get('event_date_start'))
        end = self._to_local(occ.get('event_date_end'))
        if not start:
            self.log(f"Skipping '{parent.get('event_title')}': occurrence has no start")
            return None
        if (end or start) < now:
            return None

        title = self.clean_text(parent.get('event_title') or '')
        if not title:
            return None
        park = self.clean_text(parent.get('park_unit') or '')
        description = self.clean_text(parent.get('event_description') or '')

        price, is_free, price_note = self._pricing(parent)

        lat = parent.get('y_add_coordinates') or parent.get('park_y')
        lng = parent.get('x_add_coordinates') or parent.get('park_x')

        return self.create_event(
            title=title,
            description=description,
            venue_name=park,
            address=self.clean_text(parent.get('park_address') or ''),
            event_date=start,
            end_date=end,
            url=(parent.get('event_signup_link') or '').strip() or self.events_url,
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=lat,
            longitude=lng,
        )

    @staticmethod
    def _pricing(parent: dict):
        """Return (price, is_free, price_note); unknown price leaves note empty."""
        price = None
        is_free = (parent.get('event_costType') or '').strip().lower() == 'free'
        cost = parent.get('event_cost')
        if not is_free and cost:
            price = float(cost)

        price_note = ''
        parking_cost = parent.get('parking_cost')
        if (parent.get('parking_yes_no') or '').lower() == 'yes' and parking_cost:
            price_note = f"Parking: ${parking_cost}"
        return price, is_free, price_note

    def _is_target_park(self, park_name: str) -> bool:
        """
        Check if park is in the target LA/Westside area.

        Args:
            park_name: Name of the park

        Returns:
            True if park is in target area
        """
        if not park_name:
            return False

        park_lower = park_name.lower()
        return any(target.lower() in park_lower for target in self.target_parks)

"""
Scraper for Grateful Giraffes (The Oasis).
Source: https://app.grateful.gg/events.json

Grateful Giraffes is an LA gratitude/wellness community that runs salons, sound
baths, bootcamps and dinners, mostly on the Westside. Its site (the Oasis) is a
base44-era single-page app whose /events page ships no event markup. The
publisher documents a public, read-only, key-less JSON feed of upcoming events
for exactly this purpose (listed in https://grateful.gg/llms.txt):

    GET https://app.grateful.gg/events.json

Why not the old entity API (``/api/apps/<id>/entities/Event``)? It now answers
HTTP 410 ``{"error": "not available on staging"}`` -- the app moved off that
backend (checked 2026-11-19) -- so the feed above is the replacement.

Properties of the feed that shape the code:

  * **Upcoming only.** Every record is a future event the host published, so
    there is no history to filter out.

  * **No street addresses.** The feed says "A street address goes only to
    confirmed guests, so each event gives its city." The address handed to
    create_event is therefore just that city ("Culver City", "Topanga, CA"):
    the shared geo-filter then keeps what resolves to the Westside and drops
    the rest (an "Austin" New Year's Eve, a bare "Los Angeles") rather than
    pinning them somewhere invented.

  * **Online events** (``online: true``, city "Online") have no venue to place
    on the map and are skipped.

  * **Timestamps are real ISO-8601 with the event's own offset**
    ("2026-11-21T14:00:00-08:00"), so create_event converts them to LA-local.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run dedup;
each event has its own stable permalink.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event


class GratefulGiraffesScraper(BaseScraper):
    """Scraper for Grateful Giraffes events (public events.json feed)."""

    BASE_URL = 'https://app.grateful.gg'
    FEED_URL = f'{BASE_URL}/events.json'
    LISTING_URL = f'{BASE_URL}/events'

    # This community's events are wellness/social gatherings; the shared
    # auto-classifier reads names like "The AI Salon" or "Biohacking Safari" as
    # Tech or Sports, so map the recurring formats by keyword first. Order
    # matters -- first match wins, so specific signals come before generic.
    _CATEGORY_RULES = (
        ('sound bath', 'Wellness'),
        ('sound healing', 'Wellness'),
        ('breathwork', 'Wellness'),
        ('yoga', 'Wellness'),
        ('meditation', 'Wellness'),
        ('retreat', 'Wellness'),
        ('biohacking', 'Wellness'),
        ('celebration', 'Community'),
        ('gratitude', 'Community'),
        ('salon', 'Community'),
        ('friendsgiving', 'Food'),
        ('dinner', 'Food'),
        ('brunch', 'Food'),
        ('potluck', 'Food'),
        ('concert', 'Music'),
        ('bootcamp', 'Education'),
        ('workshop', 'Education'),
    )

    def __init__(self):
        super().__init__('Grateful Giraffes')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Grateful Giraffes...")
        events: List[Event] = []

        records = self._fetch_events()
        if not records:
            self.log("No events returned by the events feed")
            return events

        self.log(f"Fetched {len(records)} event record(s) from the feed")

        for raw in records:
            if raw.get('online'):
                continue
            try:
                event = self._parse_event(raw)
            except Exception as e:
                self.log(f"  x error parsing '{raw.get('name')}': {e}")
                continue
            if event:
                events.append(event)
                self.log(f"  + {event.event_date:%Y-%m-%d} {event.title}")

        self.log(f"Scraped {len(events)} upcoming in-person event(s)")
        return events

    def _fetch_events(self) -> List[Dict[str, Any]]:
        """Read the feed's ``events`` list. Returns [] on any failure."""
        data = self.fetch_json(self.FEED_URL, method='GET')
        if isinstance(data, dict) and isinstance(data.get('events'), list):
            return [r for r in data['events'] if isinstance(r, dict)]
        return []

    def _parse_event(self, raw: Dict[str, Any]) -> Optional[Event]:
        title = self.clean_text(raw.get('name'))
        if not title:
            return None

        event_date = self._parse_timestamp(raw.get('start'))
        if not event_date:
            return None
        end_date = self._parse_timestamp(raw.get('end'))
        if end_date and end_date <= event_date:
            end_date = None

        city = self.clean_text(raw.get('city'))

        return self.create_event(
            title=title,
            description='',
            venue_name=self.source_name,
            address=city,
            event_date=event_date,
            end_date=end_date,
            url=(raw.get('url') or '').strip() or self.LISTING_URL,
            image_url=(raw.get('image') or '').strip(),
            category=self._classify(title),
            # The feed carries no price; an absent price stays an absent badge
            # per the project's pricing convention.
            price_note='',
        )

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except ValueError:
            return None

    def _classify(self, title: str) -> str:
        """Map a recurring format to a category by keyword.

        Returns '' when nothing matches so create_event falls back to the
        shared auto-classifier.
        """
        haystack = title.lower()
        for keyword, category in self._CATEGORY_RULES:
            if keyword in haystack:
                return category
        return ''

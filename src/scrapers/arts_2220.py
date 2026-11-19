"""
Scraper for 2220 Arts + Archives (Historic Filipinotown).
Source: https://www.2220arts.org/events

This is a "beyond the Westside" source: 2220 Beverly Blvd is outside the
coverage box, so REGION opts it into the separate tab and its events are
validated against LA County instead.

The venue's own events page is a Google Sites shell around a DICE ticketing
widget, so it carries no event markup. The same calendar is published on the
venue's public DICE page, whose schema.org JSON-LD lists every upcoming event
(name, start/end, image, price). Each event's own DICE page adds the
description and a more specific type (MusicEvent, ScreeningEvent, ...), so we
read the listing first and then enrich from the event pages. If an event page
can't be fetched, the listing data alone still yields a complete event.

Sold-out status isn't in the JSON-LD; it is read best-effort from the page's
Next.js data blob, keyed by event id.
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event
from src.utils.categories import classify_event


class Arts2220Scraper(BaseScraper):
    """Scraper for 2220 Arts + Archives via its public DICE venue page."""

    REGION = 'beyond'

    VENUE_NAME = '2220 Arts + Archives'
    VENUE_ADDRESS = '2220 Beverly Blvd, Los Angeles, CA 90057'
    VENUE_LAT = 34.0672209
    VENUE_LNG = -118.2723086

    EVENTS_URL = 'https://www.2220arts.org/events'
    LISTING_URL = 'https://dice.fm/venue/2220-arts--archives-bdyv'

    # schema.org types specific enough to trust over keyword classification.
    _TYPE_CATEGORIES = {
        'MusicEvent': 'Music',
        'ScreeningEvent': 'Film',
        'ComedyEvent': 'Comedy',
        'TheaterEvent': 'Theater',
        'DanceEvent': 'Theater',
        'LiteraryEvent': 'Education',
        'EducationEvent': 'Education',
        'FoodEvent': 'Food & Drink',
        'VisualArtsEvent': 'Art',
        'ExhibitionEvent': 'Art',
    }

    _LD_RE = re.compile(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
    )
    _NEXT_DATA_RE = re.compile(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S
    )

    def __init__(self):
        super().__init__('2220 Arts + Archives')
        self.base_url = 'https://www.2220arts.org'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of 2220 Arts + Archives (DICE venue page)...")
        events: List[Event] = []

        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch DICE venue page")
            return events

        listings = self._listing_events(html)
        self.log(f"Found {len(listings)} listed event(s)")
        if not listings:
            return events

        statuses = self._statuses(html)
        self.prefetch_pages([item.get('url', '') for item in listings])

        now = datetime.now()
        seen = set()
        for item in listings:
            try:
                event = self._build_event(item, statuses)
            except Exception as e:
                self.log(f"  ✗ error parsing '{item.get('name', '')}': {e}")
                continue
            if not event:
                continue
            if (event.end_date or event.event_date) < now:
                continue
            key = (event.title.lower(), event.event_date)
            if key in seen:
                continue
            seen.add(key)
            events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _json_ld(self, html: str) -> List[dict]:
        """All JSON-LD objects on a page (malformed blocks are skipped)."""
        found: List[dict] = []
        for raw in self._LD_RE.findall(html):
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            for obj in data if isinstance(data, list) else [data]:
                if isinstance(obj, dict):
                    found.append(obj)
        return found

    def _listing_events(self, html: str) -> List[dict]:
        """The venue Place's ``event`` array from the listing page."""
        for obj in self._json_ld(html):
            listed = obj.get('event')
            types = obj.get('@type')
            types = types if isinstance(types, list) else [types]
            if 'Place' in types and isinstance(listed, list):
                return [e for e in listed if isinstance(e, dict)]
        return []

    def _statuses(self, html: str) -> Dict[str, str]:
        """Map DICE event id -> status ('on-sale', 'sold-out', ...). Best effort."""
        m = self._NEXT_DATA_RE.search(html)
        if not m:
            return {}
        try:
            profile = json.loads(m.group(1))['props']['pageProps']['profile']
            return {
                str(e['id']): e.get('status') or ''
                for section in profile.get('sections') or []
                for e in section.get('events') or []
                if isinstance(e, dict) and e.get('id')
            }
        except (ValueError, KeyError, TypeError, AttributeError):
            return {}

    def _detail(self, url: str) -> dict:
        """The event page's own JSON-LD (description, specific type), or {}."""
        if not url:
            return {}
        html = self.fetch_page(url, retry=1)
        if not html:
            return {}
        for obj in self._json_ld(html):
            if str(obj.get('@type', '')).endswith('Event') and obj.get('name'):
                return obj
        return {}

    def _build_event(self, item: dict, statuses: Dict[str, str]) -> Optional[Event]:
        listing_url = item.get('url', '')
        detail = self._detail(listing_url)
        # Event-page fields win; the listing fills anything it lacks.
        data = {**item, **{k: v for k, v in detail.items() if v not in (None, '', [])}}

        title = self._clean_description(data.get('name', ''))
        event_date = self._parse_dt(data.get('startDate'))
        if not title or not event_date:
            return None

        event_status = str(data.get('eventStatus', ''))
        if 'Cancelled' in event_status or 'Postponed' in event_status:
            self.log(f"  - skipping {event_status.rsplit('/', 1)[-1]}: {title}")
            return None

        description = self._clean_description(data.get('description', ''))

        image = data.get('image')
        if isinstance(image, list):
            image = image[0] if image else ''
        image_url = image if isinstance(image, str) else ''

        price, is_free = self._price(data.get('offers'))
        price_note = ''
        event_id = listing_url.rstrip('/').rsplit('/', 1)[-1]
        if statuses.get(event_id) == 'sold-out':
            # The card shows a price in preference to the note, so drop it.
            price, is_free, price_note = None, False, 'Sold out'

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=event_date,
            end_date=self._parse_dt(data.get('endDate')),
            url=data.get('url') or self.EVENTS_URL,
            image_url=image_url,
            category=self._category(data.get('@type'), title, description),
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        """ISO-8601 with offset; create_event converts it to naive LA time."""
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _price(offers):
        """(price, is_free) from a schema.org Offer/AggregateOffer."""
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            return None, False
        raw = offers.get('lowPrice', offers.get('price'))
        try:
            low = float(raw)
        except (TypeError, ValueError):
            return None, False
        if low == 0:
            return None, True
        return low, False

    def _clean_description(self, text) -> str:
        """Flatten DICE's markdown-ish text (titles use it too) to plain text."""
        if not isinstance(text, str):
            return ''
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [label](url)
        text = re.sub(r'(?<![\w*])(\*{1,3}|_{2})(\S(?:.*?\S)?)\1(?![\w*])', r'\2', text)  # *em*
        text = re.sub(r'^\s*[~#]+\s*$', '', text, flags=re.M)  # divider lines
        text = re.sub(r'\\([*_\[\]()~#])', r'\1', text)  # escaped literals: Sh\*t
        return self.clean_text(text)

    def _category(self, schema_type, title: str, description: str) -> str:
        types = schema_type if isinstance(schema_type, list) else [schema_type]
        for t in types:
            if t in self._TYPE_CATEGORIES:
                return self._TYPE_CATEGORIES[t]
        # Classify without the venue name: "Arts" in it tags everything Art.
        return classify_event(title, description, '')

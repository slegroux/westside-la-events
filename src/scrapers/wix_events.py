"""
Scrapers for venues that publish their calendar with Wix Events.

Sam First (Westchester jazz club) and Highways Performance Space (Santa Monica)
both run the Wix Events list widget on their home page. Wix server-renders the
widget's data into the page as one JSON blob, so no JavaScript rendering is
needed:

    "events":{"events":[ {title, description, slug, mainImage, location,
                          scheduling.config{startDate (UTC), endDate,
                          timeZoneId, scheduleTbd}, status,
                          registration.ticketing{lowestTicketPrice, soldOut}},
                         ... ], "hasMore": true|false, ... }

Each event's own page (``/events/<slug>``) carries a schema.org Event in
JSON-LD with the same facts, which is how events beyond the first page are read.

Pagination: the widget only embeds its first 18 events and offers a "Load
More" button that fetches the rest from a client-side API. The blob says so
through ``hasMore``. When it is true, the remaining events are found through
the site's event sitemap: pages whose ``lastmod`` is no older than the oldest
listed event are fetched (capped), and only those dated after the last listed
event are kept, since the listing is date-ordered and therefore already
complete up to that point.

Both venues are single-site, so events without coordinates in the blob (the
JSON-LD path) fall back to the venue's fixed location.
"""
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event


# Wix Events status enum: SCHEDULED 0, STARTED 1, ENDED 2, CANCELED 3.
_SKIP_STATUSES = (2, 3)

_EVENTS_BLOB = re.compile(r'"events"\s*:\s*\{\s*"events"\s*:\s*\[')
_HAS_MORE = re.compile(r'"hasMore"\s*:\s*(true|false)')
_LD_JSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_SITEMAP_ENTRY = re.compile(
    r'<loc>[^<]*?/events/([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>'
)


def _parse_instant(value: str) -> Optional[datetime]:
    """Parse an ISO timestamp with an offset or ``Z`` into an aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    return dt.replace(microsecond=0) if dt.tzinfo else None


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text or '')


class WixEventsScraper(BaseScraper):
    """Base for a venue whose calendar is a Wix Events list on its home page."""

    BASE_URL = ''
    LISTING_URL = ''
    EVENT_PATH = '/events'
    SITEMAP_URL = ''

    VENUE_NAME = ''
    VENUE_ADDRESS = ''
    VENUE_LAT = 0.0
    VENUE_LNG = 0.0
    CATEGORY = ''

    # Cap on event pages fetched to cover what the widget did not embed.
    MAX_EXTRA_PAGES = 30

    def __init__(self, source_name: str):
        super().__init__(source_name)
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log(f"Starting scrape of {self.source_name}...")
        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch the listing page")
            return []

        raw_events, has_more = self._extract_events(html)
        self.log(f"Found {len(raw_events)} event(s) in embedded data (hasMore={has_more})")

        records: Dict[str, dict] = {}
        for raw in raw_events:
            rec = self._record_from_embedded(raw)
            if rec and rec['slug'] not in records:
                records[rec['slug']] = rec

        if has_more:
            for rec in self._records_beyond_listing(raw_events, records):
                records.setdefault(rec['slug'], rec)

        events: List[Event] = []
        now = datetime.now(timezone.utc)
        for rec in records.values():
            if (rec['end'] or rec['start']) < now:
                continue
            event = self._make_event(rec)
            if event:
                events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    # -- listing blob ------------------------------------------------------

    def _extract_events(self, html: str):
        """Return (raw event dicts, hasMore) from the embedded widget data."""
        m = _EVENTS_BLOB.search(html)
        if not m:
            return [], False
        start = m.end() - 1
        try:
            raw, end = json.JSONDecoder().raw_decode(html, start)
        except json.JSONDecodeError as e:
            self.log(f"Failed to parse embedded events JSON: {e}")
            return [], False
        more = _HAS_MORE.search(html[end:end + 80])
        return raw, bool(more and more.group(1) == 'true')

    def _record_from_embedded(self, raw: dict) -> Optional[dict]:
        slug = raw.get('slug') or ''
        title = self.clean_text(raw.get('title'))
        config = (raw.get('scheduling') or {}).get('config') or {}
        start = _parse_instant(config.get('startDate'))
        if not slug or not title or config.get('scheduleTbd') or not start:
            self.log(f"Skipping undated or incomplete event: {title or slug or '?'}")
            return None
        if raw.get('status') in _SKIP_STATUSES:
            return None

        location = raw.get('location') or {}
        coords = location.get('coordinates') or {}
        ticketing = (raw.get('registration') or {}).get('ticketing') or {}
        low = (ticketing.get('lowestTicketPrice') or {}).get('amount')

        description = self.clean_text(raw.get('description'))
        if not description:
            description = self.clean_text(_strip_html(raw.get('about')))[:600]

        return {
            'slug': slug,
            'title': title,
            'description': description,
            'start': start,
            'end': _parse_instant(config.get('endDate')),
            'image': (raw.get('mainImage') or {}).get('url', ''),
            'venue': location.get('name') or self.VENUE_NAME,
            'address': location.get('address') or self.VENUE_ADDRESS,
            'lat': coords.get('lat'),
            'lng': coords.get('lng'),
            'price': low,
            'sold_out': bool(ticketing.get('soldOut')),
        }

    # -- events past the widget's first page --------------------------------

    def _records_beyond_listing(self, raw_events: List[dict], listed: Dict[str, dict]) -> List[dict]:
        sitemap = self.fetch_page(self.SITEMAP_URL) if self.SITEMAP_URL else None
        if not sitemap or not listed:
            self.log("hasMore is set but the event sitemap is unavailable; listing may be truncated")
            return []

        lastmods = dict(_SITEMAP_ENTRY.findall(sitemap))
        listed_mods = [lastmods[s] for s in listed if s in lastmods]
        if not listed_mods:
            return []
        floor = min(listed_mods)
        last_listed_start = max(rec['start'] for rec in listed.values())

        candidates = sorted(
            (s for s, mod in lastmods.items() if mod >= floor and s not in listed),
            key=lambda s: lastmods[s], reverse=True,
        )[:self.MAX_EXTRA_PAGES]
        urls = [self._event_url(s) for s in candidates]
        self.log(f"Fetching {len(urls)} event page(s) beyond the listing")
        self.prefetch_pages(urls)

        found = []
        for slug, url in zip(candidates, urls):
            page = self.fetch_page(url)
            rec = self._record_from_jsonld(slug, page) if page else None
            if rec and rec['start'] > last_listed_start:
                found.append(rec)
        return found

    def _record_from_jsonld(self, slug: str, html: str) -> Optional[dict]:
        for block in _LD_JSON.findall(html):
            try:
                ld = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(ld, dict) and ld.get('@type') == 'Event':
                break
        else:
            return None

        start = _parse_instant(ld.get('startDate'))
        title = self.clean_text(ld.get('name'))
        if not start or not title or str(ld.get('eventStatus', '')).endswith('EventCancelled'):
            return None

        offers = ld.get('offers') or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        image = ld.get('image') or ''
        if isinstance(image, dict):
            image = image.get('url', '')
        return {
            'slug': slug,
            'title': title,
            'description': self.clean_text(ld.get('description')),
            'start': start,
            'end': _parse_instant(ld.get('endDate')),
            'image': image,
            'venue': self.VENUE_NAME,
            'address': self.VENUE_ADDRESS,
            'lat': None,
            'lng': None,
            'price': offers.get('lowPrice') or offers.get('price'),
            'sold_out': str(offers.get('availability', '')).endswith('SoldOut'),
        }

    # -- event construction -------------------------------------------------

    def _event_url(self, slug: str) -> str:
        return f"{self.BASE_URL}{self.EVENT_PATH}/{slug}"

    def _make_event(self, rec: dict) -> Optional[Event]:
        price = None
        is_free = False
        price_note = ''
        if rec['sold_out']:
            price_note = 'Sold out'
        elif rec['price'] not in (None, ''):
            try:
                amount = float(str(rec['price']).replace('$', '').replace(',', ''))
            except ValueError:
                amount = None
            if amount == 0:
                is_free = True
            elif amount is not None:
                price = amount

        lat, lng = rec['lat'], rec['lng']
        if lat is None or lng is None:
            lat, lng = self.VENUE_LAT, self.VENUE_LNG
        return self.create_event(
            title=rec['title'],
            description=rec['description'],
            venue_name=rec['venue'],
            address=rec['address'],
            event_date=rec['start'],
            end_date=rec['end'],
            url=self._event_url(rec['slug']),
            image_url=rec['image'],
            category=self.CATEGORY,
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=lat,
            longitude=lng,
        )


class SamFirstScraper(WixEventsScraper):
    """Sam First, a jazz club in Westchester."""

    BASE_URL = 'https://www.samfirstbar.com'
    LISTING_URL = 'https://www.samfirstbar.com/'
    SITEMAP_URL = 'https://www.samfirstbar.com/event-pages-sitemap.xml'
    VENUE_NAME = 'Sam First'
    VENUE_ADDRESS = '6171 W Century Blvd #180, Los Angeles, CA 90045'
    VENUE_LAT = 33.9458234
    VENUE_LNG = -118.3933758
    CATEGORY = 'Music'

    def __init__(self):
        super().__init__('Sam First')


class HighwaysScraper(WixEventsScraper):
    """Highways Performance Space, experimental and queer performance in Santa Monica."""

    BASE_URL = 'https://www.highwaysperformance.org'
    LISTING_URL = 'https://www.highwaysperformance.org/'
    SITEMAP_URL = 'https://www.highwaysperformance.org/event-pages-sitemap.xml'
    VENUE_NAME = 'Highways Performance Space'
    VENUE_ADDRESS = '1651 18th St, Santa Monica, CA 90404'
    VENUE_LAT = 34.0235056
    VENUE_LNG = -118.4774434
    CATEGORY = 'Theater'

    def __init__(self):
        super().__init__('Highways Performance Space')

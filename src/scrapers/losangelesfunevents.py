"""
Scraper for Los Angeles Fun Events (Off the Couch Adventures LLC).
Source: https://www.losangelesfunevents.com/weary-livers

The organizer runs a recurring events program (musicians nights, karaoke,
comedy shows, singles socials, World Cup watch parties, etc.) out of a single
Westside venue — Weary Livers, 2819 Pico Blvd, Santa Monica. The site is a Wix
build: the listing page ships every upcoming event as a JSON blob embedded in
the HTML under a ``"events":[ ... ]`` key, so no JavaScript rendering is needed.

Each embedded event object carries everything we need:

    title        event name
    description  short tagline
    about        longer body (usually empty on this site)
    slug         used to build the /event-details/<slug> permalink
    mainImage    { url: ... }
    location     { address, coordinates: {lat, lng} }
    scheduling   { config: { startDate, endDate, timeZoneId } }  # startDate is UTC

Dedup: the ingestion pipeline (Database.insert_event) is the source of truth for
cross-run/cross-source dedup (URL first, then title/venue/date similarity). We
additionally dedup by slug here so a single scrape never emits the same event
twice if Wix lists it more than once.
"""
import json
import re
from datetime import datetime, timezone
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class LosAngelesFunEventsScraper(BaseScraper):
    """Scraper for Los Angeles Fun Events at Weary Livers (Santa Monica)."""

    BASE_URL = 'https://www.losangelesfunevents.com'
    LISTING_URL = 'https://www.losangelesfunevents.com/weary-livers'

    # This organizer runs a small, well-defined set of recurring event types.
    # The shared auto-classifier misreads several of them (e.g. "Musicians
    # Night" -> Art because its blurb mentions "Recording Artists"; sports watch
    # parties -> Art), so map the known types by title keyword and fall back to
    # the auto-classifier for anything unrecognized. Order matters: first match
    # wins, so more specific signals come first.
    _CATEGORY_RULES = (
        ('watch party', 'Sports'),
        ('world cup', 'Sports'),
        ('musicians', 'Music'),
        ('open play', 'Music'),
        ('comedy', 'Comedy'),
        ('karaoke', 'Nightlife'),
        ('country night', 'Music'),
        ('singles', 'Nightlife'),
        ('mix and mingle', 'Nightlife'),
    )

    def __init__(self):
        super().__init__('Los Angeles Fun Events')

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Los Angeles Fun Events...")
        events: List[Event] = []

        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch the Los Angeles Fun Events listing page")
            return events

        raw_events = self._extract_events(html)
        self.log(f"Found {len(raw_events)} event(s) in embedded data")

        seen_slugs = set()
        now = datetime.now()
        for raw in raw_events:
            slug = raw.get('slug') or ''
            # Dedup within this scrape by slug (Wix can repeat the same event).
            if slug and slug in seen_slugs:
                continue

            try:
                event = self._parse_event(raw)
            except Exception as e:
                self.log(f"  ✗ error parsing event '{raw.get('title', '?')}': {e}")
                continue

            if not event:
                continue

            # Drop past events (listing occasionally retains just-finished ones).
            if event.event_date and event.event_date < now:
                continue

            if slug:
                seen_slugs.add(slug)
            events.append(event)
            self.log(f"  ✓ {event.title}")

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _extract_events(self, html: str) -> List[dict]:
        """Extract the embedded ``"events":[ ... ]`` JSON array from the page.

        The array is literal JSON inside a Wix data script. We locate the key
        and bracket-match to the closing ``]``, honoring string boundaries and
        escapes so brackets inside titles/addresses don't end the array early.
        """
        m = re.search(r'"events"\s*:\s*\[', html)
        if not m:
            return []
        # Start bracket-matching at the opening '[' of the array.
        start = m.end() - 1

        depth = 0
        in_str = False
        esc = False
        end = -1
        for j in range(start, len(html)):
            c = html[j]
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = not in_str
            elif not in_str:
                if c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
        if end == -1:
            return []

        raw = html[start:end + 1]
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            self.log(f"Failed to parse embedded events JSON: {e}")
            return []
        return data if isinstance(data, list) else []

    def _parse_event(self, raw: dict) -> Optional[Event]:
        title = self.clean_text(raw.get('title'))
        if not title:
            return None

        config = (raw.get('scheduling') or {}).get('config') or {}
        event_date = self._parse_dt(config.get('startDate'))
        if not event_date:
            return None
        end_date = self._parse_dt(config.get('endDate'))

        slug = raw.get('slug') or ''
        url = f"{self.BASE_URL}/event-details/{slug}" if slug else self.LISTING_URL

        # Prefer the longer "about" body; fall back to the short tagline.
        description = self.clean_text(raw.get('about')) or self.clean_text(raw.get('description'))

        image_url = ((raw.get('mainImage') or {}).get('url') or '').strip()

        location = raw.get('location') or {}
        address = (location.get('address') or '').strip()
        venue_name = (location.get('name') or '').strip() or 'Weary Livers'
        coords = location.get('coordinates') or {}
        latitude = coords.get('lat')
        longitude = coords.get('lng')

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=self._classify(title),
            latitude=latitude,
            longitude=longitude,
        )

    def _classify(self, title: str) -> str:
        """Map a known recurring event type to a category by title keyword.

        Returns '' when nothing matches so create_event runs the shared
        auto-classifier instead.
        """
        low = title.lower()
        for keyword, category in self._CATEGORY_RULES:
            if keyword in low:
                return category
        return ''

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        """Parse a Wix ISO-8601 UTC timestamp (e.g. '2026-07-09T02:00:00.000Z').

        Returned as an aware UTC datetime; BaseScraper.create_event normalizes it
        to naive LA-local via normalize_event_datetime.
        """
        if not value:
            return None
        s = value.strip()
        # Normalize trailing 'Z' to an explicit UTC offset for fromisoformat.
        s = re.sub(r'Z$', '+00:00', s)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

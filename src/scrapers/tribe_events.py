"""
Shared parser for WordPress sites running The Events Calendar ("Tribe").

Every Tribe install exposes the same read-only REST API:

    /wp-json/tribe/events/v1/events?start_date=<today>&per_page=50&status=publish

so one base class reads it and each venue is a small subclass that supplies its
name, URL, fallback venue, category rules and any skip rules. Used by
Boulevard Music, the Wende Museum and the UCLA School of Music.

What the API gives us, and the quirks the base class absorbs:

  * ``start_date``/``end_date`` are naive strings already in the site's local
    time (America/Los_Angeles for all current users), which is exactly the
    shape create_event() treats as canonical, so no timezone conversion.
  * ``venue`` is a dict, a list of dicts (an event at several rooms), or an
    empty list (no venue record). Names arrive HTML-escaped (``&#8217;``).
    Coordinates are often missing, so a subclass can pin per-venue addresses
    and coordinates in ``VENUE_OVERRIDES``; the single fixed venue constants
    are the last resort.
  * ``custom_fields`` is a dict, or an empty *list* when nothing is set.

Dedup: Database.insert_event owns cross-run dedup. Within one scrape a URL that
repeats (a series sharing one permalink) is made unique with a ``#<iso-minute>``
fragment so consecutive occurrences don't collapse into one.
"""
import html as _html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class TribeEventsScraper(BaseScraper):
    """Base class: subclasses set the class attributes below."""

    SOURCE_NAME = ''
    BASE_URL = ''          # e.g. https://www.example.org
    EVENTS_URL = ''        # public calendar page, used when an event has no URL

    # Fallback venue: used when an event carries no venue name or address.
    VENUE_NAME = ''
    VENUE_ADDRESS = ''
    VENUE_LAT: Optional[float] = None
    VENUE_LNG: Optional[float] = None

    # (lowercase name needle, address, lat, lng): first match wins and beats
    # whatever the API says, for installs whose venue records lack coordinates.
    VENUE_OVERRIDES: Tuple[Tuple[str, str, float, float], ...] = ()

    DEFAULT_CATEGORY = 'Other'
    # (lowercase needle, category): first match wins.
    CATEGORY_RULES: Tuple[Tuple[str, str], ...] = ()
    # Whether the title is searched for category needles as well as the Tribe
    # category names. Off where titles are free-form ("... A Regents' Lecture").
    CATEGORY_USES_TITLE = True

    # Safety rail: a venue lists a season at a time, never hundreds of shows.
    MAX_PAGES = 5
    PER_PAGE = 50

    # "$28", "$28.00", "$25 - $30" -> lowest number wins as the advertised price.
    _PRICE_RE = re.compile(r'(\d+(?:\.\d{1,2})?)')

    def __init__(self):
        super().__init__(self.SOURCE_NAME)
        self.base_url = self.BASE_URL
        self.api_url = f'{self.BASE_URL}/wp-json/tribe/events/v1/events'

    # ------------------------------------------------------------------ hooks

    def _skip_reason(self, raw: Dict[str, Any], title: str,
                     venue_name: str) -> Optional[str]:
        """Return a reason to drop this event (logged), or None to keep it."""
        return None

    # ----------------------------------------------------------------- scrape

    def scrape(self) -> List[Event]:
        self.log(f"Starting scrape of {self.SOURCE_NAME}...")
        events: List[Event] = []
        seen_urls = set()

        for raw in self._fetch_api_events():
            try:
                event = self._parse_event(raw)
            except Exception as e:
                self.log(f"  x error parsing event {raw.get('id')}: {e}")
                continue
            if not event:
                continue
            if event.url in seen_urls:
                event.url = f'{event.url.split("#")[0]}#{event.event_date:%Y-%m-%dT%H:%M}'
            seen_urls.add(event.url)
            events.append(event)
            self.log(f"  + {event.event_date:%Y-%m-%d} {event.title}")

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _fetch_api_events(self) -> List[Dict[str, Any]]:
        """Page through the Tribe API from today forward."""
        collected: List[Dict[str, Any]] = []
        today = datetime.now().strftime('%Y-%m-%d')

        for page in range(1, self.MAX_PAGES + 1):
            data = self.fetch_json(
                f'{self.api_url}?per_page={self.PER_PAGE}&page={page}'
                f'&start_date={today}&status=publish',
                method='GET',
            )
            if not data:
                break

            page_events = data.get('events') or []
            if not page_events:
                break
            collected.extend(page_events)

            if page >= (data.get('total_pages') or 1):
                break

        self.log(f"Fetched {len(collected)} event(s) from the Tribe API")
        return collected

    def _parse_event(self, raw: Dict[str, Any]) -> Optional[Event]:
        title = self.clean_text(_html.unescape(raw.get('title') or ''))
        if not title:
            return None

        event_date = self._parse_datetime(raw.get('start_date'))
        if not event_date:
            self.log(f"  - no start date, skipping: {title}")
            return None
        # The API honours start_date, but an event that began yesterday can
        # still come back; drop anything already over.
        if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            return None

        venue_name, address, lat, lng = self._venue(raw)

        reason = self._skip_reason(raw, title, venue_name)
        if reason:
            self.log(f"  - skipping ({reason}): {title}")
            return None

        end_date = self._parse_datetime(raw.get('end_date'))
        if end_date and end_date <= event_date:
            end_date = None

        description = self._strip_html(raw.get('description') or '')
        if not description:
            description = self._strip_html(raw.get('excerpt') or '')

        image = raw.get('image')
        image_url = image.get('url', '') if isinstance(image, dict) else (
            image if isinstance(image, str) else '')

        price, is_free, price_note = self._parse_cost(raw.get('cost'))

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=raw.get('url') or self.EVENTS_URL,
            image_url=image_url,
            category=self._classify(raw, title),
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=lat,
            longitude=lng,
        )

    # ------------------------------------------------------------------ venue

    def _venue(self, raw: Dict[str, Any]) -> Tuple[str, str, Optional[float], Optional[float]]:
        """(name, address, lat, lng) for an event.

        Order: subclass override by name, API coordinates, API address (left to
        the geocoder), then the fixed fallback venue.
        """
        venue = raw.get('venue')
        if isinstance(venue, list):
            venue = next((v for v in venue if isinstance(v, dict)), None)
        name = ''
        if isinstance(venue, dict):
            name = self.clean_text(_html.unescape(venue.get('venue') or ''))
        if not name:
            return self.VENUE_NAME, self.VENUE_ADDRESS, self.VENUE_LAT, self.VENUE_LNG

        for needle, address, lat, lng in self.VENUE_OVERRIDES:
            if needle in name.lower():
                return name, address, lat, lng

        try:
            lat, lng = float(venue.get('geo_lat')), float(venue.get('geo_lng'))
        except (TypeError, ValueError):
            lat = lng = None
        street = self.clean_text(_html.unescape(venue.get('address') or ''))
        parts = [street, venue.get('city'), venue.get('stateprovince') or venue.get('state')]
        address = ', '.join(p for p in parts if p) if street else ''
        if lat is not None:
            return name, address or self.VENUE_ADDRESS, lat, lng
        if address:
            return name, address, None, None
        return name, self.VENUE_ADDRESS, self.VENUE_LAT, self.VENUE_LNG

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse a Tribe 'YYYY-MM-DD HH:MM:SS' local timestamp."""
        if not value:
            return None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    def _parse_cost(self, cost: Any) -> tuple:
        """Map Tribe's free-text cost onto (price, is_free, price_note).

        An absent cost stays an empty note so the card renders no price badge,
        per the project-wide "unknown price" convention.
        """
        text = str(cost or '').strip()
        if not text:
            return None, False, ''
        if text.lower() in ('free', '0', '$0', 'free admission'):
            return None, True, 'Free'

        match = self._PRICE_RE.search(text)
        if not match:
            return None, False, self.clean_text(text)
        return float(match.group(1)), False, self.clean_text(text)

    @staticmethod
    def _category_names(raw: Dict[str, Any]) -> str:
        categories = raw.get('categories') or []
        return ' '.join(
            _html.unescape(str(c.get('name', ''))) for c in categories if isinstance(c, dict)
        ).lower()

    def _classify(self, raw: Dict[str, Any], title: str) -> str:
        haystack = self._category_names(raw)
        if self.CATEGORY_USES_TITLE:
            haystack = f'{haystack} {title}'.lower()
        for keyword, category in self.CATEGORY_RULES:
            if keyword in haystack:
                return category
        return self.DEFAULT_CATEGORY

    @staticmethod
    def _custom_field(raw: Dict[str, Any], label: str) -> str:
        """Value of the custom field with this label ('' if absent)."""
        fields = raw.get('custom_fields')
        if not isinstance(fields, dict):
            return ''
        for field in fields.values():
            if isinstance(field, dict) and str(field.get('label', '')).strip().lower() == label.lower():
                return str(field.get('value') or '').strip()
        return ''

    @staticmethod
    def _strip_html(raw: str) -> str:
        if not raw:
            return ''
        text = BeautifulSoup(raw, 'html.parser').get_text(' ')
        return _html.unescape(re.sub(r'\s+', ' ', text)).strip()

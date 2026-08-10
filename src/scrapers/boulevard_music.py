"""
Scraper for Boulevard Music (Culver City).
Source: https://www.boulevardmusic.com/events/

Boulevard Music is a guitar shop and listening room at 4316 Sepulveda Blvd whose
calendar runs on WordPress + The Events Calendar ("Tribe"), so we read the
plugin's REST API rather than parsing the rendered calendar:

    /wp-json/tribe/events/v1/events?start_date=<today>&per_page=50&status=publish

Two quirks of this particular install shape the code:

  * Every event's ``venue`` field is an empty list -- the shop never created a
    Tribe venue record -- so venue name/address/coordinates are fixed constants
    here rather than read from the payload.
  * ``start_date``/``end_date`` come back as naive strings already in
    America/Los_Angeles (``timezone`` confirms it), which is exactly the shape
    create_event() treats as canonical, so no timezone conversion is needed.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run dedup; each
event has its own permalink, so no in-scrape dedup is required.
"""
import html as _html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class BoulevardMusicScraper(BaseScraper):
    """Scraper for Boulevard Music events (Tribe Events REST API)."""

    BASE_URL = 'https://www.boulevardmusic.com'
    API_URL = f'{BASE_URL}/wp-json/tribe/events/v1/events'
    EVENTS_URL = f'{BASE_URL}/events/'

    # Single fixed venue (Culver City, inside the coverage area).
    VENUE_NAME = 'Boulevard Music'
    VENUE_ADDRESS = '4316 Sepulveda Blvd, Culver City, CA 90230'
    VENUE_LAT = 34.0043483
    VENUE_LNG = -118.4092163

    # Safety rail: the shop lists a season at a time, never hundreds of shows.
    MAX_PAGES = 5
    PER_PAGE = 50

    # "$28", "$28.00", "$25 - $30" -> lowest number wins as the advertised price.
    _PRICE_RE = re.compile(r'(\d+(?:\.\d{1,2})?)')

    # Tribe category slug -> site category. Everything here is a concert unless
    # the shop tags it otherwise, so Music is the default rather than trusting
    # the shared auto-classifier on bare performer names.
    _CATEGORY_RULES = (
        ('workshop', 'Education'),
        ('class', 'Education'),
        ('lesson', 'Education'),
        ('comedy', 'Comedy'),
    )

    def __init__(self):
        super().__init__('Boulevard Music')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Boulevard Music...")
        events: List[Event] = []

        for raw in self._fetch_api_events():
            try:
                event = self._parse_event(raw)
            except Exception as e:
                self.log(f"  x error parsing event {raw.get('id')}: {e}")
                continue
            if event:
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
                f'{self.API_URL}?per_page={self.PER_PAGE}&page={page}'
                f'&start_date={today}&status=publish',
                method='GET',
            )
            if not data:
                break

            page_events = data.get('events') or []
            if not page_events:
                break
            collected.extend(page_events)

            total_pages = data.get('total_pages') or 1
            if page >= total_pages:
                break

        self.log(f"Fetched {len(collected)} event(s) from the Tribe API")
        return collected

    def _parse_event(self, raw: Dict[str, Any]) -> Optional[Event]:
        title = self.clean_text(_html.unescape(raw.get('title') or ''))
        if not title:
            return None

        event_date = self._parse_datetime(raw.get('start_date'))
        if not event_date:
            return None
        # The API honours start_date, but an all-day event that began yesterday
        # can still come back; drop anything already over.
        if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            return None

        end_date = self._parse_datetime(raw.get('end_date'))
        if end_date and end_date <= event_date:
            end_date = None

        description = self._strip_html(raw.get('description') or '')
        if not description:
            description = self._strip_html(raw.get('excerpt') or '')

        image = raw.get('image')
        image_url = image.get('url', '') if isinstance(image, dict) else ''

        price, is_free, price_note = self._parse_cost(raw.get('cost'))

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=event_date,
            end_date=end_date,
            url=raw.get('url') or self.EVENTS_URL,
            image_url=image_url,
            category=self._classify(raw, title),
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

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

    def _classify(self, raw: Dict[str, Any], title: str) -> str:
        categories = raw.get('categories') or []
        names = ' '.join(
            str(c.get('name', '')) for c in categories if isinstance(c, dict)
        )
        haystack = f'{names} {title}'.lower()
        for keyword, category in self._CATEGORY_RULES:
            if keyword in haystack:
                return category
        return 'Music'

    @staticmethod
    def _strip_html(raw: str) -> str:
        if not raw:
            return ''
        text = BeautifulSoup(raw, 'html.parser').get_text(' ')
        return _html.unescape(re.sub(r'\s+', ' ', text)).strip()

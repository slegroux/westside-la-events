"""
Scraper for City of Santa Monica events (library programs, Annenberg Community
Beach House, farmers markets, city programs).
Source: https://www.santamonica.gov/events

The old smgov.net/events URL now redirects to a permit page; the city's events
calendar lives at santamonica.gov/events as a paged grid of cards (about nine
per page, soonest first, ~90 pages). Card links look like
``/events/<id>/<yyyymmddHHMM>`` (single-quoted hrefs) and the trailing stamp is
the occurrence's LA-local start, so it is used as the start time; the card text
supplies the end time. Each occurrence has its own URL, so recurring programs
need no fragment.

The grid has no venue. Each program's own page does (schema.org Event with a
Library/Place location), but the site rate-limits automated traffic with an
"interstitial" challenge. So: page the grid first (capped by page count and a
time budget), then enrich a small, capped number of distinct programs from
their detail pages, and stop at the first challenge page. We never try to get
past it; events without a known venue fall back to "Santa Monica".
"""
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event

_STAMP_RE = re.compile(r'/events/([^/]+)/(\d{12})(?:[/?#]|$)')
_TIME_RANGE_RE = re.compile(
    r'(\d{1,2}:\d{2}\s*[AP]M)\s*[-–]\s*(\d{1,2}:\d{2}\s*[AP]M)', re.I
)
_MULTIDAY_END_RE = re.compile(
    r'\bto\s+\w+,\s+(\w{3,9}\s+\d{1,2},\s+\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)', re.I
)
# Government meetings are listed alongside programs; they aren't events to attend.
_MEETING_RE = re.compile(
    r'\b(commission|city council|committee|board meeting|board of|task force|'
    r'public hearing|council meeting)\b',
    re.I,
)


class SantaMonicaScraper(BaseScraper):
    """Scraper for City of Santa Monica events."""

    MAX_PAGES = 12            # ~9 events per page, ~3 weeks ahead
    PAGE_BUDGET_SECONDS = 60  # stop paging after this, whatever the page count
    MAX_DETAILS = 10          # distinct programs enriched from detail pages
    TOTAL_BUDGET_SECONDS = 90

    def __init__(self):
        super().__init__('Santa Monica')
        self.base_url = 'https://www.santamonica.gov'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of City of Santa Monica events...")
        started = time.monotonic()

        items = self._page_through(started)
        if not items:
            return []
        self._enrich(items, started)

        events: List[Event] = []
        now = datetime.now()
        for item in items:
            event = self._build_event(item)
            if event and (event.end_date or event.event_date) >= now:
                events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s) from {len(items)} listed")
        return events

    # -- listing -----------------------------------------------------------

    def _page_through(self, started: float) -> List[dict]:
        items: List[dict] = []
        seen = set()
        for page in range(1, self.MAX_PAGES + 1):
            if time.monotonic() - started > self.PAGE_BUDGET_SECONDS:
                self.log(f"Page budget reached after {page - 1} page(s)")
                break
            url = self.events_url if page == 1 else f'{self.events_url}?pagenum={page}'
            html = self.fetch_page(url)
            if not html:
                self.log(f"Failed to fetch page {page}")
                break
            if self._blocked(html):
                self.log(f"Challenge page on listing page {page}; stopping")
                break
            cards = self._cards(html)
            if not cards:
                break
            for item in cards:
                if item['url'] not in seen:
                    seen.add(item['url'])
                    items.append(item)
        self.log(f"Listed {len(items)} occurrence(s)")
        return items

    @staticmethod
    def _blocked(html: str) -> bool:
        return 'Pardon Our Interruption' in html

    def _cards(self, html: str) -> List[dict]:
        cards = []
        for link in self.parse_html(html).select('a.card[href^="/events/"]'):
            try:
                item = self._parse_card(link)
            except Exception as e:
                self.log(f"Error parsing card: {e}")
                continue
            if item:
                cards.append(item)
        return cards

    def _parse_card(self, link) -> Optional[dict]:
        m = _STAMP_RE.search(link['href'])
        title_el = link.select_one('.eventTitle')
        if not m or not title_el:
            return None
        title = self.clean_text(title_el.get_text())
        text = self.clean_text(link.select_one('.description').get_text(' ')
                               if link.select_one('.description') else '')
        if 'cancel' in text.lower():
            self.log(f"  - skipping cancelled: {title}")
            return None
        if _MEETING_RE.search(title):
            return None
        try:
            start = datetime.strptime(m.group(2), '%Y%m%d%H%M')
        except ValueError:
            return None

        img = link.select_one('img[src]')
        return {
            'id': m.group(1),
            'title': title,
            'url': self.normalize_url(link['href'], self.base_url),
            'start': start,
            'end': self._end(start, text),
            'image': img['src'] if img else '',
            'venue': '',
            'address': '',
            'description': '',
            'lat': None,
            'lng': None,
        }

    @staticmethod
    def _end(start: datetime, text: str) -> Optional[datetime]:
        """End time when the card states one ("9:00 AM - 12:30 PM", "to ... 9:00 PM")."""
        multi = _MULTIDAY_END_RE.search(text)
        if multi:
            try:
                end = datetime.strptime(' '.join(multi.groups()).upper(), '%b %d, %Y %I:%M %p')
            except ValueError:
                return None
            return end if end > start else None
        rng = _TIME_RANGE_RE.search(text)
        if rng:
            try:
                t = datetime.strptime(rng.group(2).upper().replace('  ', ' '), '%I:%M %p')
            except ValueError:
                return None
            end = start.replace(hour=t.hour, minute=t.minute)
            return end if end > start else None
        return None

    # -- detail enrichment -------------------------------------------------

    def _enrich(self, items: List[dict], started: float) -> None:
        """Fill venue/description from each distinct program's page (capped)."""
        by_id: Dict[str, List[dict]] = {}
        for item in items:
            by_id.setdefault(item['id'], []).append(item)

        now = datetime.now()
        # Soonest-first, so the programs people will see first get venues.
        pending = sorted(
            (group for group in by_id.values() if group[0]['start'] >= now or group[0]['end']),
            key=lambda g: g[0]['start'],
        )[:self.MAX_DETAILS]

        for group in pending:
            if time.monotonic() - started > self.TOTAL_BUDGET_SECONDS:
                self.log("Time budget reached; skipping remaining detail pages")
                return
            html = self.fetch_page(group[0]['url'], retry=1)
            if not html:
                continue
            if self._blocked(html):
                self.log("Challenge page on a detail page; not fetching more details")
                return
            detail = self._detail(html)
            for item in group:
                for key, value in detail.items():
                    if value:
                        item[key] = value

    def _detail(self, html: str) -> dict:
        """venue/address/coords/description from the page's Event JSON-LD, or {}."""
        for raw in re.findall(
            r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S
        ):
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(data, dict) or data.get('@type') != 'Event':
                continue
            location = data.get('location') if isinstance(data.get('location'), dict) else {}
            addr = location.get('address') if isinstance(location.get('address'), dict) else {}
            street = addr.get('streetAddress', '')
            geo = location.get('geo') if isinstance(location.get('geo'), dict) else {}
            lat = geo.get('Latitude', geo.get('latitude'))
            lng = geo.get('Longitude', geo.get('longitude'))
            return {
                'venue': self.clean_text(location.get('name', '')),
                'address': ', '.join(p for p in (
                    street, addr.get('addressLocality', ''),
                    f"{addr.get('addressRegion', '')} {addr.get('postalCode', '')}".strip(),
                ) if p) if street else '',
                'lat': lat if isinstance(lat, (int, float)) else None,
                'lng': lng if isinstance(lng, (int, float)) else None,
                'description': self.clean_text(
                    self.parse_html(data.get('description') or '').get_text(' ')
                ),
            }
        return {}

    # -- event -------------------------------------------------------------

    def _build_event(self, item: dict) -> Optional[Event]:
        venue = item['venue'] or 'City of Santa Monica'
        address = item['address'] or 'Santa Monica, CA'
        return self.create_event(
            title=item['title'],
            description=item['description'],
            venue_name=venue,
            address=address,
            event_date=item['start'],
            end_date=item['end'],
            url=item['url'],
            image_url=item['image'],
            latitude=item['lat'],
            longitude=item['lng'],
        )

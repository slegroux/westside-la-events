"""
Scrapers for repertory cinemas that run on Filmbot (Nightjar's cinema CMS):
Vidiots (Eagle Rock) and Brain Dead Studios (Fairfax).

Both sites embed their schedule as schema.org JSON-LD: one @graph holding a
`Movie` per title and a `ScreeningEvent` per showtime (start/end with a UTC
offset, ticket offers with price and availability, `workPresented` pointing at
the Movie). FilmbotScraper reads that graph; each theatre is a subclass that
supplies its venue and the pages to read.

Events are one per film per day, like the Nuart scraper, so the several
showtimes of a double bill share a card. Each ticket sits behind a
per-showtime purchase URL, so the card links to the film page with a
`#YYYY-MM-DD` fragment to keep consecutive days from merging in
Database.insert_event.
"""
import html
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event

_LD_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S
)
# Screening names look like "Lady - 11/21/26 @ 7:15 pm"; only used when the
# Movie node is missing.
_NAME_SUFFIX_RE = re.compile(r'\s+-\s+\d{1,2}/\d{1,2}/\d{2,4}\s+@\s+.*$')
_LA = ZoneInfo('America/Los_Angeles')


class FilmbotScraper(BaseScraper):
    """Base parser for a Filmbot-powered cinema. Subclasses set the constants."""

    SOURCE_NAME = ''
    BASE_URL = ''
    # Pages carrying the schedule JSON-LD, relative to BASE_URL.
    PAGES = ('/coming-soon/',)
    VENUE_NAME = ''
    VENUE_ADDRESS = ''
    LATITUDE = 0.0
    LONGITUDE = 0.0

    def __init__(self):
        super().__init__(self.SOURCE_NAME)
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        movies: Dict[str, dict] = {}
        screenings: Dict[str, dict] = {}  # keyed by purchase URL: pages can overlap
        for path in self.PAGES:
            page_html = self.fetch_page(f"{self.BASE_URL}{path}")
            if not page_html:
                self.log(f"Failed to fetch {path}")
                continue
            for node in self._graph_nodes(page_html):
                kind = node.get('@type')
                if kind == 'Movie' and node.get('@id'):
                    movies[node['@id']] = node
                elif kind == 'ScreeningEvent':
                    screenings.setdefault(node.get('url') or node.get('name', ''), node)

        if not screenings:
            self.log("No screenings found")
            return []

        events: List[Event] = []
        for movie_id, day, shows in self._group_by_film_day(screenings.values()):
            try:
                event = self._build_event(movies.get(movie_id), shows, day)
            except Exception as e:
                self.log(f"Error parsing screening group {movie_id} {day}: {e}")
                continue
            if event:
                events.append(event)

        self.log(f"Successfully scraped {len(events)} events")
        return events

    @staticmethod
    def _graph_nodes(page_html: str) -> List[dict]:
        """Every JSON-LD node on the page, flattening @graph (bad blocks skipped)."""
        nodes: List[dict] = []
        for raw in _LD_RE.findall(page_html):
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            for obj in data if isinstance(data, list) else [data]:
                if not isinstance(obj, dict):
                    continue
                graph = obj.get('@graph')
                nodes.extend(n for n in (graph if isinstance(graph, list) else [obj])
                             if isinstance(n, dict))
        return nodes

    def _group_by_film_day(self, screenings):
        """Yield (movie id, date, [(start, screening)]) for upcoming showtimes."""
        now = datetime.now()
        groups: Dict[tuple, list] = {}
        for show in screenings:
            try:
                start = datetime.fromisoformat(show['startDate'])
            except (KeyError, ValueError, TypeError):
                self.log(f"Skipping screening without a usable start: {show.get('name')}")
                continue
            if start.tzinfo is not None:
                start = start.astimezone(_LA).replace(tzinfo=None)
            if start < now:
                continue
            movie_id = (show.get('workPresented') or {}).get('@id') or show.get('name', '')
            groups.setdefault((movie_id, start.date()), []).append((start, show))
        for (movie_id, day), shows in groups.items():
            yield movie_id, day, sorted(shows, key=lambda s: s[0])

    @staticmethod
    def _is_sold_out(show: dict) -> bool:
        offers = show.get('offers') or []
        return bool(offers) and all(
            str(o.get('availability', '')).endswith('SoldOut') for o in offers
        )

    @staticmethod
    def _first_price(show: dict) -> Optional[float]:
        """The headline ticket price: the first offer is the standard admission,
        ahead of the wheelchair/military/senior tiers that follow it."""
        for offer in show.get('offers') or []:
            try:
                return float(offer['price'])
            except (KeyError, ValueError, TypeError):
                continue
        return None

    def _build_event(self, movie: Optional[dict], shows: list, day) -> Optional[Event]:
        first_show = shows[0][1]
        movie = movie or {}
        title = self.clean_text(html.unescape(
            movie.get('name') or _NAME_SUFFIX_RE.sub('', first_show.get('name', ''))
        ))
        if not title:
            return None

        parts = []
        duration = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?', movie.get('duration') or '')
        if duration and (duration.group(1) or duration.group(2)):
            parts.append(f"{int(duration.group(1) or 0) * 60 + int(duration.group(2) or 0)} min")
        directors = [d.get('name') for d in movie.get('director') or [] if d.get('name')]
        if directors:
            parts.append(f"A film by {', '.join(directors)}")
        synopsis = self.clean_text(
            BeautifulSoup(html.unescape(movie.get('description') or ''), 'html.parser').get_text(' ')
        )
        if len(synopsis) > 400:
            synopsis = synopsis[:399].rsplit(' ', 1)[0] + '…'
        if synopsis:
            parts.append(synopsis)
        clock = ', '.join(
            f"{start.hour % 12 or 12}:{start.minute:02d}{'am' if start.hour < 12 else 'pm'}"
            + (' (sold out)' if self._is_sold_out(show) else '')
            for start, show in shows
        )
        parts.append(f"Showtimes - {clock}")
        description = '. '.join(p.rstrip('.') for p in parts) + '.'

        if all(self._is_sold_out(show) for _, show in shows):
            price, price_note, is_free = None, 'Sold out', False
        else:
            prices = [p for _, show in shows if not self._is_sold_out(show)
                      for p in [self._first_price(show)] if p is not None]
            price = min(prices) if prices else None
            is_free = price == 0
            price_note = ''

        # One film page serves every day, so the fragment keeps days distinct.
        film_url = movie.get('url') or first_show.get('url') or self.BASE_URL
        image = movie.get('image') or first_show.get('image') or ''
        if isinstance(image, list):
            image = image[0] if image else ''

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            latitude=self.LATITUDE,
            longitude=self.LONGITUDE,
            event_date=shows[0][0],
            url=f"{film_url}#{day.isoformat()}",
            image_url=image,
            category="Film",
            price=price,
            is_free=is_free,
            price_note=price_note,
        )


class VidiotsScraper(FilmbotScraper):
    """Vidiots, the Eagle Rock repertory cinema and video store.

    The homepage JSON-LD is stale, so only /coming-soon/ is read. Eagle Rock is
    outside the Westside box, hence the beyond region.
    """

    REGION = 'beyond'
    SOURCE_NAME = 'Vidiots'
    BASE_URL = 'https://vidiotsfoundation.org'
    VENUE_NAME = 'Vidiots'
    VENUE_ADDRESS = '4884 Eagle Rock Blvd, Los Angeles, CA 90041'
    LATITUDE = 34.1393
    LONGITUDE = -118.2118


class BrainDeadStudiosScraper(FilmbotScraper):
    """Brain Dead Studios on Fairfax.

    611 N Fairfax is inside the Westside coverage box (is_in_coverage_area is
    True), so this keeps the default region. /coming-soon/ starts tomorrow;
    the homepage lists today's showings, so both are read.
    """

    SOURCE_NAME = 'Brain Dead Studios'
    BASE_URL = 'https://studios.wearebraindead.com'
    PAGES = ('/coming-soon/', '/')
    VENUE_NAME = 'Brain Dead Studios'
    VENUE_ADDRESS = '611 N Fairfax Ave, Los Angeles, CA 90036'
    LATITUDE = 34.0830
    LONGITUDE = -118.3612

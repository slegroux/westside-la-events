"""
Scraper for The Wallis (Wallis Annenberg Center for the Performing Arts).
Source: https://www.thewallis.org/season2627

The season page is a server-rendered grid of show cards: category, title, a
date (or a "Nov 6, 2026 - Nov 22, 2026" range) and a link to the show page.
Each show page carries a schema.org event in JSON-LD whose ``offers`` list one
entry per performance, stamped with the performance's local start time
(``availabilityStarts``). That makes per-performance dates available, so a run
becomes one event per performance day (starting at that day's first show, with
the other showtimes in the description), rather than one event for the whole
run.

A show with no performance list falls back to the card's own date, following
``broad_stage.py``: the range start is the event date and the range end the end
date. Cards with no date at all (series, open calls) are skipped.

Like Broad Stage, the season slug rolls over every year (/season2627 ->
/season2728), so the live nav link is read from the home page.
"""
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class TheWallisScraper(BaseScraper):
    """Scraper for The Wallis season calendar."""

    BASE_URL = 'https://www.thewallis.org'
    DEFAULT_SEASON_URL = 'https://www.thewallis.org/season2627'

    VENUE_NAME = 'The Wallis'
    VENUE_ADDRESS = '9390 N Santa Monica Blvd, Beverly Hills, CA 90210'
    VENUE_LAT = 34.0722705
    VENUE_LNG = -118.4012411

    # Show pages fetched per scrape: the season has ~40, so this is a ceiling
    # that keeps a layout change from turning into hundreds of requests.
    MAX_SHOW_PAGES = 60

    _CATEGORIES = {
        'THEATER': 'Theater',
        'FAMILY': 'Family',
        'MUSIC': 'Music',
        'DANCE': 'Theater',
        'FILM': 'Film',
        'COMEDY': 'Comedy',
    }

    _DATE = r'[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}'
    _CARD_DATES = re.compile(_DATE)
    _LD_JSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)

    def __init__(self):
        super().__init__('The Wallis')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of The Wallis...")
        html = self.fetch_page(self._resolve_season_url())
        if not html:
            self.log("Failed to fetch the season page")
            return []

        cards = self._parse_cards(html)
        self.log(f"Found {len(cards)} dated show card(s)")
        cards = cards[:self.MAX_SHOW_PAGES]
        self.prefetch_pages([c['url'] for c in cards])

        events: List[Event] = []
        now = datetime.now()
        for card in cards:
            try:
                events.extend(self._events_for_show(card, now))
            except Exception as e:
                self.log(f"Error parsing show {card['url']}: {e}")
        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _resolve_season_url(self) -> str:
        """Find the current /seasonNNNN landing page from the home page nav."""
        try:
            home = self.fetch_page(self.BASE_URL + '/') or ''
            slugs = re.findall(r'/(season\d{4})\b', home)
            if slugs:
                return f"{self.BASE_URL}/{max(slugs)}"
        except Exception as e:
            self.log(f"Season URL resolution failed, using default: {e}")
        return self.DEFAULT_SEASON_URL

    # -- season grid ---------------------------------------------------------

    def _parse_cards(self, html: str) -> List[dict]:
        soup = self.parse_html(html)
        cards = []
        seen = set()
        for item in soup.select('div.show-card'):
            link = item.select_one('a.read-more') or item.find('a', href=True)
            heading = item.find('h3')
            if not link or not heading:
                continue
            url = self.normalize_url(link['href'], self.BASE_URL)
            if url in seen:
                continue
            seen.add(url)

            span = heading.find('span')
            dates_text = self.clean_text(span.get_text(' ')) if span else ''
            if span:
                span.extract()
            title = self.clean_text(heading.get_text(' '))
            dates = self._CARD_DATES.findall(dates_text)
            if not title or not dates:
                self.log(f"Skipping undated show: {title or url}")
                continue
            try:
                start = date_parser.parse(dates[0])
                end = date_parser.parse(dates[-1])
            except (ValueError, OverflowError):
                self.log(f"Unparseable dates for {title}: {dates_text}")
                continue

            tags = [self.clean_text(s.get_text()).upper() for s in item.select('.show-cat span')]
            img = item.find('img')
            cards.append({
                'title': title,
                'url': url,
                'start': start,
                'end': end,
                'category': self._category(tags),
                'image': (img.get('data-src') or img.get('src') or '') if img else '',
            })
        return cards

    def _category(self, tags: List[str]) -> str:
        mapped = [self._CATEGORIES[t] for t in tags if t in self._CATEGORIES]
        if 'Family' in mapped:
            return 'Family'
        return mapped[0] if mapped else ''

    # -- show pages ----------------------------------------------------------

    def _events_for_show(self, card: dict, now: datetime) -> List[Event]:
        page = self.fetch_page(card['url'])
        description, performances = self._read_show_page(page) if page else ('', {})

        today = now.date()
        if performances:
            events = []
            for day, shows in sorted(performances.items()):
                # Drop showtimes that have already started, not just past days.
                upcoming = [s for s in shows if s[0] >= now]
                if upcoming:
                    event = self._performance_day_event(card, description, day, upcoming)
                    if event:
                        events.append(event)
            return events

        # No performance list: use the card's own range, as Broad Stage does.
        if card['end'].date() < today or card['start'].date() < today:
            self.log(f"No performance times for {card['title']}; skipping")
            return []
        event = self.create_event(
            title=card['title'],
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=card['start'],
            end_date=card['end'] if card['end'] != card['start'] else None,
            url=card['url'],
            image_url=card['image'],
            category=card['category'],
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )
        return [event] if event else []

    def _read_show_page(self, html: str):
        """Return (description, {date: [(start datetime, sold_out), ...]})."""
        soup = self.parse_html(html)
        meta = soup.find('meta', attrs={'name': 'description'})
        description = self.clean_text(meta.get('content', ''))[:600] if meta else ''

        performances: Dict = {}
        for block in self._LD_JSON.findall(html):
            try:
                ld = json.loads(block)
            except json.JSONDecodeError:
                continue
            if not isinstance(ld, dict) or 'Event' not in str(ld.get('@type', '')):
                continue
            for offer in ld.get('offers') or []:
                try:
                    when = datetime.strptime(offer['availabilityStarts'].strip(), '%Y-%m-%d %H:%M:%S')
                except (KeyError, ValueError, AttributeError):
                    continue
                sold_out = str(offer.get('availability', '')).endswith('SoldOut')
                performances.setdefault(when.date(), []).append((when, sold_out))
        return description, performances

    def _performance_day_event(self, card: dict, description: str, day, shows) -> Optional[Event]:
        shows = sorted(set(shows))
        first = shows[0][0]
        times = ', '.join(w.strftime('%-I:%M %p') for w, _ in shows)
        note = f"Showtimes: {times}."
        sold_out = all(s for _, s in shows)
        return self.create_event(
            title=card['title'],
            description=f"{description} {note}".strip(),
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=first,
            end_date=None,
            # One URL per performance day, or consecutive days of a run would
            # be merged by the database's URL dedup.
            url=f"{card['url']}#{day.isoformat()}",
            image_url=card['image'],
            category=card['category'],
            price=None,
            price_note='Sold out' if sold_out else '',
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

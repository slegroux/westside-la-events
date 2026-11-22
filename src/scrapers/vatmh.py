"""
Scraper for Villa Aurora & Thomas Mann House (Pacific Palisades).
Source: https://www.vatmh.org/en/program/current.html

The two German-exile residences run one joint program from a Contao CMS site:
talks, screenings, readings and open houses. The program also lists events in
Germany (Cottbus, Berlin galleries) and the odd partner venue, so only events
whose location is one of the two houses or carries a California street address
are kept; anything else is dropped. Invitation-only events are dropped too.

The listing's <time datetime> attributes carry a Berlin offset that doesn't
match the displayed local time, so the visible LA-local date/time text is
parsed instead. A card with a date but no time becomes a midnight (date-only)
event; a card with no parseable date is skipped.
"""
import re
from datetime import datetime
from typing import List, Optional, Tuple

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event
from src.utils.categories import classify_event

_TIME_RE = re.compile(r'(\d{1,2}(?::\d{2})?\s*[ap]m)', re.I)


class VATMHScraper(BaseScraper):
    """Scraper for the Villa Aurora & Thomas Mann House public program."""

    EVENTS_URL = 'https://www.vatmh.org/en/program/current.html'

    # Lowercase location text -> (venue name, street address, lat, lng). Fixed
    # coordinates (from Nominatim): the Thomas Mann House address doesn't geocode
    # when written with its Pacific Palisades locality.
    HOUSES = {
        'villa aurora': (
            'Villa Aurora', '520 Paseo Miramar, Pacific Palisades, CA 90272',
            34.0462449, -118.5559808,
        ),
        'thomas mann house': (
            'Thomas Mann House', '1550 San Remo Dr, Pacific Palisades, CA 90272',
            34.0589502, -118.4993874,
        ),
    }

    def __init__(self):
        super().__init__('Villa Aurora & Thomas Mann House')
        self.base_url = 'https://www.vatmh.org'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Villa Aurora & Thomas Mann House...")
        events: List[Event] = []

        html = self.fetch_page(self.EVENTS_URL)
        if not html:
            self.log("Failed to fetch program page")
            return events

        cards = self.parse_html(html).select('div.kalenderliste div.event')
        self.log(f"Found {len(cards)} program entries")

        parsed = []
        for card in cards:
            try:
                item = self._parse_card(card)
            except Exception as e:
                self.log(f"  ✗ error parsing card: {e}")
                continue
            if item:
                parsed.append(item)

        # A series can reuse one page for several dates: keep each URL unique.
        url_counts = {}
        for item in parsed:
            url_counts[item['url']] = url_counts.get(item['url'], 0) + 1

        now = datetime.now()
        upcoming = [i for i in parsed if (i['end'] or i['start']) >= now]
        self.prefetch_pages([item['url'] for item in upcoming])

        for item in upcoming:
            if self._invitation_only(item['url']):
                self.log(f"  - skipping invitation-only event: {item['title']}")
                continue
            url = item['url']
            if url_counts[url] > 1:
                url = f"{url}#{item['start'].strftime('%Y-%m-%d')}"
            event = self.create_event(
                title=item['title'],
                description=item['description'],
                venue_name=item['venue'],
                address=item['address'],
                latitude=item['lat'],
                longitude=item['lng'],
                event_date=item['start'],
                end_date=item['end'],
                url=url,
                image_url=item['image'],
                category=self._category(item['title']),
            )
            if event:
                events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _parse_card(self, card) -> Optional[dict]:
        link = card.select_one('h3 a[href]')
        date_el = card.select_one('span.date')
        if not link or not date_el:
            return None
        title = self.clean_text(link.get_text())

        venue, address, lat, lng = self._location(card)
        if not venue:
            self.log(f"  - skipping event outside LA: {title}")
            return None

        start, end = self._dates(card, date_el)
        if not start:
            self.log(f"  - skipping undated event: {title}")
            return None

        url = self.normalize_url(link['href'], self.base_url)
        text = card.select_one('div.event-text')
        for heading in text.select('h3') if text else []:
            heading.decompose()  # the title is already captured
        image = card.select_one('div.event-image img[src]')
        return {
            'title': title,
            'url': url,
            'description': self.clean_text(text.get_text(' ')) if text else '',
            'venue': venue,
            'address': address,
            'lat': lat,
            'lng': lng,
            'start': start,
            'end': end,
            'image': self.normalize_url(image['src'], self.base_url) if image else '',
        }

    def _location(self, card) -> Tuple[str, str, Optional[float], Optional[float]]:
        """(venue, address, lat, lng) for an LA location, else empty strings."""
        el = card.select_one('div.location')
        text = self.clean_text(el.get_text(' ')) if el else ''
        text = re.sub(r'^Location:\s*', '', text)
        for key, (venue, address, lat, lng) in self.HOUSES.items():
            if key in text.lower():
                m = re.search(r'\(([^)]*,\s*CA\b[^)]*)\)', text)
                return venue, m.group(1).strip() if m else address, lat, lng
        m = re.match(r'(.+?)\s*\((.*,\s*CA\b.*)\)\s*$', text)
        if m:
            return m.group(1).strip(), m.group(2).strip(), None, None
        return '', '', None, None

    def _dates(self, card, date_el) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Start/end from the visible LA-local text; end only when it's stated."""
        day = self._parse_date(date_el.get_text())
        if not day:
            return None, None

        span = card.select_one('div.date-vonbis')
        if span:
            parts = [p for p in re.split(r'\s*[–-]\s*', span.get_text()) if p.strip(', ')]
            last = self._parse_date(parts[-1]) if len(parts) > 1 else None
            if last and last.date() > day.date():
                return day, last.replace(hour=23, minute=59)

        time_el = card.select_one('div.time')
        times = _TIME_RE.findall(time_el.get_text()) if time_el else []
        if not times:
            return day, None
        start = self._with_time(day, times[0])
        end = self._with_time(day, times[1]) if len(times) > 1 else None
        if end and end <= start:
            end = None
        return start, end

    @staticmethod
    def _parse_date(text: str) -> Optional[datetime]:
        text = re.sub(r'\s+', ' ', text).strip(' ,')
        try:
            return date_parser.parse(text, default=datetime(2000, 1, 1))
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _with_time(day: datetime, text: str) -> datetime:
        t = date_parser.parse(text)
        return day.replace(hour=t.hour, minute=t.minute)

    @staticmethod
    def _category(title: str) -> str:
        """Title keywords (screening, artists...), else Education: the rest are talks.

        The description is left out: it mentions films, families and exiles in
        ways that mislead the keyword classifier.
        """
        category = classify_event(title, '', '')
        return 'Education' if category == 'Other' else category

    def _invitation_only(self, url: str) -> bool:
        """True when the event's own page says it is by invitation only."""
        html = self.fetch_page(url, retry=1)
        return bool(html) and 'invitation only' in html.lower()

"""
Scraper for The Corner Door (Culver City bar).
Source: https://www.the-corner-door.com/upcoming-events

The upcoming-events page is a hand-authored Squarespace page: events are plain
content blocks inside an ``<article class="sections">``, grouped under month
headings. Each event is an ``<h4>`` title followed by paragraphs:

    <h3> SEPT                              # month heading (ignored — dates carry the month)
    <h4> MungoSound                        # event title
    <p>  Thursday 9.5  8pm - Close         # weekday + M.D[.YY] + time
    <p>  Vinyl DJs all night!              # description
    <p>  Special Guest DJ: Cruel Mistress
    ...
    <p>  Tickets: https://www.eventbrite.com/e/...   # optional ticket/RSVP link

Dates are written ``month.day`` and usually omit the year. We recover the year
by anchoring on the stated weekday: for a given month/day, only one year in a
small window lands on that weekday, which both fixes the year and validates the
date. Events that resolve to the past are dropped, so this scraper yields
nothing while the venue's page is stale and starts producing events as soon as
fresh dates are posted.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run/cross-source
dedup. Because these blocks have no stable per-event URL, we additionally dedup
within a scrape by (title, date).
"""
import calendar
import re
from datetime import datetime
from typing import List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


class CornerDoorScraper(BaseScraper):
    """Scraper for The Corner Door upcoming events."""

    BASE_URL = 'https://www.the-corner-door.com'
    LISTING_URL = 'https://www.the-corner-door.com/upcoming-events'

    # Single fixed venue (Culver City, inside the coverage area).
    VENUE_NAME = 'The Corner Door'
    VENUE_ADDRESS = '12477 Washington Blvd, Culver City, CA 90066'
    VENUE_LAT = 33.9969765
    VENUE_LNG = -118.4306276

    # "Thursday 9.5" or "Friday 8.16.24" — weekday, month.day, optional year.
    _DATE_RE = re.compile(
        r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+'
        r'(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?',
        re.I,
    )
    # First clock time in the date line, e.g. "8pm", "8:30pm", "7pm - 9pm".
    _TIME_RE = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([ap]m)', re.I)

    # This is a late-night DJ/vinyl bar; map the few non-DJ formats explicitly
    # and default the rest to Nightlife (the shared auto-classifier misreads
    # names like "MungoSound").
    _CATEGORY_RULES = (
        ('comedy', 'Comedy'),
        ('trivia', 'Community'),
    )

    def __init__(self):
        super().__init__('The Corner Door')

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of The Corner Door...")
        events: List[Event] = []

        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch The Corner Door events page")
            return events

        soup = self.parse_html(html)
        blocks = self._event_blocks(soup)
        self.log(f"Found {len(blocks)} event block(s)")

        seen = set()
        now = datetime.now()
        for title, lines, link in blocks:
            try:
                event = self._parse_block(title, lines, link)
            except Exception as e:
                self.log(f"  ✗ error parsing '{title}': {e}")
                continue
            if not event:
                continue
            if event.event_date and event.event_date < now:
                continue

            key = (event.title.lower(), event.event_date)
            if key in seen:
                continue
            seen.add(key)

            events.append(event)
            self.log(f"  ✓ {event.event_date:%Y-%m-%d} {event.title}")

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _event_blocks(self, soup) -> List[Tuple[str, List[str], str]]:
        """Group the flat heading/paragraph sequence into (title, lines, link).

        Each ``<h4>`` starts a new event; the paragraphs that follow (until the
        next heading) are its lines, and the first ticket/RSVP link found among
        them is captured as the event URL.
        """
        container = soup.find('article', class_='sections') or soup.body
        if not container:
            return []

        blocks: List[Tuple[str, List[str], str]] = []
        current: Optional[Tuple[str, List[str], List[str]]] = None
        for el in container.find_all(['h3', 'h4', 'p']):
            if el.name in ('h3', 'h4'):
                if el.name == 'h4':
                    if current:
                        blocks.append((current[0], current[1], current[2][0] if current[2] else ''))
                    title = el.get_text(' ', strip=True)
                    current = (title, [], []) if title else None
                else:
                    # A month heading closes the current event group.
                    if current:
                        blocks.append((current[0], current[1], current[2][0] if current[2] else ''))
                    current = None
                continue

            if current is None:
                continue
            text = el.get_text(' ', strip=True)
            if text:
                current[1].append(text)
            for a in el.find_all('a', href=True):
                href = a['href'].strip()
                if href.startswith('http'):
                    current[2].append(href)

        if current:
            blocks.append((current[0], current[1], current[2][0] if current[2] else ''))
        return blocks

    def _parse_block(self, title: str, lines: List[str], link: str) -> Optional[Event]:
        title = self.clean_text(title)
        if not title or not lines:
            return None

        # The date/time line is whichever line contains a weekday+date.
        date_line = next((ln for ln in lines if self._DATE_RE.search(ln)), None)
        if not date_line:
            return None
        event_date = self._parse_datetime(date_line)
        if not event_date:
            return None

        # Description: the remaining lines, minus the date line and any bare
        # "Tickets:" label / raw URL lines.
        desc_lines = [
            ln for ln in lines
            if ln is not date_line
            and not ln.lower().startswith('tickets')
            and not ln.startswith('http')
        ]
        description = self.clean_text(' '.join(desc_lines))

        # Prefer an explicit ticket/RSVP link; otherwise link back to the page.
        # A raw URL sometimes appears as its own text line rather than an <a>.
        if not link:
            url_line = next((ln for ln in lines if ln.startswith('http')), '')
            link = url_line.split()[0] if url_line else ''
        url = link or self.LISTING_URL

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=event_date,
            url=url,
            category=self._classify(f"{title} {description}"),
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

    def _parse_datetime(self, text: str) -> Optional[datetime]:
        m = self._DATE_RE.search(text)
        if not m:
            return None
        weekday, month_s, day_s, year_s = m.groups()
        month, day = int(month_s), int(day_s)

        year = self._resolve_year(weekday, month, day, year_s)
        if year is None:
            return None

        hour, minute = 0, 0
        tm = self._TIME_RE.search(text)
        if tm:
            hour = int(tm.group(1)) % 12
            minute = int(tm.group(2) or 0)
            if tm.group(3).lower() == 'pm':
                hour += 12

        try:
            return datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    @staticmethod
    def _resolve_year(weekday: str, month: int, day: int, year_s: Optional[str]) -> Optional[int]:
        """Determine the event's year.

        With an explicit year in the source, use it. Otherwise pick the year in
        a rolling window whose date lands on the stated weekday, preferring the
        soonest one that is today-or-later (falling back to the most recent past
        match, which the caller then filters out).
        """
        if year_s:
            y = int(year_s)
            return 2000 + y if y < 100 else y

        today = datetime.now().date()
        wd_target = weekday.capitalize()
        candidates = []
        for y in range(today.year - 1, today.year + 3):
            try:
                d = datetime(y, month, day).date()
            except ValueError:
                continue
            if calendar.day_name[d.weekday()] == wd_target:
                candidates.append(d)
        if not candidates:
            return None
        upcoming = [d for d in candidates if d >= today]
        return (min(upcoming) if upcoming else max(candidates)).year

    def _classify(self, text: str) -> str:
        low = text.lower()
        for keyword, category in self._CATEGORY_RULES:
            if keyword in low:
                return category
        return 'Nightlife'

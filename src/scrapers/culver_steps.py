"""
Scraper for The Culver Steps (Culver City).
Source: https://theculversteps.com/happenings/

The Culver Steps is the public plaza at 9300 Culver Blvd; its programming is
free and seasonal (sunset yoga, kids' play mornings, summer concerts). The
"Happenings" page is a hand-authored WPBakery grid rather than a calendar
plugin, so there is no API and no machine-readable date anywhere:

    <div class="col span_4 element events">
        <h4>PLAY at the Steps</h4>
        <p>Wednesdays, July 8 - August 26 at 10:00am</p>   # free text, no year
        <a href="/directory/play-at-the-steps-2/">          # detail page
        <img src=".../PlayAtTheSteps-600x403.png">

Two consequences drive the design:

  * **Years are inferred from the weekday.** The source writes "Wednesdays,
    July 8 - August 26" with no year. For a given month/day only one year in a
    small window lands on the stated weekday, which both recovers the year and
    validates the parse -- the same trick the Corner Door scraper uses.

  * **Only bounded series are emitted.** Most items are weekly series, which we
    expand into one Event per occurrence. An item whose text gives a weekday but
    no end date (e.g. a bare "Tuesdays at 6:30pm") is skipped rather than
    projected forward indefinitely: this page goes stale between seasons, and
    inventing occurrences for a series that has quietly ended is worse than
    listing nothing. Detail pages usually restate the range in prose ("every
    Tuesday from June 2nd to August 25th"), so they are fetched to recover a
    range the card text omitted.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run dedup.
Occurrences of one series share a detail URL, so each carries a #YYYY-MM-DD
fragment to stay individually addressable.
"""
import calendar
import re
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


_MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
}

_WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}

_WEEKDAY_RE = r'(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day'
_MONTH_RE = (
    r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|'
    r'Aug(?:ust)?|Sep(?:t)?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
)
_DAY_RE = r'(\d{1,2})(?:st|nd|rd|th)?'


class CulverStepsScraper(BaseScraper):
    """Scraper for The Culver Steps happenings."""

    BASE_URL = 'https://theculversteps.com'
    LISTING_URL = 'https://theculversteps.com/happenings/'

    # Single fixed venue (Culver City, inside the coverage area).
    VENUE_NAME = 'The Culver Steps'
    VENUE_ADDRESS = '9300 Culver Blvd, Culver City, CA 90232'
    VENUE_LAT = 34.0244516
    VENUE_LNG = -118.3933641

    # Safety rail on series expansion: a season of weekly events, no more.
    MAX_OCCURRENCES = 30

    # "Wednesdays, July 8 - August 26" / "every Tuesday* from June 2nd to August 25th"
    _RANGE_RE = re.compile(
        _WEEKDAY_RE + r's?\b[^.]{0,40}?\b' + _MONTH_RE + r'\s+' + _DAY_RE +
        r'\s*(?:-|–|—|to|through)\s*(?:' + _MONTH_RE + r'\s+)?' + _DAY_RE,
        re.I,
    )
    # "Tuesday, August 4th" -- a one-off with an explicit weekday.
    _SINGLE_RE = re.compile(
        _WEEKDAY_RE + r',?\s+' + _MONTH_RE + r'\s+' + _DAY_RE,
        re.I,
    )
    # "5-8pm" / "7 - 9 pm" -- the leading hour inherits the trailing meridiem.
    _TIME_RANGE_RE = re.compile(
        r'\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*(?:-|–|—|to)\s*'
        r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?'
        r'|\b(\d{1,2})(?::(\d{2}))?\s*(?:-|–|—|to)\s*'
        r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?',
        re.I,
    )
    # "at 6:30pm" / "7pm"
    _TIME_RE = re.compile(r'\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?', re.I)

    # Matched as whole words and in order: the specific formats win before the
    # generic ones. "play" in particular must not fire on "display"/"players",
    # which is why these are word-boundary matches rather than substrings.
    _CATEGORY_RULES = (
        ('yoga', 'Wellness'),
        ('fitness', 'Wellness'),
        ('meditation', 'Wellness'),
        ('concert', 'Music'),
        ('concerts', 'Music'),
        ('music', 'Music'),
        ('movie', 'Film'),
        ('movies', 'Film'),
        ('film', 'Film'),
        ('screening', 'Film'),
        ('play', 'Family'),
        ('kids', 'Family'),
        ('family', 'Family'),
    )

    def __init__(self):
        super().__init__('The Culver Steps')
        self.base_url = self.BASE_URL
        # Detail pages 403 without a browser-shaped referer/language pair.
        self.session.headers.update({
            'Referer': self.LISTING_URL,
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of The Culver Steps...")
        events: List[Event] = []

        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch The Culver Steps happenings page")
            return events

        cards = self._parse_cards(self.parse_html(html))
        self.log(f"Found {len(cards)} happening card(s)")

        detail_urls = [c[2] for c in cards if c[2]]
        if detail_urls:
            self.prefetch_pages(detail_urls, max_concurrent=4)

        for title, blurb, url, image_url in cards:
            try:
                events.extend(self._build_events(title, blurb, url, image_url))
            except Exception as e:
                self.log(f"  x error parsing '{title}': {e}")

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _parse_cards(self, soup) -> List[Tuple[str, str, str, str]]:
        """Extract (title, blurb, detail_url, image_url) from the happenings grid."""
        cards: List[Tuple[str, str, str, str]] = []
        for card in soup.select('div.col.span_4.element.events'):
            heading = card.find(['h3', 'h4'])
            if not heading:
                continue
            title = self.clean_text(heading.get_text(' ', strip=True))
            if not title:
                continue

            # The blurb is everything in the card except the title itself.
            full_text = card.get_text(' ', strip=True)
            blurb = self.clean_text(full_text.replace(heading.get_text(' ', strip=True), '', 1))

            link = card.find('a', href=True)
            url = self.normalize_url(link['href'], self.BASE_URL) if link else ''

            img = card.find('img')
            image_url = self.normalize_url(img.get('src', ''), self.BASE_URL) if img else ''

            cards.append((title, blurb, url, image_url))
        return cards

    def _build_events(self, title: str, blurb: str, url: str, image_url: str) -> List[Event]:
        """Turn one card into zero or more Events (a series expands per occurrence)."""
        detail_text, description = self._fetch_detail(url)
        description = self._strip_leading_title(description or blurb, title)

        # The card blurb carries the canonical schedule line, so it is parsed
        # alone first: the detail page repeats other dates in prose, and reading
        # both as one string lets a stray range there outrank the real date.
        occurrences = self._parse_schedule(blurb) or self._parse_schedule(detail_text)
        if not occurrences:
            # Distinguish "this one already happened" from "we could not read a
            # date at all": the second means the page's wording has drifted and
            # the parser needs attention, while the first is routine.
            recognized = any(
                pattern.search(text)
                for pattern in (self._RANGE_RE, self._SINGLE_RE)
                for text in (blurb, detail_text)
            )
            reason = 'already past' if recognized else 'no resolvable date'
            self.log(f"  - skipping '{title}' ({reason})")
            return []

        category = self._classify(title, description)
        # Every listed happening on the Steps is free and open to all.
        events = []
        for start, end in occurrences:
            event = self.create_event(
                title=title,
                description=description,
                venue_name=self.VENUE_NAME,
                address=self.VENUE_ADDRESS,
                event_date=start,
                end_date=end,
                url=f'{url}#{start:%Y-%m-%d}' if url else self.LISTING_URL,
                image_url=image_url,
                category=category,
                is_free=True,
                price_note='Free',
                latitude=self.VENUE_LAT,
                longitude=self.VENUE_LNG,
            )
            if event:
                events.append(event)
                self.log(f"  + {start:%Y-%m-%d} {title}")
        return events

    def _fetch_detail(self, url: str) -> Tuple[str, str]:
        """Return (raw_text, description) for a detail page, or empty strings."""
        if not url:
            return '', ''
        html = self.fetch_page(url)
        if not html:
            return '', ''

        soup = self.parse_html(html)
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()

        body = soup.find('div', class_='container-wrap') or soup.body
        if not body:
            return '', ''
        text = self.clean_text(body.get_text(' ', strip=True))

        # The page's own prose ends at the site-wide "Become an Insider" pitch.
        description = text.split('Become an Insider')[0]
        description = re.sub(r'^.*?Back to Happenings\s*', '', description).strip()
        # Trim the trailing "Where ... When ..." metadata strip from the blurb.
        description = re.split(r'\bWhere\b', description)[0].strip()

        return text, self.clean_text(description)

    @staticmethod
    def _strip_leading_title(description: str, title: str) -> str:
        """Drop the page heading that detail pages repeat before their prose."""
        if description.lower().startswith(title.lower()):
            return description[len(title):].strip(' -–—:').strip()
        return description

    def _parse_schedule(self, text: str) -> List[Tuple[datetime, Optional[datetime]]]:
        """Resolve schedule text into concrete (start, end) datetimes."""
        start_t, end_t = self._parse_times(text)

        match = self._RANGE_RE.search(text)
        if match:
            return self._expand_series(match, start_t, end_t)

        match = self._SINGLE_RE.search(text)
        if match:
            return self._single_occurrence(match, start_t, end_t)

        return []

    def _expand_series(self, match, start_t, end_t) -> List[Tuple[datetime, Optional[datetime]]]:
        """Expand "Wednesdays, July 8 - August 26" into one entry per week."""
        weekday_s, m1_s, d1_s, m2_s, d2_s = match.groups()
        weekday = _WEEKDAYS[f'{weekday_s.lower()}day']
        month1 = _MONTHS[m1_s.lower()]
        month2 = _MONTHS[m2_s.lower()] if m2_s else month1
        day1, day2 = int(d1_s), int(d2_s)

        span = self._resolve_range_years(weekday, month1, day1, month2, day2)
        if not span:
            return []
        range_start, range_end = span

        today = date.today()
        cursor = max(range_start, today)
        # Advance to the first occurrence of the stated weekday.
        cursor += timedelta(days=(weekday - cursor.weekday()) % 7)

        occurrences = []
        while cursor <= range_end and len(occurrences) < self.MAX_OCCURRENCES:
            occurrences.append(self._with_times(cursor, start_t, end_t))
            cursor += timedelta(days=7)
        return occurrences

    def _single_occurrence(self, match, start_t, end_t) -> List[Tuple[datetime, Optional[datetime]]]:
        """Resolve "Tuesday, August 4th" to a single dated occurrence."""
        weekday_s, month_s, day_s = match.groups()
        weekday = _WEEKDAYS[f'{weekday_s.lower()}day']
        year = self._resolve_year(weekday, _MONTHS[month_s.lower()], int(day_s))
        if year is None:
            return []

        try:
            day = date(year, _MONTHS[month_s.lower()], int(day_s))
        except ValueError:
            return []
        if day < date.today():
            return []
        return [self._with_times(day, start_t, end_t)]

    @staticmethod
    def _with_times(day: date, start_t, end_t) -> Tuple[datetime, Optional[datetime]]:
        start = datetime(day.year, day.month, day.day, start_t[0], start_t[1])
        end = None
        if end_t:
            end = datetime(day.year, day.month, day.day, end_t[0], end_t[1])
            if end <= start:
                end = None
        return start, end

    @staticmethod
    def _resolve_range_years(weekday: int, month1: int, day1: int,
                             month2: int, day2: int) -> Optional[Tuple[date, date]]:
        """Pick the year for an undated "July 8 - August 26" range.

        Prefers a year whose range start lands on the stated weekday (which is
        how this source writes its series), and among the candidates takes the
        soonest range that has not already finished.
        """
        today = date.today()
        anchored, fallback = [], []
        for year in range(today.year - 1, today.year + 2):
            try:
                start = date(year, month1, day1)
                # A range that wraps the new year ends in the following year.
                end = date(year + 1 if month2 < month1 else year, month2, day2)
            except ValueError:
                continue
            if end < today:
                continue
            (anchored if start.weekday() == weekday else fallback).append((start, end))

        candidates = anchored or fallback
        return min(candidates, key=lambda se: se[1]) if candidates else None

    @staticmethod
    def _resolve_year(weekday: int, month: int, day: int) -> Optional[int]:
        """Pick the year in which month/day falls on the stated weekday."""
        today = date.today()
        candidates = []
        for year in range(today.year - 1, today.year + 3):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if candidate.weekday() == weekday:
                candidates.append(candidate)
        if not candidates:
            return None
        upcoming = [c for c in candidates if c >= today]
        return (min(upcoming) if upcoming else max(candidates)).year

    def _parse_times(self, text: str) -> Tuple[Tuple[int, int], Optional[Tuple[int, int]]]:
        """Extract (start, end) clock times, defaulting to midnight start."""
        match = self._TIME_RANGE_RE.search(text)
        if match:
            g = match.groups()
            if g[0] is not None:
                # Both sides carry a meridiem: "5pm - 8pm".
                start = self._to_24h(g[0], g[1], g[2])
                end = self._to_24h(g[3], g[4], g[5])
            else:
                # Only the trailing side does: "5-8pm" means 5pm to 8pm.
                start = self._to_24h(g[6], g[7], g[10])
                end = self._to_24h(g[8], g[9], g[10])
            return start, end

        match = self._TIME_RE.search(text)
        if match:
            return self._to_24h(match.group(1), match.group(2), match.group(3)), None
        return (0, 0), None

    @staticmethod
    def _to_24h(hour_s: str, minute_s: Optional[str], meridiem: Optional[str]) -> Tuple[int, int]:
        hour = int(hour_s) % 12
        if meridiem and meridiem.lower() == 'p':
            hour += 12
        return hour, int(minute_s or 0)

    def _classify(self, title: str, description: str = '') -> str:
        """Classify by title first, falling back to the description.

        The title is the reliable signal: "PLAY at the Steps" is a kids' event
        whose blurb happens to name a band ("LoveBug and Me Music"), so scanning
        both together as one string would file it under Music.
        """
        for text in (title, description):
            low = text.lower()
            for keyword, category in self._CATEGORY_RULES:
                if re.search(rf'\b{keyword}\b', low):
                    return category
        return 'Community'

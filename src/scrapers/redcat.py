"""
Scraper for REDCAT (CalArts' downtown center, Walt Disney Concert Hall complex).
Source: https://redcat.org/events

REDCAT is a "beyond the Westside" source (REGION = 'beyond').

The site is Drupal with no JSON-LD and no iCal export, so the listing page
only gives each event's link; the date and time live in the event page's
facts list as free text, e.g. ``DATE: NOV 19-21`` / ``TIME: THU-SAT, 8 PM``.
Performances are expanded only from that stated pattern: each day in the date
range whose weekday is named in TIME gets one event per stated time. A time
range ("6-8 PM") is one show at its first time; door times and parenthesised
notes are ignored; a range over a week with no weekday in TIME is skipped. The
pages carry no year, so it is inferred as the nearby year in which the range
starts on a weekday named in TIME. Anything that doesn't parse cleanly is
skipped and logged rather than guessed. Exhibitions (HOURS, no TIME) are not
dated performances and are skipped.
"""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event


_WEEKDAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
_MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
_DAY = r'(MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z]*'
_MON = r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*'

# "NOV 19-21", "DEC 6", "SEP 12 - DEC 13": (month, day) start, (month, day) end.
_DATE_SEG = re.compile(
    rf'{_MON}\s+(\d{{1,2}})(?:\s*[-–]\s*(?:{_MON}\s+)?(\d{{1,2}}))?'
)
_DAY_RANGE = re.compile(rf'{_DAY}\s*[-–]\s*{_DAY}')
_DAY_ONE = re.compile(rf'\b{_DAY}\b')
_TIME = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([AP]M)?')
# "6-8 PM", "11 AM-1 PM": a time range is ONE show, starting at the first time.
_TIME_RANGE = re.compile(
    r'(\d{1,2})((?::\d{2})?)\s*([AP]M)?\s*[-–]\s*(\d{1,2})(?::\d{2})?\s*([AP]M)'
)
# A new weekday clause starts at a comma followed by a weekday ("FRI 8 PM, SAT 3 PM").
_CLAUSE_SPLIT = re.compile(r'[;/]|,(?=\s*(?:MON|TUE|WED|THU|FRI|SAT|SUN))')
# A date range with no weekday in TIME is only expanded nightly up to a week.
_MAX_NIGHTLY_DAYS = 7
# Longest run believed as stated, and longest gap a year rollover may jump.
_MAX_RUN_DAYS = 120
_MAX_ROLLOVER_GAP_DAYS = 92

# REDCAT's own genre labels -> site categories (first listed genre wins).
_GENRE_CATEGORIES = {
    'dance': 'Theater',
    'theater': 'Theater',
    'music': 'Music',
    'film': 'Film',
    'talk': 'Education',
    'art': 'Art',
}


class RedcatScraper(BaseScraper):
    """Scraper for REDCAT performances, screenings and talks."""

    REGION = 'beyond'

    VENUE_NAME = 'REDCAT'
    VENUE_ADDRESS = '631 W 2nd St, Los Angeles, CA 90012'
    VENUE_LAT = 34.0553
    VENUE_LNG = -118.2495

    EVENTS_URL = 'https://redcat.org/events'
    MAX_EVENTS = 40  # detail fetches per run; the live list is under ten

    def __init__(self):
        super().__init__('REDCAT')
        self.base_url = 'https://redcat.org'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of REDCAT...")
        html = self.fetch_page(self.EVENTS_URL)
        if not html:
            self.log("Failed to fetch events page")
            return []

        paths = self._event_paths(html)
        self.log(f"Found {len(paths)} listed event(s)")
        if not paths:
            return []
        urls = [self.base_url + p for p in paths[:self.MAX_EVENTS]]
        self.prefetch_pages(urls)

        now = datetime.now()
        events: List[Event] = []
        seen = set()
        for url in urls:
            try:
                built = self._build_events(url, now)
            except Exception as e:
                self.log(f"  x error parsing {url}: {e}")
                continue
            for event in built:
                if event.url not in seen:
                    seen.add(event.url)
                    events.append(event)

        self.log(f"Scraped {len(events)} upcoming performance(s)")
        return events

    def _event_paths(self, html: str) -> List[str]:
        soup = self.parse_html(html)
        paths: List[str] = []
        for a in soup.select('a.event-card-stacked'):
            href = (a.get('href') or '').strip()
            if re.match(r'^/events/[^/?#]+$', href) and href != '/events/archive' and href not in paths:
                paths.append(href)
        return paths

    # -- event page ------------------------------------------------------

    def _facts(self, soup) -> Dict[str, str]:
        """The page's DATE / TIME / Price / Genre list as {label upper-cased: text}."""
        facts: Dict[str, str] = {}
        for dt in soup.select('dl dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                facts[dt.get_text(' ', strip=True).upper()] = self.clean_text(dd.get_text(' ', strip=True))
        return facts

    def _build_events(self, url: str, now: datetime) -> List[Event]:
        html = self.fetch_page(url, retry=1)
        if not html:
            return []
        soup = self.parse_html(html)

        title_el = soup.find('title')
        title = self.clean_text((title_el.get_text() if title_el else '').rsplit('|', 1)[0])
        facts = self._facts(soup)
        date_text, time_text = facts.get('DATE', ''), facts.get('TIME', '')
        if not title or not date_text:
            self.log(f"  - skipping {url}: no title or date")
            return []
        if not time_text:
            self.log(f"  - skipping '{title}': no performance times (exhibition or untimed)")
            return []

        starts = self._performances(date_text, time_text, now.date())
        if not starts:
            self.log(f"  - skipping '{title}': could not read DATE '{date_text}' / TIME '{time_text}' (or an open-ended nightly range)")
            return []

        meta = soup.find('meta', attrs={'name': 'description'})
        description = self.clean_text(meta.get('content', '')) if meta else ''
        image = soup.find('meta', property='og:image')
        price, is_free = self._price(facts.get('PRICE', ''))
        category = self._category(facts.get('GENRE') or facts.get('GENRES') or '')

        events = []
        for start in starts:
            if start < now:
                continue
            event = self.create_event(
                title=title,
                description=description,
                venue_name=self.VENUE_NAME,
                address=self.VENUE_ADDRESS,
                event_date=start,
                url=f"{url}#{start:%Y-%m-%dT%H:%M}",
                image_url=image.get('content', '') if image else '',
                category=category,
                price=price,
                is_free=is_free,
                latitude=self.VENUE_LAT,
                longitude=self.VENUE_LNG,
            )
            if event:
                events.append(event)
        return events

    @staticmethod
    def _price(text: str) -> Tuple[Optional[float], bool]:
        """Face price from '$25 + $2 Convenience Fee*' (the fee is extra, not the price)."""
        if re.search(r'\bfree\b', text, re.I):
            return None, True
        m = re.search(r'\$\s?(\d+(?:\.\d{2})?)', text)
        return (float(m.group(1)), False) if m else (None, False)

    @staticmethod
    def _category(genres: str) -> str:
        first = re.split(r'[,/&]', genres)[0].strip().lower()
        return _GENRE_CATEGORIES.get(first, '')

    # -- date / time grammar --------------------------------------------

    @classmethod
    def _performances(cls, date_text: str, time_text: str, today: date) -> List[datetime]:
        """Every stated performance, or [] when DATE/TIME don't parse cleanly."""
        segments = []
        for part in re.split(r'[&;,]|\bAND\b', date_text.upper()):
            m = _DATE_SEG.search(part)
            if not m and segments and re.fullmatch(r'\s*\d{1,2}\s*', part):
                # "DEC 4 AND 6": a bare day continues the previous month.
                m = _DATE_SEG.search(f'{_MONTHS[segments[-1][1][0]]} {part}')
            if not m:
                if part.strip():
                    return []
                continue
            m1, d1, m2, d2 = m.groups()
            start = (_MONTHS.index(m1), int(d1))
            end = (_MONTHS.index(m2 or m1), int(d2 or d1))
            segments.append((start, end))
        slots = cls._time_slots(time_text)
        if not segments or not slots:
            return []

        stated_days = {d for days, _ in slots if days for d in days}
        year = cls._year(segments[0][0], stated_days, today)
        if year is None:
            return []

        found = set()
        prev_end = None
        prev_last = None
        for (sm, sd), (em, ed) in segments:
            if prev_end is not None and (sm, sd) < prev_end:
                year += 1  # "DEC 30 AND JAN 2": the later segment is next year
            try:
                first = date(year, sm + 1, sd)
                last = date(year if (em, ed) >= (sm, sd) else year + 1, em + 1, ed)
            except ValueError:
                return []
            # A year rollover is only believable across a short gap (DEC 30 ->
            # JAN 2). Out-of-order dates ("DEC 31 AND 2", "DEC 3 & NOV 28") or a
            # range that wraps most of a year ("DEC 3 - NOV 28") are ambiguous:
            # skip rather than push a date a year out or expand ~50 weeks.
            if prev_last is not None and (first - prev_last).days > _MAX_ROLLOVER_GAP_DAYS:
                return []
            if (last - first).days > _MAX_RUN_DAYS:
                return []
            year, prev_end, prev_last = last.year, (em, ed), last
            span = (last - first).days + 1
            if span > _MAX_NIGHTLY_DAYS and any(days is None for days, _ in slots):
                return []  # open-ended nightly run: never invent every night
            for offset in range(span):
                day = first + timedelta(days=offset)
                for days, times in slots:
                    if days is None or day.weekday() in days:
                        for hour, minute in times:
                            found.add(datetime(day.year, day.month, day.day, hour, minute))
        return sorted(found)

    @staticmethod
    def _year(start: Tuple[int, int], weekdays: set, today: date) -> Optional[int]:
        """Year (near today) in which `start` falls on a stated weekday."""
        candidates = []
        for year in (today.year - 1, today.year, today.year + 1):
            try:
                first = date(year, start[0] + 1, start[1])
            except ValueError:
                continue
            if not weekdays or first.weekday() in weekdays:
                candidates.append((abs((first - today).days), year))
        return min(candidates)[1] if candidates else None

    @staticmethod
    def _time_slots(text: str) -> List[Tuple[Optional[set], List[Tuple[int, int]]]]:
        """[(weekday set or None for every day, [(hour, minute), ...])] from a TIME string.

        Groups are separated by ';', '/' or a comma before a weekday ("FRI, 8 PM;
        SAT, 3 & 8 PM", "FRI 8 PM, SAT 3 PM"); a weekday-only piece joins the
        next one ("THU, SAT, 8 PM"). A group with no weekday applies to every
        day. Returns [] if any group has no readable time (e.g. no AM/PM) or
        mixes weekday clauses with separate times (never cross-multiplied).
        """
        slots = []
        pending = ''
        for piece in _CLAUSE_SPLIT.split(text.upper()):
            # Door times and parenthesised notes are not performances.
            piece = re.split(r'\bDOORS?\b', re.sub(r'\([^)]*\)', ' ', piece))[0]
            if not piece.strip():
                continue
            if not re.search(r'\d', piece):
                pending += piece + ' '  # weekdays only: the times follow
                continue
            group, pending = pending + piece, ''
            digit = re.search(r'\d', group).start()
            day_starts = [m.start() for m in re.finditer(_DAY, group)]
            if any(d < digit for d in day_starts) and any(d > digit for d in day_starts):
                return []  # "FRI 8 PM SAT 3 PM": clauses without a separator
            days = set()
            for m in _DAY_RANGE.finditer(group):
                a, b = _WEEKDAYS.index(m.group(1)), _WEEKDAYS.index(m.group(2))
                days.update(range(a, b + 1) if a <= b else list(range(a, 7)) + list(range(0, b + 1)))
            rest = _DAY_RANGE.sub(' ', group)
            for m in _DAY_ONE.finditer(rest):
                days.add(_WEEKDAYS.index(m.group(1)))
            rest = _DAY_ONE.sub(' ', rest)
            for m in _TIME_RANGE.finditer(rest):
                # "11-1 PM" with no meridiem of its own is ambiguous (11 AM or PM).
                if not m.group(3) and int(m.group(1)) % 12 > int(m.group(4)) % 12:
                    return []
            rest = _TIME_RANGE.sub(
                lambda m: f'{m.group(1)}{m.group(2)} {m.group(3) or m.group(5)}', rest
            )

            tokens = _TIME.findall(rest)
            times: List[Tuple[int, int]] = []
            meridiem = ''
            for hour, minute, mer in reversed(tokens):  # "3 & 8 PM": 3 takes PM from 8
                meridiem = mer or meridiem
                if not meridiem or not 1 <= int(hour) <= 12:
                    return []
                h = int(hour) % 12 + (12 if meridiem == 'PM' else 0)
                times.append((h, int(minute or 0)))
            if not times:
                return []
            slots.append((days or None, sorted(times)))
        return [] if pending else slots

"""
Scraper for the Pepperdine Center for the Arts (Lisa Smith Wengler Center for
the Arts, Malibu).
Source: https://arts.pepperdine.edu/events

The events page is one table of the season's shows: title, a date line, tags,
a link to the show page, and two machine dates (``SORTDATE``, the last day of
the show, and ``EXPDATE``). It includes shows that already ran.

The date line is written out in full and often covers several performances,
for example:

    Tuesday, September 22–Friday, September 25, 2026 • 7:30 PM | Saturday, September 26, 2026 • 2 PM and 7:30 PM
    Thursday, February 25 and Saturday, February 27, 2027 • 7:30 PM

Ranges ("A–B") and lists ("A and B") are both stated explicitly, so each named
day becomes its own event, starting at that day's first showtime (the other
showtimes go in the description). Every event gets a ``#YYYY-MM-DD`` URL
fragment so consecutive days of one show are not merged by URL dedup.

Each upcoming show's page is fetched for its venue, ticket price, description
and image. Only shows at the Malibu campus are kept (Smothers Theatre, Raitt
Recital Hall, Lindhurst Theatre, the Weisman Museum, ...); a show whose venue
is not recognised as on campus is skipped and logged. The number of detail
pages is capped, and they are fetched five at a time.
"""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event


_MONTHS = ('January|February|March|April|May|June|July|August|September|'
           'October|November|December')
_DAY_TOKEN = re.compile(
    rf'(?:(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s*)?'
    rf'({_MONTHS})\s+(\d{{1,2}})(?:,?\s*(\d{{4}}))?'
)
_TIME = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\b', re.I)
_PRICE = re.compile(r'\$\s*(\d+(?:\.\d+)?)')

# Listing tags (lowercase substrings) -> site category; first match wins, and
# an unmatched show is left to the keyword classifier.
_TAG_CATEGORIES = (
    ('pepperdine theatre', 'Theater'),
    ('family fun', 'Family'),
    ('dance', 'Theater'),
    ('music', 'Music'),
    ('virtuosi', 'Music'),
    ('recital', 'Music'),
    ('singer/songwriter', 'Music'),
    ('global jazz', 'Music'),
    ('pop/rock', 'Music'),
    ('stars of stage', 'Theater'),
)

# Venue names (lowercase substrings) that mean the Malibu campus.
_CAMPUS_VENUES = (
    'smothers', 'raitt', 'lindhurst', 'weisman', 'wengler', 'center for the arts',
    'pepperdine', 'malibu', 'elkins', 'stauffer', 'alumni park', 'drescher',
)


class PepperdineArtsScraper(BaseScraper):
    """Scraper for Pepperdine's Center for the Arts season."""

    BASE_URL = 'https://arts.pepperdine.edu'
    EVENTS_URL = 'https://arts.pepperdine.edu/events'

    VENUE_ADDRESS = '24255 Pacific Coast Highway, Malibu, CA 90263'
    VENUE_LAT = 34.0385744
    VENUE_LNG = -118.7070564
    DEFAULT_VENUE = 'Lisa Smith Wengler Center for the Arts'

    # Upcoming show pages fetched per scrape; the season has about 40.
    MAX_DETAIL_PAGES = 50

    def __init__(self):
        super().__init__('Pepperdine Center for the Arts')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Pepperdine Center for the Arts...")
        html = self.fetch_page(self.EVENTS_URL)
        if not html:
            self.log("Failed to fetch the events page")
            return []

        now = datetime.now()
        today = now.date()
        shows = [s for s in self._parse_listing(html) if self._is_upcoming(s, today)]
        self.log(f"Found {len(shows)} upcoming show(s) on the events page")
        shows = shows[:self.MAX_DETAIL_PAGES]
        self.prefetch_pages([s['url'] for s in shows], max_concurrent=5)

        events: List[Event] = []
        for show in shows:
            try:
                events.extend(self._events_for_show(show, now))
            except Exception as e:
                self.log(f"Error parsing {show['url']}: {e}")
        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    # -- listing -------------------------------------------------------------

    def _parse_listing(self, html: str) -> List[dict]:
        soup = self.parse_html(html)
        shows = []
        seen = set()
        for row in soup.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 6:
                continue
            link = cells[1].find('a', href=True) or cells[3].find('a', href=True)
            if not link:
                continue
            url = self.normalize_url(link['href'], self.BASE_URL)
            if url in seen:
                continue
            seen.add(url)
            date_line = next(
                (self.clean_text(p.get_text(' ')) for p in cells[1].find_all('p')
                 if '•' in p.get_text()),
                '',
            )
            shows.append({
                'url': url,
                'title': self.clean_text(cells[1].find('a').get_text(' ')) if cells[1].find('a') else '',
                'date_line': date_line,
                'tags': self.clean_text(cells[2].get_text(' ')).lower(),
                'last_day': self.clean_text(cells[-2].get_text()),
            })
        return shows

    @staticmethod
    def _is_upcoming(show: dict, today: date) -> bool:
        """Skip shows whose last day (SORTDATE, YYYYMMDD) has passed."""
        last = show['last_day']
        if re.fullmatch(r'\d{8}', last):
            return datetime.strptime(last, '%Y%m%d').date() >= today
        return True

    # -- date line -----------------------------------------------------------

    def _parse_schedule(self, text: str) -> Dict[date, List[datetime]]:
        """Expand a date line into {day: [showtimes]}; days without a time are dropped."""
        schedule: Dict[date, List[datetime]] = {}
        for segment in text.split('|'):
            if '•' not in segment:
                continue
            date_part, time_part = segment.split('•', 1)
            times = [
                (int(h) % 12 + (12 if ap.lower() == 'p' else 0), int(mi or 0))
                for h, mi, ap in _TIME.findall(time_part)
            ]
            if not times:
                self.log(f"No showtime in '{segment.strip()}'; skipping")
                continue
            for day in self._days_in(date_part):
                schedule.setdefault(day, []).extend(
                    datetime(day.year, day.month, day.day, h, mi) for h, mi in times
                )
        return schedule

    @staticmethod
    def _days_in(date_part: str) -> List[date]:
        tokens = list(_DAY_TOKEN.finditer(date_part))
        # A year is written once after the last date of a group, so fill the
        # earlier dates from the next stated year.
        years: List[Optional[int]] = [int(t.group(3)) if t.group(3) else None for t in tokens]
        for i in range(len(years) - 2, -1, -1):
            if years[i] is None:
                years[i] = years[i + 1]
        days: List[date] = []
        prev_end = 0
        for i, tok in enumerate(tokens):
            if years[i] is None:
                continue
            month = _MONTHS.split('|').index(tok.group(1)) + 1
            day = date(years[i], month, int(tok.group(2)))
            if i > 0 and re.search(r'[–—-]', date_part[prev_end:tok.start()]) and days:
                if day < days[-1]:
                    # A range across New Year ("December 30-January 2, 2027").
                    days[-1] = days[-1].replace(year=days[-1].year - 1)
                cursor = days[-1] + timedelta(days=1)
                while cursor < day:
                    days.append(cursor)
                    cursor += timedelta(days=1)
            days.append(day)
            prev_end = tok.end()
        return days

    # -- show pages ----------------------------------------------------------

    def _events_for_show(self, show: dict, now: datetime) -> List[Event]:
        schedule = self._parse_schedule(show['date_line'])
        if not schedule:
            self.log(f"No dated performances for {show['title'] or show['url']}")
            return []

        page = self.fetch_page(show['url'])
        if not page:
            return []
        soup = self.parse_html(page)

        venue_el = soup.select_one('.venue-row .large')
        venue = self.clean_text(venue_el.get_text(' ')) if venue_el else ''
        if venue and not any(k in venue.lower() for k in _CAMPUS_VENUES):
            self.log(f"Skipping off-campus show {show['title']} at {venue}")
            return []

        h1 = soup.find('h1')
        title = self.clean_text(h1.get_text(' ')) if h1 else show['title']
        if not title:
            return []
        price, is_free = self._price(soup)
        description = self._description(soup)
        image = self._image(soup)

        events = []
        for day, shows in sorted(schedule.items()):
            # Drop showtimes that have already started, not just past days.
            shows = sorted({s for s in shows if s >= now})
            if not shows:
                continue
            times = ', '.join(s.strftime('%-I:%M %p') for s in shows)
            suffix = f" Showtimes: {times}." if len(shows) > 1 else ''
            event = self.create_event(
                title=title,
                description=f"{description}{suffix}".strip(),
                venue_name=venue or self.DEFAULT_VENUE,
                address=self.VENUE_ADDRESS,
                event_date=shows[0],
                url=f"{show['url']}#{day.isoformat()}",
                image_url=image,
                category=self._category(show['tags']),
                price=price,
                is_free=is_free,
                latitude=self.VENUE_LAT,
                longitude=self.VENUE_LNG,
            )
            if event:
                events.append(event)
        return events

    @staticmethod
    def _category(tags: str) -> str:
        return next((cat for key, cat in _TAG_CATEGORIES if key in tags), '')

    def _price(self, soup):
        """(low price, is_free) from the page's Tickets line; unknown is (None, False)."""
        el = soup.select_one('.ticket-row .large')
        text = self.clean_text(el.get_text(' ')) if el else ''
        if not text:
            return None, False
        if 'free' in text.lower():
            return None, True
        prices = [float(p) for p in _PRICE.findall(text)]
        return (min(prices), False) if prices else (None, False)

    def _description(self, soup) -> str:
        """The show blurb: paragraphs in the main column that are not the date line."""
        main = soup.select_one('div.widget.twothirds')
        if not main:
            return ''
        parts: List[str] = []
        for p in main.find_all('p'):
            text = self.clean_text(p.get_text(' '))
            if len(text) < 60 or '•' in text:
                continue
            parts.append(text)
            if sum(len(x) for x in parts) > 500:
                break
        return ' '.join(parts)[:600]

    def _image(self, soup) -> str:
        img = soup.select_one('.w-image img') or soup.select_one('div.widget.twothirds img')
        src = img.get('src', '') if img else ''
        return self.normalize_url(src, self.BASE_URL) if src else ''

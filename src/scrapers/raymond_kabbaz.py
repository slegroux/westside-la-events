"""
Scraper for Théâtre Raymond Kabbaz events.
Source: https://www.theatreraymondkabbaz.com/season-2026-2027

The site (Squarespace) no longer has an events collection: ``/upcoming-events``
redirects to a hand-built season page ("Season 2026-2027") whose only content
is a grid of image links, one per show. Each show is an ordinary page with:

    <h1> Walter Smith III            # title
    <h1> mar 6 - 8:00 PM             # "<month> <day>[-<day>|/<day>] [- <time>]", no year
    <p>  Genre: Jazz Music
    <p>  Duration: 75 minutes
    <p>  🇺🇸 English description ...  # then a 🇫🇷 French copy, which we drop

Dates carry no year. We resolve it from the "Season YYYY-YYYY" label in the
season page title (August-December belong to the first year, January-July to
the second). Ticketing (ludus.com) blocks automated access, so the event URL
is the show's own page and the price is left unknown.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .base import BaseScraper
from src.data.models import Event

_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class RaymondKabbazScraper(BaseScraper):
    """Scraper for Théâtre Raymond Kabbaz events."""

    # "Nov 19 - 8:00 PM", "mar 18-21", "Jan 22/23"
    _DATE_RE = re.compile(
        r'^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?!\d)(?:[-/–](\d{1,2})(?!\d))?'
        r'(?:\s*-\s*(\d{1,2})(?::(\d{2}))?\s*([AP]M))?',
        re.I,
    )
    _SEASON_RE = re.compile(r'Season\s+(\d{4})\s*-\s*(\d{4})', re.I)

    def __init__(self):
        super().__init__('Théâtre Raymond Kabbaz')
        self.base_url = 'https://www.theatreraymondkabbaz.com'
        self.events_url = f'{self.base_url}/upcoming-events'
        # Fixed venue information
        self.venue_name = 'Théâtre Raymond Kabbaz'
        self.venue_address = '10361 West Pico Boulevard, Los Angeles, CA 90064'
        self.venue_lat = 34.0470845
        self.venue_lng = -118.4158768

    def scrape(self) -> List[Event]:
        """Scrape the season page, then each show page it links to."""
        self.log("Starting scrape...")
        events: List[Event] = []

        html = self.fetch_page(self.events_url)
        if not html:
            self.log("Failed to fetch events page")
            return events

        soup = self.parse_html(html)
        title_tag = soup.find('title')
        page_title = title_tag.get_text() if title_tag else ''
        season_start = self._season_start_year(page_title)

        show_urls = self._show_urls(soup)
        self.log(f"Page title: {page_title!r}; found {len(show_urls)} show link(s)")
        if not show_urls:
            return events
        self.prefetch_pages(show_urls)

        now = datetime.now()
        seen = set()
        for url in show_urls:
            try:
                event = self._scrape_show(url, season_start)
            except Exception as e:
                self.log(f"Error parsing {url}: {e}")
                continue
            if not event:
                continue
            if (event.end_date or event.event_date) < now:
                continue
            key = (event.title.lower(), event.event_date)
            if key in seen:
                continue
            seen.add(key)
            events.append(event)

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _season_start_year(self, page_title: str) -> Optional[int]:
        m = self._SEASON_RE.search(page_title or '')
        return int(m.group(1)) if m else None

    def _show_urls(self, soup) -> List[str]:
        """Show pages linked from the season page's main content, in order."""
        main = soup.find('main') or soup
        urls: List[str] = []
        for a in main.find_all('a', href=True):
            href = a['href'].strip()
            # Same-site, single-segment page paths only (shows live at /<slug>).
            if not re.fullmatch(r'/[a-z0-9][a-z0-9-]*', href, re.I):
                continue
            url = self.normalize_url(href, self.base_url)
            if url not in urls:
                urls.append(url)
        return urls

    def _scrape_show(self, url: str, season_start: Optional[int]) -> Optional[Event]:
        html = self.fetch_page(url)
        if not html:
            return None
        soup = self.parse_html(html)
        main = soup.find('main') or soup
        for tag in main.find_all(['style', 'script']):
            tag.decompose()

        h1s = [self.clean_text(h.get_text(' ')) for h in main.find_all('h1')]
        title = h1s[0] if h1s else ''
        if not title:
            return None

        parsed = None
        for text in h1s[1:]:
            parsed = self._parse_date_line(text, season_start)
            if parsed:
                break
        if not parsed:
            self.log(f"Skipping '{title}': no parseable date on {url}")
            return None
        event_date, end_date = parsed

        genre = ''
        description_parts: List[str] = []
        for p in main.find_all('p'):
            text = self.clean_text(p.get_text(' '))
            if not text:
                continue
            if text.startswith('\U0001F1EB\U0001F1F7'):  # 🇫🇷 French copy starts
                break
            if text.lower().startswith('genre:'):
                genre = text.split(':', 1)[1].strip()
            elif text.lower().startswith('duration:'):
                continue
            else:
                description_parts.append(text.replace('\U0001F1FA\U0001F1F8', '').strip())
        description = ' '.join(p for p in description_parts if p)

        image_url = ''
        for img in main.find_all('img'):
            src = img.get('data-src') or img.get('src')
            if src:
                image_url = src.split('?')[0]
                break

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=self._category(genre, title, description),
            latitude=self.venue_lat,
            longitude=self.venue_lng,
        )

    def _parse_date_line(
        self, text: str, season_start: Optional[int]
    ) -> Optional[Tuple[datetime, Optional[datetime]]]:
        """Parse "Dec 1 - 7:30 PM" / "mar 18-21" into (start, end-or-None)."""
        m = self._DATE_RE.match(text.strip())
        if not m:
            return None
        month = _MONTHS.get(m.group(1)[:3].lower())
        if not month:
            return None
        day, day2 = int(m.group(2)), m.group(3)
        hour, minute, ampm = m.group(4), m.group(5), m.group(6)

        year = self._resolve_year(month, day, season_start)
        try:
            start = datetime(year, month, day)
            end = datetime(year, month, int(day2)) if day2 and int(day2) > day else None
        except ValueError:
            return None
        if hour:
            h = int(hour) % 12 + (12 if ampm.upper() == 'PM' else 0)
            start = start.replace(hour=h, minute=int(minute or 0))
        if end:
            end = end.replace(hour=23, minute=59)
        return start, end

    @staticmethod
    def _resolve_year(month: int, day: int, season_start: Optional[int]) -> int:
        """Season label gives the year; without one, take the next occurrence."""
        if season_start:
            return season_start if month >= 8 else season_start + 1
        today = datetime.now()
        year = today.year
        try:
            if datetime(year, month, day) < today - timedelta(days=30):
                year += 1
        except ValueError:
            pass
        return year

    @staticmethod
    def _category(genre: str, title: str, description: str) -> str:
        g = genre.lower()
        if 'dance' in g:
            return 'Dance'
        if 'film' in g or 'animat' in g:
            return 'Film'
        if 'theater' in g or 'theatre' in g:
            return 'Theater'
        if 'music' in g or 'jazz' in g or 'concert' in g:
            return 'Music'
        return 'Cultural'

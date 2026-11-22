"""
Scraper for Monday Evening Concerts (M.E.C.), LA's long-running new-music series.
Source: https://www.mondayeveningconcerts.org

A "beyond the Westside" source: concerts are at the Colburn School downtown and
at the Marciano Art Foundation, so REGION opts it into the separate tab.

The site is Squarespace, but its home page is a hand-laid page of text blocks,
not an events collection, so ``?format=json`` carries no events (empty
mainContent). We read the season list from the home page (everything above the
"RECENT EVENTS" heading), then each concert's own page, which states every
date with its time plus the venue and street address. A concert whose date
isn't fixed yet ("MARCH 2027 (DATES TBA)") has no date line and is skipped.
"""
import re
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class MondayEveningConcertsScraper(BaseScraper):
    """Scraper for Monday Evening Concerts' season page and concert pages."""

    REGION = 'beyond'

    HOME_URL = 'https://www.mondayeveningconcerts.org'

    # "MONDAY, DECEMBER 7, 2026 | 7 PM" (time optional).
    _DATE_RE = re.compile(
        r'^(?:[A-Za-z]+,\s*)?([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})'
        r'(?:\s*\|\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm]))?\s*$'
    )
    _ADDRESS_RE = re.compile(r'^\d+\s+\S+')
    _MONTHS = {m: i for i, m in enumerate(
        ['january', 'february', 'march', 'april', 'may', 'june', 'july',
         'august', 'september', 'october', 'november', 'december'], 1)}

    def __init__(self):
        super().__init__('Monday Evening Concerts')
        self.base_url = self.HOME_URL

    # -- scrape --------------------------------------------------------------

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Monday Evening Concerts...")
        html = self.fetch_page(self.HOME_URL)
        if not html:
            self.log("Failed to fetch home page")
            return []

        concerts = self._season_list(html)
        self.log(f"Found {len(concerts)} listed concert(s)")
        if not concerts:
            return []

        now = datetime.now()
        events: List[Event] = []
        for href, listing in concerts.items():
            page = self.fetch_page(f'{self.HOME_URL}{href}')
            if not page:
                self.log(f"  ✗ could not fetch {href}")
                continue
            for event in self._concert_events(href, listing, page):
                if (event.end_date or event.event_date) >= now:
                    events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    # -- home page -----------------------------------------------------------

    @staticmethod
    def _lines(node) -> List[str]:
        """A block's text, one entry per line (<br> and paragraph breaks)."""
        for br in node.find_all('br'):
            br.replace_with('\n')
        for para in node.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
            para.append('\n')
        text = node.get_text('')  # inline <em>/<strong> stay on their line
        return [re.sub(r'[\s\xa0]+', ' ', ln).strip() for ln in text.split('\n') if ln.strip()]

    def _season_list(self, html: str) -> Dict[str, dict]:
        """href -> {'title_lines', 'image'} for each concert above 'RECENT EVENTS'."""
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()

        concerts: Dict[str, dict] = {}
        for block in soup.select('.fe-block'):
            lines = self._lines(block)
            if lines and lines[0].upper() == 'RECENT EVENTS':
                break  # everything below is past
            link = block.find('a', href=True)
            if not link or not link['href'].startswith('/') or len(link['href']) < 2:
                continue
            entry = concerts.setdefault(link['href'], {'title_lines': [], 'image': ''})
            img = block.find('img')
            if img and not entry['image']:
                entry['image'] = img.get('data-src') or img.get('src') or ''
            # The title block is the one that isn't the dated date/venue line.
            if lines and not re.search(r'\b(19|20)\d\d\b', ' '.join(lines)):
                entry['title_lines'] = lines
        return {h: e for h, e in concerts.items() if e['title_lines']}

    def _date_line(self, line: str) -> Optional[re.Match]:
        return self._DATE_RE.match(line)

    def _title(self, lines: List[str]) -> str:
        """'COMPOSER | “WORK”' lines -> 'Composer: Work'; 'alongside' joins two."""
        def pretty(text: str) -> str:
            return text.strip(' “”"').title().replace("’S", "’s")

        segments: List[List[str]] = [[]]
        for ln in lines:
            if ln.lower().startswith('alongside'):
                segments.append([])
                ln = ln[len('alongside'):].strip()
            if ln:
                segments[-1].append(ln)

        parts = []
        for seg in segments:
            if seg and all('|' in ln for ln in seg):
                entries = [': '.join(pretty(p) for p in ln.split('|', 1)) for ln in seg]
            elif len(seg) == 2:
                entries = [f'{pretty(seg[0])}: {pretty(seg[1])}']
            else:
                entries = [pretty(ln) for ln in seg]
            parts.append(' / '.join(entries))
        return ' alongside '.join(p for p in parts if p)

    # -- concert page --------------------------------------------------------

    @staticmethod
    def _pretty_address(raw: str) -> str:
        words = [w if w == 'CA' else w.capitalize() for w in raw.split()]
        return re.sub(r'(?<!,)\s+CA\b', ', CA', ' '.join(words))

    def _concert_events(self, href: str, listing: dict, html: str) -> List[Event]:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()

        blocks: List[List[str]] = []
        seen = set()
        for block in soup.select('.sqs-block'):
            lines = self._lines(block)
            key = tuple(lines)
            if lines and key not in seen:
                seen.add(key)
                blocks.append(lines)

        dates: List[datetime] = []
        venue = address = ''
        for lines in blocks:
            found = [self._parse_date(m) for m in map(self._date_line, lines) if m]
            if not any(found):
                continue
            dates = [d for d in found if d]
            others = [ln for ln in lines if not self._date_line(ln)]
            addr = next((ln for ln in others if self._ADDRESS_RE.match(ln)), '')
            name = next((ln for ln in others if ln != addr), '')
            address = self._pretty_address(addr)
            venue = ' '.join(name.split()).title().replace(' At ', ' at ').replace(' The ', ' the ')
            break
        if not dates:
            self.log(f"  - skipping {href}: no fixed date")
            return []

        title = self._title(listing['title_lines'])
        if not title:
            self.log(f"  - skipping {href}: no title")
            return []
        description = self._description(blocks)

        events: List[Event] = []
        for when in dates:
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue,
                address=address,
                event_date=when,
                url=f'{self.HOME_URL}{href}#{when.strftime("%Y-%m-%d")}',
                image_url=listing['image'],
                category='Music',
            )
            if event:
                events.append(event)
        return events

    def _parse_date(self, m: re.Match) -> Optional[datetime]:
        """Naive LA-local datetime; midnight when the page states no time."""
        month = self._MONTHS.get(m.group(1).lower())
        if not month:
            return None
        hour = minute = 0
        if m.group(4):
            hour = int(m.group(4)) % 12 + (12 if m.group(6).lower() == 'pm' else 0)
            minute = int(m.group(5) or 0)
        try:
            return datetime(int(m.group(3)), month, int(m.group(2)), hour, minute)
        except ValueError:
            return None

    def _description(self, blocks: List[List[str]]) -> str:
        """First long text block between the performers heading and BIOS."""
        started = False
        for lines in blocks:
            head = lines[0].upper()
            if head in ('PERFORMERS', 'ARTISTS'):
                started = True
            elif head == 'BIOS':
                break
            elif started:
                text = self.clean_text(' '.join(lines))
                if len(text) > 150:
                    return text
        return ''

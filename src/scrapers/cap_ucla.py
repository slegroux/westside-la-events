"""
Scraper for CAP UCLA (Center for the Art of Performance at UCLA, Westwood).
Source: https://cap.ucla.edu/calendar

The calendar is one server-rendered Drupal view: each performance is an
``<a class="views-row">`` linking to its page, with date, artist, title, venue,
type and genre in ``views-field-field-event-*`` blocks.

Date quirk (verified against the visible "| 8 pm" text on every row):

  * Single-night events carry ``datetime="2026-11-21T20:00:00Z"`` -- a "Z"
    (UTC) stamp that is really the LOCAL wall clock (it reads 8 pm, the show's
    advertised time). Converting it as UTC would put the show at noon.
  * Multi-night runs carry two ``<time>`` elements whose values have no "Z" and
    ARE true UTC (``2027-01-09T04:00:00`` is Fri Jan 8, 8 pm Pacific), so those
    are converted to LA time.

Either way the displayed time text is checked, and a disagreement is resolved
in favour of the text, which is what a visitor sees. A run is listed once, on
its first night, like the Broad Stage scraper.

Venues are UCLA's Royce Hall, the Nimoy Theater and the Freud Playhouse; each
event gets its own venue's coordinates. K-12 school matinees are not public
events and are dropped.
"""
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event
from src.utils.categories import classify_event

LA_TZ = ZoneInfo('America/Los_Angeles')


class CAPUCLAScraper(BaseScraper):
    """Scraper for CAP UCLA performances."""

    BASE_URL = 'https://cap.ucla.edu'
    LISTING_URL = f'{BASE_URL}/calendar'

    # (lowercase needle in the listing's venue text, display name, address, lat, lng)
    VENUES = (
        ('royce', 'Royce Hall', '340 Royce Dr, Los Angeles, CA 90095',
         34.0728, -118.4421),
        ('nimoy', 'The Nimoy Theater', '1262 Westwood Blvd, Los Angeles, CA 90024',
         34.0577521, -118.4427816),
        ('freud', 'Freud Playhouse', '245 Charles E Young Dr N, Los Angeles, CA 90095',
         34.0733, -118.4412),
    )

    # Matches the trailing "8 pm" / "10:45 am" next to the date.
    _TIME_RE = re.compile(r'(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m', re.I)

    def __init__(self):
        super().__init__('CAP UCLA')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of CAP UCLA...")
        events: List[Event] = []

        html = self.fetch_page(self.LISTING_URL)
        if not html:
            self.log("Failed to fetch the CAP UCLA calendar")
            return events

        soup = BeautifulSoup(html, 'html.parser')
        rows = soup.select('a.views-row')
        self.log(f"Found {len(rows)} listed performance(s)")

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        seen_urls = set()
        for row in rows:
            try:
                event = self._parse_row(row)
            except Exception as e:
                self.log(f"  x error parsing row: {e}")
                continue
            if not event or event.event_date < today:
                continue
            if event.url in seen_urls:
                event.url = f'{event.url.split("#")[0]}#{event.event_date:%Y-%m-%dT%H:%M}'
            seen_urls.add(event.url)
            events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _field(self, row, name: str, sep: str = ' ') -> str:
        el = row.select_one(f'.views-field-field-event-{name} .field-content')
        return self.clean_text(el.get_text(sep, strip=True)) if el else ''

    def _parse_row(self, row) -> Optional[Event]:
        href = row.get('href', '')
        artist = self._field(row, 'artist', sep=' & ')  # <br> separates co-billed artists
        name = self._field(row, 'title')
        event_type = self._field(row, 'type')
        genre = self._field(row, 'genre')
        venue_text = self._field(row, 'venue')

        if event_type.lower().startswith('k') and '12' in event_type:
            self.log(f"  - skipping K-12 school program: {artist} {name}")
            return None
        title = self._title(artist, name)
        if not title or not href:
            return None

        event_date = self._start(row)
        if not event_date:
            self.log(f"  - no usable date, skipping: {title}")
            return None

        if not venue_text:
            self.log(f"  - no venue named, skipping: {title}")
            return None
        venue_name, address, lat, lng = self._venue(venue_text)

        img = row.find('img')
        image_url = self.normalize_url(img['src'], self.BASE_URL) if img and img.get('src') else ''

        return self.create_event(
            title=title,
            description='',
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=self.normalize_url(href, self.BASE_URL),
            image_url=image_url,
            category=self._category(title, event_type, genre),
            latitude=lat,
            longitude=lng,
        )

    @staticmethod
    def _title(artist: str, name: str) -> str:
        """"Artist: Title", or joined by a space when the pair reads as a sentence."""
        if not (artist and name):
            return artist or name
        if re.match(r'(with|featuring|feat\.|written by|and)\b', name, re.I):
            return f'{artist} {name[0].lower()}{name[1:]}'
        if artist.lower().endswith(('present', 'presents')):
            return f'{artist} {name}'
        return f'{artist}: {name}'

    def _start(self, row) -> Optional[datetime]:
        """Naive LA-local start of the first (or only) performance."""
        field = row.select_one('.views-field-field-event-date .field-content')
        first = field.find('time') if field else None
        if not first or not first.get('datetime'):
            return None
        stamp = first['datetime'].strip()
        try:
            if stamp.endswith('Z'):
                # Mislabelled: this is the local wall clock, not UTC.
                start = datetime.fromisoformat(stamp[:-1])
            else:
                start = (datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc)
                         .astimezone(LA_TZ).replace(tzinfo=None))
        except ValueError:
            return None

        shown = self._shown_time(field.get_text(' '))
        if shown and shown != (start.hour, start.minute):
            self.log(f"  ! datetime {stamp} disagrees with shown time {shown}; using shown")
            start = start.replace(hour=shown[0], minute=shown[1])
        return start

    def _shown_time(self, text: str) -> Optional[Tuple[int, int]]:
        matches = self._TIME_RE.findall(text)
        if not matches:
            return None
        hour, minute, meridiem = matches[-1]
        hour = int(hour) % 12 + (12 if meridiem.lower() == 'p' else 0)
        return hour, int(minute or 0)

    def _venue(self, text: str) -> Tuple[str, str, Optional[float], Optional[float]]:
        """Known UCLA hall -> pinned coordinates; any other named venue is geocoded."""
        lowered = text.lower()
        for needle, name, address, lat, lng in self.VENUES:
            if needle in lowered:
                return name, address, lat, lng
        return text, '', None, None

    @staticmethod
    def _category(title: str, event_type: str, genre: str) -> str:
        kinds = f'{event_type} {genre}'.lower()
        if 'film' in kinds or 'screening' in kinds:
            return 'Film'
        if 'dance' in kinds or 'theater' in kinds or 'theatre' in kinds:
            return 'Theater'
        if any(k in kinds for k in ('talk', 'conversation', 'lecture', 'discussion')):
            return 'Education'
        if any(k in kinds for k in ('music', 'classical', 'jazz', 'global', 'opera')):
            return 'Music'
        return classify_event(title, genre, '')

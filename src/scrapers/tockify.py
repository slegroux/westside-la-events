"""
Scrapers for venues that publish their calendar on Tockify.

Tockify's public JSON endpoint,
``https://tockify.com/api/ngevent?calname=<name>&startms=...&endms=...&max=...``,
returns one item per *occurrence*: a weekly jam is already expanded into one
item per week (``kind`` is 'repeat'/'rdate', each with its own ``eid.tid``).
So nothing is invented here; we ask for a bounded window and keep whatever the
API returns inside it. Without ``endms`` the API runs to the calendar's far
future (hundreds of recurring items), hence WINDOW_DAYS.

TockifyScraper holds the shared parsing; each calendar is a small subclass
giving its calendar name and venue. Item times carry the calendar's own tzid,
so they become aware datetimes and create_event converts them to LA time.
"""
import re
import time
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from .base import BaseScraper
from src.data.models import Event


class TockifyScraper(BaseScraper):
    """Base for one Tockify calendar. Subclasses set CALNAME and the venue."""

    CALNAME: str = ''
    VENUE_NAME: str = ''
    VENUE_ADDRESS: str = ''
    VENUE_LAT: Optional[float] = None
    VENUE_LNG: Optional[float] = None
    # A per-item address that doesn't contain this is treated as another venue.
    VENUE_STREET: str = ''

    API_URL = 'https://tockify.com/api/ngevent'
    WINDOW_DAYS = 60
    MAX_ITEMS = 200
    # The list API cuts descriptions at exactly this many characters.
    DESCRIPTION_CAP = 400

    # Items with no location that are online sessions, not at the venue.
    _ONLINE_RE = re.compile(r'\b(online|zoom|webinar|virtual)\b', re.I)

    def __init__(self, source_name: str):
        super().__init__(source_name)
        self.base_url = f'https://tockify.com/{self.CALNAME}'

    # -- fetch ---------------------------------------------------------------

    def _api_url(self) -> str:
        start_ms = int(time.time() * 1000)
        end_ms = start_ms + self.WINDOW_DAYS * 86400 * 1000
        return (
            f'{self.API_URL}?calname={self.CALNAME}'
            f'&startms={start_ms}&endms={end_ms}&max={self.MAX_ITEMS}'
        )

    def scrape(self) -> List[Event]:
        self.log(f"Starting scrape of Tockify calendar '{self.CALNAME}'...")
        data = self.fetch_json(self._api_url(), method='GET')
        items = (data or {}).get('events')
        if not isinstance(items, list):
            self.log("No event list in Tockify response")
            return []
        if (data.get('metaData') or {}).get('hasNext'):
            self.log(f"More than {self.MAX_ITEMS} items in window; truncated")

        now = datetime.now()
        events: List[Event] = []
        skipped = 0
        for item in items:
            try:
                event = self._build_event(item)
            except Exception as e:
                self.log(f"  ✗ error parsing item: {e}")
                continue
            if not event:
                skipped += 1
                continue
            if (event.end_date or event.event_date) < now:
                continue
            events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s) ({skipped} skipped)")
        return events

    # -- parse ---------------------------------------------------------------

    @staticmethod
    def _moment(when: dict) -> Optional[datetime]:
        """An aware datetime from a Tockify {millis, tzid} object."""
        if not isinstance(when, dict) or not when.get('millis'):
            return None
        try:
            tz = ZoneInfo(when.get('tzid') or 'America/Los_Angeles')
            return datetime.fromtimestamp(when['millis'] / 1000, tz)
        except (ValueError, OSError, KeyError):
            return None

    def _description(self, text) -> str:
        raw = text if isinstance(text, str) else ''
        text = self.clean_text(raw)
        if len(raw) >= self.DESCRIPTION_CAP:
            # Cut mid-sentence by the API: end on a word boundary, mark it.
            text = text.rsplit(' ', 1)[0].rstrip(',;:') + '…'
        return text

    def _skip_reason(self, title: str, description: str, content: dict) -> str:
        """Why an item shouldn't be listed (empty string to keep it)."""
        loc = content.get('location') or {}
        has_location = bool(loc.get('latitude') and loc.get('longitude'))
        if not has_location and self._ONLINE_RE.search(f'{title} {description}'):
            return 'online-only'
        return ''

    def _category(self, title: str, description: str) -> str:
        """Override to force a category; empty means classify from the text."""
        return ''

    def _price(self, description: str):
        """(price, price_note) from a stated '$N' amount; unknown stays empty."""
        m = re.search(r'\$\s?(\d+(?:\.\d{1,2})?)', description)
        if not m:
            return None, ''
        note = 'Suggested donation' if re.search(r'suggested donation', description, re.I) else ''
        return float(m.group(1)), note

    def _build_event(self, item: dict) -> Optional[Event]:
        content = item.get('content') or {}
        title = self.clean_text((content.get('summary') or {}).get('text'))
        when = item.get('when') or {}
        start = self._moment(when.get('start'))
        if not title or not start:
            self.log(f"  - skipping undated item: {title or item.get('eid')}")
            return None
        if (item.get('status') or {}).get('name', 'scheduled') != 'scheduled':
            self.log(f"  - skipping non-scheduled item: {title}")
            return None
        end = None if when.get('allDay') else self._moment(when.get('end'))

        description = self._description((content.get('description') or {}).get('text'))
        reason = self._skip_reason(title, description, content)
        if reason:
            self.log(f"  - skipping {reason}: {title}")
            return None

        # Where: the item's own location when it has one, else the venue.
        loc = content.get('location') or {}
        address = self.clean_text(content.get('address')) or self.VENUE_ADDRESS
        lat, lng = loc.get('latitude'), loc.get('longitude')
        venue_name = self.VENUE_NAME
        if lat and lng and self.VENUE_STREET and self.VENUE_STREET not in address:
            venue_name = self.clean_text(content.get('place')) or address
        else:
            address = self.VENUE_ADDRESS
            lat, lng = self.VENUE_LAT, self.VENUE_LNG

        eid = item.get('eid') or {}
        occurrence = start.strftime('%Y-%m-%dT%H:%M')
        if content.get('customButtonLink'):
            # One ticket link can serve every occurrence of a recurring item.
            url = f"{content['customButtonLink']}#{occurrence}"
        else:
            url = f"{self.base_url}/detail/{eid.get('uid')}/{eid.get('tid')}"

        price, price_note = self._price(description)
        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=start,
            end_date=end,
            url=url,
            category=self._category(title, description),
            price=price,
            price_note=price_note,
            latitude=lat,
            longitude=lng,
        )


class PhilosophicalResearchSocietyScraper(TockifyScraper):
    """Talks, screenings, salons and workshops at PRS in Los Feliz."""

    REGION = 'beyond'

    CALNAME = 'eventbrite'
    VENUE_NAME = 'Philosophical Research Society'
    VENUE_ADDRESS = '3910 Los Feliz Blvd, Los Angeles, CA 90027'
    VENUE_LAT = 34.1131212
    VENUE_LNG = -118.2776505
    VENUE_STREET = '3910 Los Feliz'

    def __init__(self):
        super().__init__('Philosophical Research Society')


class WorldStageScraper(TockifyScraper):
    """Concerts, jam sessions and workshops at The World Stage, Leimert Park."""

    CALNAME = 'the.world.stage'
    VENUE_NAME = 'The World Stage'
    VENUE_ADDRESS = '4321 Degnan Blvd, Los Angeles, CA 90008'
    VENUE_LAT = 34.0053013
    VENUE_LNG = -118.3317536
    VENUE_STREET = '4321 Degnan'

    # Children's classes aren't listings for this site's audience.
    _KIDS_RE = re.compile(r'\b(children|kids|youth|ages? \d+)\b', re.I)
    _WORKSHOP_RE = re.compile(r'\bworkshop\b', re.I)

    def __init__(self):
        super().__init__('The World Stage')

    def _skip_reason(self, title: str, description: str, content: dict) -> str:
        if (self._WORKSHOP_RE.search(f'{title} {description}')
                and self._KIDS_RE.search(description)):
            return "children's workshop"
        return super()._skip_reason(title, description, content)

    def _category(self, title: str, description: str) -> str:
        # Instruction sessions are not concerts; jams and shows stay Music.
        if self._WORKSHOP_RE.search(title) or 'this workshop' in description.lower():
            return 'Education'
        return 'Music'

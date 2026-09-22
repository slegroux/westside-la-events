"""
Scraper for Grateful Giraffes (The Oasis).
Source: https://app.grateful.gg/events

Grateful Giraffes is an LA gratitude/wellness community that runs salons, sound
baths, bootcamps and dinners, mostly on the Westside. The site is a base44
single-page app: ``/events`` ships no event markup at all, and the listing
arrives client-side from a public entity API, which is what this scraper reads
instead of driving a browser:

    GET /api/apps/<APP_ID>/entities/Event?sort=-date&limit=400

No key or session is needed. (The app's ``entities/User/me`` call 401s for an
anonymous visitor, but the Event collection is public -- it is what an
unauthenticated browser renders the page from.)

Three properties of the feed shape the code:

  * **It is the community's whole history.** One request returns every event
    ever run, past included, plus a few records the site does not surface
    itself, so the filtering in ``_is_listable`` is what makes the result match
    what a visitor actually sees.

  * **Times are hand-entered free text.** The same field carries '7:00 PM',
    '17:30', '6:30pm', '9:00 AM PST' and '300PM', and one end_time is the prose
    'Sunday afternoon'. ``_parse_time`` accepts the shapes that denote a real
    clock time and rejects the rest rather than guessing.

  * **Most gatherings hide their address** (``address_hidden``), publishing only
    a neighbourhood until you RSVP. The address handed to create_event is
    therefore the most specific one available, and no more. That is deliberate:
    an event that resolves no finer than "Los Angeles" fails the shared
    geo-filter as ``address_not_recognized`` and is dropped, which is the honest
    outcome -- nothing in the record lets us claim it is on the Westside, and
    inventing a city-centre pin would put a wrong marker on the map.

Dedup: the ingestion pipeline (Database.insert_event) owns cross-run dedup.
Slugs are stable and give each event its own permalink; the ~1 in 3 records
with no slug fall back to the listing page, so they dedup on title/venue/date.
"""
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import BaseScraper
from src.data.models import Event


class GratefulGiraffesScraper(BaseScraper):
    """Scraper for Grateful Giraffes events (base44 entity API)."""

    BASE_URL = 'https://app.grateful.gg'
    APP_ID = '69882c256690d6f8c4ce18bf'
    API_URL = f'{BASE_URL}/api/apps/{APP_ID}/entities/Event'
    LISTING_URL = f'{BASE_URL}/events'

    # The feed is the full history; a season of future events is a fraction of
    # it, so this cap is about bounding one response, not about paging.
    API_LIMIT = 400

    # Statuses/flags that make a record invisible on the site itself.
    LISTABLE_STATUS = 'active'
    # 'invite_only' events are private. 'giraffes_only' ones are listed publicly
    # (the site shows them with a GIRAFFE-ONLY badge) and so are kept.
    PRIVATE_ACCESS_LEVELS = frozenset({'invite_only'})

    # venue_host is free text and sometimes holds the RSVP call-to-action rather
    # than a venue ("Register to See Address", and one corrupted variant of it).
    # Matched loosely because the corruption is inside the phrase.
    _VENUE_PLACEHOLDER_RE = re.compile(r'register\s*to\s*see', re.I)

    # '7:00 PM' / '6:30pm' / '9:00 AM PST' -- 12-hour, optional trailing zone.
    _TIME_12H_RE = re.compile(
        r'^(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?(?:\s+[A-Z]{2,4})?$', re.I
    )
    # '300PM' -- someone dropped the colon. Read as H:MM, never HH:M.
    _TIME_COMPACT_RE = re.compile(r'^(\d{1,2})(\d{2})\s*([ap])\.?m\.?$', re.I)
    # '17:30' / '09:00' -- 24-hour, no meridiem.
    _TIME_24H_RE = re.compile(r'^(\d{1,2}):(\d{2})$')

    # This community's events are wellness/social gatherings; the shared
    # auto-classifier reads names like "The AI Salon" or "Biohacking Safari" as
    # Tech or Sports, so map the recurring formats by keyword first. Order
    # matters -- first match wins, so specific signals come before generic.
    _CATEGORY_RULES = (
        ('sound bath', 'Wellness'),
        ('sound healing', 'Wellness'),
        ('breathwork', 'Wellness'),
        ('yoga', 'Wellness'),
        ('meditation', 'Wellness'),
        ('retreat', 'Wellness'),
        ('biohacking', 'Wellness'),
        ('gratitude', 'Community'),
        ('salon', 'Community'),
        ('dinner', 'Food'),
        ('brunch', 'Food'),
        ('potluck', 'Food'),
        ('concert', 'Music'),
        ('bootcamp', 'Education'),
        ('workshop', 'Education'),
    )

    def __init__(self):
        super().__init__('Grateful Giraffes')
        self.base_url = self.BASE_URL

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Grateful Giraffes...")
        events: List[Event] = []

        records = self._fetch_events()
        if not records:
            self.log("No events returned by the entity API")
            return events

        self.log(f"Fetched {len(records)} event record(s) from the API")

        listable = [r for r in records if self._is_listable(r)]
        self.log(f"{len(listable)} upcoming, publicly listed, in-person event(s)")

        for raw in listable:
            try:
                event = self._parse_event(raw)
            except Exception as e:
                self.log(f"  x error parsing '{raw.get('title')}': {e}")
                continue
            if event:
                events.append(event)
                self.log(f"  + {event.event_date:%Y-%m-%d} {event.title}")

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    def _fetch_events(self) -> List[Dict[str, Any]]:
        """Read the Event collection. Returns [] on any failure."""
        data = self.fetch_json(
            f'{self.API_URL}?sort=-date&limit={self.API_LIMIT}',
            method='GET',
        )
        # The endpoint returns a bare JSON array; fetch_json is typed for the
        # dict-shaped APIs it was written for, so guard the shape here.
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        if isinstance(data, dict):
            for key in ('items', 'results', 'data'):
                if isinstance(data.get(key), list):
                    return [r for r in data[key] if isinstance(r, dict)]
        return []

    def _is_listable(self, raw: Dict[str, Any]) -> bool:
        """Mirror the visibility rules the site applies to its own listing."""
        if raw.get('status') != self.LISTABLE_STATUS:
            return False
        # is_public/is_hidden are independent switches in the admin, and an
        # event needs both pointing the right way to appear.
        if raw.get('is_hidden') or not raw.get('is_public'):
            return False
        if raw.get('is_sample'):
            return False
        if raw.get('access_level') in self.PRIVATE_ACCESS_LEVELS:
            return False
        # Virtual events have no venue to place on the map or filter by area.
        if raw.get('event_type') != 'in_person':
            return False
        return self._is_upcoming(raw.get('date'))

    @staticmethod
    def _is_upcoming(date_str: Optional[str]) -> bool:
        """True when the ISO date is today or later (dates are local, no zone)."""
        if not date_str:
            return False
        try:
            day = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            return False
        return day >= datetime.now().date()

    def _parse_event(self, raw: Dict[str, Any]) -> Optional[Event]:
        title = self.clean_text(raw.get('title'))
        if not title:
            return None

        event_date = self._combine(raw.get('date'), raw.get('time'))
        if not event_date:
            return None
        end_date = self._combine(raw.get('date'), raw.get('end_time'))
        # An end time earlier than the start means the gathering runs past
        # midnight ('7:00 PM' -> '1:00 AM'), which this feed has no way to say.
        # Dropping it is safer than emitting an event that ends before it began.
        if end_date and end_date <= event_date:
            end_date = None

        slug = (raw.get('slug') or '').strip()
        url = f'{self.BASE_URL}/{slug}' if slug else self.LISTING_URL

        price, is_free = self._parse_price(raw)

        return self.create_event(
            title=title,
            description=self.clean_text(raw.get('description')),
            venue_name=self._venue_name(raw),
            address=self._address(raw),
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=self._image_url(raw),
            category=self._classify(title, raw.get('tags')),
            price=price,
            is_free=is_free,
            # The feed states a price or says nothing; it never says "free but
            # unpriced", so an absent price stays an absent badge per the
            # project's pricing convention.
            price_note='',
        )

    def _venue_name(self, raw: Dict[str, Any]) -> str:
        """Best available venue, ignoring RSVP call-to-action placeholders."""
        host = self.clean_text(raw.get('venue_host'))
        if host and not self._VENUE_PLACEHOLDER_RE.search(host):
            return host
        # Fall back to the organizer so the card still names someone, rather
        # than to the neighbourhood (which the address already carries).
        return self.clean_text(raw.get('organizer')) or self.source_name

    def _address(self, raw: Dict[str, Any]) -> str:
        """Build the most specific address the record actually supports.

        Nothing is invented: when the street address is withheld this returns
        just "<neighbourhood>, <city>", and when even the neighbourhood is
        missing it returns the bare city -- which is what lets the shared
        geo-filter reject events we cannot honestly place on the Westside.
        """
        parts: List[str] = []
        street = self.clean_text(raw.get('street_address'))
        # street_address is only meaningful when the host chose to publish it.
        if street and not raw.get('address_hidden'):
            parts.append(street)

        neighborhood = self.clean_text(raw.get('town_or_neighborhood'))
        city = self.clean_text(raw.get('city'))
        # A neighbourhood equal to the city ("Beverly Hills" twice) adds nothing.
        if neighborhood and neighborhood.lower() != (city or '').lower():
            parts.append(neighborhood)
        if city:
            parts.append(city)

        return ', '.join(parts)

    def _image_url(self, raw: Dict[str, Any]) -> str:
        for key in ('image_url', 'cover_photo_url', 'og_image_url'):
            value = (raw.get(key) or '').strip()
            if value:
                return value
        return ''

    @staticmethod
    def _parse_price(raw: Dict[str, Any]) -> tuple:
        """Return (price, is_free). A stated 0 is free; absent is unknown."""
        value = raw.get('price')
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, False
        if value <= 0:
            return 0.0, True
        return float(value), False

    def _combine(self, date_str: Optional[str],
                 time_str: Optional[str]) -> Optional[datetime]:
        """Join the record's ISO date with its free-text time.

        A missing or unreadable time yields midnight rather than dropping the
        event: the date is the reliable half, and the site itself shows several
        of these with no time.
        """
        if not date_str:
            return None
        try:
            day = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
        except ValueError:
            return None

        hour, minute = self._parse_time(time_str) or (0, 0)
        return datetime(day.year, day.month, day.day, hour, minute)

    def _parse_time(self, value: Optional[str]) -> Optional[tuple]:
        """Read one hand-entered clock time, or None if it is not one.

        Handles '7:00 PM', '6:30pm', '9:00 AM PST', '300PM' and 24-hour
        '17:30'. Prose such as 'Sunday afternoon' is rejected: an unreadable
        time is better represented as no time than as a guess.
        """
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None

        match = self._TIME_12H_RE.match(text) or self._TIME_COMPACT_RE.match(text)
        if match:
            hour, minute, meridiem = match.group(1), match.group(2), match.group(3)
            hour = int(hour)
            if not 1 <= hour <= 12:
                return None
            hour %= 12
            if meridiem.lower() == 'p':
                hour += 12
            minute = int(minute or 0)
            return (hour, minute) if minute < 60 else None

        match = self._TIME_24H_RE.match(text)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            if hour < 24 and minute < 60:
                return hour, minute

        return None

    def _classify(self, title: str, tags: Optional[List[str]]) -> str:
        """Map a recurring format to a category by keyword.

        Returns '' when nothing matches so create_event falls back to the
        shared auto-classifier.
        """
        haystack = title.lower()
        if tags:
            haystack += ' ' + ' '.join(str(t).lower() for t in tags)
        for keyword, category in self._CATEGORY_RULES:
            if keyword in haystack:
                return category
        return ''

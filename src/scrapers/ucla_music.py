"""
Scraper for the UCLA Herb Alpert School of Music (Westwood).
Source: https://schoolofmusic.ucla.edu/events

Student, faculty and guest concerts are free and open to the public. The
calendar is a WordPress + The Events Calendar install, parsed by the shared
TribeEventsScraper.

Quirks of this install:
  * Most venue records are a bare room name ("Lani Hall", "Henry Mancini
    Studio") with no address or coordinates. The school's rooms all sit in the
    Schoenberg Music Building complex, so those fall back to its coordinates;
    the one regular off-campus venue (St. Paul the Apostle, for choral
    concerts) is pinned in VENUE_OVERRIDES.
  * An "Event Type" custom field marks "Public Event"; anything it labels as
    something else is dropped, as are masterclasses (studio teaching sessions,
    not concerts). Events without the field are kept.
  * Every event is free (``cost`` is "Free").
"""
from typing import Any, Dict, Optional

from .tribe_events import TribeEventsScraper


class UCLAMusicScraper(TribeEventsScraper):
    """Scraper for UCLA School of Music events (Tribe Events REST API)."""

    SOURCE_NAME = 'UCLA School of Music'
    BASE_URL = 'https://schoolofmusic.ucla.edu'
    EVENTS_URL = f'{BASE_URL}/events/'

    VENUE_NAME = 'Schoenberg Hall'
    VENUE_ADDRESS = '445 Charles E Young Dr E, Los Angeles, CA 90095'
    VENUE_LAT = 34.0707483
    VENUE_LNG = -118.4401261

    VENUE_OVERRIDES = (
        ('st. paul the apostle', '10750 Ohio Ave, Los Angeles, CA 90024',
         34.0559659, -118.43745),
    )

    DEFAULT_CATEGORY = 'Music'
    CATEGORY_RULES = (
        ('lectures and symposia', 'Education'),
        ('conference', 'Education'),
        ('workshop', 'Education'),
    )
    CATEGORY_USES_TITLE = False

    def _skip_reason(self, raw: Dict[str, Any], title: str,
                     venue_name: str) -> Optional[str]:
        if 'masterclass' in f'{self._category_names(raw)} {title.lower()}':
            return 'masterclass'
        event_type = self._custom_field(raw, 'Event Type')
        if event_type and 'public' not in event_type.lower():
            return f'not public ({event_type})'
        return None

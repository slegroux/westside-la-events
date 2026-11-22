"""
Scraper for the Wende Museum (Culver City).
Source: https://www.wendemuseum.org/programs

The Wende (Cold War art and artifacts) publishes films, concerts, talks,
workshops and community-partner programs through The Events Calendar REST API,
parsed by the shared TribeEventsScraper.

Quirks of this install:
  * Two sites share the calendar: the museum (10808 Culver Blvd) and its
    Community Center across the street (10858 Culver Blvd). Venue records carry
    an address but no coordinates, so both are pinned in VENUE_OVERRIDES.
  * "Deadline" entries (application due dates) and events whose venue is
    "Online" are not things to attend at the museum, so they are dropped.
  * Recurring programs (Wellness Wednesday, Samizdat Sundays) arrive as one
    API event per occurrence, each with its own dated permalink.
  * ``cost`` is empty everywhere, so no price is shown.
"""
from typing import Any, Dict, Optional

from .tribe_events import TribeEventsScraper


class WendeMuseumScraper(TribeEventsScraper):
    """Scraper for Wende Museum programs (Tribe Events REST API)."""

    SOURCE_NAME = 'Wende Museum'
    BASE_URL = 'https://wendemuseum.org'
    EVENTS_URL = f'{BASE_URL}/programs'

    VENUE_NAME = 'The Wende Museum'
    VENUE_ADDRESS = '10808 Culver Blvd, Culver City, CA 90230'
    VENUE_LAT = 34.011323
    VENUE_LNG = -118.4041322

    # "Community Center" must come first: its full name also contains "Wende Museum".
    VENUE_OVERRIDES = (
        ('community center', '10858 Culver Blvd, Culver City, CA 90230',
         34.010829, -118.4049949),
        ('wende museum', VENUE_ADDRESS, VENUE_LAT, VENUE_LNG),
    )

    DEFAULT_CATEGORY = 'Art'
    # Order matters: a "Wellness" + "Workshop" writing group is Wellness, and a
    # "Community Partner" + "Wellness" support circle is Wellness too.
    CATEGORY_RULES = (
        ('screening', 'Film'),
        ('music', 'Music'),
        ('family', 'Family'),
        ('wellness', 'Wellness'),
        ('community partner', 'Community'),
        ('workshop', 'Education'),
        ('conversation', 'Education'),
    )
    CATEGORY_USES_TITLE = False

    def _skip_reason(self, raw: Dict[str, Any], title: str,
                     venue_name: str) -> Optional[str]:
        if 'deadline' in self._category_names(raw):
            return 'application deadline, not an event'
        if raw.get('is_virtual') or venue_name.strip().lower() == 'online':
            return 'online only'
        return None

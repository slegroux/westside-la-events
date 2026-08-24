"""
Scraper for Zinqué (Le Zinque) community events.
Source: https://lezinque.com/community

Zinqué runs one Squarespace events list covering every location, and encodes
which restaurant an event belongs to as a suffix on the title
("martini monday | venice"). Addresses come from the site's own location
footer; events outside the coverage area are left to the geo filter.
"""
from datetime import date, datetime
from typing import List, Optional

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class ZinqueScraper(BaseScraper):
    """Scraper for the Zinqué community events calendar."""

    # Location suffix (as written in event titles) -> (venue name, address).
    # Addresses are the ones published in lezinque.com's own footer.
    LOCATIONS = {
        'venice': ('Zinqué Venice', '1440 S Lincoln Blvd, Venice, CA 90291'),
        'malibu': ('Zinqué Malibu', '23841 Malibu Road, Malibu, CA 90265'),
        'century city': (
            'Zinqué Century City',
            '10250 Santa Monica Blvd, Los Angeles, CA 90067',
        ),
        'west hollywood': (
            'Zinqué West Hollywood',
            '8684 Melrose Ave, West Hollywood, CA 90069',
        ),
        'weho': (
            'Zinqué West Hollywood',
            '8684 Melrose Ave, West Hollywood, CA 90069',
        ),
        'dtla': ('Zinqué DTLA', '939 S Broadway, Los Angeles, CA 90015'),
        'massilia dtla': ('Massilia DTLA', '939 S Broadway, Los Angeles, CA 90015'),
        'newport': ('Zinqué Newport', '3446 Via Oporto, Newport Beach, CA 92663'),
        'westlake': ('Zinqué Westlake', '2809 Agoura Rd, Westlake Village, CA 91361'),
    }

    # Events billed as running at every restaurant are emitted once per
    # location in the coverage area; the rest are dropped by the geo filter.
    ALL_LOCATIONS_KEY = 'all locations'
    ALL_LOCATIONS_FANOUT = ('venice', 'malibu', 'century city')

    def __init__(self):
        super().__init__('Zinqué')
        self.base_url = 'https://lezinque.com'
        self.events_url = f'{self.base_url}/community'

    def scrape(self) -> List[Event]:
        """Scrape events from the Zinqué community page."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)
            cards = soup.select('article.eventlist-event')
            self.log(f"Found {len(cards)} event cards")

            for card in cards:
                try:
                    events.extend(self._parse_card(card))
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_card(self, card) -> List[Event]:
        """Parse one event card into one Event per applicable location."""
        link = card.select_one('.eventlist-title-link')
        if not link:
            return []

        raw_title = self.clean_text(link.get_text())
        if not raw_title:
            return []

        title, location_key = self._split_location(raw_title)

        event_date = self._parse_datetime(card)
        if not event_date:
            return []

        # The community page lists past events alongside upcoming ones, so
        # anything already over is dropped rather than backfilled.
        if event_date.date() < date.today():
            return []

        end_date = self._parse_datetime(card, end=True)

        desc_elem = card.select_one('.eventlist-description')
        description = self.clean_text(desc_elem.get_text(' ')) if desc_elem else ''

        url = self.normalize_url(link.get('href', ''), self.base_url)

        image_url = ''
        img = card.find('img')
        if img:
            image_url = img.get('data-src') or img.get('src') or ''

        # The listing frequently says "free event" in the blurb; anything else
        # is a restaurant event with no published ticket price, which per
        # project convention means leaving price_note empty.
        is_free = 'free event' in description.lower()

        events = []
        for key in self._locations_for(location_key):
            venue_name, address = self.LOCATIONS[key]
            event = self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                is_free=is_free,
                price_note='',
            )
            if event:
                events.append(event)

        return events

    def _split_location(self, raw_title: str):
        """Split "title | location" into (title, location key).

        Returns a None key when the suffix isn't a location we recognize, so
        the title is left intact rather than silently truncated.
        """
        if '|' not in raw_title:
            return raw_title, None

        head, _, tail = raw_title.rpartition('|')
        key = tail.strip().lower()
        if key == self.ALL_LOCATIONS_KEY or key in self.LOCATIONS:
            return head.strip(), key
        return raw_title, None

    def _locations_for(self, location_key: Optional[str]) -> List[str]:
        """Which location entries an event should be emitted for."""
        if location_key == self.ALL_LOCATIONS_KEY:
            return list(self.ALL_LOCATIONS_FANOUT)
        if location_key in self.LOCATIONS:
            return [location_key]
        # Unlabeled events default to the Venice location, the only Zinqué on
        # the Westside proper.
        return ['venice']

    def _parse_datetime(self, card, end: bool = False) -> Optional[datetime]:
        """Combine the card's date tag with its localized start/end time."""
        date_elem = card.select_one('time.event-date')
        if not date_elem:
            return None

        date_str = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
        if not date_str:
            return None

        time_class = 'time.event-time-localized-end' if end else 'time.event-time-localized-start'
        time_elem = card.select_one(time_class)
        time_str = self.clean_text(time_elem.get_text()) if time_elem else ''
        # Squarespace renders times with a narrow no-break space before AM/PM.
        time_str = time_str.replace(' ', ' ')

        try:
            if time_str:
                return date_parser.parse(f'{date_str} {time_str}')
            if end:
                return None
            return date_parser.parse(date_str)
        except (ValueError, OverflowError):
            return None

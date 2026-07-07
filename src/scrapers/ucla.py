"""
Scraper for UCLA community events.
Source: https://community.ucla.edu
"""
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class UCLAScraper(BaseScraper):
    """Scraper for UCLA community events."""

    def __init__(self):
        super().__init__('UCLA')
        self.base_url = 'https://community.ucla.edu'

    def scrape(self) -> List[Event]:
        """
        Scrape events from UCLA community events calendar.

        The site loads event data dynamically via JavaScript, so we need
        Playwright. Each event renders as a ``.event-card`` carrying the title,
        a UTC start timestamp, the full location text (e.g. "Hammer Museum,
        10899 Wilshire Blvd, ..."), and a detail-page link — richer and more
        reliable than the page's embedded JSON blob, which loads inconsistently.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Use Playwright since events are loaded dynamically
            html = self.fetch_page_js(self.base_url, wait_selector='.event-card')
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)
            cards = soup.select('.event-card')
            self.log(f"Found {len(cards)} event cards")

            seen = set()
            for card in cards:
                try:
                    event = self._parse_card(card)
                    if event:
                        key = (event.title, event.event_date)
                        if key in seen:
                            continue
                        seen.add(key)
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_card(self, card) -> Event:
        """
        Parse a single rendered ``.event-card`` element.

        Args:
            card: BeautifulSoup element for one event card

        Returns:
            Event object or None
        """
        # Title + detail-page link
        summary = card.select_one('.event-card-summary a')
        if not summary:
            return None
        title = self.clean_text(summary.get_text())
        if not title:
            return None
        url = self.normalize_url(summary.get('href', ''), self.base_url)

        # Start time: prefer the LA-local timestamp on .event-card-time, falling
        # back to the UTC timestamp on the card. create_event normalizes both.
        event_date = None
        time_elem = card.select_one('.event-card-time')
        start_str = ''
        if time_elem and time_elem.get('data-event-start'):
            start_str = time_elem['data-event-start']  # naive LA-local
        elif card.get('data-event-start'):
            start_str = card['data-event-start']  # UTC (Z suffix)
        if start_str:
            try:
                event_date = date_parser.parse(start_str)
            except Exception:
                pass

        # Location text drives the geo-fence (e.g. an off-campus Hammer address).
        loc_elem = card.select_one('.event-card-location')
        location_text = self.clean_text(loc_elem.get_text()) if loc_elem else ''
        is_virtual = bool(card.select_one('.event-card-virtuallocation')) or \
            location_text.lower() in ('zoom', 'digital event', 'online', 'virtual')

        if is_virtual or not location_text:
            venue_name = 'UCLA'
            address = 'Los Angeles, CA 90095'
        else:
            # location_text is usually "Venue, Street, City, State Zip".
            venue_name = location_text.split(',')[0].strip()
            address = location_text

        # Description
        desc_elem = card.select_one('.event-card-description')
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ''

        # Image (cards may lazy-load; tolerate absence)
        image_url = ''
        img_elem = card.find('img')
        if img_elem:
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            is_free=True,
        )

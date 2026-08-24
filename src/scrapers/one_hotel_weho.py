"""
Scraper for 1 Hotel West Hollywood "Happenings".
Source: https://www.1hotels.com/west-hollywood/do/events

The listing is a Drupal view rendered client-side, so the static HTML has no
event cards -- Playwright is required. Cards carry a day/month but no year, and
the page mixes in other 1 Hotels properties, so both are handled here.
"""
from datetime import datetime
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


MONTH_ABBR = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


class OneHotelWeHoScraper(BaseScraper):
    """Scraper for 1 Hotel West Hollywood's events calendar."""

    # Sunset Blvd sits just north of the Westside coverage box.
    REGION = 'beyond'

    VENUE_NAME = '1 Hotel West Hollywood'
    ADDRESS = '8490 Sunset Blvd, West Hollywood, CA 90069'

    # The view can show other properties; only this one's cards are kept.
    PROPERTY_LABEL = 'west hollywood'

    def __init__(self):
        super().__init__('1 Hotel West Hollywood')
        self.base_url = 'https://www.1hotels.com'
        self.events_url = f'{self.base_url}/west-hollywood/do/events'

    def scrape(self) -> List[Event]:
        """Render the happenings page and parse its event cards."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page_js(
                self.events_url, wait_selector='article.event', timeout=45000
            )
            if not html:
                self.log("Failed to fetch events page (JS render)")
                return events

            soup = self.parse_html(html)
            cards = soup.select('article.event')
            self.log(f"Found {len(cards)} event cards")

            for card in cards:
                try:
                    event = self._parse_card(card)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing card: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_card(self, card) -> Optional[Event]:
        link = card.find('a', href=True)
        if not link or '/do/events/' not in link['href']:
            return None

        title_elem = card.find('h3')
        title = self.clean_text(title_elem.get_text()) if title_elem else ''
        if not title:
            return None

        label_elem = card.select_one('.property-label')
        label = self.clean_text(label_elem.get_text()).lower() if label_elem else ''
        if label and label != self.PROPERTY_LABEL:
            return None

        event_date = self._parse_card_date(card)
        if not event_date:
            return None

        # The card names the room the event runs in ("Harriet's Rooftop"), which
        # is more useful than the hotel name alone.
        space_elem = card.select_one('.property-location')
        space = self.clean_text(space_elem.get_text()) if space_elem else ''
        venue_name = f'{self.VENUE_NAME} — {space}' if space else self.VENUE_NAME

        # ".location" holds the run of dates ("June 15 - August"), which is
        # context rather than a parseable date.
        run_elem = card.select_one('.location')
        description = self.clean_text(run_elem.get_text()) if run_elem else ''

        image_url = ''
        img = card.find('img')
        if img and img.get('src'):
            image_url = self.normalize_url(img['src'], self.base_url)

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=self.ADDRESS,
            event_date=event_date,
            url=self.normalize_url(link['href'], self.base_url),
            image_url=image_url,
            price_note='',
        )

    def _parse_card_date(self, card) -> Optional[datetime]:
        """Read the card's date badge ("Tue | 18 | Aug").

        The badge omits the year, so a month behind the current one is read as
        next year's -- that's how the calendar rolls over in December.
        """
        date_elem = card.select_one('.date')
        if not date_elem:
            return None

        parts = [self.clean_text(s.get_text()) for s in date_elem.find_all('span')]
        day = month = None
        for part in parts:
            if part.isdigit():
                day = int(part)
            elif part[:3].lower() in MONTH_ABBR:
                month = MONTH_ABBR[part[:3].lower()]

        if not day or not month:
            return None

        today = datetime.now()
        year = today.year if month >= today.month else today.year + 1
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

"""
Scraper for Geffen Playhouse events.
Source: https://geffenplayhouse.org/tickets/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class GeffenPlayhouseScraper(BaseScraper):
    """Scraper for Geffen Playhouse events."""

    def __init__(self):
        super().__init__('Geffen Playhouse')
        self.base_url = 'https://geffenplayhouse.org'
        self.events_url = f'{self.base_url}/tickets/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Geffen Playhouse website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the events page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Each show is rendered inside a div.show-details containing h1 (title),
            # p (date range), summary, and a "Learn More" link pointing to /shows/<slug>/.
            show_cards = soup.find_all('div', class_='show-details')

            self.log(f"Found {len(show_cards)} show cards")

            seen_urls = set()
            for card in show_cards:
                try:
                    # Locate the show detail URL via the "Learn More" link
                    detail_link = card.find('a', href=re.compile(r'/shows/[a-z0-9-]+/?'))
                    if not detail_link:
                        continue
                    url = self.normalize_url(detail_link['href'], self.base_url)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    event = self._parse_event(card, url)
                    if event:
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

    def _parse_event(self, item, url: str) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data
            url: Event detail URL

        Returns:
            Event object or None
        """
        # Title is in the h1 element inside .show-details
        title_elem = item.find('h1')
        if not title_elem:
            title_elem = item.find('h3')
        if not title_elem:
            return None

        # Replace <br> with spaces so multi-line titles collapse cleanly
        for br in title_elem.find_all('br'):
            br.replace_with(' ')
        title = self.clean_text(title_elem.get_text())

        # Strip any premiere/designation prefixes that may leak in
        title = re.sub(
            r'^(World Premiere|Los Angeles Premiere|West Coast Premiere|The .* Production of)\s*',
            '',
            title,
            flags=re.IGNORECASE,
        ).strip()

        # Extract description
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date range - format like "11.05 – 12.07.2025"
        event_date = None
        end_date = None
        date_text = item.get_text()

        # Match date range pattern
        date_pattern = r'(\d{1,2})\.(\d{1,2})\s*[–-]\s*(\d{1,2})\.(\d{1,2})\.(\d{4})'
        date_match = re.search(date_pattern, date_text)

        if date_match:
            try:
                start_month = int(date_match.group(1))
                start_day = int(date_match.group(2))
                end_month = int(date_match.group(3))
                end_day = int(date_match.group(4))
                year = int(date_match.group(5))

                event_date = datetime(year, start_month, start_day)
                end_date = datetime(year, end_month, end_day)
            except Exception as e:
                self.log(f"Error parsing date range: {e}")

        # Venue info - Geffen Playhouse in Westwood
        venue_name = "Geffen Playhouse"
        address = "10886 Le Conte Ave, Los Angeles, CA 90024"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - all are theater performances
        category = "Theater"

        # Price info
        is_free = False
        price = None
        price_note = "TBD"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

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

            # Find all show links - they follow the pattern /shows/[show-slug]/
            show_links = soup.find_all('a', href=re.compile(r'/shows/[a-z0-9-]+/?'))

            self.log(f"Found {len(show_links)} show links")

            # Process unique show URLs
            seen_urls = set()
            for link in show_links:
                try:
                    url = self.normalize_url(link['href'], self.base_url)
                    if url in seen_urls or '/shows/' not in url:
                        continue
                    seen_urls.add(url)

                    # Find the card container for this show
                    card = link.find_parent(['div', 'article', 'section'])
                    if card:
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
        # Extract title from h3 element
        title_elem = item.find('h3')
        if not title_elem:
            title_elem = item.find('a', href=re.compile(r'/shows/'))

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())

        # Remove premiere designations like "World Premiere" from title
        title = re.sub(r'(World Premiere|Los Angeles Premiere|The .* Production of)\s*', '', title, flags=re.IGNORECASE).strip()

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
        category = "Performing Arts"

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

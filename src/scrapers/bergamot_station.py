"""
Scraper for Bergamot Station Arts Center events.
Source: https://bergamotstation.com
Note: Bergamot Station primarily hosts open house events and gallery shows
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class BergamotStationScraper(BaseScraper):
    """Scraper for Bergamot Station Arts Center events."""

    def __init__(self):
        super().__init__('Bergamot Station Arts Center')
        self.base_url = 'https://bergamotstation.com'
        self.events_url = f'{self.base_url}/exhibitions'

    def scrape(self) -> List[Event]:
        """
        Scrape exhibitions from Bergamot Station website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch exhibitions page")
                return events

            soup = self.parse_html(html)

            # Find exhibition items - typically in article or a tags
            event_items = soup.find_all('article', class_=re.compile(r'event|exhibition', re.IGNORECASE))

            if not event_items:
                # Try finding exhibition links
                event_items = soup.find_all('a', href=re.compile(r'/exhibitions/[a-z0-9-]+'))

            self.log(f"Found {len(event_items)} exhibition items")

            # Track unique URLs to avoid duplicates
            seen_urls = set()
            for item in event_items:
                try:
                    # If item is a link, get its parent container
                    container = item if item.name != 'a' else item.find_parent(['article', 'div', 'section'])
                    if not container:
                        container = item

                    event = self._parse_event(container)
                    if event and event.url not in seen_urls:
                        seen_urls.add(event.url)
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing exhibition: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} exhibitions")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single exhibition item.

        Args:
            item: BeautifulSoup element containing exhibition data

        Returns:
            Event object or None
        """
        # Extract URL first
        url = self.events_url
        link = item.find('a', href=re.compile(r'/exhibitions/')) if item.name != 'a' else item
        if link and link.get('href'):
            url = self.normalize_url(link['href'], self.base_url)

        # Extract title from h2 element
        title_elem = item.find(['h2', 'h3', 'h1'])
        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())
        if not title:
            return None

        # Extract gallery name from title (format: "Gallery Name - Exhibition Title")
        gallery_name = "Bergamot Station Arts Center"
        if ' - ' in title:
            parts = title.split(' - ', 1)
            gallery_name = parts[0].strip()
            # Keep full title for the event

        # Extract description
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract dates. Prefer the structured <time> elements (robust, and they
        # carry the opening time); fall back to the "Oct 11 to Nov 22" text.
        event_date = None
        end_date = None
        text_content = item.get_text()

        def _cls(t):
            return ' '.join(t.get('class') or [])

        date_el = next((t for t in item.find_all('time')
                        if t.get('datetime') and 'event-date' in _cls(t)), None)
        if date_el:
            try:
                event_date = date_parser.parse(date_el['datetime'])
                # Opening time, if exposed (e.g. <time class="event-time-12hr">11:00 AM</time>)
                time_el = next((t for t in item.find_all('time')
                                if 'time-12hr' in _cls(t) and t.get_text(strip=True)), None)
                if time_el:
                    try:
                        tt = date_parser.parse(time_el.get_text(strip=True))
                        event_date = event_date.replace(hour=tt.hour, minute=tt.minute)
                    except Exception:
                        pass
            except Exception as e:
                self.log(f"Error parsing <time> date: {e}")
                event_date = None

        # Date-range text ("Oct 11 to Nov 22") supplies the end date (and the
        # start date as a fallback when no <time> element was found).
        date_match = re.search(
            r'([A-Z][a-z]{2})\s+(\d{1,2})\s+to\s+([A-Z][a-z]{2})\s+(\d{1,2})', text_content)
        if date_match:
            try:
                current_year = datetime.now().year
                if event_date is None:
                    event_date = date_parser.parse(
                        f"{date_match.group(1)} {date_match.group(2)}, {current_year}")
                end_date = date_parser.parse(
                    f"{date_match.group(3)} {date_match.group(4)}, {current_year}")
                if end_date < event_date:
                    end_date = date_parser.parse(
                        f"{date_match.group(3)} {date_match.group(4)}, {current_year + 1}")
            except Exception as e:
                self.log(f"Error parsing date range: {e}")

        # Address - Bergamot Station in Santa Monica
        address = "2525 Michigan Ave, Santa Monica, CA 90404"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('data-image', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - art galleries and exhibitions
        category = "Art"

        # Price info - typically free admission
        is_free = True
        price = None
        price_note = "Free admission"

        return self.create_event(
            title=title,
            description=description,
            venue_name=gallery_name,
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

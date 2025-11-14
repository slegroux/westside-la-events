"""
Scraper for Getty Center events.
Source: https://www.getty.edu/visit/calendar/
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class GettyCenterScraper(BaseScraper):
    """Scraper for Getty Center events."""

    def __init__(self):
        super().__init__('Getty Center')
        self.base_url = 'https://www.getty.edu'
        self.events_url = f'{self.base_url}/visit/calendar/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Getty Center website.

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

            # Find all event links following the pattern /visit/cal/events/ev_*.html
            event_links = soup.find_all('a', href=re.compile(r'/visit/cal/events/ev_\d+\.html'))

            self.log(f"Found {len(event_links)} event items")

            # Process unique event URLs
            seen_urls = set()
            for link in event_links:
                try:
                    url = self.normalize_url(link['href'], self.base_url)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    # Find the event container
                    event_container = link.find_parent(['div', 'article', 'section'])
                    if event_container:
                        event = self._parse_event(event_container, url)
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
        # Extract title from h4 element
        title_elem = item.find('h4')
        if not title_elem:
            title_elem = item.find('a', href=re.compile(r'/visit/cal/events/'))
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Remove category tags like [FILM], [TOURS], [EXHIBITIONS] from title
        title = re.sub(r'\[.*?\]', '', title).strip()

        # Extract description - usually in a p tag or text node after title
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract category from bracketed tags
        category = ""
        category_match = re.search(r'\[(.*?)\]', item.get_text())
        if category_match:
            category_text = category_match.group(1).lower()
            # Map Getty categories to our categories
            category_map = {
                'film': 'Film & Screenings',
                'tours': 'Tours & Experiences',
                'exhibitions': 'Art & Museums',
                'music': 'Music & Concerts',
                'performance': 'Performing Arts',
                'family': 'Family & Kids'
            }
            category = category_map.get(category_text, '')

        # Extract date/time
        event_date = None
        # Look for date strings like "Friday OCT 25" or time strings like "6:30 pm"
        date_text = item.get_text()

        # Try to find date and time patterns
        date_match = re.search(r'([A-Z][a-z]+)\s+([A-Z]{3})\s+(\d{1,2})', date_text)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', date_text, re.IGNORECASE)

        if date_match:
            try:
                # Construct date string from matches
                month = date_match.group(2)
                day = date_match.group(3)
                current_year = datetime.now().year
                date_str = f"{month} {day} {current_year}"

                if time_match:
                    date_str += f" {time_match.group(1)}"

                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date: {e}")

        # Venue info - Getty Center
        venue_name = "Getty Center"
        address = "1200 Getty Center Dr, Los Angeles, CA 90049"

        # Extract image
        image_url = ""
        img_elem = item.find('img', src=re.compile(r'/visit/cal/images/'))
        if img_elem:
            image_url = self.normalize_url(img_elem.get('src', ''), self.base_url)

        # Price info - Getty Center admission is free, parking is $20
        is_free = True
        price = None
        price_note = "Free admission; parking $20 ($15 after 3 PM)"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

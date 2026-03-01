"""
Scraper for Skirball Cultural Center events.
Source: https://www.skirball.org/programs/public-programs
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class SkirballScraper(BaseScraper):
    """Scraper for Skirball Cultural Center events."""

    def __init__(self):
        super().__init__('Skirball Cultural Center')
        self.base_url = 'https://www.skirball.org'
        self.events_url = f'{self.base_url}/programs/public-programs'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Skirball Cultural Center website.

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

            # Find all event items - they're in article.node-type--event elements
            event_items = soup.find_all('article', class_=lambda x: x and 'node-type--event' in (x if isinstance(x, list) else [x]))

            if not event_items:
                # Fallback: any article with an h3 link
                event_items = [a for a in soup.find_all('article') if a.find('h3') and a.find('a', href=True)]

            self.log(f"Found {len(event_items)} event items")

            for item in event_items:
                try:
                    event = self._parse_event(item)
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

    def _parse_event(self, item) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object or None
        """
        # Extract title from h3 > a element
        title_elem = item.find('h3')
        if not title_elem:
            return None

        link_elem = title_elem.find('a', href=True)
        if not link_elem:
            return None

        title = self.clean_text(link_elem.get_text())
        url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract description from p > span element (actual content, not dates)
        description = ""
        span_elem = item.find('span')
        if span_elem:
            description = self.clean_text(span_elem.get_text())
        else:
            desc_elem = item.find('p')
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())

        # Extract date/time from p.dates element
        # Format: "Sunday, March 8, 2:00–5:00 pm"
        event_date = None
        date_elem = item.find('p', class_='dates')
        if date_elem:
            date_text = self.clean_text(date_elem.get_text())
            try:
                import re
                # Replace en-dash time ranges to keep only start time
                date_text_clean = re.sub(r'(\d{1,2}:\d{2})\s*[–-]\s*\d{1,2}:\d{2}', r'\1', date_text)
                event_date = date_parser.parse(date_text_clean, fuzzy=True)
                if event_date.year < datetime.now().year:
                    event_date = event_date.replace(year=datetime.now().year)
            except Exception as e:
                self.log(f"Error parsing date '{date_text}': {e}")

        # Extract category from dl.skirball-tags > dd.category
        category = ""
        cat_elem = item.find('dd', class_='category')
        if cat_elem:
            cat_text = self.clean_text(cat_elem.get_text()).lower()
            if 'film' in cat_text or 'screening' in cat_text:
                category = 'Film & Screenings'
            elif 'music' in cat_text or 'concert' in cat_text:
                category = 'Music & Concerts'
            elif 'performance' in cat_text or 'theater' in cat_text:
                category = 'Performing Arts'
            elif 'family' in cat_text or 'kids' in cat_text:
                category = 'Family & Kids'
            else:
                category = 'Arts & Culture'

        # Venue info - Skirball Cultural Center in Brentwood
        venue_name = "Skirball Cultural Center"
        address = "2701 N Sepulveda Blvd, Los Angeles, CA 90049"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - varies by event
        is_free = False
        price = None
        price_note = "TBD"

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

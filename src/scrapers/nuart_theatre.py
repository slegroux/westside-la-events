"""
Scraper for Nuart Theatre events.
Source: https://www.landmarktheatres.com/los-angeles/nuart-theatre
Note: This page uses JavaScript to load content dynamically
"""
from datetime import datetime, timedelta
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class NuartTheatreScraper(BaseScraper):
    """Scraper for Nuart Theatre events."""

    def __init__(self):
        super().__init__('Nuart Theatre')
        self.base_url = 'https://www.landmarktheatres.com'
        self.theatre_url = f'{self.base_url}/los-angeles/nuart-theatre'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Nuart Theatre website.
        Requires JavaScript rendering.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the page with JavaScript rendering
            html = self.fetch_page_js(
                self.theatre_url,
                wait_selector='.css-19kfbo9, [class*="movie"], article',
                timeout=45000
            )
            if not html:
                self.log("Failed to fetch theatre page")
                return events

            soup = self.parse_html(html)

            # Find movie cards or article elements
            movie_items = soup.find_all(['article', 'div'], class_=re.compile(r'movie|film|card', re.IGNORECASE))

            if not movie_items:
                # Try alternative selector
                movie_items = soup.find_all('a', href=re.compile(r'/film/|/movie/'))

            self.log(f"Found {len(movie_items)} movie items")

            seen_titles = set()
            for item in movie_items:
                try:
                    event = self._parse_event(item)
                    if event and event.title not in seen_titles:
                        seen_titles.add(event.title)
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
        # Extract title
        title_elem = item.find(['h1', 'h2', 'h3', 'h4'])
        if not title_elem:
            title_elem = item.find('a', href=True)

        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())
        if not title:
            return None

        # Extract URL
        url = self.theatre_url
        link = item.find('a', href=True)
        if link:
            url = self.normalize_url(link['href'], self.base_url)

        # Extract description
        description = ""
        desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time - Nuart often has specific showtimes
        event_date = None
        time_elem = item.find(['time', 'span'], class_=lambda x: x and ('time' in str(x).lower() or 'date' in str(x).lower()))

        if time_elem:
            date_str = time_elem.get('datetime', '') or time_elem.get_text()
            try:
                event_date = date_parser.parse(date_str)
            except Exception:
                pass

        # If no specific date found, default to today (movies showing now)
        if not event_date:
            event_date = datetime.now()

        # Venue info - Nuart Theatre in West LA
        venue_name = "Nuart Theatre"
        address = "11272 Santa Monica Blvd, Los Angeles, CA 90025"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url and not image_url.startswith('http'):
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - film screenings
        category = "Film & Screenings"

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
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

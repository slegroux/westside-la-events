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
            # Use domcontentloaded + extra wait since networkidle never fires
            html = self.fetch_page_js(
                self.theatre_url,
                wait_selector='a[href*="/movies/"]',
                timeout=35000
            )
            if not html:
                self.log("Failed to fetch theatre page")
                return events

            soup = self.parse_html(html)

            # Each currently-showing film has an <a href="/movies/..."> containing title + director <p> tags
            movie_links = soup.find_all('a', href=lambda x: x and '/movies/' in str(x))

            self.log(f"Found {len(movie_links)} movie links")

            seen_urls = set()
            for link in movie_links:
                try:
                    event = self._parse_event(link)
                    url = self.normalize_url(link.get('href', ''), self.base_url)
                    if event and url not in seen_urls:
                        seen_urls.add(url)
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
        # Each item is an <a> tag with movie name and director in deeply nested text
        # Use separator to get ordered text chunks: "TITLE|A film by DIRECTOR"
        parts = [p for p in item.get_text(separator='|', strip=True).split('|') if p]
        if not parts:
            return None

        title = self.clean_text(parts[0])
        if not title or title.lower().startswith('a film by'):
            return None

        # Build description from director credit
        director_parts = [p for p in parts[1:] if p.lower().startswith('a film by')]
        description = self.clean_text(director_parts[0]) if director_parts else ""

        # Extract URL from the link itself
        url = self.normalize_url(item.get('href', self.theatre_url), self.base_url)

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
        category = "Film"

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

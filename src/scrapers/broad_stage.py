"""
Scraper for The Broad Stage events.
Source: https://www.thebroadstage.org/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class BroadStageScraper(BaseScraper):
    """Scraper for The Broad Stage events."""

    def __init__(self):
        super().__init__('The Broad Stage')
        self.base_url = 'https://broadstage.org'
        # The season landing page rolls over each year (e.g. /2526-season/ ->
        # /2627-season/). Default to the current cycle but resolve the live
        # link at scrape time so we don't go stale when the site advances.
        self.events_url = f'{self.base_url}/2627-season/'

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Broad Stage website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            events_url = self._resolve_season_url()

            # Fetch the events page (requires JavaScript to render the cards)
            html = self.fetch_page_js(events_url, wait_selector='.inner h3')
            if not html:
                # Try without JS
                html = self.fetch_page(events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find all show items — each is a div.inner with p.heading (date) + h3 (title) + a (link)
            event_items = [
                d for d in soup.find_all('div', class_='inner')
                if d.find('p', class_='heading') and d.find('h3')
            ]

            self.log(f"Found {len(event_items)} event items")

            seen_urls = set()
            for item in event_items:
                try:
                    link = item.find('a', href=True)
                    if not link:
                        continue
                    url = self.normalize_url(link['href'], self.base_url)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    event = self._parse_event(item, url)
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

    def _resolve_season_url(self) -> str:
        """Find the current ``/NNNN-season/`` landing page.

        Broad Stage advances the season slug every year (2526 -> 2627 -> ...),
        which silently breaks a hardcoded URL. Read the site's nav and pick the
        highest season slug present; fall back to the configured default.
        """
        try:
            home = self.fetch_page(self.base_url) or ""
            slugs = re.findall(r'/(\d{4})-season/', home)
            if slugs:
                best = max(slugs, key=int)
                return f"{self.base_url}/{best}-season/"
        except Exception as e:
            self.log(f"Season URL resolution failed, using default: {e}")
        return self.events_url

    def _parse_event(self, item, url: str) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data
            url: Event detail URL

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

        # Extract description
        description = ""
        desc_elem = item.find('p', class_=lambda x: x and 'desc' in str(x).lower())
        if not desc_elem:
            desc_elem = item.find('p')
        if desc_elem:
            description = self.clean_text(desc_elem.get_text())

        # Extract date/time from p.heading (e.g. "February 27, 2026" or "April 18-19, 2026")
        event_date = None
        date_elem = item.find('p', class_='heading')
        if date_elem:
            date_str = self.clean_text(date_elem.get_text())
            # Handle date ranges — use the start date. Covers same-month
            # ("April 18-19, 2026") and cross-month ("September 22-November 1,
            # 2026") forms by dropping everything from the range dash to the
            # trailing year.
            start = re.sub(r'\s*-\s*.*?(\d{4})\s*$', r', \1', date_str)
            try:
                event_date = date_parser.parse(start, fuzzy=True)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Venue info - The Broad Stage in Santa Monica
        venue_name = "The Broad Stage"
        address = "1310 11th St, Santa Monica, CA 90401"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Category - performing arts venue
        category = "Theater"

        # Price info — unknown at the listing level; leave the note empty so the
        # card renders no price badge (project pricing convention).
        is_free = False
        price = None
        price_note = ""

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

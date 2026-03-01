"""
Scraper for La Puglia restaurant special events.
Source: https://lapuglia.us/events

La Puglia is an Italian restaurant in Santa Monica that hosts special dining events,
live music, themed dinners, and seasonal menus. Events are displayed as individual
pages linked from the main events page.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class LaPugliaScraper(BaseScraper):
    """Scraper for La Puglia restaurant events."""

    def __init__(self):
        super().__init__('La Puglia')
        self.base_url = 'https://lapuglia.us'
        self.events_url = f'{self.base_url}/events'
        self.venue_name = 'La Puglia'
        self.venue_address = '2830 Ocean Park Blvd, Santa Monica, CA 90405'

    def scrape(self) -> List[Event]:
        """
        Scrape events from La Puglia.

        Process:
        1. Fetch the main events page to find all event page links
        2. Visit each event page to extract details

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the main events page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            # Parse the HTML to find event page links
            # The HTML is minified and has a non-standard format:
            # <link prefetch="" prerender="/event-path">
            # We need to use regex to extract these paths
            event_links = []

            # Find all prefetch/prerender patterns in the HTML
            # Pattern: prerender="/some-path"
            pattern = r'prerender="(/[^"]+)"'
            matches = re.findall(pattern, html)

            for path in matches:
                if self._is_event_link(path):
                    event_links.append(path)

            self.log(f"Found {len(event_links)} event page links")

            # Prefetch all event pages concurrently
            if event_links:
                self.prefetch_pages([f'{self.base_url}{path}' for path in event_links])

            # Visit each event page and extract details
            for i, event_path in enumerate(event_links, 1):
                try:
                    event_url = f'{self.base_url}{event_path}'
                    event = self._scrape_event_page(event_url)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_links)}: {event.title}")
                except Exception as e:
                    self.log(f"Error scraping event page {event_url}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        # Filter out past events
        now = datetime.now()
        events = [e for e in events if e.event_date is None or e.event_date >= (now - timedelta(days=1))]

        self.log(f"Scraped {len(events)} upcoming events")
        return events

    def _is_event_link(self, href: str) -> bool:
        """
        Determine if a link represents an event page.

        Args:
            href: Link href attribute

        Returns:
            True if this is likely an event page
        """
        # Skip certain paths that are not events
        skip_patterns = [
            '/store', '/blog', '/menu', '/catering', '/contact', '/our-story',
            '/private-parties-menu', '/breakfast-brunch', '/lunch-dinner', '/happy-hour',
            '/food-gallery', '/gift-ideas', '/career', '/home', '/events-copy',
            '/cooking-classes', '/musician-menu', '/la-puglia-band', '/la-puglia-blog',
            '/full-menu', '/lunch-tasting-menu', '/'
        ]

        # Check if it matches a skip pattern
        for pattern in skip_patterns:
            if href == pattern or href.startswith(pattern + '/'):
                return False

        # Check for event-like patterns (holidays, special occasions, years)
        event_patterns = [
            r'valentine',  # Valentine's Day
            r'nye|new-year',  # New Year's Eve/Day
            r'thanksgiving',  # Thanksgiving
            r'christmas',  # Christmas
            r'easter',  # Easter
            r'202[0-9]',  # Contains a year (2020-2029)
            r'dinner',  # Special dinners
            r'night',  # Special nights (e.g., Amativo Night)
        ]

        # If it matches any event pattern, it's likely an event
        href_lower = href.lower()
        for pattern in event_patterns:
            if re.search(pattern, href_lower):
                return True

        # Default: not an event
        return False

    def _scrape_event_page(self, url: str) -> Optional[Event]:
        """
        Scrape a single event page.

        Args:
            url: URL of the event page

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Fetch the event page
            html = self.fetch_page(url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'lxml')

            # Extract title from page title or h1
            title = None
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text().strip()
                # Remove " - La Puglia" suffix if present
                title = title_text.replace(' - La Puglia', '').strip()

            if not title or title == 'Events':
                # Try to get from h1
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text().strip()

            if not title:
                self.log(f"No title found for {url}")
                return None

            # Try to parse date from the URL slug or title
            event_date = self._parse_date_from_context(url, title)

            # Look for description in meta tags or body content
            description = ''

            # Try Open Graph description
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                description = og_desc['content'].strip()

            # Try meta description
            if not description:
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    description = meta_desc['content'].strip()

            # If still no description, try to extract from body (would need JS rendering)
            if not description:
                description = f"Special event at {self.venue_name}"

            # Try to extract image from Open Graph
            image_url = ''
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']

            # Create the event
            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category='Food',  # La Puglia is a restaurant
                price_note='TBD'  # Pricing details typically require calling
            )

        except Exception as e:
            self.log(f"Error parsing event page {url}: {e}")
            return None

    def _holiday_dates_for_year(self, year: int) -> dict:
        """Return approximate holiday dates for the given year."""
        import calendar
        # Easter: compute via a simple algorithm (anonymous Gregorian)
        a = year % 19
        b, c = divmod(year, 100)
        d, e = divmod(b, 4)
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = divmod(c, 4)
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = ((h + l - 7 * m + 114) % 31) + 1
        easter_str = f'{year}-{month:02d}-{day:02d}'
        # Thanksgiving: 4th Thursday of November
        nov_first_weekday = calendar.weekday(year, 11, 1)
        days_to_thursday = (3 - nov_first_weekday) % 7
        thanksgiving_day = 1 + days_to_thursday + 21
        thanksgiving_str = f'{year}-11-{thanksgiving_day:02d}'
        return {
            'valentine': f'{year}-02-14',
            'easter': easter_str,
            'thanksgiving': thanksgiving_str,
            'christmas': f'{year}-12-25',
            'nye': f'{year}-12-31',
            'new-year': f'{year}-12-31',
        }

    def _parse_date_from_context(self, url: str, title: str) -> Optional[datetime]:
        """
        Try to parse event date from URL slug or title.

        Args:
            url: Event page URL
            title: Event title

        Returns:
            datetime object or None if no date found
        """
        current_year = datetime.now().year
        text = (url + ' ' + title).lower()

        # Check for explicit year in URL or title (e.g. 2025, 2026, ...)
        year_match = re.search(r'(20\d{2})', url + ' ' + title)
        year = int(year_match.group(1)) if year_match else current_year

        holiday_dates = self._holiday_dates_for_year(year)

        # Check if URL/title contains a holiday name
        for holiday, date_str in holiday_dates.items():
            if holiday in text:
                try:
                    return date_parser.parse(date_str)
                except Exception:
                    pass

        # Try to find explicit date patterns in title
        date_patterns = [
            r'([A-Z][a-z]+)\s+(\d{1,2}),?\s*(20\d{2})?',  # "February 14, 2026"
            r'(\d{1,2})[/-](\d{1,2})[/-](20\d{2})',        # "2/14/2026"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, title + ' ' + url)
            if match:
                try:
                    date_str = match.group(0)
                    if not re.search(r'20\d{2}', date_str):
                        date_str += f' {year}'
                    return date_parser.parse(date_str)
                except Exception:
                    continue

        return None

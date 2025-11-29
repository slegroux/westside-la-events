"""
Scraper for La Puglia restaurant special events.
Source: https://lapuglia.us/events

La Puglia is an Italian restaurant in Santa Monica that hosts special dining events,
live music, themed dinners, and seasonal menus. Events are displayed as individual
pages linked from the main events page.
"""
import re
from datetime import datetime
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

        self.log(f"Scraped {len(events)} events")
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

    def _parse_date_from_context(self, url: str, title: str) -> Optional[datetime]:
        """
        Try to parse event date from URL slug or title.

        Args:
            url: Event page URL
            title: Event title

        Returns:
            datetime object or None if no date found
        """
        # Common holiday/event date patterns
        holiday_dates_2025 = {
            'valentine': '2025-02-14',
            'easter': '2025-04-20',
            'thanksgiving': '2025-11-27',
            'christmas': '2025-12-25',
            'nye': '2025-12-31',
            'new-year': '2025-12-31'
        }

        holiday_dates_2024 = {
            'valentine': '2024-02-14',
            'easter': '2024-03-31',
            'thanksgiving': '2024-11-28',
            'christmas': '2024-12-25',
            'nye': '2024-12-31',
            'new-year': '2024-12-31'
        }

        # Check for explicit year in URL or title
        year_match = re.search(r'(202[45])', url + ' ' + title)
        year = year_match.group(1) if year_match else '2025'  # Default to 2025

        # Select appropriate holiday date mapping
        holiday_dates = holiday_dates_2025 if year == '2025' else holiday_dates_2024

        # Check if URL/title contains a holiday name
        text = (url + ' ' + title).lower()
        for holiday, date_str in holiday_dates.items():
            if holiday in text:
                try:
                    return date_parser.parse(date_str)
                except:
                    pass

        # Try to find date patterns in title or URL
        # Format: "Month Day" or "Month Day, Year"
        date_patterns = [
            r'([A-Z][a-z]+)\s+(\d{1,2}),?\s*(202[45])?',  # "February 14, 2025" or "February 14"
            r'(\d{1,2})[/-](\d{1,2})[/-](202[45])',  # "2/14/2025"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, title + ' ' + url)
            if match:
                try:
                    date_str = match.group(0)
                    if not re.search(r'202[45]', date_str):
                        date_str += f' {year}'
                    return date_parser.parse(date_str)
                except:
                    continue

        # If no specific date found, return None
        # (Event will still be created, just without a specific date)
        return None

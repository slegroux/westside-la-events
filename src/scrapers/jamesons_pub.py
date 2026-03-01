"""
Scraper for Jameson's Irish Pub Santa Monica events.
Source: https://santamonica.jamesonsirishpub.com/santa-monica-jameson-s-pub-santa-monica-events

Jameson's Pub is an authentic Irish pub in Santa Monica offering sports viewing,
holiday celebrations, live music, trivia nights, and pub events.
"""
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class JamesonsPubScraper(BaseScraper):
    """Scraper for Jameson's Irish Pub Santa Monica events."""

    VENUE_FALLBACK_IMAGE = 'https://static.spotapps.co/web/santamonica--jamesonsirishpub--com/custom/about_us_right.jpg'

    def __init__(self):
        super().__init__('Jamesons Pub')
        self.events_url = 'https://santamonica.jamesonsirishpub.com/santa-monica-jameson-s-pub-santa-monica-events'
        self.venue_name = "Jameson's Pub - Santa Monica"
        self.venue_address = '221 Broadway, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Jameson's Pub.

        The site uses a simple structure with repeating event blocks.
        Each event has embedded calendar data in <var> tags within an
        "addtocalendar" span.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the page HTML
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Find all event sections - they're in divs with class "events-holder"
            event_sections = soup.find_all('div', class_='events-holder')
            self.log(f"Found {len(event_sections)} event sections")

            for i, section in enumerate(event_sections, 1):
                try:
                    event = self._parse_event_section(section)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_sections)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event section {i}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        self.log(f"Scraped {len(events)} events")
        return events

    def _parse_event_section(self, section) -> Optional[Event]:
        """
        Parse an event from an event section element.

        Args:
            section: BeautifulSoup element for an event section

        Returns:
            Event object or None
        """
        try:
            # Extract title from <h2>
            title_elem = section.find('h2')
            if not title_elem:
                return None

            title = title_elem.get_text().strip()
            if not title:
                return None

            # Extract description from the event-info-text div
            description = ''
            desc_elem = section.find('div', class_='event-info-text')
            if desc_elem:
                # Get the <p> text
                p_elem = desc_elem.find('p')
                if p_elem:
                    description = p_elem.get_text().strip()

            if not description:
                description = f"Event at {self.venue_name}"

            # Extract date from the embedded calendar data
            # The data is in <var> tags with specific classes
            event_date = None
            date_start_elem = section.find('var', class_='atc_date_start')
            if date_start_elem:
                date_text = date_start_elem.get_text().strip()
                # Format: "2025-12-25 11:00:00"
                event_date = self._parse_datetime(date_text)

            # Extract time display (for reference)
            time_elem = section.find('h3', class_='event-time')
            time_text = ''
            if time_elem:
                time_text = time_elem.get_text().strip()
                # Format: "11:00 AM - 02:00 AM"
                # Add to description if available
                if time_text:
                    description = f"{description}\n\nTime: {time_text}"

            # Extract date subtitle for display
            date_subtitle = ''
            h3_elems = section.find_all('h3')
            if len(h3_elems) > 0:
                # First h3 after h2 is usually the date subtitle
                date_subtitle = h3_elems[0].get_text().strip()
                # Format: "Thursday December 25th"

            # Don't set URL since all events share the same events page
            # This prevents them from being detected as duplicates
            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=None,
                image_url=self.VENUE_FALLBACK_IMAGE,
                category='Nightlife',
                price_note='TBD'
            )

        except Exception as e:
            self.log(f"Error parsing event section: {e}")
            return None

    def _parse_datetime(self, date_text: str) -> Optional[datetime]:
        """
        Parse datetime from format like "2025-12-25 11:00:00"

        Args:
            date_text: Datetime string from the calendar data

        Returns:
            datetime object or None
        """
        try:
            # Parse ISO-like format
            parsed_date = datetime.strptime(date_text, '%Y-%m-%d %H:%M:%S')
            return parsed_date

        except Exception as e:
            self.log(f"Error parsing datetime '{date_text}': {e}")
            # Try with dateutil as fallback
            try:
                parsed_date = date_parser.parse(date_text)
                return parsed_date
            except:
                return None

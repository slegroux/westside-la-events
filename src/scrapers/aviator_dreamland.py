"""
Scraper for Aviator Nation Dreamland events in Malibu.
Source: https://aviatornationdreamland.com/pages/event-calendar-custom

Aviator Nation Dreamland is an iconic music venue reborn in Malibu featuring live music,
weekly performances, and ticketed events. The venue hosts a custom calendar on their
Shopify site with events linked to tixr.com for ticketing.
"""
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class AviatorDreamlandScraper(BaseScraper):
    """Scraper for Aviator Nation Dreamland music venue events."""

    def __init__(self):
        super().__init__('Aviator Nation Dreamland')
        self.base_url = 'https://aviatornationdreamland.com'
        self.calendar_url = f'{self.base_url}/pages/event-calendar-custom'
        self.venue_name = 'Aviator Nation Dreamland'
        self.venue_address = '26025 Pacific Coast Highway, Malibu, CA 90265'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aviator Nation Dreamland calendar.

        Process:
        1. Fetch the custom calendar page
        2. Parse the embedded calendar structure
        3. Extract event details (title, date, time, URL)

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the calendar page
            html = self.fetch_page(self.calendar_url)
            if not html:
                self.log("Failed to fetch calendar page")
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Find all calendar sections (one per month)
            calendar_sections = soup.find_all('div', class_=re.compile(r'event-calendar-block-horizontal-1'))
            self.log(f"Found {len(calendar_sections)} calendar sections")

            for section in calendar_sections:
                # Extract month and year from section
                month_elem = section.find('div', class_='event-calendar-month')
                if not month_elem:
                    continue

                # Get month name and year
                month_text = month_elem.get_text(strip=True)

                # Find year (could be in next sibling or nearby)
                year_elem = section.find_all('div', class_='event-calendar-month')
                year_text = None
                if len(year_elem) > 1:
                    year_text = year_elem[1].get_text(strip=True)

                if not year_text or not year_text.isdigit():
                    # Default to current year if not found
                    year_text = str(datetime.now().year)

                self.log(f"Processing {month_text} {year_text} calendar")

                # Find all event blocks
                event_blocks = section.find_all('div', class_='event-calendar-block')

                for block in event_blocks:
                    try:
                        # Get day number
                        day_elem = block.find('div', class_=re.compile(r'event-calendar-block-day'))
                        if not day_elem:
                            continue

                        day_text = day_elem.get_text(strip=True)
                        if not day_text or not day_text.isdigit():
                            continue

                        day = int(day_text)

                        # Check if this block has an event (has a link)
                        event_link = block.find('a', href=True)
                        if not event_link or not event_link.get('href'):
                            continue

                        url = event_link['href']

                        # Skip non-dreamland events (e.g., composersbreakfastclub)
                        if 'tixr.com/groups/dreamland' not in url:
                            continue

                        # Extract title from richtext
                        title_elem = block.find('div', class_='event-calendar-block-richtext')
                        if not title_elem:
                            continue

                        # Get all <p> tags for title (could be multi-line)
                        title_parts = [p.get_text(strip=True) for p in title_elem.find_all('p')]
                        title = ' - '.join(title_parts) if title_parts else 'Event'

                        # Extract time from small-text
                        time_elem = block.find('div', class_='event-calendar-block-small-text')
                        time_text = ''
                        if time_elem:
                            time_parts = [p.get_text(strip=True) for p in time_elem.find_all('p')]
                            time_text = ' | '.join(time_parts)

                        # Parse event date
                        try:
                            date_str = f"{month_text} {day}, {year_text}"
                            event_date = date_parser.parse(date_str)
                        except:
                            self.log(f"Failed to parse date: {date_str}")
                            continue

                        # Build description
                        description = f"Live music event at {self.venue_name} in Malibu."
                        if time_text:
                            description = f"{time_text} | {description}"

                        # Create event
                        event = self.create_event(
                            title=title,
                            description=description,
                            venue_name=self.venue_name,
                            address=self.venue_address,
                            event_date=event_date,
                            url=url,
                            image_url='',  # No images in calendar
                            category='Music',  # Music venue
                            price_note='TBD'  # Ticketing via tixr.com
                        )

                        if event:
                            events.append(event)
                            self.log(f"  ✓ {title} on {event_date.strftime('%b %d')}")

                    except Exception as e:
                        self.log(f"Error parsing event block: {e}")
                        continue

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        self.log(f"Scraped {len(events)} events")
        return events

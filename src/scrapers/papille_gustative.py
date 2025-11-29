"""
Scraper for Papille Gustative restaurant events.
Source: https://papillegustativela.com/santa-monica-main-street-santa-monica-papille-gustative-events

Papille Gustative is a farm-to-table cafe-restaurant in Santa Monica offering
special events like holiday celebrations and seasonal gatherings.
"""
import asyncio
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .base import BaseScraper
from src.data.models import Event


class PapilleGustativeScraper(BaseScraper):
    """Scraper for Papille Gustative events."""

    def __init__(self):
        super().__init__('Papille Gustative')
        self.events_url = 'https://papillegustativela.com/santa-monica-main-street-santa-monica-papille-gustative-events'
        self.venue_name = 'Papille Gustative'
        self.venue_address = '618 Santa Monica Blvd, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Papille Gustative.

        The site uses JavaScript to load events, so we need Playwright.
        Events are in divs with class 'row event-content'.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Use async function to fetch page with Playwright
            html = asyncio.run(self._fetch_with_playwright())
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = BeautifulSoup(html, 'lxml')

            # Find all event containers
            # Events are in <div class="row event-content">
            event_containers = soup.find_all('div', class_='event-content')
            self.log(f"Found {len(event_containers)} events")

            for i, container in enumerate(event_containers, 1):
                try:
                    event = self._parse_event(container)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_containers)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        self.log(f"Scraped {len(events)} events")
        return events

    async def _fetch_with_playwright(self) -> Optional[str]:
        """
        Fetch page HTML using Playwright to render JavaScript.

        Returns:
            HTML string or None
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                self.log(f"Fetching {self.events_url} with Playwright...")
                await page.goto(self.events_url, wait_until='networkidle', timeout=30000)

                # Wait for events to load
                await asyncio.sleep(3)

                html = await page.content()
                await browser.close()

                return html

        except Exception as e:
            self.log(f"Error fetching page with Playwright: {e}")
            return None

    def _parse_event(self, container) -> Optional[Event]:
        """
        Parse an event from an event container element.

        Args:
            container: BeautifulSoup element for an event container

        Returns:
            Event object or None
        """
        try:
            # Find the event text holder which contains title and date
            text_holder = container.find('div', class_='event-text-holder')
            if not text_holder:
                return None

            # Extract title - it's in an <h2> tag
            title_elem = text_holder.find('h2')
            if not title_elem:
                return None

            title = title_elem.get_text().strip()
            if not title:
                return None

            # Extract date - it's in the first <h3> tag
            date_elem = text_holder.find('h3')
            date_text = ''
            if date_elem:
                date_text = date_elem.get_text().strip()

            # Extract time - it's in the second <h3> tag
            h3_tags = text_holder.find_all('h3')
            time_text = ''
            if len(h3_tags) > 1:
                time_text = h3_tags[1].get_text().strip()

            # Extract description - it's in a <p> tag (not the time one)
            desc_elem = text_holder.find('p')
            description = ''
            if desc_elem:
                description = desc_elem.get_text().strip()

            if not description:
                description = f"Special event at {self.venue_name}"

            # Parse the date and time
            event_date = self._parse_datetime(date_text, time_text)

            # Try to get exact date from the add-to-calendar section if available
            calendar_elem = container.find('div', class_='event-add-to-calendar')
            if calendar_elem and not event_date:
                # Look for datetime in the calendar data
                time_tag = calendar_elem.find('time')
                if time_tag:
                    datetime_str = time_tag.get('datetime', '')
                    if datetime_str:
                        try:
                            event_date = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                        except:
                            pass

            # Get image if available
            image_url = ''
            img_elem = container.find('img')
            if img_elem:
                image_url = img_elem.get('src', '')
                # Make sure it's a full URL
                if image_url and not image_url.startswith('http'):
                    image_url = f"https:{image_url}" if image_url.startswith('//') else f"https://papillegustativela.com{image_url}"

            # Determine category based on title/description
            category = self._determine_category(title, description)

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=self.events_url,
                image_url=image_url,
                category=category,
                price_note='TBD'
            )

        except Exception as e:
            self.log(f"Error parsing event: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_datetime(self, date_text: str, time_text: str) -> Optional[datetime]:
        """
        Parse date and time from separate text strings.

        Args:
            date_text: Date string like "Thursday December 25th"
            time_text: Time string like "11:00 AM - 09:00 PM"

        Returns:
            datetime object or None
        """
        try:
            if not date_text:
                return None

            # Clean up the date text
            date_text = date_text.strip()

            # Remove ordinal suffixes (1st, 2nd, 3rd, 4th, etc.)
            date_text = date_text.replace('st,', ',').replace('nd,', ',').replace('rd,', ',').replace('th,', ',')
            date_text = date_text.replace('st ', ' ').replace('nd ', ' ').replace('rd ', ' ').replace('th ', ' ')

            # If we have time text, extract start time
            time_str = ''
            if time_text:
                # Format is typically "11:00 AM - 09:00 PM"
                # Extract the start time
                if '-' in time_text or '–' in time_text:
                    time_str = time_text.split('-')[0].split('–')[0].strip()
                else:
                    time_str = time_text.strip()

            # Combine date and time
            full_text = f"{date_text} {time_str}".strip()

            # Parse with dateutil
            parsed_date = date_parser.parse(full_text, fuzzy=True)

            # If year is not specified, dateutil might use current year
            # Check if the date makes sense
            if parsed_date < datetime.now() and parsed_date.month >= datetime.now().month:
                # Event is in the past but same month or later - must be next year
                parsed_date = parsed_date.replace(year=datetime.now().year + 1)

            return parsed_date

        except Exception as e:
            self.log(f"Error parsing datetime from '{date_text}' and '{time_text}': {e}")
            return None

    def _determine_category(self, title: str, description: str) -> str:
        """
        Determine event category based on title and description.

        Args:
            title: Event title
            description: Event description

        Returns:
            Category string
        """
        text = f"{title} {description}".lower()

        # Check for holiday/seasonal events
        holidays = ['christmas', 'new year', 'valentine', 'easter', 'thanksgiving',
                   'halloween', 'mother', 'father', 'holiday']
        if any(holiday in text for holiday in holidays):
            return 'Food'

        # Check for music events
        music_keywords = ['music', 'concert', 'band', 'jazz', 'acoustic', 'performance']
        if any(keyword in text for keyword in music_keywords):
            return 'Music'

        # Default to Food category for a restaurant
        return 'Food'

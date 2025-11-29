"""
Scraper for Recreation Cafe events.
Source: https://www.recreation.cafe/events-1

Recreation Cafe is a social club and cafe in Santa Monica offering community events,
creative workshops, music performances, networking nights, and creative meetups.
"""
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class RecreationCafeScraper(BaseScraper):
    """Scraper for Recreation Cafe events."""

    def __init__(self):
        super().__init__('Recreation Cafe')
        self.events_url = 'https://www.recreation.cafe/events-1'
        self.venue_name = 'Recreation Cafe'
        self.venue_address = '4500 W. Washington Blvd, Los Angeles, CA 90016'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Recreation Cafe.

        The site uses Wix which renders events in the initial HTML as
        event cards with data-hook="events-card" attributes.

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

            # Find event cards - they're in <li> elements with data-hook="events-card"
            event_cards = soup.find_all('li', {'data-hook': 'events-card'})
            self.log(f"Found {len(event_cards)} event cards")

            for i, card in enumerate(event_cards, 1):
                try:
                    event = self._parse_event_card(card)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_cards)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event card {i}: {e}")
                    continue

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        self.log(f"Scraped {len(events)} events")
        return events

    def _parse_event_card(self, card) -> Optional[Event]:
        """
        Parse an event from an event card element.

        Args:
            card: BeautifulSoup element for an event card

        Returns:
            Event object or None
        """
        try:
            # Extract title from the link with data-hook="title"
            title_link = card.find('a', {'data-hook': 'title'})
            if not title_link:
                return None

            title = title_link.get_text().strip()
            if not title:
                return None

            # Extract URL from the title link
            url = title_link.get('href', '')
            if url and not url.startswith('http'):
                url = f'https://www.recreation.cafe{url}'
            if not url:
                url = self.events_url

            # Extract date from short-date element (basic date)
            date_elem = card.find('div', {'data-hook': 'short-date'})
            event_date = None
            if date_elem:
                date_text = date_elem.get_text().strip()
                # Format is like "Fri, Nov 28" or "Sat, Nov 29"
                event_date = self._parse_date(date_text)

            # Extract image URL
            image_url = ''
            img_elem = card.find('img')
            if img_elem:
                # Get the high-res image from srcset if available
                srcset = img_elem.get('srcset', '')
                if srcset:
                    # srcset format: "url 1x, url 2x"
                    # Take the 2x version for better quality
                    parts = srcset.split(',')
                    if len(parts) > 1:
                        # Get the 2x version
                        image_url = parts[1].strip().split(' ')[0]
                    else:
                        image_url = parts[0].strip().split(' ')[0]
                else:
                    image_url = img_elem.get('src', '')

            # Description - get alt text from image as a starting point
            description = ''
            if img_elem:
                description = img_elem.get('alt', '')
            if not description:
                description = f"Event at {self.venue_name}"

            # Check if it's a recurring event (has "Multiple Dates" ribbon)
            ribbon = card.find('div', {'data-hook': 'ribbon'})
            if ribbon and 'Multiple Dates' in ribbon.get_text():
                description = f"Recurring Event: {description}"

            # Fetch additional details from event detail page
            if url and url != self.events_url:
                self.log(f"Fetching details for: {title}")
                details = self._fetch_event_details(url)
                if details:
                    # Use full description if available
                    if details.get('description'):
                        description = details['description']
                    # Use full date with time if available
                    if details.get('event_date'):
                        event_date = details['event_date']
                    # Use venue address from detail page if available
                    if details.get('address'):
                        address = details['address']
                    else:
                        address = self.venue_address
                else:
                    address = self.venue_address
            else:
                address = self.venue_address

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category='Community',
                price_note='TBD'
            )

        except Exception as e:
            self.log(f"Error parsing event card: {e}")
            return None

    def _fetch_event_details(self, url: str) -> dict:
        """
        Fetch additional event details from the event detail page.

        Args:
            url: URL of the event detail page

        Returns:
            Dictionary with description, event_date, and address
        """
        try:
            html = self.fetch_page(url)
            if not html:
                return {}

            soup = BeautifulSoup(html, 'lxml')
            details = {}

            # Get full description
            desc_elem = soup.find(attrs={'data-hook': 'event-description'})
            if desc_elem:
                details['description'] = desc_elem.get_text().strip()

            # Get full date with time
            date_elem = soup.find(attrs={'data-hook': 'event-full-date'})
            if date_elem:
                date_text = date_elem.get_text().strip()
                # Format: "Nov 28, 2025, 5:00 PM – 9:00 PM"
                # Extract just the start date/time
                if '–' in date_text or '-' in date_text:
                    # Get start time only
                    date_text = date_text.split('–')[0].split('-')[0].strip()

                parsed_date = self._parse_full_date(date_text)
                if parsed_date:
                    details['event_date'] = parsed_date

            # Get full location/address
            location_elem = soup.find(attrs={'data-hook': 'event-full-location'})
            if location_elem:
                address_text = location_elem.get_text().strip()
                # Remove venue name prefix if present (e.g., "Re/creation Cafe, ")
                if ',' in address_text:
                    # Split and take everything after first comma if it starts with the venue name
                    parts = address_text.split(',', 1)
                    if len(parts) > 1:
                        # Use the part after venue name
                        address_text = parts[1].strip()
                details['address'] = address_text

            return details

        except Exception as e:
            self.log(f"Error fetching event details from {url}: {e}")
            return {}

    def _parse_full_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse full date from format like "Nov 28, 2025, 5:00 PM"

        Args:
            date_text: Full date string with time

        Returns:
            datetime object or None
        """
        try:
            # Use dateutil to parse the full date and time
            parsed_date = date_parser.parse(date_text, fuzzy=True)
            return parsed_date

        except Exception as e:
            self.log(f"Error parsing full date '{date_text}': {e}")
            return None

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse date from format like "Fri, Nov 28" or "Sat, Nov 29"

        Args:
            date_text: Date string from the event card

        Returns:
            datetime object or None
        """
        try:
            # Format is typically "Day, Month Date"
            # We need to add the year
            current_year = datetime.now().year

            # Clean up the text
            date_text = date_text.strip()

            # Parse with dateutil, adding current year
            # If month is December and we're in January, use last year
            # If month is January and we're in December, use next year
            parsed_date = date_parser.parse(f"{date_text}, {current_year}", fuzzy=True)

            # Adjust year if needed
            current_month = datetime.now().month
            if parsed_date.month == 12 and current_month == 1:
                # December event seen in January - use last year
                parsed_date = parsed_date.replace(year=current_year - 1)
            elif parsed_date.month == 1 and current_month == 12:
                # January event seen in December - use next year
                parsed_date = parsed_date.replace(year=current_year + 1)

            return parsed_date

        except Exception as e:
            self.log(f"Error parsing date '{date_text}': {e}")
            return None

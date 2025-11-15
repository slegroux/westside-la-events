"""
Scraper for Brightside California Kitchen events.
Source: https://brightsidecaliforniakitchen.com/events

Brightside is an all-day California eatery in Santa Monica offering brunch,
dinner, and special events including live jazz music on Saturdays.
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class BrightsideScraper(BaseScraper):
    """Scraper for Brightside California Kitchen events."""

    def __init__(self):
        super().__init__("Brightside California Kitchen")
        self.events_url = 'https://brightsidecaliforniakitchen.com/events'
        self.venue_name = "Brightside California Kitchen"
        self.venue_address = '2901 Ocean Park Blvd, Santa Monica, CA 90405'
        self.logo_url = 'https://static.spotapps.co/website_images/ab_websites/19630_website_v1/logo.png'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Brightside California Kitchen website.

        The events page embeds event data directly in HTML with data attributes.
        Events are displayed in calendar cards with title, date, time, and description.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find all event cards
            event_cards = soup.find_all('div', class_='event-calendar-card')
            self.log(f"Found {len(event_cards)} event cards")

            for card in event_cards:
                try:
                    event = self._parse_event_card(card)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event card: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event_card(self, card) -> Optional[Event]:
        """
        Parse a single event card.

        Args:
            card: BeautifulSoup element containing event card data

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract title
            title_elem = card.find('h2')
            title = self.clean_text(title_elem.get_text()) if title_elem else None
            if not title:
                return None

            # Extract start date from data attribute
            start_date_str = card.get('data-event-start-date')
            if not start_date_str:
                self.log(f"No start date found for event: {title}")
                return None

            # Parse start date
            event_date = date_parser.parse(start_date_str)

            # Extract end date if available
            end_date = None
            end_date_str = card.get('data-event-end-date')
            if end_date_str:
                try:
                    end_date = date_parser.parse(end_date_str)
                except Exception:
                    pass

            # Extract time from the event-time element
            time_elem = card.find('p', class_='event-time')
            time_str = self.clean_text(time_elem.get_text()) if time_elem else ""

            # Parse time and update event_date with specific time
            if time_str:
                event_date = self._parse_time_into_date(time_str, event_date)

            # Extract recurrence type
            recurrence_type = card.get('data-event-recurrence-type', '')

            # Extract description from event-info-text
            description_parts = []

            # Get the main event day text
            day_elem = card.find('p', class_='event-day')
            if day_elem:
                day_text = self.clean_text(day_elem.get_text())
                if recurrence_type and recurrence_type != 'Does not Repeat':
                    description_parts.append(day_text)

            # Get the event info (description)
            info_elem = card.find('div', class_='event-info-text')
            if info_elem:
                # Get all <p> tags within event-info-text
                info_paragraphs = info_elem.find_all('p')
                for p in info_paragraphs:
                    text = self.clean_text(p.get_text())
                    if text:
                        description_parts.append(text)

            description = '\n\n'.join(description_parts) if description_parts else ""

            # Add time info to description if available
            if time_str:
                description = f"Time: {time_str}\n\n{description}" if description else f"Time: {time_str}"

            # Determine category based on title and description
            category = self._determine_category(title, description)

            # Extract pricing info (Brightside doesn't seem to list prices on events page)
            # Most events appear to be free/included with dining
            is_free = True
            price = None

            # Create unique URL by appending event ID
            event_id = card.get('id', '')
            event_url = f"{self.events_url}#{event_id}" if event_id else self.events_url

            # Create event
            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=event_url,
                image_url=self.logo_url,  # Use logo as event image
                category=category,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing event card: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_time_into_date(self, time_str: str, base_date: datetime) -> datetime:
        """
        Parse time string like "10:30 AM - 02:00 PM" and combine with base date.

        Args:
            time_str: Time string to parse
            base_date: Base date to combine with time

        Returns:
            DateTime with time component set
        """
        # Extract start time from range (e.g., "10:30 AM - 02:00 PM" -> "10:30 AM")
        match = re.match(r'(\d{1,2}:\d{2}\s*[AP]M)', time_str, re.IGNORECASE)
        if not match:
            # Try without colon (e.g., "11:00 AM" or "11am")
            match = re.match(r'(\d{1,2}(?::\d{2})?\s*[AP]M)', time_str, re.IGNORECASE)

        if match:
            time_only_str = match.group(1)
            try:
                # Parse the time
                time_obj = datetime.strptime(time_only_str.upper().strip(), '%I:%M %p')
                # Combine with base date
                return base_date.replace(hour=time_obj.hour, minute=time_obj.minute)
            except ValueError:
                try:
                    # Try without minutes
                    time_obj = datetime.strptime(time_only_str.upper().strip(), '%I %p')
                    return base_date.replace(hour=time_obj.hour, minute=0)
                except ValueError:
                    pass

        return base_date

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

        if 'music' in text or 'jazz' in text or 'live' in text:
            return 'Music'
        elif 'thanksgiving' in text or 'christmas' in text or 'valentine' in text or "new year" in text:
            return 'Food & Drink'
        elif 'brunch' in text or 'dinner' in text or 'food' in text:
            return 'Food & Drink'
        else:
            return 'Community'

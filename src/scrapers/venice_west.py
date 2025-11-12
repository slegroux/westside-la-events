"""
Scraper for The Venice West venue events.
Source: https://www.thevenicewest.com/calendar
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class VeniceWestScraper(BaseScraper):
    """Scraper for The Venice West events."""

    def __init__(self):
        super().__init__('The Venice West')
        self.base_url = 'https://www.thevenicewest.com'
        self.calendar_url = f'{self.base_url}/calendar'
        self.venue_name = 'The Venice West'
        self.venue_address = '1910 Lincoln Blvd, Venice, CA 90291'

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Venice West calendar.

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

            soup = self.parse_html(html)

            # Find all event items (Webflow dynamic items)
            event_items = soup.find_all('div', class_='cal-info-2 w-dyn-item')
            self.log(f"Found {len(event_items)} events on calendar page")

            for i, item in enumerate(event_items, 1):
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_items)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single event from a calendar item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object
        """
        # Extract title from the b-show div
        title_elem = item.find('div', class_='b-show')
        title = self.clean_text(title_elem.get_text()) if title_elem else 'Untitled Event'

        # Extract date/time from the dates div
        date_elem = item.find('p', class_='b-venue')
        event_date = None
        if date_elem:
            date_text = self.clean_text(date_elem.get_text())
            try:
                # Parse date like "Nov 14, 2025 8:00 PM"
                event_date = date_parser.parse(date_text)
            except Exception as e:
                self.log(f"Could not parse date '{date_text}': {e}")

        # Extract event URL from the background link or buy tickets link
        event_url = self.calendar_url  # Default to calendar
        link_elem = item.find('a', href=True)
        if link_elem:
            href = link_elem.get('href', '')
            if 'tixr.com' in href:
                event_url = href
            else:
                event_url = self.normalize_url(href, self.base_url)

        # Extract image URL from style attribute of cal-container
        image_url = ''
        container = item.find('a', class_='cal-container')
        if container:
            style = container.get('style', '')
            # Extract URL from background-image:url("...")
            if 'background-image:url(' in style:
                start = style.find('url(') + 4
                end = style.find(')', start)
                image_url = style[start:end].strip('"').strip("'")
                # Normalize relative URLs
                if image_url and not image_url.startswith('http'):
                    image_url = self.normalize_url(image_url, self.base_url)

        # Extract categories/tags from filter elements
        category_tags = []
        area_filters = item.find_all('p', class_='areas filter')
        for area in area_filters:
            tag = self.clean_text(area.get_text())
            if tag:
                category_tags.append(tag)

        # Determine category from tags or title
        category = self._determine_category(category_tags, title)

        # Check if it's a free event (RSVP button visible)
        is_free = False
        price = None
        rsvp_button = item.find('a', class_='button short')
        buy_button = item.find('a', class_='button short white')

        # If RSVP button exists and is not invisible, it's free
        if rsvp_button and 'w-condition-invisible' not in rsvp_button.get('class', []):
            is_free = True
        elif buy_button:
            # Try to extract price from buy button text
            button_text = self.clean_text(buy_button.get_text())
            import re
            price_match = re.search(r'\$(\d+(?:\.\d{2})?)', button_text)
            if price_match:
                try:
                    price = float(price_match.group(1))
                except ValueError:
                    pass

        # Build description from available info
        description_parts = []

        # Add event type and title
        if category_tags:
            primary_tag = category_tags[0].title()
            description_parts.append(f"{primary_tag} event featuring {title}")
        else:
            description_parts.append(f"Live event featuring {title}")

        # Add venue info
        description_parts.append(f"at {self.venue_name} in Venice Beach")

        # Add date info if available
        if event_date:
            date_str = event_date.strftime("%A, %B %d at %I:%M %p")
            description_parts.append(f"on {date_str}")

        # Add pricing info
        if is_free:
            description_parts.append("Free event with RSVP")
        elif price:
            description_parts.append(f"Tickets from ${price:.2f}")

        # Add all tags if multiple
        if len(category_tags) > 1:
            description_parts.append(f"Tags: {', '.join(category_tags)}")

        description = ". ".join(description_parts) + "."

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=None,
            url=event_url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free
        )

    def _determine_category(self, tags: List[str], title: str) -> str:
        """
        Determine event category from tags and title.

        Args:
            tags: List of tag strings
            title: Event title

        Returns:
            Category string
        """
        # Convert to lowercase for matching
        tags_lower = [t.lower() for t in tags]
        title_lower = title.lower()

        # Priority matching based on tags
        if any(tag in tags_lower for tag in ['live music', 'concert']):
            return 'music'
        elif any(tag in tags_lower for tag in ['brunch', 'bottomless mimosas', 'mimosas']):
            return 'food'
        elif any(tag in tags_lower for tag in ['trivia', 'bingo', 'game']):
            return 'entertainment'
        elif any(tag in tags_lower for tag in ['grateful dead', 'jerry garcia']):
            return 'music'
        elif 'line dancing' in title_lower or 'dance' in title_lower:
            return 'entertainment'
        elif 'tribute' in title_lower or 'band' in title_lower:
            return 'music'
        else:
            # Default to music since Venice West is primarily a music venue
            return 'music'

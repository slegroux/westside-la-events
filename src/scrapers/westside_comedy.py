"""
Scraper for M.I.'s Westside Comedy Theater events.
Source: https://westsidecomedy.com/tickets/

The venue uses WordPress For Events & Activities (WFEA) plugin for displaying events.
Event data is rendered server-side with structured HTML classes.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class WestsideComedyScraper(BaseScraper):
    """Scraper for M.I.'s Westside Comedy Theater events."""

    def __init__(self):
        super().__init__("M.I.'s Westside Comedy Theater")
        self.base_url = 'https://westsidecomedy.com'
        self.tickets_url = f'{self.base_url}/tickets/'
        self.venue_name = "M.I.'s Westside Comedy Theater"
        self.venue_address = '1323-A 3rd St Promenade, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Westside Comedy tickets page.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the tickets page
            html = self.fetch_page(self.tickets_url)
            if not html:
                self.log("Failed to fetch tickets page")
                return events

            soup = self.parse_html(html)

            # Find all event items using WFEA plugin classes
            event_items = soup.find_all('article', class_='wfea-card-list-item')
            self.log(f"Found {len(event_items)} events on tickets page")

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

    def _extract_time_from_event_page(self, url: str) -> str:
        """
        Fetch individual event page and extract time information.

        Args:
            url: URL of the individual event page

        Returns:
            Time string (e.g., "8:00 PM") or empty string if not found
        """
        try:
            html = self.fetch_page(url)
            if not html:
                return ''

            soup = self.parse_html(html)

            # Look for time in various formats using regex
            import re
            text = soup.get_text()

            # Match patterns like "8:00 pm", "8:00 PM", "8:00pm"
            time_match = re.search(r'\b(\d{1,2}:\d{2}\s*[AP]M)\b', text, re.IGNORECASE)
            if time_match:
                time_str = time_match.group(1)
                # Normalize spacing (e.g., "8:00pm" -> "8:00 PM")
                time_str = re.sub(r'(\d{1,2}:\d{2})\s*([AP]M)', r'\1 \2', time_str, flags=re.IGNORECASE)
                self.log(f"Found time on event page: {time_str}")
                return time_str

        except Exception as e:
            self.log(f"Error extracting time from {url}: {e}")

        return ''

    def _parse_event(self, item) -> Optional[Event]:
        """
        Parse a single event from an event card.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object or None if parsing fails
        """
        # Extract title from h3 in content block
        title_elem = item.find('h3')
        if not title_elem:
            return None

        title_link = title_elem.find('a')
        title = self.clean_text(title_link.get_text() if title_link else title_elem.get_text())
        if not title:
            return None

        # Extract event URL from title link
        event_url = self.tickets_url  # Default to tickets page
        if title_link and title_link.get('href'):
            href = title_link.get('href')
            # Check if it's an external link (Eventbrite, etc.)
            if href.startswith('http'):
                event_url = href
            else:
                event_url = self.normalize_url(href, self.base_url)

        # Extract date from calendar date section
        event_date = None
        date_section = item.find('div', class_='eaw-calendar-date')
        if date_section:
            month_elem = date_section.find('div', class_='eaw-calendar-date-month')
            day_elem = date_section.find('div', class_='eaw-calendar-date-day')

            if month_elem and day_elem:
                month_text = self.clean_text(month_elem.get_text())
                day_text = self.clean_text(day_elem.get_text())

                # Also look for time information on listing page
                time_elem = item.find('div', class_='eaw-time')
                time_text = self.clean_text(time_elem.get_text()) if time_elem else ''

                # If no time on listing page, try to fetch from individual event page
                if not time_text and event_url and event_url != self.tickets_url:
                    time_text = self._extract_time_from_event_page(event_url)

                # Combine date parts into parseable string
                # Format: "Nov 15 2025 8:00 PM"
                date_string = f"{month_text} {day_text} {datetime.now().year}"
                if time_text:
                    date_string += f" {time_text}"

                try:
                    event_date = date_parser.parse(date_string, fuzzy=True)

                    # If parsed date is more than 30 days in the past, assume it's next year
                    if event_date < (datetime.now() - timedelta(days=30)):
                        date_string = f"{month_text} {day_text} {datetime.now().year + 1}"
                        if time_text:
                            date_string += f" {time_text}"
                        event_date = date_parser.parse(date_string, fuzzy=True)

                except Exception as e:
                    self.log(f"Could not parse date '{date_string}': {e}")

        # Extract image URL from thumbnail
        image_url = ''
        thumb_wrap = item.find('div', class_='eaw-thumb-wrap')
        if thumb_wrap:
            img = thumb_wrap.find('img')
            if img and img.get('src'):
                src = img.get('src')
                # Skip placeholder images
                if not src.startswith('data:image'):
                    image_url = self.normalize_url(src, self.base_url)
            # Also check for data-src (lazy loading)
            elif img and img.get('data-src'):
                data_src = img.get('data-src')
                if not data_src.startswith('data:image'):
                    image_url = self.normalize_url(data_src, self.base_url)

        # Extract description from content block
        description = f"Comedy show at {self.venue_name}"
        content_block = item.find('div', class_='eaw-content-block')
        if content_block:
            # Look for description paragraphs (exclude title and time)
            for p in content_block.find_all('p'):
                if 'eaw-time' not in p.get('class', []):
                    desc_text = self.clean_text(p.get_text())
                    if desc_text and desc_text not in description:
                        description = desc_text

        # Check for ticket/booking link to extract price info if available
        is_free = False
        price = None
        book_button = item.find('a', class_='eaw-booknow')
        if book_button:
            button_text = self.clean_text(book_button.get_text()).lower()
            if 'free' in button_text or 'rsvp' in button_text:
                is_free = True
            # Try to extract price from button text
            # e.g., "Buy Tickets - $15"
            if '$' in button_text:
                try:
                    import re
                    price_match = re.search(r'\$(\d+(?:\.\d{2})?)', button_text)
                    if price_match:
                        price = float(price_match.group(1))
                except Exception:
                    pass

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=None,
            url=event_url,
            image_url=image_url,
            category='entertainment',  # Comedy is categorized as entertainment
            price=price,
            is_free=is_free
        )

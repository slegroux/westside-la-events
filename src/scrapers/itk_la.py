"""
Scraper for ITK LA events.
Source: https://itk.la
"""
from datetime import datetime
from typing import List, Dict, Optional
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class ITKLAScraper(BaseScraper):
    """Scraper for ITK LA (itk.la) events."""

    def __init__(self):
        super().__init__('ITK LA')
        self.base_url = 'https://itk.la'
        self.events_url = self.base_url

    def scrape(self) -> List[Event]:
        """
        Scrape events from ITK LA website.

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

            # ITK LA uses a list structure with date sections
            # Find all list items that contain event data
            event_items = soup.find_all('li')

            if not event_items:
                self.log("No list items found on page")
                return events

            self.log(f"Found {len(event_items)} list items")

            # Track current date section for parsing
            current_date = None

            for item in event_items:
                try:
                    # Check if this item contains date information (e.g., "Tue 11/11")
                    text = item.get_text(strip=True)

                    # Try to extract date from the item or its previous siblings
                    date_match = re.search(r'([A-Za-z]{3})\s+(\d{1,2}/\d{1,2})', text)
                    if date_match:
                        # This might be a date header
                        date_str = f"{date_match.group(2)}/{datetime.now().year}"
                        try:
                            current_date = datetime.strptime(date_str, "%m/%d/%Y")
                        except:
                            pass

                    # Parse event if item contains a link to /events/
                    link = item.find('a', href=lambda x: x and '/events/' in x)
                    if link:
                        event = self._parse_event(item, link, current_date)
                        if event:
                            events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event item: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, item, link, current_date: Optional[datetime]) -> Optional[Event]:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data
            link: Link element containing event URL
            current_date: Current date context for events

        Returns:
            Event object or None
        """
        # Extract URL
        event_path = link.get('href', '')
        url = self.normalize_url(event_path, self.base_url)

        if not url:
            return None

        # Get the full text of the item
        full_text = item.get_text(strip=True)

        # Extract category (e.g., #Music, #Comedy, #DJ, #Art, #ETC)
        category_match = re.search(r'#([A-Za-z]+)', full_text)
        category = category_match.group(1) if category_match else None

        # Extract title (after ### marker)
        title_match = re.search(r'###\s*(.+?)(?:\d{1,2}:\d{2}|$)', full_text)
        title = title_match.group(1).strip() if title_match else None

        if not title:
            # Fallback: use link text
            title = self.clean_text(link.get_text())

        # Extract time and venue (format: "6:00pm @ Venue Name")
        time_venue_match = re.search(r'(\d{1,2}:\d{2}[ap]m)\s*@\s*(.+?)(?:\(|via|$)', full_text)
        time_str = None
        venue_name = ""

        if time_venue_match:
            time_str = time_venue_match.group(1).strip()
            venue_name = time_venue_match.group(2).strip()

        # Parse event date/time
        event_date = None
        if current_date and time_str:
            try:
                # Combine date and time
                time_obj = datetime.strptime(time_str, "%I:%M%p")
                event_date = current_date.replace(
                    hour=time_obj.hour,
                    minute=time_obj.minute
                )
            except Exception as e:
                self.log(f"Failed to parse time '{time_str}': {e}")
                event_date = current_date
        elif current_date:
            event_date = current_date

        # Fetch detailed information from event page
        details = self._fetch_event_details(url)

        # Use description from details
        description = details.get('description', '')

        # Use more accurate date/time from details page if available
        if details.get('event_date'):
            event_date = details['event_date']

        # Use address from details
        address = details.get('address', '')

        # Get image from details
        image_url = details.get('image_url', '')

        # Get price information
        price = details.get('price')
        is_free = details.get('is_free', False)

        # Use category from details if not found in listing
        if not category and details.get('category'):
            category = details['category']

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
            is_free=is_free
        )

    def _fetch_event_details(self, event_url: str) -> Dict:
        """
        Fetch detailed event information from the detail page.

        Args:
            event_url: URL of the event detail page

        Returns:
            Dictionary with event details
        """
        details = {
            'description': '',
            'address': '',
            'image_url': '',
            'event_date': None,
            'category': None,
            'price': None,
            'is_free': False
        }

        try:
            self.log(f"Fetching details from {event_url}")
            html = self.fetch_page(event_url)
            if not html:
                return details

            soup = self.parse_html(html)

            # Extract from JSON-LD schema if available
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    import json
                    schema_data = json.loads(json_ld.string)

                    if schema_data.get('@type') == 'Event':
                        # Extract start date
                        if schema_data.get('startDate'):
                            details['event_date'] = date_parser.parse(schema_data['startDate'])

                        # Extract location/address
                        location = schema_data.get('location', {})
                        if isinstance(location, dict):
                            address_data = location.get('address', {})
                            if isinstance(address_data, dict):
                                # Build full address
                                address_parts = []
                                if address_data.get('streetAddress'):
                                    address_parts.append(address_data['streetAddress'])
                                if address_data.get('addressLocality'):
                                    address_parts.append(address_data['addressLocality'])
                                if address_data.get('addressRegion'):
                                    address_parts.append(address_data['addressRegion'])
                                details['address'] = ', '.join(address_parts)

                        # Extract image
                        if schema_data.get('image'):
                            image = schema_data['image']
                            if isinstance(image, str):
                                details['image_url'] = image
                            elif isinstance(image, list) and len(image) > 0:
                                details['image_url'] = image[0]
                            elif isinstance(image, dict):
                                details['image_url'] = image.get('url', '')

                except Exception as e:
                    self.log(f"Error parsing JSON-LD: {e}")

            # Extract category from hashtag on the page
            category_match = soup.find(string=re.compile(r'#(Music|Comedy|DJ|Art|ETC)'))
            if category_match:
                cat_match = re.search(r'#([A-Za-z]+)', category_match)
                if cat_match:
                    details['category'] = cat_match.group(1)

            # Extract description from main content
            paragraphs = soup.find_all('p')
            description_parts = []

            for p in paragraphs:
                text = self.clean_text(p.get_text())

                # Skip short text and navigation/footer content
                if len(text) < 40:
                    continue
                if any(keyword in text.lower() for keyword in ['submit an event', 'about itk', 'copyright']):
                    continue

                description_parts.append(text)

                # Usually 2-3 paragraphs is enough
                if len(description_parts) >= 3:
                    break

            if description_parts:
                details['description'] = ' '.join(description_parts)

            # Extract price information from page text
            page_text = soup.get_text()

            # Check for free events
            if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                free_context = re.search(
                    r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free',
                    page_text,
                    re.IGNORECASE
                )
                if free_context:
                    details['is_free'] = True
                    details['price'] = None

            # Extract price if not free
            if not details['is_free']:
                price_patterns = [
                    r'\$(\d+)(?:\.\d{2})?(?:\s*-\s*\$?(\d+)(?:\.\d{2})?)?',
                    r'(?:from\s+)?\$(\d+)',
                ]

                for pattern in price_patterns:
                    price_match = re.search(pattern, page_text)
                    if price_match:
                        try:
                            details['price'] = float(price_match.group(1))
                            break
                        except (ValueError, TypeError, IndexError):
                            continue

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

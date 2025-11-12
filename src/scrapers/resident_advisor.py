"""
Scraper for Resident Advisor events.
Source: https://ra.co/events/us/losangeles

Resident Advisor is a leading electronic music platform featuring DJ events,
club nights, and electronic music festivals.

NOTE: As of November 2025, Resident Advisor uses Cloudflare CAPTCHA protection
which blocks automated scraping. This scraper is implemented but will not work
without CAPTCHA bypass solutions (e.g., residential proxies, CAPTCHA solving services).

Alternative approaches:
1. Use undetected-chromedriver or similar libraries
2. Use residential proxy services
3. Use CAPTCHA solving services
4. Wait for RA to provide an official API
"""
from datetime import datetime
from typing import List, Dict, Optional
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class ResidentAdvisorScraper(BaseScraper):
    """Scraper for Resident Advisor events in Los Angeles."""

    def __init__(self):
        super().__init__('Resident Advisor')
        self.base_url = 'https://ra.co'
        self.events_url = f'{self.base_url}/events/us/losangeles'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Resident Advisor website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # RA uses JavaScript to render content, so we need Playwright
            html = self.fetch_page_js(
                self.events_url,
                wait_selector='ul[class*="EventList"]',
                timeout=60000
            )

            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find event list items - RA uses CSS modules with dynamic class names
            # Look for list items within EventList container
            event_list = soup.find('ul', class_=lambda x: x and 'EventList' in x)

            if not event_list:
                # Fallback: find all li elements that look like events
                event_items = soup.find_all('li', class_=lambda x: x and 'event' in str(x).lower())
            else:
                event_items = event_list.find_all('li')

            if not event_items:
                self.log("No event items found on page")
                return events

            self.log(f"Found {len(event_items)} event items")

            for item in event_items:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, item) -> Optional[Event]:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object or None if parsing fails or event is outside coverage area
        """
        try:
            # Extract event URL (link to event detail page)
            link_elem = item.find('a', href=re.compile(r'/events/\d+'))
            url = ""
            if link_elem and link_elem.get('href'):
                url = self.normalize_url(link_elem['href'], self.base_url)

            if not url:
                # No valid event URL, skip
                return None

            # Extract title
            # RA usually has title in an h3 or within the link
            title_elem = item.find('h3')
            if not title_elem:
                title_elem = link_elem

            title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

            # Extract date
            # RA typically shows date in <time> elements
            date_elem = item.find('time')
            event_date = None

            if date_elem:
                # Try datetime attribute first
                datetime_attr = date_elem.get('datetime')
                if datetime_attr:
                    try:
                        event_date = date_parser.parse(datetime_attr)
                    except Exception as e:
                        self.log(f"Failed to parse datetime attribute '{datetime_attr}': {e}")

                # Try parsing text content as fallback
                if not event_date:
                    date_text = self.clean_text(date_elem.get_text())
                    try:
                        event_date = self._parse_date_text(date_text)
                    except Exception as e:
                        self.log(f"Failed to parse date text '{date_text}': {e}")

            # Extract venue
            # RA shows venue as a link to club page
            venue_elem = item.find('a', href=re.compile(r'/clubs/\d+'))
            venue_name = ""

            if venue_elem:
                venue_name = self.clean_text(venue_elem.get_text())

            # Extract image
            img_elem = item.find('img')
            image_url = ""

            if img_elem:
                # Try srcset first (higher quality)
                srcset = img_elem.get('srcset', '')
                if srcset:
                    # Parse srcset and get the highest resolution
                    urls = [s.strip().split()[0] for s in srcset.split(',') if s.strip()]
                    if urls:
                        image_url = urls[-1]

                if not image_url:
                    image_url = img_elem.get('src', '')

                # Make URL absolute
                if image_url and not image_url.startswith('http'):
                    image_url = self.normalize_url(image_url, self.base_url)

            # Fetch detailed information from event page
            details = self._fetch_event_details(url)

            # Merge details
            description = details.get('description', '')

            if details.get('venue_name'):
                venue_name = details['venue_name']

            address = details.get('address', '')

            # Use more accurate time from details if available
            if details.get('event_date'):
                event_date = details['event_date']

            end_date = details.get('end_date')

            # Price information
            price = details.get('price')
            is_free = details.get('is_free', False)

            # Better image from details
            if details.get('image_url'):
                image_url = details['image_url']

            # RA events are primarily electronic music
            category = 'Music'

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                category=category,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error in _parse_event: {e}")
            return None

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """
        Parse various date text formats used by RA.

        Examples:
        - "Fri, 15 Nov"
        - "Today"
        - "Tomorrow"
        - "15 Nov 2025"

        Args:
            date_text: Date text to parse

        Returns:
            datetime object or None
        """
        if not date_text:
            return None

        date_text = date_text.strip()

        # Handle relative dates
        if date_text.lower() == 'today':
            return datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
        elif date_text.lower() == 'tomorrow':
            from datetime import timedelta
            return (datetime.now() + timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)

        # Try parsing with dateutil
        try:
            parsed = date_parser.parse(date_text, fuzzy=True)
            return parsed
        except Exception:
            return None

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
            'venue_name': '',
            'address': '',
            'image_url': '',
            'event_date': None,
            'end_date': None,
            'price': None,
            'is_free': False
        }

        try:
            self.log(f"Fetching details from {event_url}")
            html = self.fetch_page_js(
                event_url,
                wait_selector='article',
                timeout=30000
            )

            if not html:
                return details

            soup = self.parse_html(html)

            # Try to extract from JSON-LD schema first (most reliable)
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    import json
                    schema_data = json.loads(json_ld.string)

                    if schema_data.get('@type') == 'Event':
                        # Extract description
                        if schema_data.get('description'):
                            details['description'] = schema_data['description']

                        # Extract start date
                        if schema_data.get('startDate'):
                            details['event_date'] = date_parser.parse(schema_data['startDate'])

                        # Extract end date
                        if schema_data.get('endDate'):
                            details['end_date'] = date_parser.parse(schema_data['endDate'])

                        # Extract location/venue
                        location = schema_data.get('location', {})
                        if isinstance(location, dict):
                            if location.get('name'):
                                details['venue_name'] = location['name']

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

                        # Extract price
                        offers = schema_data.get('offers', {})
                        if isinstance(offers, dict):
                            if offers.get('price'):
                                try:
                                    details['price'] = float(offers['price'])
                                except (ValueError, TypeError):
                                    pass

                except Exception as e:
                    self.log(f"Error parsing JSON-LD: {e}")

            # If no description from JSON-LD, scrape from page
            if not details['description']:
                desc_elem = soup.find('div', class_=lambda x: x and 'description' in str(x).lower())
                if not desc_elem:
                    desc_elem = soup.find('div', class_=lambda x: x and 'content' in str(x).lower())

                if desc_elem:
                    paragraphs = desc_elem.find_all('p')
                    description_parts = []

                    for p in paragraphs:
                        text = self.clean_text(p.get_text())
                        if len(text) > 30:
                            description_parts.append(text)

                        if len(description_parts) >= 3:
                            break

                    details['description'] = ' '.join(description_parts)

            # Extract venue if not found in JSON-LD
            if not details['venue_name']:
                venue_elem = soup.find('a', href=re.compile(r'/clubs/\d+'))
                if venue_elem:
                    details['venue_name'] = self.clean_text(venue_elem.get_text())

            # Extract date/time if not found in JSON-LD
            if not details['event_date']:
                time_elem = soup.find('time')
                if time_elem:
                    datetime_attr = time_elem.get('datetime')
                    if datetime_attr:
                        try:
                            details['event_date'] = date_parser.parse(datetime_attr)
                        except Exception as e:
                            self.log(f"Could not parse datetime '{datetime_attr}': {e}")

            # Extract price information from page text if not in JSON-LD
            if details['price'] is None:
                page_text = soup.get_text()

                # Check for free events
                if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                    free_patterns = [
                        r'free\s+entry',
                        r'entry\s*:\s*free',
                        r'admission\s*:\s*free',
                        r'tickets\s*:\s*free'
                    ]

                    for pattern in free_patterns:
                        if re.search(pattern, page_text, re.IGNORECASE):
                            details['is_free'] = True
                            details['price'] = None
                            break

                # Look for price patterns
                if not details['is_free']:
                    price_patterns = [
                        r'\$(\d+)(?:\.\d{2})?',  # $25 or $25.00
                        r'(\d+)\s*USD',           # 25 USD
                        r'(\d+)\s*GBP',           # 25 GBP (RA is international)
                    ]

                    for pattern in price_patterns:
                        price_match = re.search(pattern, page_text)
                        if price_match:
                            try:
                                details['price'] = float(price_match.group(1))
                                break
                            except (ValueError, TypeError):
                                continue

            # Get high-res image from Open Graph if not in JSON-LD
            if not details['image_url']:
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    details['image_url'] = og_image.get('content', '')

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

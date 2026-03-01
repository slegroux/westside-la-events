"""
Scraper for ITK LA events.
Source: https://itk.la

ITK LA shows weekly events in day columns. Each column has an h2 date header
and a ul.ml-8 containing li > a event items. Event URLs contain the date as
YYYY-MM-DD suffix (e.g. /events/some-title-2026-03-01).
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

            # Find all event links — each <a href="/events/slug-YYYY-MM-DD"> is one event
            event_links = soup.find_all('a', href=re.compile(r'^/events/'))

            if not event_links:
                self.log("No event links found on page")
                return events

            self.log(f"Found {len(event_links)} event links")

            # Prefetch detail pages concurrently
            detail_urls = [self.normalize_url(a['href'], self.base_url) for a in event_links]
            self.prefetch_pages(detail_urls)

            seen = set()
            for a in event_links:
                try:
                    url = self.normalize_url(a['href'], self.base_url)
                    if url in seen:
                        continue
                    seen.add(url)

                    event = self._parse_event_link(a, url)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event item: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event_link(self, a_tag, url: str) -> Optional[Event]:
        """
        Parse a single event from its <a> container element.

        Args:
            a_tag: <a> BeautifulSoup element containing event data
            url: Full event URL

        Returns:
            Event object or None
        """
        # Extract title from h3 inside the link
        h3 = a_tag.find('h3')
        if not h3:
            return None
        title = self.clean_text(h3.get_text())
        if not title:
            return None

        # Extract date from URL slug (e.g. /events/slug-2026-03-01)
        event_date = None
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})$', url.rstrip('/'))
        if date_match:
            try:
                event_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            except Exception:
                pass

        # Extract time from the red paragraph "HH:MMpm @ Venue"
        time_p = a_tag.find('p', class_=lambda x: x and 'red' in ' '.join(x if isinstance(x, list) else [x]))
        venue_name = ""
        if time_p:
            time_venue_text = self.clean_text(time_p.get_text())
            # "12:00pm @ RSVP required for location"
            time_match = re.match(r'(\d{1,2}:\d{2}[ap]m)\s*@\s*(.*)', time_venue_text, re.IGNORECASE)
            if time_match and event_date:
                try:
                    time_obj = datetime.strptime(time_match.group(1), '%I:%M%p')
                    event_date = event_date.replace(hour=time_obj.hour, minute=time_obj.minute)
                except Exception:
                    pass
                venue_name = time_match.group(2).strip()

        # Extract category from color-coded p (e.g. class="text-music", "text-comedy")
        category = ""
        cat_p = a_tag.find('p', class_=re.compile(r'text-(music|comedy|etc|art|dj)', re.I))
        if cat_p:
            cat_text = self.clean_text(cat_p.get_text()).lstrip('#')
            cat_map = {
                'music': 'Music', 'comedy': 'Comedy', 'art': 'Arts & Culture',
                'dj': 'Music', 'etc': 'Other',
            }
            category = cat_map.get(cat_text.lower(), cat_text)

        # Fetch detail page for address and description
        details = self._fetch_event_details(url)
        description = details.get('description', '')
        address = details.get('address', '')
        image_url = details.get('image_url', '')
        price = details.get('price')
        is_free = details.get('is_free', False)

        if details.get('event_date'):
            event_date = details['event_date']
        if details.get('category') and not category:
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
                        if schema_data.get('startDate'):
                            details['event_date'] = date_parser.parse(schema_data['startDate'])

                        location = schema_data.get('location', {})
                        if isinstance(location, dict):
                            address_data = location.get('address', {})
                            if isinstance(address_data, dict):
                                address_parts = []
                                for key in ('streetAddress', 'addressLocality', 'addressRegion'):
                                    if address_data.get(key):
                                        address_parts.append(address_data[key])
                                details['address'] = ', '.join(address_parts)

                        image = schema_data.get('image')
                        if isinstance(image, str):
                            details['image_url'] = image
                        elif isinstance(image, list) and image:
                            details['image_url'] = image[0]
                        elif isinstance(image, dict):
                            details['image_url'] = image.get('url', '')

                except Exception as e:
                    self.log(f"Error parsing JSON-LD: {e}")

            # Extract description
            paragraphs = soup.find_all('p')
            description_parts = []
            for p in paragraphs:
                text = self.clean_text(p.get_text())
                if len(text) < 40:
                    continue
                if any(k in text.lower() for k in ['submit an event', 'about itk', 'copyright']):
                    continue
                description_parts.append(text)
                if len(description_parts) >= 3:
                    break
            if description_parts:
                details['description'] = ' '.join(description_parts)

            # Price extraction
            page_text = soup.get_text()
            if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                free_ctx = re.search(r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free', page_text, re.I)
                if free_ctx:
                    details['is_free'] = True

            if not details['is_free']:
                price_match = re.search(r'\$(\d+(?:\.\d{2})?)', page_text)
                if price_match:
                    try:
                        details['price'] = float(price_match.group(1))
                    except ValueError:
                        pass

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

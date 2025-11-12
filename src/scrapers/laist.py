"""
Scraper for LAist events.
Source: https://laist.com/events
"""
from datetime import datetime
from typing import List, Dict, Optional
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class LAistScraper(BaseScraper):
    """Scraper for LAist events."""

    def __init__(self):
        super().__init__('LAist')
        self.base_url = 'https://laist.com'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from LAist website.

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

            # LAist uses a list structure for events
            event_list = soup.find('ul', class_='EventList-LoadMore-items')
            if not event_list:
                self.log("No event list found on page")
                return events

            event_items = event_list.find_all('li', class_='EventList-LoadMore-items-item')

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

    def _parse_event(self, item) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object
        """
        # Extract title - in h2 or h3 tag
        title_elem = item.find('h2') or item.find('h3')
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract URL - in Link class anchor
        link_elem = item.find('a', class_='Link')
        url = ""
        if link_elem and link_elem.get('href'):
            url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract image - in img tag
        img_elem = item.find('img')
        image_url = ""
        if img_elem:
            src = img_elem.get('src', '')
            if src:
                image_url = src  # Already full URL from Brightspot CDN

        # Fetch detailed information from event page
        details = self._fetch_event_details(url) if url else {}

        # Get date, venue, description from details page
        event_date = details.get('event_date')
        end_date = details.get('end_date')
        venue_name = details.get('venue_name', '')
        address = details.get('address', '')
        description = details.get('description', '')
        category = details.get('category')
        price = details.get('price')
        is_free = details.get('is_free', False)

        # Use high-res image if available
        if details.get('image_url'):
            image_url = details['image_url']

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
            'image_url': '',
            'event_date': None,
            'end_date': None,
            'venue_name': '',
            'address': '',
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

            # Extract description paragraphs from the main content
            # LAist typically has several paragraphs describing the event
            page_body = soup.find('div', class_='OneOffPage-body')
            if page_body:
                paragraphs = page_body.find_all('p')
                description_parts = []

                for p in paragraphs:
                    text = self.clean_text(p.get_text())

                    # Skip very short paragraphs
                    if len(text) < 40:
                        continue

                    # Skip footer/meta content
                    if any(keyword in text.lower() for keyword in [
                        'donate to laist',
                        'copyright',
                        'laist member',
                        'follow us on',
                        'newsletter',
                        'email us at'
                    ]):
                        break

                    description_parts.append(text)

                    # Usually descriptions are 2-4 paragraphs
                    if len(description_parts) >= 4:
                        break

                details['description'] = ' '.join(description_parts)

            # Extract date/time information
            # Look for patterns like "Thursday, November 13" or "Thu, Nov 13"
            date_patterns = [
                r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Z][a-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?',
                r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([A-Z][a-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?'
            ]

            page_text = soup.get_text()
            for pattern in date_patterns:
                date_match = re.search(pattern, page_text)
                if date_match:
                    try:
                        # Build date string
                        day_of_week = date_match.group(1)
                        month = date_match.group(2)
                        day = date_match.group(3)
                        year = date_match.group(4) if len(date_match.groups()) >= 4 and date_match.group(4) else str(datetime.now().year)

                        date_str = f"{month} {day} {year}"

                        # Look for time nearby (within 50 characters)
                        time_match = re.search(r'(\d{1,2}):(\d{2})\s*([AP]M)', page_text[date_match.end():date_match.end()+50], re.IGNORECASE)
                        if time_match:
                            date_str += f" {time_match.group(0)}"

                        details['event_date'] = date_parser.parse(date_str)
                        self.log(f"Parsed event date: {details['event_date']}")
                        break
                    except Exception as e:
                        self.log(f"Could not parse date: {e}")

            # Extract venue and address information
            # LAist stores venue info in structured data and also in a list item

            # Try method 1: JSON-LD structured data
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    import json
                    data = json.loads(json_ld.string)
                    if data.get('@type') == 'Event' and 'location' in data:
                        locations = data['location']
                        if isinstance(locations, list) and len(locations) > 0:
                            location = locations[0]
                            if location.get('name'):
                                details['venue_name'] = location['name']
                            if location.get('address'):
                                addr = location['address']
                                # Build full address from structured data
                                address_parts = []
                                if addr.get('streetAddress'):
                                    address_parts.append(addr['streetAddress'])
                                if addr.get('addressLocality'):
                                    address_parts.append(addr['addressLocality'])
                                if addr.get('addressRegion'):
                                    address_parts.append(addr['addressRegion'])
                                if addr.get('postalCode'):
                                    address_parts.append(addr['postalCode'])
                                details['address'] = ', '.join(address_parts)
                                self.log(f"Found venue from JSON-LD: {details['venue_name']}")

                        # Also extract date from JSON-LD if not already found
                        if not details['event_date'] and data.get('startDate'):
                            try:
                                details['event_date'] = date_parser.parse(data['startDate'])
                                self.log(f"Parsed event date from JSON-LD: {details['event_date']}")
                            except Exception as e:
                                self.log(f"Could not parse date from JSON-LD: {e}")

                        if not details['end_date'] and data.get('endDate'):
                            try:
                                details['end_date'] = date_parser.parse(data['endDate'])
                            except Exception as e:
                                pass

                except Exception as e:
                    self.log(f"Error parsing JSON-LD: {e}")

            # Try method 2: Look in EventPage-information-venues list
            if not details['venue_name']:
                venue_list = soup.find('ul', class_='EventPage-information-venues-items')
                if venue_list:
                    venue_item = venue_list.find('li', class_='EventPage-information-venues-items-item')
                    if venue_item:
                        full_text = self.clean_text(venue_item.get_text())
                        # Format: "Venue Name, Street Address, City"
                        parts = [p.strip() for p in full_text.split(',')]
                        if parts:
                            details['venue_name'] = parts[0]
                            details['address'] = full_text
                        self.log(f"Found venue from list: {details['venue_name']}")

            # Extract price information
            # Check for free events
            if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                # Look for context that confirms it's about admission
                free_context = re.search(
                    r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free',
                    page_text,
                    re.IGNORECASE
                )
                if free_context or 'free' in details['description'].lower():
                    details['is_free'] = True
                    details['price'] = None

            # Look for price patterns
            if not details['is_free']:
                price_patterns = [
                    r'\$(\d+)(?:\.\d{2})?(?:\s*-\s*\$?(\d+)(?:\.\d{2})?)?',  # $25 or $25.00 or $25-$75
                    r'(?:from\s+)?\$(\d+)',     # from $25
                    r'(?:ticket(?:s)?|admission|price|cost)[:is\s]+\$(\d+)',  # tickets: $25
                ]

                for pattern in price_patterns:
                    price_match = re.search(pattern, page_text, re.IGNORECASE)
                    if price_match:
                        try:
                            details['price'] = float(price_match.group(1))
                            break
                        except (ValueError, TypeError, IndexError):
                            continue

            # Try to infer category from event title or description
            # Common LAist categories: Music, Film, Art, Food, Community
            category_keywords = {
                'Music': ['concert', 'live music', 'band', 'singer', 'performance', 'musician'],
                'Film': ['screening', 'movie', 'film', 'cinema'],
                'Food': ['cookbook', 'chef', 'culinary', 'dining', 'food'],
                'Art': ['gallery', 'exhibition', 'artist', 'museum', 'art show'],
                'Community': ['town hall', 'community', 'discussion', 'panel', 'talk'],
                'Family': ['family', 'kids', 'children'],
                'Sports': ['game', 'match', 'sports'],
            }

            combined_text = (details.get('description', '') + ' ' + soup.find('h1').get_text() if soup.find('h1') else '').lower()

            for category, keywords in category_keywords.items():
                if any(keyword in combined_text for keyword in keywords):
                    details['category'] = category
                    break

            # Get high-res image from OpenGraph meta tag
            og_image = soup.find('meta', property='og:image')
            if og_image:
                details['image_url'] = og_image.get('content', '')

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

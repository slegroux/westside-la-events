"""
Scraper for Discover Los Angeles events.
Source: https://www.discoverlosangeles.com/events
"""
from datetime import datetime
from typing import List, Optional
import json
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class DiscoverLAScraper(BaseScraper):
    """Scraper for Discover Los Angeles events."""

    def __init__(self):
        super().__init__('Discover LA')
        self.base_url = 'https://www.discoverlosangeles.com'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Discover Los Angeles website.

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

            # Find all event articles
            event_articles = soup.find_all('article', class_=lambda x: x and 'node--type-event' in str(x))
            self.log(f"Found {len(event_articles)} event articles")

            # Collect detail URLs and prefetch them concurrently
            # Cap at 60 to stay well within the 120s scraper timeout
            MAX_EVENTS = 60
            detail_urls = []
            for article in event_articles:
                link = article.find('a', href=True)
                if link:
                    detail_urls.append(self.normalize_url(link.get('href', ''), self.base_url))
            if len(detail_urls) > MAX_EVENTS:
                self.log(f"Capping from {len(detail_urls)} to {MAX_EVENTS} detail pages to avoid timeout")
                detail_urls = detail_urls[:MAX_EVENTS]
                event_articles = event_articles[:MAX_EVENTS]
            if detail_urls:
                self.prefetch_pages(detail_urls, max_concurrent=10)

            for article in event_articles:
                try:
                    event = self._parse_event(article)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, article) -> Optional[Event]:
        """
        Parse a single event article.

        Args:
            article: BeautifulSoup element containing event data

        Returns:
            Event object or None if parsing fails
        """
        # Find the main link with all the data attributes
        link = article.find('a', href=True)
        if not link:
            return None

        # Extract data from attributes
        title = link.get('data-content-title', '').strip()
        if not title:
            return None

        # Extract URL
        event_url = link.get('href', '')
        url = self.normalize_url(event_url, self.base_url)

        # Extract category and normalize to standard set
        raw_category = link.get('data-category', '').strip()
        category = self._normalize_category(raw_category)

        # Extract venue information
        venue_name = link.get('data-venue', '').strip()
        neighborhood = link.get('data-neighborhood', '').strip()

        # Build address from available location data
        address_parts = []
        if venue_name:
            address_parts.append(venue_name)
        if neighborhood:
            address_parts.append(neighborhood)
        address_parts.append('Los Angeles, CA')
        address = ', '.join(address_parts)

        # Extract date
        date_str = link.get('data-start-date', '')
        event_date = None
        if date_str:
            try:
                event_date = date_parser.parse(date_str)
            except Exception as e:
                self.log(f"Error parsing date '{date_str}': {e}")

        # Extract image - look for img tag with data-src (lazy loading) or src
        image_url = ""
        img = article.find('img')
        if img:
            # Try data-src first (lazy loading), then src
            image_url = img.get('data-src', '') or img.get('src', '')
            # Handle srcset if available
            if not image_url:
                srcset = img.get('srcset', '')
                if srcset:
                    # Get the highest resolution image from srcset
                    srcset_parts = srcset.split(',')
                    if srcset_parts:
                        # Take the last (usually highest res) image
                        image_url = srcset_parts[-1].strip().split(' ')[0]

        image_url = self.normalize_url(image_url, self.base_url)

        # Fetch detailed information from the event page
        details = self._fetch_event_details(url)

        # Use description from details page
        description = details.get('description', '')

        # Use more accurate date/time from details page if available
        if details.get('event_date'):
            event_date = details['event_date']

        end_date = details.get('end_date')

        # Use price information from details page
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

    # Map Discover LA's raw category tags to standard categories
    _CATEGORY_MAP = {
        'arts & theatre': 'Theater',
        'theatre': 'Theater',
        'art': 'Art',
        'museums': 'Art',
        'art & museums': 'Art',
        'music': 'Music',
        'food & drink': 'Food & Drink',
        'food': 'Food & Drink',
        'sports & active': 'Sports',
        'sports': 'Sports',
        'outdoors & adventure': 'Wellness',
        'outdoors': 'Wellness',
        'film': 'Film',
        'nightlife': 'Nightlife',
        'family & kids': 'Family',
        'family': 'Family',
        'kids': 'Family',
        'educational': 'Education',
        'education': 'Education',
        'community': 'Community',
        'tech': 'Tech',
        'wellness': 'Wellness',
        'comedy': 'Comedy',
    }

    def _normalize_category(self, raw: str) -> str:
        """Map a raw Discover LA category tag to a standard category name."""
        return self._CATEGORY_MAP.get(raw.lower(), 'Other')

    @staticmethod
    def _is_event_node(node) -> bool:
        """Is this JSON-LD node an Event?

        ``@type`` is not always a plain string: schema.org allows a list, and
        Discover LA uses it for pages that are several things at once (an
        Event that is also a Festival). Treat a list as a match if Event is
        anywhere in it.
        """
        if not isinstance(node, dict):
            return False
        node_type = node.get('@type')
        if isinstance(node_type, list):
            return 'Event' in node_type
        return node_type == 'Event'

    @classmethod
    def _find_event_node(cls, nodes):
        """Pick the Event out of a JSON-LD graph or array.

        Entries are not guaranteed to be dicts -- /dinela nests a *list* inside
        its @graph, and calling .get() on it used to raise
        "'list' object has no attribute 'get'", which aborted the whole detail
        fetch. Recurse into nested lists and skip anything that is not a dict.
        """
        if not isinstance(nodes, list):
            return None
        for item in nodes:
            if cls._is_event_node(item):
                return item
            if isinstance(item, list):
                found = cls._find_event_node(item)
                if found:
                    return found
        return None

    def _fetch_event_details(self, url: str) -> dict:
        """
        Fetch additional details from individual event page.

        Args:
            url: Event page URL

        Returns:
            Dictionary with additional details (description, event_date, end_date, price, etc.)
        """
        details = {
            'description': '',
            'image_url': '',
            'event_date': None,
            'end_date': None,
            'price': None,
            'is_free': False
        }

        try:
            html = self.fetch_page(url)
            if not html:
                return details

            soup = self.parse_html(html)

            # First, try to extract structured data from JSON-LD
            # This is the most reliable method for Discover LA
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle @graph structure
                    if isinstance(data, dict) and '@graph' in data:
                        # Find the Event object in the graph
                        data = self._find_event_node(data['@graph'])
                    # Handle array of objects
                    elif isinstance(data, list):
                        data = self._find_event_node(data)

                    if data and self._is_event_node(data):
                        # Extract description
                        if data.get('description'):
                            details['description'] = self.clean_text(data['description'])

                        # Extract event date and time
                        if data.get('startDate'):
                            try:
                                details['event_date'] = date_parser.parse(data['startDate'])
                            except Exception as e:
                                self.log(f"Error parsing startDate: {e}")

                        # Extract end date and time
                        if data.get('endDate'):
                            try:
                                details['end_date'] = date_parser.parse(data['endDate'])
                            except Exception as e:
                                self.log(f"Error parsing endDate: {e}")

                        # Extract image
                        if data.get('image'):
                            image = data['image']
                            if isinstance(image, str):
                                details['image_url'] = image
                            elif isinstance(image, dict) and image.get('url'):
                                details['image_url'] = image['url']
                            elif isinstance(image, list) and len(image) > 0:
                                details['image_url'] = image[0] if isinstance(image[0], str) else image[0].get('url', '')

                        # Extract price information from offers
                        if data.get('offers'):
                            offers = data['offers']
                            if not isinstance(offers, list):
                                offers = [offers]

                            for offer in offers:
                                # Check if event is free
                                price_val = offer.get('price')
                                if price_val == 0 or price_val == '0' or (isinstance(price_val, str) and price_val.lower() == 'free'):
                                    details['is_free'] = True
                                    details['price'] = None
                                    break

                                # Extract price
                                if price_val is not None:
                                    try:
                                        # Handle price ranges (e.g., "25-75")
                                        if isinstance(price_val, str):
                                            # Extract first number from range
                                            price_match = re.search(r'(\d+(?:\.\d{2})?)', price_val)
                                            if price_match:
                                                details['price'] = float(price_match.group(1))
                                        else:
                                            details['price'] = float(price_val)
                                    except (ValueError, TypeError):
                                        pass

                                # Also check for lowPrice and highPrice
                                if not details['price']:
                                    if offer.get('lowPrice'):
                                        try:
                                            details['price'] = float(offer['lowPrice'])
                                        except (ValueError, TypeError):
                                            pass

                        # Successfully parsed JSON-LD, we're done
                        break

                except json.JSONDecodeError:
                    continue

            # Fallback: If no JSON-LD data found, try scraping HTML
            if not details['description']:
                # Get description from meta tag
                meta_desc = soup.find('meta', {'name': 'description'})
                if meta_desc:
                    details['description'] = self.clean_text(meta_desc.get('content', ''))
                else:
                    # Try to find description in content area
                    desc_elem = soup.find(['div', 'p'], class_=lambda x: x and 'description' in str(x).lower())
                    if desc_elem:
                        details['description'] = self.clean_text(desc_elem.get_text())
                    else:
                        # Try to find first paragraphs in content area
                        content = soup.find(['article', 'div'], class_=lambda x: x and ('content' in str(x).lower() or 'body' in str(x).lower()))
                        if content:
                            paragraphs = content.find_all('p', limit=3)
                            if paragraphs:
                                details['description'] = ' '.join([self.clean_text(p.get_text()) for p in paragraphs])

            # Fallback: Get high-res image from og:image if not found in JSON-LD
            if not details['image_url']:
                og_image = soup.find('meta', property='og:image')
                if og_image:
                    details['image_url'] = og_image.get('content', '')

            # Fallback: Try to extract price from HTML if not found in JSON-LD
            if details['price'] is None and not details['is_free']:
                # Look for price patterns in the page text
                # Common patterns: "$25", "$25-$75", "Free", etc.
                page_text = soup.get_text()

                # Check for "Free" or "FREE"
                if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                    free_context = re.search(r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free', page_text, re.IGNORECASE)
                    if free_context:
                        details['is_free'] = True
                        details['price'] = None

                # Look for price patterns like $25 or $25-$75
                if not details['is_free']:
                    # Try to find price in metadata or specific elements first
                    price_patterns = [
                        r'\$(\d+)(?:-\$?(\d+))?',  # $25 or $25-$75
                        r'(?:from\s+)?\$(\d+)',     # from $25
                    ]

                    for pattern in price_patterns:
                        price_match = re.search(pattern, page_text)
                        if price_match:
                            try:
                                # Get the first price (minimum price in a range)
                                details['price'] = float(price_match.group(1))
                                break
                            except (ValueError, TypeError, IndexError):
                                continue

            return details

        except Exception as e:
            self.log(f"Error fetching event details from {url}: {e}")
            return details

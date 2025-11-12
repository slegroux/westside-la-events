"""
Scraper for Discover Los Angeles events.
Source: https://www.discoverlosangeles.com/events
"""
from datetime import datetime
from typing import List, Optional
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

        # Extract category
        category = link.get('data-category', '').strip()

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

        # Note: Description is not available in list view
        # We could fetch individual event pages for full details if needed
        description = ""

        # Extract price information from data attributes or text
        is_free = False
        price = None

        # Check for free events in title or tags
        price_tag = link.get('data-price', '').lower()
        if 'free' in title.lower() or 'free' in price_tag:
            is_free = True
        elif price_tag and price_tag != 'varies':
            # Try to extract price from data attribute
            import re
            price_match = re.search(r'\$?(\d+(?:\.\d{2})?)', price_tag)
            if price_match:
                try:
                    price = float(price_match.group(1))
                except ValueError:
                    pass

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

    def _fetch_event_details(self, url: str) -> dict:
        """
        Fetch additional details from individual event page.

        Args:
            url: Event page URL

        Returns:
            Dictionary with additional details (description, full date/time, etc.)
        """
        details = {
            'description': '',
            'image_url': '',
            'full_date': None
        }

        try:
            html = self.fetch_page(url)
            if not html:
                return details

            soup = self.parse_html(html)

            # Get description
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

            # Get high-res image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                details['image_url'] = og_image.get('content', '')

            return details

        except Exception as e:
            self.log(f"Error fetching event details from {url}: {e}")
            return details

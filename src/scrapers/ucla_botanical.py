"""
Scraper for UCLA Mathias Botanical Garden events.
Source: https://www.botgard.ucla.edu/garden-events-news/

The garden is located at:
- 707 Tiverton Drive, Los Angeles, CA 90095
- Events held at various locations within the garden including La Kretz Garden Pavilion
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class UCLABotanicalScraper(BaseScraper):
    """Scraper for UCLA Mathias Botanical Garden events."""

    def __init__(self):
        super().__init__('UCLA Mathias Botanical Garden')
        self.base_url = 'https://www.botgard.ucla.edu'
        self.events_url = f'{self.base_url}/garden-events-news/'
        self.default_venue_name = 'UCLA Mathias Botanical Garden'
        self.default_address = '707 Tiverton Drive, Los Angeles, CA 90095'

    def scrape(self) -> List[Event]:
        """
        Scrape events from UCLA Botanical Garden.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the main events page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Find event links - look for links in the events section
            # Events are in article tags with class 'tribe-events-calendar-list__event'
            event_articles = soup.find_all('article', class_=re.compile(r'tribe-events'))

            if not event_articles:
                # Fallback: look for event links directly
                event_links = soup.find_all('a', href=re.compile(r'/event/[^/]+/?$'))
                self.log(f"Found {len(event_links)} event links on page")
            else:
                # Extract links from articles
                event_links = []
                for article in event_articles:
                    link = article.find('a', class_='tribe-events-calendar-list__event-title-link')
                    if link and link.get('href'):
                        event_links.append(link)
                self.log(f"Found {len(event_links)} events in articles")

            # Get unique event URLs
            event_urls = set()
            for link in event_links:
                href = link.get('href', '')
                if '/event/' in href:
                    full_url = self.normalize_url(href, self.base_url)
                    event_urls.add(full_url)

            self.log(f"Processing {len(event_urls)} unique event URLs")

            # Prefetch all event detail pages concurrently
            if event_urls:
                self.prefetch_pages(list(event_urls))

            # Process each event detail page
            for i, url in enumerate(event_urls, 1):
                try:
                    event = self._scrape_event_detail(url)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_urls)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i} ({url}): {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _scrape_event_detail(self, url: str) -> Optional[Event]:
        """
        Scrape details from an individual event page.

        Args:
            url: URL of the event detail page

        Returns:
            Event object or None if parsing fails
        """
        html = self.fetch_page(url)
        if not html:
            return None

        soup = self.parse_html(html)

        # Extract title
        title_elem = soup.find('h1', class_='tribe-events-single-event-title')
        if not title_elem:
            # Fallback to any h1
            title_elem = soup.find('h1')
        title = self.clean_text(title_elem.get_text()) if title_elem else 'Untitled Event'

        # Extract description
        description = self._extract_description(soup)

        # Extract date and time
        event_date, end_date = self._extract_dates(soup)

        # Extract venue information
        venue_name, address = self._extract_venue(soup)

        # Extract image
        image_url = self._extract_image(soup)

        # Extract pricing information
        price, is_free, price_note = self._extract_pricing(soup)

        # Determine category based on title and description
        category = self._determine_category(title, description)

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name or self.default_venue_name,
            address=address or self.default_address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

    def _extract_description(self, soup) -> str:
        """Extract event description from the page."""
        description_parts = []

        # Look for the main event description
        desc_elem = soup.find('div', class_='tribe-events-single-event-description')
        if desc_elem:
            # Get text from paragraphs
            paragraphs = desc_elem.find_all('p')
            for p in paragraphs:
                text = self.clean_text(p.get_text())
                if text and not text.startswith('Tickets for this event'):
                    description_parts.append(text)

        # If no description found, look for any content div
        if not description_parts:
            content_div = soup.find('div', class_=re.compile(r'content|description'))
            if content_div:
                text = self.clean_text(content_div.get_text())
                if text:
                    description_parts.append(text[:500])  # Limit length

        return ' '.join(description_parts) if description_parts else ''

    def _extract_dates(self, soup) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract start and end dates from the page."""
        event_date = None
        end_date = None

        # Look for date/time in meta tags (Schema.org format)
        start_meta = soup.find('meta', {'property': 'event:start_date'})
        end_meta = soup.find('meta', {'property': 'event:end_date'})

        if start_meta and start_meta.get('content'):
            try:
                event_date = date_parser.parse(start_meta['content'])
            except Exception as e:
                self.log(f"Could not parse start date from meta: {e}")

        if end_meta and end_meta.get('content'):
            try:
                end_date = date_parser.parse(end_meta['content'])
            except Exception as e:
                self.log(f"Could not parse end date from meta: {e}")

        # Fallback: look for date in the page text
        if not event_date:
            date_elem = soup.find('div', class_='tribe-events-schedule')
            if not date_elem:
                date_elem = soup.find('time', class_='tribe-events-start-datetime')

            if date_elem:
                date_text = self.clean_text(date_elem.get_text())
                # Handle format like "December 6 @ 10:00 am - 11:00 am"
                # or "November 22 @ 10:30 am - 12:00 pm"
                try:
                    # Split at @ to separate date from time
                    if '@' in date_text:
                        date_part = date_text.split('@')[0].strip()
                        time_part = date_text.split('@')[1].strip()
                        # Take first time (before the dash)
                        if '-' in time_part:
                            start_time = time_part.split('-')[0].strip()
                            end_time = time_part.split('-')[1].strip()
                            # Combine date and start time
                            full_date_str = f"{date_part} {start_time}"
                            event_date = date_parser.parse(full_date_str)
                            # Parse end time too
                            full_end_str = f"{date_part} {end_time}"
                            end_date = date_parser.parse(full_end_str)
                        else:
                            full_date_str = f"{date_part} {time_part}"
                            event_date = date_parser.parse(full_date_str)
                    else:
                        event_date = date_parser.parse(date_text)
                except Exception as e:
                    self.log(f"Could not parse date '{date_text}': {e}")

        return event_date, end_date

    def _extract_venue(self, soup) -> tuple[str, str]:
        """Extract venue name and address from the page."""
        venue_name = ''
        address = ''

        # Look for venue information
        venue_elem = soup.find('div', class_='tribe-events-meta-group-venue')
        if venue_elem:
            # Get venue name
            name_elem = venue_elem.find('dd', class_='tribe-venue')
            if name_elem:
                venue_name = self.clean_text(name_elem.get_text())

            # Get address - construct from components
            address_elem = venue_elem.find('address', class_='tribe-events-address')
            if address_elem:
                # Get individual components
                street = address_elem.find('span', class_='tribe-street-address')
                locality = address_elem.find('span', class_='tribe-locality')
                region = address_elem.find('abbr', class_='tribe-region')
                postal = address_elem.find('span', class_='tribe-postal-code')

                # Build address carefully to avoid duplicates
                address_parts = []
                if street:
                    address_parts.append(self.clean_text(street.get_text()))

                # Combine city, state, zip
                city_state_zip = []
                if locality:
                    city_state_zip.append(self.clean_text(locality.get_text()))
                if region:
                    city_state_zip.append(self.clean_text(region.get_text()))
                if postal:
                    city_state_zip.append(self.clean_text(postal.get_text()))

                if city_state_zip:
                    address_parts.append(' '.join(city_state_zip))

                address = ', '.join(filter(None, address_parts))

        # Check if it's specifically at La Kretz Garden Pavilion
        page_text = soup.get_text().lower()
        if 'la kretz' in page_text or 'lakretz' in page_text:
            venue_name = 'UCLA La Kretz Garden Pavilion'

        return venue_name, address

    def _extract_image(self, soup) -> str:
        """Extract event image URL from the page."""
        # Look for featured image
        img_elem = soup.find('div', class_='tribe-events-event-image')
        if img_elem:
            img = img_elem.find('img')
            if img and img.get('src'):
                return img['src']

        # Look for og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']

        # Look for any image in the content
        img = soup.find('img', src=re.compile(r'\.(jpg|jpeg|png|webp)', re.I))
        if img and img.get('src'):
            # Avoid logo/icon images
            src = img['src']
            if 'logo' not in src.lower() and 'icon' not in src.lower():
                return self.normalize_url(src, self.base_url)

        return ''

    def _extract_pricing(self, soup) -> tuple[Optional[float], bool, str]:
        """Extract pricing information from the page."""
        price = None
        is_free = False
        price_note = ''

        # Look for pricing text
        page_text = soup.get_text().lower()

        # Check if sold out
        if 'sold out' in page_text:
            price_note = 'Sold out'

        # Look for price patterns
        price_patterns = [
            r'\$(\d+(?:\.\d{2})?)\s*per\s*ticket',
            r'cost:\s*\$(\d+(?:\.\d{2})?)',
            r'price:\s*\$(\d+(?:\.\d{2})?)',
            r'\$(\d+(?:\.\d{2})?)\s*per\s*person'
        ]

        for pattern in price_patterns:
            match = re.search(pattern, page_text)
            if match:
                try:
                    price = float(match.group(1))
                    break
                except ValueError:
                    pass

        # Check if free
        if 'free admission' in page_text or 'free event' in page_text:
            is_free = True
            price = None
        elif price is None and 'ticket' in page_text:
            # If tickets are mentioned but no price found, display as $TBD
            price_note = None

        return price, is_free, price_note

    def _determine_category(self, title: str, description: str) -> str:
        """
        Determine event category from title and description.

        Args:
            title: Event title
            description: Event description

        Returns:
            Category string
        """
        text = (title + ' ' + description).lower()

        # Check for specific event types
        if any(word in text for word in ['workshop', 'class', 'wreath', 'craft', 'making']):
            return 'workshop'
        elif any(word in text for word in ['tour', 'walk', 'garden walk', 'guided']):
            return 'tours'
        elif any(word in text for word in ['plant sale', 'sale', 'marketplace']):
            return 'shopping'
        elif any(word in text for word in ['lecture', 'talk', 'presentation', 'discussion']):
            return 'education'
        elif any(word in text for word in ['family', 'kids', 'children', 'youth']):
            return 'family'
        elif any(word in text for word in ['music', 'concert', 'performance']):
            return 'music'
        elif any(word in text for word in ['volunteer', 'volunteering']):
            return 'community'
        else:
            # Default to nature/outdoors for botanical garden
            return 'outdoors'

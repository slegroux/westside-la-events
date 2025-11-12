"""
Scraper for Théâtre Raymond Kabbaz events.
Source: https://www.theatreraymondkabbaz.com/upcoming-events
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class RaymondKabbazScraper(BaseScraper):
    """Scraper for Théâtre Raymond Kabbaz events."""

    def __init__(self):
        super().__init__('Théâtre Raymond Kabbaz')
        self.base_url = 'https://www.theatreraymondkabbaz.com'
        self.events_url = f'{self.base_url}/upcoming-events'
        # Fixed venue information
        self.venue_name = 'Théâtre Raymond Kabbaz'
        self.venue_address = '10361 West Pico Boulevard, Los Angeles, CA 90064'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Théâtre Raymond Kabbaz website.

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

            # First check for the main events container
            main_container = soup.find('div', class_='eventlist--upcoming')
            if main_container:
                # Squarespace uses article tags with eventlist-event class for individual event cards
                event_containers = main_container.find_all('article', class_='eventlist-event')
            else:
                # Fallback: search entire page
                event_containers = soup.find_all('article', class_='eventlist-event')

            if not event_containers:
                self.log("No event containers found")
                # Debug: print some of the page structure
                self.log(f"Page title: {soup.find('title').get_text() if soup.find('title') else 'No title'}")
                return events

            self.log(f"Found {len(event_containers)} event containers")

            for item in event_containers:
                try:
                    event = self._parse_event_card(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event card: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event_card(self, item) -> Optional[Event]:
        """
        Parse a single event card from the main listing page.

        Args:
            item: BeautifulSoup element (article) containing event data

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract title from eventlist-title (h1 element)
            title_elem = item.find(class_='eventlist-title')
            if not title_elem:
                return None

            title_link = title_elem.find('a', class_='eventlist-title-link')
            title = self.clean_text(title_link.get_text()) if title_link else self.clean_text(title_elem.get_text())

            # Extract URL
            url = ""
            if title_link and title_link.get('href'):
                url = self.normalize_url(title_link['href'], self.base_url)

            # Extract image
            image_url = ""
            img_tag = item.find('img')
            if img_tag:
                # Squarespace can use data-src for lazy loading
                img_src = img_tag.get('data-src') or img_tag.get('src')
                if img_src:
                    # Remove URL parameters and get clean image URL
                    img_src = img_src.split('?')[0] if '?' in img_src else img_src
                    # Handle protocol-relative URLs
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    image_url = self.normalize_url(img_src, self.base_url)

            # Extract date and time from eventlist-meta (ul element)
            event_date = None
            time_text = ""
            meta_elem = item.find('ul', class_='eventlist-meta')
            if meta_elem:
                # Look for the date in a <time> element with datetime attribute
                date_time_elem = meta_elem.find('time', class_='event-date')
                if date_time_elem:
                    datetime_str = date_time_elem.get('datetime')
                    if datetime_str:
                        try:
                            event_date = date_parser.parse(datetime_str)
                        except Exception as e:
                            self.log(f"Error parsing datetime '{datetime_str}': {e}")

                # Look for start time
                time_elem = meta_elem.find('time', class_='event-time-localized-start')
                if time_elem:
                    time_text = self.clean_text(time_elem.get_text())
                    # Combine date and time
                    if event_date and time_text:
                        event_date = self._parse_datetime(event_date, time_text)

            # Extract description
            description = ""
            desc_elem = item.find('div', class_='eventlist-description')
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())

            # Extract category from category link
            category = self._extract_category(item, title, description)

            # If we have a URL and need more details, scrape the detail page
            if url and (not description or len(description) < 50):
                return self._scrape_event_detail(url, title, event_date, image_url)

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category=category
            )

        except Exception as e:
            self.log(f"Error in _parse_event_card: {e}")
            import traceback
            self.log(traceback.format_exc())
            return None

    def _scrape_event_detail(
        self,
        url: str,
        title: str = None,
        event_date: datetime = None,
        image_url: str = None
    ) -> Optional[Event]:
        """
        Scrape detailed information from an individual event page.

        Args:
            url: URL of the event detail page
            title: Pre-parsed title (optional)
            event_date: Pre-parsed event date (optional)
            image_url: Pre-parsed image URL (optional)

        Returns:
            Event object or None if scraping fails
        """
        try:
            html = self.fetch_page(url)
            if not html:
                return None

            soup = self.parse_html(html)

            # Extract title if not provided
            if not title:
                title_elem = soup.find('h1', class_='eventitem-title') or soup.find('h1')
                title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

            # Extract description from event content
            description = ""
            # Look for Squarespace content blocks
            content_elem = soup.find('div', class_='eventitem-column-content') or \
                          soup.find('div', class_='sqs-block-content')

            if content_elem:
                # Remove unwanted elements
                for unwanted in content_elem.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    unwanted.decompose()

                # Get all paragraphs
                paragraphs = content_elem.find_all('p')
                description = ' '.join([self.clean_text(p.get_text()) for p in paragraphs])

            # Fallback: get all paragraphs from the page
            if not description:
                paragraphs = soup.find_all('p')
                description = ' '.join([self.clean_text(p.get_text()) for p in paragraphs[:3]])

            # Extract date if not provided
            if not event_date:
                date_elem = soup.find('time', class_='event-date') or \
                           soup.find('div', class_='eventitem-meta-date')

                if date_elem:
                    date_str = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                    try:
                        event_date = date_parser.parse(date_str, fuzzy=True)
                    except Exception as e:
                        self.log(f"Error parsing date from detail page: {e}")

            # Extract image if not provided
            if not image_url:
                img_elem = soup.find('img', class_='eventitem-column-thumbnail') or \
                          soup.find('img', {'data-src': True}) or \
                          soup.find('img', src=True)

                if img_elem:
                    # Squarespace uses data-src for lazy loading
                    img_src = img_elem.get('data-src') or img_elem.get('src')
                    if img_src:
                        image_url = self.normalize_url(img_src, self.base_url)

            # Extract price information
            is_free = False
            price = None
            price_text = f"{title} {description}".lower()

            if any(word in price_text for word in ['free', 'no cost', 'no admission', 'complimentary']):
                is_free = True
            else:
                # Try to extract price
                price_match = re.search(r'\$(\d+(?:\.\d{2})?)', price_text)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                    except ValueError:
                        pass

            # Extract category
            category = self._extract_category(soup, title, description)

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category=category,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error scraping detail page {url}: {e}")
            return None

    def _parse_datetime(self, event_date: datetime, time_text: str) -> datetime:
        """
        Combine date with time text to create full datetime.

        Args:
            event_date: Base date
            time_text: Time string (e.g., "7:00 PM 10:00 PM" or "7:00 PM - 10:00 PM")

        Returns:
            datetime with time information
        """
        try:
            # Extract first time (start time)
            # Patterns: "7:00 PM", "19:00"
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?)', time_text, re.IGNORECASE)
            if time_match:
                time_str = time_match.group(1)
                # Parse time
                parsed_time = date_parser.parse(time_str, fuzzy=True)
                # Combine date with time
                event_date = event_date.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=0,
                    microsecond=0
                )
        except Exception as e:
            self.log(f"Error parsing time '{time_text}': {e}")

        return event_date

    def _extract_category(self, element, title: str, description: str) -> str:
        """
        Extract or infer category from event data.

        Args:
            element: BeautifulSoup element (could be card or detail page)
            title: Event title
            description: Event description

        Returns:
            Category string
        """
        # Look for explicit category tags/links
        category_elem = element.find('a', href=re.compile(r'\?category=')) if element else None
        if category_elem:
            category_match = re.search(r'category=([^&]+)', category_elem.get('href', ''))
            if category_match:
                return category_match.group(1).replace('-', ' ').replace('+', ' ').title()

        # Infer from content
        content = f"{title} {description}".lower()

        # Category keywords
        if any(word in content for word in ['concert', 'music', 'orchestra', 'jazz', 'festival', 'performance']):
            return 'Music'
        elif any(word in content for word in ['film', 'movie', 'cinema', 'screening']):
            return 'Film'
        elif any(word in content for word in ['dance', 'ballet', 'choreograph']):
            return 'Dance'
        elif any(word in content for word in ['theater', 'theatre', 'play', 'drama']):
            return 'Theater'
        elif any(word in content for word in ['exhibition', 'gallery', 'art', 'artist']):
            return 'Art'
        elif any(word in content for word in ['lecture', 'talk', 'discussion', 'seminar']):
            return 'Talk'
        elif any(word in content for word in ['workshop', 'class', 'lesson']):
            return 'Workshop'

        # Default for cultural venue
        return 'Cultural'

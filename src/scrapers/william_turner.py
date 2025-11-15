"""
Scraper for William Turner Gallery events.
Source: https://www.williamturnergallery.com/events
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class WilliamTurnerScraper(BaseScraper):
    """Scraper for William Turner Gallery events."""

    def __init__(self):
        super().__init__('William Turner Gallery')
        self.base_url = 'https://www.williamturnergallery.com'
        self.events_url = f'{self.base_url}/events'
        # Fixed venue information
        self.venue_name = 'William Turner Gallery'
        self.venue_address = '2525 Michigan Ave, Bergamot Station Arts Center B5, Santa Monica, CA 90404'

    def scrape(self) -> List[Event]:
        """
        Scrape events from William Turner Gallery website.

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

            # Find event items - Squarespace uses article.eventlist-event
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
            # Extract title from h1 element with eventlist-title class
            title = ""
            title_elem = item.find('h1', class_='eventlist-title')
            if title_elem:
                title_link = title_elem.find('a')
                title = self.clean_text(title_link.get_text() if title_link else title_elem.get_text())

            if not title:
                return None

            # Extract URL from the title link
            url = ""
            title_link = title_elem.find('a') if title_elem else None
            if title_link and title_link.get('href'):
                url = self.normalize_url(title_link['href'], self.base_url)

            # Extract date from time element with datetime attribute
            event_date = None
            time_elem = item.find('time', class_='event-date')
            if time_elem:
                datetime_str = time_elem.get('datetime')
                if datetime_str:
                    try:
                        event_date = date_parser.parse(datetime_str)
                    except Exception as e:
                        self.log(f"Error parsing datetime '{datetime_str}': {e}")

            # Try to get time information from event-time elements
            if event_date:
                start_time_elem = item.find('time', class_='event-time-12hr-start')
                if start_time_elem:
                    time_text = self.clean_text(start_time_elem.get_text())
                    if time_text:
                        try:
                            # Combine date with time
                            full_datetime_str = f"{event_date.strftime('%Y-%m-%d')} {time_text}"
                            event_date = date_parser.parse(full_datetime_str)
                        except Exception as e:
                            self.log(f"Error parsing time '{time_text}': {e}")

            if not event_date:
                self.log(f"No date found for event: {title}")
                return None

            # Skip past events (older than yesterday)
            if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                return None

            # Extract image from eventlist-thumbnail
            image_url = ""
            img_tag = item.find('img', class_='eventlist-thumbnail')
            if img_tag:
                # Squarespace can use data-src or data-image for lazy loading
                img_src = img_tag.get('data-src') or img_tag.get('data-image') or img_tag.get('src')
                if img_src:
                    # Remove URL parameters and get clean image URL
                    img_src = img_src.split('?')[0] if '?' in img_src else img_src
                    # Handle protocol-relative URLs
                    if img_src.startswith('//'):
                        img_src = 'https:' + img_src
                    image_url = self.normalize_url(img_src, self.base_url)

            # Try to get more details from the event detail page if URL exists
            if url:
                detailed_event = self._scrape_event_detail(url, title, event_date, image_url)
                if detailed_event:
                    return detailed_event

            # Fallback: create event with available data
            return self.create_event(
                title=title,
                description="",
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category="Art"  # Gallery exhibitions
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

            # Look for Squarespace content blocks - try multiple strategies
            content_elem = soup.find('div', class_='eventitem-column-content')

            if not content_elem:
                # Try to find the main content area
                content_elem = soup.find('div', class_='sqs-block-content')

            if not content_elem:
                # Try to find any content section
                content_elem = soup.find('section', class_='eventitem-body')

            if content_elem:
                # Remove unwanted elements
                for unwanted in content_elem.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    unwanted.decompose()

                # Get all paragraphs
                paragraphs = content_elem.find_all('p')
                if paragraphs:
                    description = ' '.join([self.clean_text(p.get_text()) for p in paragraphs])
                else:
                    # If no paragraphs, get text directly
                    description = self.clean_text(content_elem.get_text())

            # Fallback: get description from meta tags or any paragraphs
            if not description or len(description) < 20:
                # Try meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'}) or \
                           soup.find('meta', attrs={'property': 'og:description'})
                if meta_desc and meta_desc.get('content'):
                    description = meta_desc['content']
                else:
                    # Get first few paragraphs from the page
                    paragraphs = soup.find_all('p')
                    if paragraphs:
                        description = ' '.join([self.clean_text(p.get_text()) for p in paragraphs[:3]])

            # Extract date if not provided
            if not event_date:
                date_elem = soup.find('time', class_='event-date')

                if not date_elem:
                    date_elem = soup.find('div', class_='eventitem-meta-date')

                if date_elem:
                    date_str = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                    try:
                        event_date = date_parser.parse(date_str, fuzzy=True)
                    except Exception as e:
                        self.log(f"Error parsing date from detail page: {e}")

            # Extract end date if available
            end_date = None
            end_date_elem = soup.find('time', class_='event-time-localized-end')
            if end_date_elem:
                end_date_str = end_date_elem.get('datetime') or self.clean_text(end_date_elem.get_text())
                try:
                    end_date = date_parser.parse(end_date_str, fuzzy=True)
                except Exception as e:
                    self.log(f"Error parsing end date: {e}")

            # Extract image if not provided
            if not image_url:
                img_elem = soup.find('img', class_='eventitem-column-thumbnail')

                if not img_elem:
                    img_elem = soup.find('img', {'data-src': True})

                if not img_elem:
                    img_elem = soup.find('img', src=True)

                if img_elem:
                    # Squarespace uses data-src for lazy loading
                    img_src = img_elem.get('data-src') or img_elem.get('src')
                    if img_src:
                        # Remove URL parameters
                        img_src = img_src.split('?')[0] if '?' in img_src else img_src
                        # Handle protocol-relative URLs
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        image_url = self.normalize_url(img_src, self.base_url)

            # Extract price information
            is_free = False
            price = None
            price_text = f"{title} {description}".lower()

            # Most gallery exhibitions are free admission
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
                else:
                    # Default to free for art galleries
                    is_free = True

            # Category is Art for gallery exhibitions
            category = "Art"

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                category=category,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error scraping detail page {url}: {e}")
            import traceback
            self.log(traceback.format_exc())
            return None

"""
Scraper for Italian Cultural Institute of Los Angeles (IIC LA) events.
Source: https://iiclosangeles.esteri.it/en/gli_eventi/calendario/
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class IICLAScraper(BaseScraper):
    """Scraper for Italian Cultural Institute of Los Angeles events."""

    def __init__(self):
        super().__init__('IIC Los Angeles')
        self.base_url = 'https://iiclosangeles.esteri.it'
        self.events_url = f'{self.base_url}/en/gli_eventi/calendario/'
        # Fixed venue information
        self.venue_name = 'Italian Cultural Institute of Los Angeles'
        self.venue_address = '1023 Hilgard Ave, Los Angeles, CA 90024'

    def scrape(self) -> List[Event]:
        """
        Scrape events from IIC LA website.

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

            # Look for links to event detail pages
            # The site doesn't have distinct event containers, so we'll use the URL-based approach
            event_containers = []

            # Always use the URL-based approach for this site
            if not event_containers:
                # Look for links to /en/gli_eventi/calendario/[event-slug]/
                event_links = soup.find_all('a', href=re.compile(r'/en/gli_eventi/calendario/.+/$'))

                # Deduplicate URLs (each event may have multiple links)
                seen_urls = set()
                unique_links = []
                for link in event_links:
                    url = self.normalize_url(link['href'], self.base_url)
                    if url not in seen_urls:
                        seen_urls.add(url)
                        unique_links.append(url)

                for event_url in unique_links:
                    try:
                        event = self._scrape_event_detail(event_url)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error scraping event detail: {e}")
                        continue
            else:
                # Parse event cards on main page
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
            item: BeautifulSoup element containing event data

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract title - look in h5, h3, h2, or link text
            title_elem = item.find('h5') or item.find('h3') or item.find('h2') or item.find('a')
            if not title_elem:
                return None
            title = self.clean_text(title_elem.get_text())

            # Extract URL - look for "Read more" link or title link
            link_elem = item.find('a', href=True)
            url = self.normalize_url(link_elem['href'], self.base_url) if link_elem else ""

            # Extract image
            img_elem = item.find('img', src=True)
            image_url = self.normalize_url(img_elem['src'], self.base_url) if img_elem else ""

            # Extract date - look for date text (e.g., "Mon Sep 29 2025 Sat Dec 13 2025")
            date_text = ""
            # Try to find date in various possible locations
            date_patterns = [
                item.find('time'),
                item.find('span', class_=lambda x: x and 'date' in x.lower()),
                item.find('div', class_=lambda x: x and 'date' in x.lower()),
            ]

            for date_elem in date_patterns:
                if date_elem:
                    date_text = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                    break

            # If still no date found, search in all text
            if not date_text:
                all_text = item.get_text()
                # Look for date pattern like "Mon Sep 29 2025 Sat Dec 13 2025"
                date_match = re.search(r'([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4})', all_text)
                if date_match:
                    date_text = date_match.group(1)

            event_date, end_date = self._parse_dates(date_text)

            # Extract description
            desc_elem = item.find('p') or item.find('div', class_=lambda x: x and 'description' in x.lower())
            description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

            # If we have a URL and minimal info, try to get more details from the detail page
            if url and not description:
                return self._scrape_event_detail(url, title, event_date, end_date, image_url)

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url
            )

        except Exception as e:
            self.log(f"Error in _parse_event_card: {e}")
            return None

    def _scrape_event_detail(
        self,
        url: str,
        title: str = None,
        event_date: datetime = None,
        end_date: datetime = None,
        image_url: str = None
    ) -> Optional[Event]:
        """
        Scrape detailed information from an individual event page.

        Args:
            url: URL of the event detail page
            title: Pre-parsed title (optional)
            event_date: Pre-parsed event date (optional)
            end_date: Pre-parsed end date (optional)
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
                title_elem = soup.find('h1') or soup.find('h2', class_=lambda x: x and 'title' in x.lower())
                title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

            # Extract description - look for main content area
            description = ""
            desc_elem = soup.find('div', class_=lambda x: x and any(word in str(x).lower() for word in ['content', 'description', 'body', 'article']))
            if desc_elem:
                # Get text but exclude navigation, headers, footers
                for unwanted in desc_elem.find_all(['nav', 'header', 'footer', 'script', 'style']):
                    unwanted.decompose()
                description = self.clean_text(desc_elem.get_text())

            # Fallback: get all paragraphs
            if not description:
                paragraphs = soup.find_all('p')
                description = ' '.join([self.clean_text(p.get_text()) for p in paragraphs[:3]])

            # Extract dates if not provided
            if not event_date or not end_date:
                date_text = ""
                # Look for date information in structured elements
                date_elem = soup.find('time') or \
                           soup.find('div', class_=lambda x: x and 'date' in str(x).lower()) or \
                           soup.find('span', class_=lambda x: x and 'date' in str(x).lower())

                if date_elem:
                    date_text = date_elem.get('datetime') or self.clean_text(date_elem.get_text())
                else:
                    # Look for date patterns in the full text
                    all_text = soup.get_text()
                    # Find date patterns like "September 29 2025" or "Sep 29 2025"
                    date_matches = re.findall(r'([A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4})', all_text)
                    if date_matches:
                        # If we have 2+ dates, assume start and end date
                        if len(date_matches) >= 2:
                            date_text = f"{date_matches[0]} - {date_matches[1]}"
                        else:
                            date_text = date_matches[0]

                if date_text:
                    parsed_date, parsed_end_date = self._parse_dates(date_text)
                    event_date = event_date or parsed_date
                    end_date = end_date or parsed_end_date

            # Extract image if not provided
            if not image_url:
                img_elem = soup.find('img', class_=lambda x: x and any(word in str(x).lower() for word in ['featured', 'hero', 'main'])) or \
                          soup.find('img', src=True)
                image_url = self.normalize_url(img_elem['src'], self.base_url) if img_elem else ""

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

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error scraping detail page {url}: {e}")
            return None

    def _parse_dates(self, date_text: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse date text which may contain start and end dates.

        Examples:
            "Mon Sep 29 2025 Sat Dec 13 2025"
            "September 29, 2025"
            "2025-09-29"

        Args:
            date_text: Text containing date information

        Returns:
            Tuple of (start_date, end_date) - end_date may be None
        """
        event_date = None
        end_date = None

        if not date_text:
            return event_date, end_date

        try:
            # Try to split on common separators for date ranges
            # Pattern: "Mon Sep 29 2025 Sat Dec 13 2025" or "Sep 29 - Dec 13, 2025"

            # Look for two distinct dates
            date_parts = re.split(r'\s+-\s+|\s+to\s+|\s+through\s+', date_text, maxsplit=1)

            if len(date_parts) == 2:
                # We have a date range
                try:
                    event_date = date_parser.parse(date_parts[0], fuzzy=True)
                    end_date = date_parser.parse(date_parts[1], fuzzy=True)
                except Exception:
                    pass

            # If parsing range failed, try to find multiple dates in the text
            if not event_date:
                # Find all date-like patterns
                date_matches = re.findall(r'[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}', date_text)
                if len(date_matches) >= 2:
                    try:
                        event_date = date_parser.parse(date_matches[0], fuzzy=True)
                        end_date = date_parser.parse(date_matches[1], fuzzy=True)
                    except Exception:
                        pass
                elif len(date_matches) == 1:
                    try:
                        event_date = date_parser.parse(date_matches[0], fuzzy=True)
                    except Exception:
                        pass

            # Last resort: try to parse the entire string
            if not event_date:
                try:
                    event_date = date_parser.parse(date_text, fuzzy=True)
                except Exception:
                    pass

        except Exception as e:
            self.log(f"Error parsing dates from '{date_text}': {e}")

        return event_date, end_date

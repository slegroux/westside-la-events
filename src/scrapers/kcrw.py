"""
Scraper for KCRW events.
Source: https://www.kcrw.com/events
"""
from datetime import datetime
from typing import List, Dict, Optional
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class KCRWScraper(BaseScraper):
    """Scraper for KCRW events."""

    def __init__(self):
        super().__init__('KCRW')
        self.base_url = 'https://www.kcrw.com'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from KCRW website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # KCRW (kcrw.com) sits behind Vercel's bot challenge for plain
            # requests (HTTP 429 with challenge token). The events list is
            # also rendered client-side by Next.js, so static HTML has no
            # event cards. Use a real browser via Playwright instead.
            html = self.fetch_page_js(
                self.events_url,
                wait_selector='[class*="EventCard_cardContainer__"]',
                timeout=30000
            )
            if not html:
                self.log("Failed to fetch events page (JS render)")
                return events

            soup = self.parse_html(html)

            # KCRW uses CSS modules with unique class names
            # Event cards have class starting with EventCard_cardContainer__
            event_items = soup.find_all('div', class_=lambda x: x and 'EventCard_cardContainer__' in x)

            # Fallback: CSS module class changes on every Next.js rebuild, use semantic HTML
            if not event_items:
                self.log("Primary CSS module selector failed, trying semantic HTML fallback")
                event_items = soup.find_all('article')
            if not event_items:
                event_items = soup.find_all('li', attrs={'data-testid': True})

            if not event_items:
                self.log("No event cards found on page")
                return events

            self.log(f"Found {len(event_items)} event cards")

            # Detail pages also sit behind Vercel's bot challenge, so
            # plain HTTP prefetching returns HTML challenge pages instead
            # of real content. Skip detail fetching — card data (title,
            # date, venue, tag, image, URL) is sufficient. Running
            # Playwright per detail page would explode runtime (16+ JS
            # navigations) for minimal gain (description text).

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
        # Extract title - in EventCard_cardTitle__
        title_elem = item.find('p', class_=lambda x: x and 'EventCard_cardTitle__' in x)
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract date - in EventCard_date__
        date_elem = item.find('div', class_=lambda x: x and 'EventCard_date__' in x)
        event_date = None
        if date_elem:
            # Date is split into month and day
            date_parts = [s.strip() for s in date_elem.stripped_strings]
            if len(date_parts) >= 2:
                # Construct date string like "Nov 14" and add current year
                from datetime import datetime
                current_year = datetime.now().year
                date_str = f"{date_parts[0]} {date_parts[1]} {current_year}"
                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Failed to parse date '{date_str}': {e}")

        # Extract venue - in small-text class
        venue_elem = item.find('p', class_='small-text')
        venue_name = ""
        address = ""
        if venue_elem:
            # Format is typically "Venue Name, City, State"
            full_location = self.clean_text(venue_elem.get_text())
            parts = [p.strip() for p in full_location.split(',')]
            if parts:
                venue_name = parts[0]
                address = full_location

        # Extract category/tags
        tags = item.find_all('div', class_=lambda x: x and 'Tag_tag__' in x)
        category = None
        if tags:
            # Use first meaningful tag as category
            tag_texts = [tag.get_text(strip=True) for tag in tags]
            # Skip generic tags like "Featured"
            for tag in tag_texts:
                if tag.lower() not in ['featured', 'kcrw presents']:
                    category = tag
                    break

        # Extract URL - parent <a> tag wraps the card
        parent_link = item.find_parent('a')
        url = ""
        if parent_link and parent_link.get('href'):
            url = self.normalize_url(parent_link['href'], self.base_url)

        # Extract image
        img_elem = item.find('img')
        image_url = ""
        if img_elem:
            src = img_elem.get('src', '')
            if src:
                image_url = src  # Already full URL from Contentful CDN

        # Detail pages are behind Vercel bot challenge; skip them and
        # rely on card data only.
        description = ""
        end_date = None
        price = None
        is_free = False

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
            Dictionary with event details (description, event_date, end_date, price, etc.)
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
            self.log(f"Fetching details from {event_url}")
            html = self.fetch_page(event_url)
            if not html:
                return details

            soup = self.parse_html(html)

            # Extract description paragraphs
            # Strategy: Get first few substantial paragraphs before the donation message
            paragraphs = soup.find_all('p')
            description_parts = []

            for p in paragraphs:
                text = self.clean_text(p.get_text())

                # Skip short paragraphs and footer content
                if len(text) < 50:
                    continue
                if any(keyword in text.lower() for keyword in ['donate to kcrw', 'copyright', 'kcrw member']):
                    break  # Stop at footer content

                # Add this paragraph to description
                description_parts.append(text)

                # Usually descriptions are 1-3 paragraphs
                if len(description_parts) >= 3:
                    break

            details['description'] = ' '.join(description_parts)

            # Extract date and time from page
            # KCRW format: "Tue Nov 11, 2025 • 6:00 PM"
            time_spans = soup.find_all('span', class_='paragraph')
            for span in time_spans:
                text = span.get_text(strip=True)
                # Look for date/time pattern
                if re.search(r'[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+•\s+\d{1,2}:\d{2}\s+[AP]M', text):
                    try:
                        # Remove the bullet separator
                        date_time_str = text.replace('•', '').strip()
                        details['event_date'] = date_parser.parse(date_time_str)
                        self.log(f"Parsed event date/time: {details['event_date']}")
                        break
                    except Exception as e:
                        self.log(f"Could not parse date/time '{text}': {e}")

            # Extract price information
            page_text = soup.get_text()

            # Check for free events
            if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                free_context = re.search(r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free', page_text, re.IGNORECASE)
                if free_context or 'free' in details['description'].lower():
                    details['is_free'] = True
                    details['price'] = None

            # Look for price patterns
            if not details['is_free']:
                price_patterns = [
                    r'\$(\d+)(?:-\$?(\d+))?',  # $25 or $25-$75
                    r'(?:from\s+)?\$(\d+)',     # from $25
                    r'(?:ticket(?:s)?|admission)[:is\s]+\$(\d+)',  # tickets: $25
                ]

                for pattern in price_patterns:
                    price_match = re.search(pattern, page_text, re.IGNORECASE)
                    if price_match:
                        try:
                            details['price'] = float(price_match.group(1))
                            break
                        except (ValueError, TypeError, IndexError):
                            continue

            # Get high-res image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                details['image_url'] = og_image.get('content', '')

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

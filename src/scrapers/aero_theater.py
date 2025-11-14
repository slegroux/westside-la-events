"""
Scraper for Aero Theater (American Cinematheque) events.
Source: https://www.americancinematheque.com/now-showing/?event_location=54

Note: This site uses WooCommerce FooEvents plugin with JavaScript rendering.
The events are loaded dynamically, so we use Playwright with extended wait times.
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re
import time

from .base import BaseScraper
from src.data.models import Event


class AeroTheaterScraper(BaseScraper):
    """Scraper for Aero Theater events."""

    def __init__(self):
        super().__init__('Aero Theater')
        self.base_url = 'https://www.americancinematheque.com'
        self.events_url = f'{self.base_url}/now-showing/?event_location=54&view_type=list'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aero Theater website.
        Uses Playwright for JavaScript rendering with custom logic.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Use custom Playwright fetch with longer waits for dynamic content
            html = self._fetch_with_playwright()

            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Try multiple selectors for event cards
            event_cards = soup.find_all('article', class_='card')
            if not event_cards:
                event_cards = soup.find_all('div', class_=lambda x: x and 'event' in str(x).lower())
            if not event_cards:
                event_cards = soup.find_all('div', class_=lambda x: x and 'film' in str(x).lower())

            self.log(f"Found {len(event_cards)} event cards")

            for i, card in enumerate(event_cards, 1):
                try:
                    event = self._parse_event_card(card)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_cards)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event_card(self, card) -> Optional[Event]:
        """
        Parse an event card from the listing page.

        Args:
            card: BeautifulSoup element representing an event card

        Returns:
            Event object or None
        """
        try:
            # Extract title - try multiple patterns
            title = None
            title_elem = (
                card.find('h2') or
                card.find('h3') or
                card.find(class_=lambda x: x and 'title' in str(x).lower())
            )
            if title_elem:
                title = self.clean_text(title_elem.get_text())

            if not title:
                self.log("No title found, skipping event")
                return None

            # Extract description
            description = ""
            desc_elem = (
                card.find('p', class_=lambda x: x and 'description' in str(x).lower()) or
                card.find('div', class_=lambda x: x and 'excerpt' in str(x).lower()) or
                card.find('p')
            )
            if desc_elem:
                description = self.clean_text(desc_elem.get_text())

            # Extract URL
            url = self.events_url
            link_elem = card.find('a', href=True)
            if link_elem:
                url = self.normalize_url(link_elem['href'], self.base_url)

            # Extract date/time
            event_date = None
            end_date = None

            # Look for time element
            time_elem = card.find('time')
            if time_elem:
                datetime_str = time_elem.get('datetime')
                if datetime_str:
                    try:
                        event_date = date_parser.parse(datetime_str)
                    except:
                        pass

            # If no time element, look for date text
            if not event_date:
                date_elem = card.find(class_=lambda x: x and ('date' in str(x).lower() or 'time' in str(x).lower()))
                if date_elem:
                    date_text = self.clean_text(date_elem.get_text())
                    event_date = self._parse_date_text(date_text)

            # Extract image
            image_url = ""
            img_elem = card.find('img')
            if img_elem:
                image_url = (
                    img_elem.get('src') or
                    img_elem.get('data-src') or
                    img_elem.get('data-lazy-src') or
                    ""
                )
                if image_url and not image_url.startswith('http'):
                    image_url = self.normalize_url(image_url, self.base_url)

            # Extract price
            price = None
            is_free = False
            price_elem = card.find(class_=lambda x: x and 'price' in str(x).lower())
            if price_elem:
                price_text = self.clean_text(price_elem.get_text()).lower()
                if 'free' in price_text:
                    is_free = True
                    price = 0.0
                else:
                    # Try to extract numeric price
                    price_match = re.search(r'\$?\s*(\d+(?:\.\d{2})?)', price_text)
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                        except:
                            pass

            # Venue details
            venue_name = "Aero Theatre"
            address = "1328 Montana Ave, Santa Monica, CA 90403"

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                end_date=end_date,
                url=url,
                image_url=image_url,
                category="Film",
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing event card: {e}")
            return None

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """
        Parse date from text string.

        Args:
            date_text: Date text to parse

        Returns:
            datetime object or None
        """
        if not date_text:
            return None

        try:
            # Try standard parsing first
            return date_parser.parse(date_text, fuzzy=True)
        except:
            pass

        # Try to extract month/day patterns
        patterns = [
            r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?',  # "January 15th"
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',       # "1/15/2024"
            r'(\d{1,2})-(\d{1,2})-(\d{2,4})',       # "1-15-2024"
        ]

        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return date_parser.parse(match.group(0))
                except:
                    pass

        return None

    def _fetch_with_playwright(self) -> Optional[str]:
        """
        Fetch page using Playwright with custom wait logic for dynamic content.
        Falls back to regular HTTP fetch if Playwright fails.

        Returns:
            HTML content or None on failure
        """
        # First, try regular HTTP fetch as it's faster and more reliable
        self.log("Trying regular HTTP fetch first...")
        html = self.fetch_page(self.events_url)

        if html and len(html) > 5000:  # Check if we got substantial content
            self.log(f"Successfully fetched page via HTTP ({len(html)} bytes)")
            return html

        # Fallback to Playwright if regular fetch didn't work
        self.log("Regular fetch didn't work, trying Playwright...")
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )

                page = context.new_page()

                # Navigate to page
                try:
                    self.log(f"Navigating to {self.events_url}")
                    page.goto(self.events_url, wait_until='domcontentloaded', timeout=30000)
                    self.log("Page loaded")
                except Exception as e:
                    self.log(f"Navigation error: {e}")
                    browser.close()
                    return None

                # Wait for content to load
                self.log("Waiting for dynamic content to load...")
                time.sleep(5)  # Give JS time to execute

                # Get HTML
                html = page.content()
                browser.close()

                # Rate limiting
                time.sleep(2)

                return html

        except Exception as e:
            self.log(f"Error in Playwright fetch: {e}")
            return None

"""
Scraper for Tripp Santa Monica
URL: https://www.tripsantamonica.com/calendar

IMPLEMENTATION STATUS: Disabled in current environment - HTTPS networking issue

The Tripp calendar uses a fully client-side rendered Wix site. This scraper uses
Playwright to render the JavaScript and extract event data.

ENVIRONMENTAL ISSUE:
- Playwright's Chromium cannot establish HTTPS connections in current environment
- Returns ERR_SOCKET_NOT_CONNECTED for all HTTPS sites
- Works fine with HTTP (tested successfully with http://example.com)
- Will likely work in Docker/Cloud Run/standard Linux containers

TO ENABLE:
1. Test in target deployment environment
2. If successful, set enabled=True in config.py EVENT_SOURCES
3. Add to run_scrapers.py if needed

VENUE INFO:
- Name: Tripp
- Address: 1431 3rd Street Promenade, Santa Monica, CA 90401
- Type: Nightclub/Bar
- Website: https://www.tripsantamonica.com/
"""

import asyncio
from datetime import datetime
import logging
import re
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event

logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(
        "Playwright not installed. Install with: "
        "pip install playwright && playwright install chromium"
    )


class TrippScraper(BaseScraper):
    """Scraper for Tripp Santa Monica events using Playwright."""

    def __init__(self):
        super().__init__(source_name='tripp')
        self.source_url = 'https://www.tripsantamonica.com/calendar'
        self.venue_name = 'Tripp'
        self.venue_address = '1431 3rd Street Promenade, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Tripp calendar.

        Uses Playwright to render JavaScript and extract event data from Wix calendar.
        Currently disabled due to HTTPS networking issues in this environment.

        Returns:
            List of Event objects (empty if Playwright unavailable or errors occur)
        """
        if not PLAYWRIGHT_AVAILABLE:
            self.log("Playwright not available - scraper disabled")
            return []

        try:
            # Run async scraping
            events = asyncio.run(self._scrape_async())
            self.log(f"Successfully scraped {len(events)} events")
            return events

        except Exception as e:
            self.log(f"Error during scraping: {e}")
            return []

    async def _scrape_async(self) -> List[Event]:
        """
        Async method to scrape events using Playwright.

        Returns:
            List of Event objects
        """
        events = []

        async with async_playwright() as p:
            try:
                self.log(f"Launching browser for {self.source_url}")

                # Launch browser with settings optimized for scraping
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                    ]
                )

                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )

                page = await context.new_page()

                # Navigate and wait for content
                self.log("Loading calendar page...")
                await page.goto(self.source_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for Wix site to render
                await asyncio.sleep(5)

                # Extract event data from rendered DOM
                events = await self._extract_events_from_page(page)

                await browser.close()

            except Exception as e:
                self.log(f"Browser automation error: {e}")
                # Log but don't raise - return empty list

        return events

    async def _extract_events_from_page(self, page) -> List[Event]:
        """
        Extract event data from rendered Wix calendar page.

        Args:
            page: Playwright page object

        Returns:
            List of Event objects
        """
        events = []

        try:
            # Save HTML for debugging
            content = await page.content()
            with open('/tmp/tripp_rendered.html', 'w') as f:
                f.write(content)
            self.log("Saved rendered HTML to /tmp/tripp_rendered.html")

            # Take screenshot for debugging
            await page.screenshot(path='/tmp/tripp_calendar.png')
            self.log("Saved screenshot to /tmp/tripp_calendar.png")

            # Try to find event elements in Wix calendar
            # Wix uses various dynamic class names, so we look for common patterns
            event_selectors = [
                'a[href*="/event/"]',  # Event detail links
                '[data-testid*="event"]',  # Data test IDs
                '[class*="event"]',  # Class names containing "event"
                'article',  # Semantic HTML
            ]

            for selector in event_selectors:
                elements = await page.locator(selector).all()
                self.log(f"Found {len(elements)} elements for selector: {selector}")

                for elem in elements:
                    try:
                        # Extract text and link
                        text = await elem.text_content()
                        href = await elem.get_attribute('href')

                        if text and text.strip():
                            self.log(f"Potential event: {text.strip()[:50]}...")

                            # Create basic event object
                            # TODO: Parse dates, times, descriptions when structure is known
                            event = Event(
                                title=text.strip(),
                                venue_name=self.venue_name,
                                address=self.venue_address,
                                url=self._normalize_url(href),
                                source=self.source_name,
                                source_logo_url=self.source_logo_url,
                            )

                            # Geocode if needed
                            if not event.latitude or not event.longitude:
                                self.geocode_event(event)

                            events.append(event)

                    except Exception as e:
                        self.log(f"Error parsing element: {e}")
                        continue

                # If we found events, stop searching with other selectors
                if events:
                    break

        except Exception as e:
            self.log(f"Error extracting events: {e}")

        return events

    def _normalize_url(self, url: Optional[str]) -> Optional[str]:
        """
        Normalize event URL.

        Args:
            url: Raw URL from page

        Returns:
            Full URL or None
        """
        if not url:
            return None

        # Make relative URLs absolute
        if url.startswith('/'):
            return f"https://www.tripsantamonica.com{url}"

        # Return as-is if already absolute
        if url.startswith('http'):
            return url

        return None


def main():
    """Test the scraper."""
    scraper = TrippScraper()
    events = scraper.scrape()

    print(f"\nFound {len(events)} events from Tripp\n")

    if events:
        for event in events:
            print(f"Title: {event.title}")
            print(f"Venue: {event.venue_name}")
            print(f"URL: {event.url}")
            print(f"Location: {event.latitude}, {event.longitude}")
            print("-" * 80)
    else:
        print("No events found.")
        print("\nNote: This scraper requires Playwright and may not work in")
        print("environments with HTTPS networking issues. Try deploying to")
        print("Docker or Cloud Run for better compatibility.")


if __name__ == '__main__':
    main()

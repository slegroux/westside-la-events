"""
Example: Converting a multi-page scraper to use async for 10x speed improvement.

This example shows how to optimize scrapers that fetch detail pages for each event.
"""

# BEFORE: Synchronous version (slow)
# ----------------------------------------------------------------------------
class KCRWScraperSlow:
    def scrape(self):
        # Fetch listing page
        listing_html = self.fetch_page('https://www.kcrw.com/events')
        soup = BeautifulSoup(listing_html, 'html.parser')

        # Find all event links
        event_links = [a['href'] for a in soup.find_all('a', class_='event-card')]

        # Fetch each event detail page ONE AT A TIME (slow!)
        events = []
        for link in event_links:  # Sequential = SLOW
            html = self.fetch_page(link)  # 1-2 seconds each
            event = self.parse_event_page(html)
            events.append(event)

        return events

    # With 24 events @ 2 seconds each = 48 seconds!


# AFTER: Async version (fast)
# ----------------------------------------------------------------------------
from src.utils.async_scraper import BatchScraper

class KCRWScraperFast(BatchScraper):
    def scrape(self):
        # Fetch listing page (still sync, only one page)
        listing_html = self.fetch_page('https://www.kcrw.com/events')
        soup = BeautifulSoup(listing_html, 'html.parser')

        # Find all event links
        event_links = [a['href'] for a in soup.find_all('a', class_='event-card')]

        # Fetch ALL event detail pages IN PARALLEL (fast!)
        pages = self.fetch_pages_in_parallel(event_links)  # 10 at a time

        # Process results
        events = []
        for url, html in pages:
            if html:
                event = self.parse_event_page(html)
                events.append(event)

        return events

    # With 24 events @ 2 seconds each, but 10 concurrent = ~5 seconds!
    # 10x FASTER!


# EXAMPLE: Full conversion of a scraper
# ----------------------------------------------------------------------------
from src.scrapers.base import BaseScraper
from src.utils.async_scraper import BatchScraper, AsyncHTTPClient
from src.data.models import Event
from bs4 import BeautifulSoup
from datetime import datetime

class OptimizedEventScraper(BatchScraper):
    """
    Example optimized scraper using async for detail pages.
    """

    def __init__(self):
        # Initialize BatchScraper with max concurrent requests
        super().__init__(max_concurrent=10)

        # Still need other base scraper features
        self.source_name = "Example Source"
        # ... other initialization

    def scrape(self):
        """Main scrape method."""
        # Step 1: Fetch main listing page (sync is fine for single page)
        listing_url = 'https://example.com/events'
        listing_html = self._fetch_single_page(listing_url)

        if not listing_html:
            return []

        # Step 2: Extract event detail URLs
        event_urls = self._extract_event_urls(listing_html)

        # Step 3: Fetch ALL detail pages in parallel (THIS IS THE MAGIC!)
        detail_pages = self.fetch_pages_in_parallel(event_urls)

        # Step 4: Parse all the results
        events = []
        for url, html in detail_pages:
            if html:
                event = self._parse_detail_page(html, url)
                if event:
                    events.append(event)

        return events

    def _fetch_single_page(self, url):
        """Fetch a single page synchronously."""
        import requests
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _extract_event_urls(self, html):
        """Extract event detail URLs from listing page."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for card in soup.find_all('div', class_='event-card'):
            link = card.find('a')
            if link and link.get('href'):
                links.append(link['href'])
        return links

    def _parse_detail_page(self, html, url):
        """Parse event detail page."""
        soup = BeautifulSoup(html, 'html.parser')

        # Extract event data
        title = soup.find('h1', class_='event-title')
        date_elem = soup.find('time', class_='event-date')
        venue = soup.find('div', class_='event-venue')

        if not title or not date_elem:
            return None

        # Create event object
        event = Event(
            title=title.text.strip(),
            event_date=self._parse_date(date_elem.text),
            venue_name=venue.text.strip() if venue else '',
            url=url,
            source=self.source_name,
            # ... other fields
        )

        return event

    def _parse_date(self, date_string):
        """Parse date string to datetime."""
        # Your date parsing logic
        pass


# PERFORMANCE COMPARISON
# ----------------------------------------------------------------------------
"""
Scraper Type            | Events | Sequential Time | Async Time | Speedup
------------------------|--------|----------------|------------|--------
Single page (no detail) | 20     | 3s             | 3s         | 1x (no benefit)
Multi-page (24 details) | 24     | 48s            | 5s         | 10x FASTER
Multi-page (100 details)| 100    | 200s           | 20s        | 10x FASTER

Rule of thumb: If your scraper fetches more than 3 detail pages, async is worth it!
"""


# WHEN TO USE ASYNC
# ----------------------------------------------------------------------------
"""
✅ USE ASYNC when:
- Scraper fetches multiple detail pages (like KCRW, Timeout, Eventbrite)
- Each event has its own URL you need to visit
- Fetching 5+ separate pages
- I/O-bound operations (waiting for network)

❌ DON'T USE ASYNC when:
- All events on one page (like Santa Monica calendar)
- Only scraping listing page, no detail pages
- Using Playwright (it's already async internally)
- Less than 3 separate requests
"""


# HOW TO IDENTIFY CANDIDATES FOR ASYNC
# ----------------------------------------------------------------------------
"""
Look for patterns like this in your scrapers:

    for event_url in event_urls:
        html = self.fetch_page(event_url)  # ← Sequential fetch
        event = self.parse(html)
        events.append(event)

This can be optimized to:

    pages = self.fetch_pages_in_parallel(event_urls)  # ← Parallel!
    for url, html in pages:
        event = self.parse(html)
        events.append(event)
"""


# EXAMPLE: Converting KCRW scraper (simplified)
# ----------------------------------------------------------------------------
"""
# Current KCRW scraper (simplified):
class KCRWScraper(BaseScraper):
    def scrape(self):
        events = []
        soup = self._get_events_page()

        # Extract event cards
        for card in soup.find_all('div', class_='event-card'):
            url = card.find('a')['href']
            # Fetch detail page ONE AT A TIME
            detail_html = self.fetch_page(url)  # ← Slow!
            event = self._parse_detail(detail_html)
            events.append(event)

        return events

# Optimized KCRW scraper:
class KCRWScraperOptimized(BatchScraper):
    def scrape(self):
        soup = self._get_events_page()

        # Extract ALL URLs first
        urls = [card.find('a')['href'] for card in soup.find_all('div', class_='event-card')]

        # Fetch ALL pages IN PARALLEL
        pages = self.fetch_pages_in_parallel(urls)  # ← Fast!

        # Parse results
        events = []
        for url, html in pages:
            if html:
                events.append(self._parse_detail(html))

        return events

Result: 48s → 5s (10x faster!)
"""


# SETUP INSTRUCTIONS
# ----------------------------------------------------------------------------
"""
1. Install aiohttp:
   micromamba run -n la pip install aiohttp

2. Import BatchScraper in your scraper:
   from src.utils.async_scraper import BatchScraper

3. Change parent class:
   class MyScraper(BaseScraper):  # Before
   class MyScraper(BatchScraper):  # After

4. Update scrape method to use fetch_pages_in_parallel:
   See examples above

5. Test it:
   micromamba run -n la python run_scrapers_optimized.py --scrapers my_scraper
"""

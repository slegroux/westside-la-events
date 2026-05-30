"""
Base scraper class for event scrapers.
Provides common functionality for all scrapers.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
import time
import os
import requests
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

import config
from src.data.models import Event
from src.utils.geocoding import get_geocoding_service, resolve_known_venue_address
from src.utils.categories import classify_event
from src.utils.logo_scraper import LogoScraper
from src.utils.geo_filter import validate_event_location, is_denylisted_venue


LA_TZ = ZoneInfo("America/Los_Angeles")


def normalize_event_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Canonical event datetime: naive, LA-local.

    Scrapers feed a mix of naive datetimes (already LA-local) and aware
    datetimes (often UTC from APIs). Persisting both shapes leaves
    timezone offsets in event_date strings, which breaks day-boundary
    comparisons because SQLite's date() converts those to UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(LA_TZ).replace(tzinfo=None)


class BaseScraper(ABC):
    """Abstract base class for event scrapers."""

    def __init__(self, source_name: str):
        """
        Initialize base scraper.

        Args:
            source_name: Name of the event source
        """
        self.source_name = source_name
        self.geocoding_service = get_geocoding_service()
        self.logo_scraper = LogoScraper()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SCRAPER_CONFIG['user_agent']
        })
        # Provide a default URL attribute so generic scraper checks can rely on it.
        self.base_url = ""
        self._page_cache = {}

        # Allow disabling logo fetches in constrained/offline environments.
        disable_logos = os.getenv('SCRAPER_DISABLE_LOGOS', 'false').lower() == 'true'
        if disable_logos:
            self.source_logo_url = ""
        else:
            # Download and cache logo locally for this source
            self.source_logo_url = self.logo_scraper.download_logo(source_name)

    @abstractmethod
    def scrape(self) -> List[Event]:
        """
        Scrape events from the source.

        Returns:
            List of Event objects
        """
        pass

    def prefetch_pages(self, urls: List[str], max_concurrent: int = 5) -> None:
        """
        Pre-fetch multiple URLs concurrently and cache results.
        Subsequent fetch_page() calls for these URLs will return instantly from cache.

        Args:
            urls: List of URLs to pre-fetch
            max_concurrent: Maximum concurrent requests (default 5 for politeness)
        """
        from src.utils.async_scraper import AsyncHTTPClient

        # Filter out already-cached URLs
        uncached = [u for u in urls if u and u not in self._page_cache]
        if not uncached:
            return

        self.log(f"Pre-fetching {len(uncached)} pages concurrently...")
        client = AsyncHTTPClient(max_concurrent=max_concurrent, delay=0.2)
        # Pass session cookies and headers so sites that require them work
        client.headers = dict(self.session.headers)
        cookies = {c.name: c.value for c in self.session.cookies} if self.session.cookies else None
        results = client.fetch_all_sync(uncached, cookies=cookies)

        for url, content in zip(uncached, results):
            if content is not None:
                self._page_cache[url] = content

        fetched = sum(1 for c in results if c is not None)
        self.log(f"Pre-fetched {fetched}/{len(uncached)} pages successfully")

    def fetch_page(self, url: str, retry: int = 3) -> Optional[str]:
        """
        Fetch a web page with retries. Returns from cache if pre-fetched.

        Args:
            url: URL to fetch
            retry: Number of retries on failure

        Returns:
            Page HTML content or None if fetch fails
        """
        # Check prefetch cache first (only use if successfully fetched)
        if url in self._page_cache:
            cached = self._page_cache.pop(url)
            if cached is not None:
                return cached
            # Prefetch already tried and failed for this URL; don't retry
            # sequentially as that would burn timeout budget on unreachable pages
            return None

        for attempt in range(retry):
            try:
                response = self.session.get(
                    url,
                    timeout=config.SCRAPER_CONFIG['timeout_seconds']
                )
                response.raise_for_status()

                # Rate limiting
                time.sleep(config.SCRAPER_CONFIG['delay_seconds'])

                return response.text

            except requests.RequestException as e:
                self.log(f"Error fetching {url} (attempt {attempt + 1}/{retry}): {e}")
                error_text = str(e)
                # DNS resolution failures are not transient here; fail fast.
                if 'NameResolutionError' in error_text or 'Failed to resolve' in error_text:
                    return None
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
                return None

        return None

    def fetch_page_js(self, url: str, wait_selector: str = None, timeout: int = 30000) -> Optional[str]:
        """
        Fetch a web page that requires JavaScript rendering using Playwright.

        Args:
            url: URL to fetch
            wait_selector: CSS selector to wait for (optional)
            timeout: Maximum wait time in milliseconds (default: 30000)

        Returns:
            Page HTML content after JavaScript execution or None if fetch fails
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                # Launch browser with stealth arguments
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security'
                    ]
                )

                # Create context with realistic viewport and user agent
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Los_Angeles',
                    permissions=['geolocation'],
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )

                page = context.new_page()

                # Remove webdriver detection
                page.add_init_script("""
                    // Overwrite the `plugins` property to use a custom getter.
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    // Overwrite the `plugins` property to use a custom getter.
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });

                    // Overwrite the `languages` property to use a custom getter.
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });

                    // Pass chrome checks
                    window.chrome = {
                        runtime: {}
                    };

                    // Pass permissions check
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)

                # Navigate to URL
                page.goto(url, wait_until='domcontentloaded', timeout=timeout)

                # Wait for specific selector if provided
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout)
                    except:
                        # Continue even if selector not found
                        pass
                else:
                    # Wait a bit for dynamic content
                    page.wait_for_timeout(5000)

                # Get the rendered HTML
                html = page.content()

                browser.close()

                # Rate limiting
                time.sleep(config.SCRAPER_CONFIG['delay_seconds'])

                return html

        except Exception as e:
            self.log(f"Error fetching {url} with JavaScript: {e}")
            return None

    def parse_html(self, html: str) -> BeautifulSoup:
        """
        Parse HTML content with BeautifulSoup.

        Args:
            html: HTML content string

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html, 'lxml')

    def create_event(
        self,
        title: str,
        description: str = "",
        venue_name: str = "",
        address: str = "",
        event_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        url: str = "",
        image_url: str = "",
        category: str = "",
        price: Optional[float] = None,
        is_free: bool = False,
        price_note: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        strict_geo: bool = False
    ) -> Optional[Event]:
        """
        Create an Event object with geocoding, categorization, and location filtering.

        Args:
            title: Event title
            description: Event description
            venue_name: Venue name
            address: Event address
            event_date: Event start date/time
            end_date: Event end date/time
            url: Event URL
            image_url: Event image URL
            category: Event category (auto-classified if not provided)
            price: Event price (optional)
            is_free: Whether event is free (default False)
            price_note: Additional pricing information (e.g. "Check website for pricing")

        Returns:
            Event object if in coverage area, None otherwise
        """
        # If the venue is listed only by name (no usable street address), swap in
        # its known canonical address so it both geocodes and shows a real address.
        known_addr = resolve_known_venue_address(venue_name)
        if known_addr:
            address = known_addr

        # Geocode (with address normalization + venue-name fallback) if we have
        # anything to locate on. The fallback recovers messy addresses that fail
        # Nominatim verbatim and venue-only events with no street address.
        # Use caller-provided coordinates (e.g. a source's JSON-LD geo) when
        # available; otherwise geocode the address/venue.
        if latitude is None or longitude is None:
            if address or venue_name:
                coords = self.geocoding_service.geocode_with_fallback(address, venue_name=venue_name)
                if coords:
                    latitude, longitude = coords

        # Hard denylist: specific non-Westside venues (e.g. Mid-City farmers
        # markets) that sit inside the coverage box but should never be listed.
        if is_denylisted_venue(venue_name=venue_name, title=title):
            self.log(f"Skipping denylisted venue: '{title}' at {venue_name or address}")
            return None

        # Validate location - filter out events outside Westside/Malibu
        if strict_geo:
            # Stricter validation for aggregator scrapers (e.g. Shore Hotel).
            # When coords are available, accept only by bounding-box — no
            # text/radius fallback that would let distant events slip through.
            # When coords are missing, fall back to address text match only.
            from src.utils.geo_filter import is_in_coverage_area, is_westside_address
            if latitude is not None and longitude is not None:
                is_valid = is_in_coverage_area(latitude, longitude)
                reason = "coordinates_in_bounds" if is_valid else "coordinates_outside_area"
            else:
                is_valid = is_westside_address(address, venue_name=venue_name)
                reason = "address_text_match" if is_valid else "address_not_recognized"
        else:
            is_valid, reason = validate_event_location(
                latitude=latitude,
                longitude=longitude,
                address=address,
                venue_name=venue_name
            )

        if not is_valid:
            self.log(f"Skipping non-Westside event: '{title}' at {venue_name or address} ({reason})")
            return None

        # Auto-classify category if not provided
        if not category:
            category = classify_event(title, description, venue_name)

        return Event(
            title=title.strip() if title else "",
            description=description.strip() if description else "",
            venue_name=venue_name.strip() if venue_name else "",
            address=address.strip() if address else "",
            latitude=latitude,
            longitude=longitude,
            event_date=normalize_event_datetime(event_date),
            end_date=normalize_event_datetime(end_date),
            category=category,
            source=self.source_name,
            url=url.strip() if url else "",
            image_url=image_url.strip() if image_url else "",
            source_logo_url=self.source_logo_url or "",
            price=price,
            is_free=is_free,
            price_note=price_note.strip() if price_note else ""
        )

    def clean_text(self, text: Optional[str]) -> str:
        """
        Clean and normalize text.

        Args:
            text: Text to clean

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    def normalize_url(self, url: str, base_url: str = "") -> str:
        """
        Normalize a URL (handle relative URLs).

        Args:
            url: URL to normalize
            base_url: Base URL for relative URLs

        Returns:
            Normalized absolute URL
        """
        if not url:
            return ""

        # Already absolute URL
        if url.startswith('http://') or url.startswith('https://'):
            return url

        # Relative URL
        if base_url:
            if url.startswith('/'):
                # Get domain from base_url
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{url}"
            else:
                return f"{base_url.rstrip('/')}/{url.lstrip('/')}"

        return url

    def log(self, message: str):
        """
        Log a message.

        Args:
            message: Message to log
        """
        import logging
        logger = logging.getLogger(f"scraper.{self.source_name}")
        logger.info(message)


class ScraperError(Exception):
    """Exception raised for scraper-related errors."""
    pass

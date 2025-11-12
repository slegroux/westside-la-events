"""
Base scraper class for event scrapers.
Provides common functionality for all scrapers.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
import time
import requests
from bs4 import BeautifulSoup

import config
from src.data.models import Event
from src.utils.geocoding import get_geocoding_service
from src.utils.categories import classify_event
from src.utils.logo_scraper import LogoScraper
from src.utils.geo_filter import validate_event_location


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

    def fetch_page(self, url: str, retry: int = 3) -> Optional[str]:
        """
        Fetch a web page with retries.

        Args:
            url: URL to fetch
            retry: Number of retries on failure

        Returns:
            Page HTML content or None if fetch fails
        """
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
                print(f"Error fetching {url} (attempt {attempt + 1}/{retry}): {e}")
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
                # Launch browser in headless mode
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Set user agent
                page.set_extra_http_headers({
                    'User-Agent': config.SCRAPER_CONFIG['user_agent']
                })

                # Navigate to URL
                page.goto(url, wait_until='networkidle', timeout=timeout)

                # Wait for specific selector if provided
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout)
                else:
                    # Default: wait for page to be loaded
                    page.wait_for_load_state('networkidle', timeout=timeout)

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
        is_free: bool = False
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

        Returns:
            Event object if in coverage area, None otherwise
        """
        # Geocode address if provided
        latitude, longitude = None, None
        if address:
            coords = self.geocoding_service.geocode(address)
            if coords:
                latitude, longitude = coords

        # Validate location - filter out events outside Westside/Malibu
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
            event_date=event_date,
            end_date=end_date,
            category=category,
            source=self.source_name,
            url=url.strip() if url else "",
            image_url=image_url.strip() if image_url else "",
            source_logo_url=self.source_logo_url or "",
            price=price,
            is_free=is_free
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
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{self.source_name}] {message}")


class ScraperError(Exception):
    """Exception raised for scraper-related errors."""
    pass

"""
Async utilities for faster scraping with aiohttp.
This module provides async alternatives to the synchronous scraping approach.
"""
import asyncio
import aiohttp
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import config


class AsyncHTTPClient:
    """Async HTTP client for faster concurrent requests."""

    def __init__(self, max_concurrent: int = 5, delay: float = 0.2):
        """
        Initialize async HTTP client.

        Args:
            max_concurrent: Maximum number of concurrent requests
            delay: Delay in seconds between requests for rate limiting
        """
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.headers = {
            'User-Agent': config.SCRAPER_CONFIG['user_agent']
        }

    async def fetch(self,
                   session: aiohttp.ClientSession,
                   url: str,
                   semaphore: asyncio.Semaphore,
                   timeout: int = 30) -> Optional[str]:
        """
        Fetch a single URL asynchronously.

        Args:
            session: aiohttp session
            url: URL to fetch
            semaphore: Concurrency limiter bound to the running loop
            timeout: Request timeout in seconds

        Returns:
            HTML content or None if failed
        """
        async with semaphore:
            try:
                # Small delay between requests for politeness
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
                timeout_obj = aiohttp.ClientTimeout(total=timeout)
                async with session.get(url, timeout=timeout_obj, headers=self.headers) as response:
                    response.raise_for_status()
                    return await response.text()
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                return None

    async def fetch_multiple(self, urls: List[str], cookies: Optional[Dict[str, str]] = None) -> List[Optional[str]]:
        """
        Fetch multiple URLs concurrently.

        Args:
            urls: List of URLs to fetch
            cookies: Optional cookies dict to include with requests

        Returns:
            List of HTML contents (None for failed requests)
        """
        # Create the semaphore inside the coroutine so it binds to the loop
        # that actually runs fetch_multiple (which may be a fresh loop spun up
        # by fetch_all_sync's thread fallback), not whatever loop happened to
        # exist at construction time.
        semaphore = asyncio.Semaphore(self.max_concurrent)
        connector = aiohttp.TCPConnector(limit_per_host=self.max_concurrent)
        async with aiohttp.ClientSession(connector=connector, cookies=cookies) as session:
            tasks = [self.fetch(session, url, semaphore) for url in urls]
            return await asyncio.gather(*tasks)

    def fetch_all_sync(self, urls: List[str], cookies: Optional[Dict[str, str]] = None) -> List[Optional[str]]:
        """
        Synchronous wrapper for async fetch_multiple.

        Safe to call from a synchronous context with no event loop (uses
        asyncio.run) AND from inside an already-running event loop (e.g. when a
        scraper's scrape() is awaited directly rather than run in a thread): in
        that case asyncio.run() would raise "cannot be called from a running
        event loop", so we run the coroutine in a dedicated worker thread with
        its own loop.

        Args:
            urls: List of URLs to fetch
            cookies: Optional cookies dict to include with requests

        Returns:
            List of HTML contents
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No loop running on this thread — safe to drive one directly.
            return asyncio.run(self.fetch_multiple(urls, cookies=cookies))

        # A loop is already running on this thread; offload to a separate
        # thread so we don't try to nest asyncio.run inside it.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                lambda: asyncio.run(self.fetch_multiple(urls, cookies=cookies))
            )
            return future.result()


class BatchScraper:
    """Base class for scrapers that need to fetch multiple pages."""

    def __init__(self, max_concurrent: int = 10):
        """
        Initialize batch scraper.

        Args:
            max_concurrent: Maximum concurrent requests
        """
        self.client = AsyncHTTPClient(max_concurrent=max_concurrent)

    def fetch_pages_in_parallel(self, urls: List[str]) -> List[tuple[str, Optional[str]]]:
        """
        Fetch multiple pages in parallel and return URL-content pairs.

        Args:
            urls: List of URLs to fetch

        Returns:
            List of (url, html_content) tuples
        """
        contents = self.client.fetch_all_sync(urls)
        return list(zip(urls, contents))


def batch_parse_html(html_contents: List[str],
                    parser: str = 'html.parser') -> List[Optional[BeautifulSoup]]:
    """
    Parse multiple HTML contents into BeautifulSoup objects.

    Args:
        html_contents: List of HTML strings
        parser: BeautifulSoup parser to use

    Returns:
        List of BeautifulSoup objects
    """
    soups = []
    for html in html_contents:
        if html:
            try:
                soups.append(BeautifulSoup(html, parser))
            except Exception as e:
                print(f"Error parsing HTML: {e}")
                soups.append(None)
        else:
            soups.append(None)
    return soups


# Example usage in a scraper:
"""
from src.utils.async_scraper import BatchScraper

class MyScraper(BatchScraper):
    def scrape(self):
        # Get list of event URLs
        event_urls = self.get_event_urls()

        # Fetch all event pages in parallel (10x faster!)
        pages = self.fetch_pages_in_parallel(event_urls)

        # Parse and extract events
        events = []
        for url, html in pages:
            if html:
                event = self.parse_event_page(html, url)
                events.append(event)

        return events
"""

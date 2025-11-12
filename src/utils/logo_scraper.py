"""
Utility to scrape and cache source logos.
"""
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Optional, Dict
import hashlib
import logging

logger = logging.getLogger(__name__)


class LogoScraper:
    """Scraper for source logos."""

    # Mapping of source names to their base URLs
    SOURCE_URLS = {
        'Santa Monica': 'https://www.smgov.net',
        'Timeout LA': 'https://www.timeout.com',
        'KCRW': 'https://www.kcrw.com',
        'Discover LA': 'https://www.discoverlosangeles.com',
        'Meetup': 'https://www.meetup.com',
        'Eventbrite': 'https://www.eventbrite.com',
        "M.I.'s Westside Comedy Theater": 'https://westsidecomedy.com',
    }

    # Known logo URLs (fallback if scraping fails)
    FALLBACK_LOGOS = {
        'Santa Monica': 'https://www.smgov.net/SantaMonica.Gov.Theme/Images/Logos/LogoStacked.svg',
        'Timeout LA': 'https://media.timeout.com/images/105686275/image.jpg',
        'KCRW': 'https://images.ctfassets.net/2658fe8gbo8o/4ihQCzOkflDXnbaITo07yM/efa81104badd9a9e4dc8d3cdbd092f32/kcrw-logo.png',
        'Discover LA': 'https://assets.simpleviewinc.com/simpleview/image/upload/c_fill,f_avif,g_xy_center,h_640,q_65,w_640,x_2250,y_1500/v1/clients/losangeles/discoverla_logo_social_f04983de-c052-47e0-80c5-d6b8039c2add.jpg',
        'Meetup': 'https://secure.meetupstatic.com/next/images/shared/online_events.svg?w=640',
        'Eventbrite': 'https://cdn.evbstatic.com/s3-build/fe/build/images/eblogo_white.72eb78bc.svg',
        "M.I.'s Westside Comedy Theater": 'https://westsidecomedy.com/wp-content/uploads/2025/03/WSC-logo.png',
    }

    def __init__(self, cache_dir: str = "static/logos"):
        """Initialize logo scraper with cache directory."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_logo_url(self, source: str) -> Optional[str]:
        """
        Get logo URL for a given source.

        Args:
            source: Source name (e.g., 'Santa Monica', 'Timeout LA')

        Returns:
            URL to logo image or None if not found
        """
        # Try to scrape logo from the source website
        scraped_url = self._scrape_logo(source)
        if scraped_url:
            return scraped_url

        # Fall back to known logo URLs
        return self.FALLBACK_LOGOS.get(source)

    def _scrape_logo(self, source: str) -> Optional[str]:
        """
        Scrape logo from source website.

        Args:
            source: Source name

        Returns:
            URL to logo or None
        """
        base_url = self.SOURCE_URLS.get(source)
        if not base_url:
            logger.warning(f"No URL configured for source: {source}")
            return None

        try:
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Try multiple strategies to find the logo
            logo_url = (
                self._find_logo_in_header(soup, base_url) or
                self._find_logo_in_meta(soup, base_url) or
                self._find_logo_in_footer(soup, base_url)
            )

            return logo_url

        except Exception as e:
            logger.error(f"Error scraping logo for {source}: {e}")
            return None

    def _find_logo_in_header(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find logo in page header."""
        header = soup.find('header') or soup.find('div', class_='header')
        if not header:
            return None

        # Look for logo images
        logo_selectors = [
            ('img', {'class': 'logo'}),
            ('img', {'class': 'site-logo'}),
            ('img', {'id': 'logo'}),
            ('a', {'class': 'logo'}),
            ('a', {'class': 'site-logo'}),
        ]

        for tag, attrs in logo_selectors:
            elem = header.find(tag, attrs)
            if elem:
                if tag == 'img':
                    src = elem.get('src') or elem.get('data-src')
                    if src:
                        return self._normalize_url(src, base_url)
                elif tag == 'a':
                    img = elem.find('img')
                    if img:
                        src = img.get('src') or img.get('data-src')
                        if src:
                            return self._normalize_url(src, base_url)

        return None

    def _find_logo_in_meta(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find logo in meta tags."""
        # Check Open Graph image
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return self._normalize_url(og_image['content'], base_url)

        # Check Twitter image
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return self._normalize_url(twitter_image['content'], base_url)

        return None

    def _find_logo_in_footer(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find logo in page footer."""
        footer = soup.find('footer')
        if not footer:
            return None

        logo_img = footer.find('img', {'class': 'logo'}) or footer.find('img', {'class': 'site-logo'})
        if logo_img:
            src = logo_img.get('src') or logo_img.get('data-src')
            if src:
                return self._normalize_url(src, base_url)

        return None

    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normalize relative URLs to absolute URLs."""
        if url.startswith('http://') or url.startswith('https://'):
            return url
        elif url.startswith('//'):
            return f'https:{url}'
        elif url.startswith('/'):
            return f'{base_url}{url}'
        else:
            return f'{base_url}/{url}'

    def download_logo(self, source: str) -> Optional[str]:
        """
        Download and cache logo locally.

        Args:
            source: Source name

        Returns:
            Local path to cached logo or None
        """
        logo_url = self.get_logo_url(source)
        if not logo_url:
            return None

        try:
            # Create filename from source name
            # Extract extension from URL, removing query parameters
            from urllib.parse import urlparse
            parsed_url = urlparse(logo_url)
            path = parsed_url.path
            ext = Path(path).suffix

            # Use appropriate extension or default to .png
            if not ext or ext not in ['.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp']:
                ext = '.png'

            filename = f"{source.lower().replace(' ', '_')}{ext}"
            filepath = self.cache_dir / filename

            # Download if not already cached
            if not filepath.exists():
                response = self.session.get(logo_url, timeout=10)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Downloaded logo for {source} to {filepath}")

            # Return web-accessible path
            return f"/static/logos/{filename}"

        except Exception as e:
            logger.error(f"Error downloading logo for {source}: {e}")
            return None

    def get_all_logos(self) -> Dict[str, str]:
        """
        Get all source logos.

        Returns:
            Dictionary mapping source names to logo URLs
        """
        logos = {}
        for source in self.SOURCE_URLS.keys():
            logo_url = self.get_logo_url(source)
            if logo_url:
                logos[source] = logo_url
        return logos


def get_logo_for_source(source: str) -> Optional[str]:
    """
    Convenience function to get logo URL for a source.

    Args:
        source: Source name

    Returns:
        Logo URL or None
    """
    scraper = LogoScraper()
    return scraper.get_logo_url(source)

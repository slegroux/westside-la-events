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
    """
    Scraper for source logos.

    When adding a new event source/scraper:
    1. Add the source's base URL to SOURCE_URLS below
    2. Add a fallback logo URL to FALLBACK_LOGOS below
    3. Run: micromamba run -n la python migrate_logos.py
    4. Verify: micromamba run -n la python check_missing_logos.py

    See docs/LOGO_MANAGEMENT.md for detailed instructions.
    """

    # Mapping of source names to their base URLs
    SOURCE_URLS = {
        'Santa Monica': 'https://www.santamonica.gov',
        'Timeout LA': 'https://www.timeout.com',
        'KCRW': 'https://www.kcrw.com',
        'Discover LA': 'https://www.discoverlosangeles.com',
        'Meetup': 'https://www.meetup.com',
        'Eventbrite': 'https://www.eventbrite.com',
        "M.I.'s Westside Comedy Theater": 'https://westsidecomedy.com',
        'Resident Advisor': 'https://ra.co',
        'The Venice West': 'https://thevenicewest.com',
        'LAist': 'https://laist.com',
        'Nerd Nite LA': 'https://losangeles.nerdnite.com',
        'Aviator Nation': 'https://www.aviatornation.com',
        'Gnarwhal Coffee': 'https://www.gnarwhal.com',
        'ITK LA': 'https://itk.la',
        'The Penmar': 'https://thepenmar.com',
        'Winston House': 'https://www.winstonhouse.com',
        'IIC Los Angeles': 'https://iiclosangeles.esteri.it',
        'AFdela': 'https://afdela.org',
        'California State Parks': 'https://www.parks.ca.gov',
        'Théâtre Raymond Kabbaz': 'https://theatreraymonkabbaz.com',
        'UCLA Mathias Botanical Garden': 'https://botgard.ucla.edu',
        'KINN': 'https://luma.com/KINNevents',
        'LA Tech Events': 'https://luma.com/latechevents',
        'Apero Francophone': 'https://www.eventbrite.com/o/apero-francophone-de-los-angeles-59137584493',
        'UCLA': 'https://community.ucla.edu',
        'Hammer Museum': 'https://hammer.ucla.edu',
        'LACMA': 'https://www.lacma.org',
        'Venice Beach Events': 'https://www.visitveniceca.com',
        'West Hollywood': 'https://www.weho.org',
        'Culver City': 'https://www.culvercity.gov',
        'MUD\\WTR :gather': 'https://www.mudwtrgather.com',
        'Brightside California Kitchen': 'https://brightsidecaliforniakitchen.com',
        'Sounds Like LA': 'https://soundslikela.org',
        'Beyond Baroque': 'https://www.beyondbaroque.org',
        'Tripp': 'https://www.tripsantamonica.com',
        'The Victorian': 'https://www.thevictorian.com',
        'Papille Gustative': 'https://papillegustativela.com',
        'Recreation Cafe': 'https://www.recreation.cafe',
        'Jamesons Pub': 'https://santamonica.jamesonsirishpub.com',
    }

    # Known logo URLs (fallback if scraping fails)
    FALLBACK_LOGOS = {
        'Santa Monica': 'https://www.santamonica.gov/SantaMonica.Gov.Theme/Images/LogoStacked.svg',
        'Timeout LA': 'https://media.timeout.com/images/105686275/image.jpg',
        'KCRW': 'https://images.ctfassets.net/2658fe8gbo8o/4ihQCzOkflDXnbaITo07yM/efa81104badd9a9e4dc8d3cdbd092f32/kcrw-logo.png',
        'Discover LA': 'https://assets.simpleviewinc.com/simpleview/image/upload/c_fill,f_avif,g_xy_center,h_640,q_65,w_640,x_2250,y_1500/v1/clients/losangeles/discoverla_logo_social_f04983de-c052-47e0-80c5-d6b8039c2add.jpg',
        'Meetup': 'https://secure.meetupstatic.com/next/images/shared/online_events.svg?w=640',
        'Eventbrite': 'https://cdn.evbstatic.com/s3-build/fe/build/images/eblogo_white.72eb78bc.svg',
        "M.I.'s Westside Comedy Theater": 'https://westsidecomedy.com/wp-content/uploads/2025/03/WSC-logo.png',
        'Resident Advisor': 'https://ra.co/images/logos/ra-logo.svg',
        'The Venice West': 'https://cdn.prod.website-files.com/67520e05423749e937df7101/6758e7e1b4d718be007546e4_Venice-wht-500.png',
        'LAist': 'https://scpr.brightspotcdn.com/3d/90/a00620904650ba75eb573b46106b/laistlogo-black.svg',
        'Nerd Nite LA': 'https://nerdnite.com/wp-content/themes/nerdnite/assets/images/nn-logo.svg',
        'Aviator Nation': 'https://cdn.shopify.com/s/files/1/1149/5724/files/AVN_VIP_V5.png',
        'Gnarwhal Coffee': 'https://www.gnarwhal.com/logo.png',
        'ITK LA': 'https://itk.la/ITK-logo.png',
        'The Penmar': 'https://thepenmar.com/logo.png',
        'Winston House': 'https://www.winstonhouse.com/logo.png',
        'IIC Los Angeles': 'https://iiclosangeles.esteri.it/logo.png',
        'AFdela': 'https://www.afdela.org/wp-content/uploads/2020/03/website-logo2020.png',
        'California State Parks': 'https://www.parks.ca.gov/img/content/ParksLogo.png',
        'Théâtre Raymond Kabbaz': 'https://images.squarespace-cdn.com/content/v1/68484ef7a2c3c851600f4307/6dfad1be-3a49-453f-96eb-146a2291958a/logo-noir-sansfond.png',
        'UCLA Mathias Botanical Garden': 'https://sites.lifesci.ucla.edu/botgard/wp-content/uploads/sites/120/2024/01/UCLA_MBG_Logo_UCLAalt_RGB-1030x265.png',
        'KINN': 'https://images.lumacdn.com/calendars/ba/19c73f3c-4578-4fac-83ee-947fd4a62beb',
        'LA Tech Events': 'https://images.lumacdn.com/calendars/ba/40aabdcc-fc58-41e9-ad11-34ed6fecb30a',
        'Apero Francophone': 'https://img.evbuc.com/https%3A%2F%2Fcdn.evbuc.com%2Fimages%2F789199169%2F147203442267%2F1%2Foriginal.20240613-175946?auto=format%2Ccompress&q=75&sharp=10&s=013e5c242fa306aeee088837cd6377f3',
        'UCLA': 'https://newsroom.ucla.edu/file?fid=58a741882cfac20c4a08ef0b',
        'Hammer Museum': 'https://hammer.ucla.edu/sites/default/files/logo_0.png',
        'LACMA': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/LACMA_logo.svg/320px-LACMA_logo.svg.png',
        'Venice Beach Events': 'https://www.visitveniceca.com/wp-content/uploads/2021/03/venice-logo.png',
        'West Hollywood': 'https://www.weho.org/Home/ShowPublishedImage/6958/637444285636730000',
        'Culver City': 'https://www.culvercity.gov/files/assets/public/v/1/images/culver-city-logo.png',
        'MUD\\WTR :gather': 'https://images.squarespace-cdn.com/content/v1/655100b54c023d4139e41375/7f13fce4-ed7a-4844-a017-d5a1153bd5dc/gather-logo.png',
        'Brightside California Kitchen': 'https://static.spotapps.co/website_images/ab_websites/19630_website_v1/logo.png',
        'Sounds Like LA': 'https://soundslikela.org/wp-content/uploads/2024/06/logo-SLL-RGB.svg',
        'Beyond Baroque': 'https://www.beyondbaroque.org/images/Logo%20for%20new%20website%20copy.jpg',
        'Tripp': 'https://static.wixstatic.com/media/b1ebb4_8d9e8e4c1caa4e4c9f8d8e4c1caa4e4c~mv2.png',
        'The Victorian': 'https://static.wixstatic.com/media/60d1c0_981c8cc2eca6480eb4ce978bc9c58db6~mv2.png/v1/fill/w_314,h_184,al_c,q_85,usm_0.66_1.00_0.01,enc_avif,quality_auto/vic-logo_bw-SM-1.png',
        'Papille Gustative': 'https://static.spotapps.co/website_images/ab_websites/72211_website/logo.png',
        'Recreation Cafe': 'https://images.squarespace-cdn.com/content/v1/62c3a4bf2c1e2e57e6b0be39/8c2a7d45-7e0f-4c82-8a4c-4ba95a3f4c4d/recreation-cafe-logo.png',
        'Jamesons Pub': 'https://static.spotapps.co/web/santamonica--jamesonsirishpub--com/custom/logo.png',
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
        # Check if source has mappings configured
        if source not in self.SOURCE_URLS and source not in self.FALLBACK_LOGOS:
            logger.warning(
                f"Source '{source}' is missing from both SOURCE_URLS and FALLBACK_LOGOS. "
                f"Add it to src/utils/logo_scraper.py for logo support. "
                f"Run 'python check_missing_logos.py' to see all missing sources."
            )
            return None

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
        # Check for manually provided logos with alternative naming patterns
        alternative_names = self._get_alternative_filenames(source)
        for alt_filename in alternative_names:
            alt_filepath = self.cache_dir / alt_filename
            if alt_filepath.exists():
                logger.info(f"Using manually provided logo: {alt_filename}")
                return f"/static/logos/{alt_filename}"

        logo_url = self.get_logo_url(source)
        if not logo_url:
            logger.warning(
                f"No logo URL found for source '{source}'. "
                f"Check SOURCE_URLS and FALLBACK_LOGOS in src/utils/logo_scraper.py"
            )
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

    def _get_alternative_filenames(self, source: str) -> list:
        """
        Get alternative filename patterns for manually provided logos.

        Args:
            source: Source name

        Returns:
            List of possible alternative filenames
        """
        alternatives = []

        # Standard name with common extensions
        base_name = source.lower().replace(' ', '_')

        # Special case mappings for manually provided logos with shortened names
        manual_mappings = {
            "m.i.'s_westside_comedy_theater": "westside_comedy",
            "the_penmar": "penmar",
        }

        # Check multiple variations
        for ext in ['.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp']:
            # Check manual mapping first (highest priority)
            if base_name in manual_mappings:
                # Prioritize _full version first
                alternatives.append(manual_mappings[base_name] + '_full' + ext)
                alternatives.append(manual_mappings[base_name] + ext)

            # With "the_" prefix removed
            alternatives.append(base_name.replace('the_', '') + ext)
            # Original name
            alternatives.append(base_name + ext)
            # Without quotes/apostrophes
            alternatives.append(base_name.replace("'", '').replace('"', '') + ext)

        return alternatives

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

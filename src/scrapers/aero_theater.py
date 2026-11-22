"""
Scrapers for the American Cinematheque's repertory cinemas.
Source: https://www.americancinematheque.com/wp-json/wp/v2/event

Note: This site uses WordPress REST API. We fetch events directly from the
event API (not the product API) which includes images via _embed parameter.

One WordPress site serves all three theatres, told apart by the `event_location`
taxonomy term (each event carries exactly one). AeroTheaterScraper holds the
parser; the Egyptian Theatre and Los Feliz 3 (both outside the Westside box,
so REGION = 'beyond') only override the venue constants.
"""
import time
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class AeroTheaterScraper(BaseScraper):
    """Scraper for Aero Theater events (also the base for the sibling theatres)."""

    SOURCE_NAME = 'Aero Theater'
    LOCATION_ID = 54  # `event_location` term for the Aero on the event API
    VENUE_NAME = 'Aero Theatre'
    VENUE_ADDRESS = '1328 Montana Ave, Santa Monica, CA 90403'
    # Fixed venue coordinates skip geocoding. The Aero leaves them unset and is
    # geocoded from its address as it always was.
    LATITUDE = None
    LONGITUDE = None
    # The Aero has always stored "TBD" when no price is listed; the beyond
    # theatres follow the empty-note convention (see CLAUDE.md).
    UNKNOWN_PRICE_NOTE = 'TBD'
    MAX_PAGES = 3  # Cap pages to avoid timeout
    # `_embed` makes the API ~15x slower (a 50-item page takes ~20 s instead of
    # ~1.5 s) and only adds a featured-media image that the ACF fields already
    # cover on every item sampled. The Aero keeps it as it always has; the
    # sibling theatres ask for just the fields the parser reads.
    EMBED_MEDIA = True
    SCRAPE_BUDGET_SECONDS = 80  # the runner kills a scraper at 120 s

    def __init__(self):
        super().__init__(self.SOURCE_NAME)
        self.base_url = 'https://www.americancinematheque.com'
        self.api_url = f'{self.base_url}/wp-json/wp/v2/event'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Aero Theater using WordPress REST API.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Quick reachability check — lets tests mock fetch_page to short-circuit
            if self.fetch_page(self.base_url, retry=1) is None:
                self.log("Site unreachable, aborting")
                return events

            # Fetch events from API (paginated)
            page = 1
            max_pages = self.MAX_PAGES
            per_page = 50  # Use smaller page size since _embed is slower
            deadline = time.monotonic() + self.SCRAPE_BUDGET_SECONDS

            while page <= max_pages:
                remaining = deadline - time.monotonic()
                if remaining <= 1:
                    self.log(f"Time budget spent before page {page}; stopping")
                    break

                params = {
                    'per_page': per_page,
                    'page': page,
                    'event_location': self.LOCATION_ID,
                }
                if self.EMBED_MEDIA:
                    params['_embed'] = 1  # Include embedded media data (images)
                else:
                    params['_fields'] = 'title,link,content,acf'

                self.log(f"Fetching page {page} from API...")
                response = self.session.get(
                    self.api_url, params=params, timeout=min(30, remaining)
                )

                if response.status_code != 200:
                    self.log(f"API returned status {response.status_code}")
                    break

                event_data = response.json()

                if not event_data:
                    break

                self.log(f"Found {len(event_data)} events on page {page}")

                for item in event_data:
                    try:
                        event = self._parse_event(item)
                        if event:
                            events.append(event)
                            self.log(f"Parsed: {event.title}")
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

                # Check if there are more pages
                if len(event_data) < per_page:
                    break

                page += 1

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, event: dict) -> Optional[Event]:
        """
        Parse an event from the WordPress API response.

        Args:
            event: Dictionary containing event data from API

        Returns:
            Event object or None
        """
        try:
            # Extract title
            raw_title = event.get('title', {}).get('rendered', '')
            if not raw_title:
                return None

            # Clean up HTML entities
            import html
            from bs4 import BeautifulSoup
            title = html.unescape(BeautifulSoup(raw_title, 'html.parser').get_text())

            # Skip placeholder/test entries the venue leaves in their CMS
            # (e.g. "Test Event", "E2E Scheduled Test"). Match the whole title
            # so real films like "THE TESTAMENTS" are not affected.
            if re.fullmatch(r'(?i)\s*(test event|e2e scheduled test)\s*', title):
                return None

            # Extract ACF (Advanced Custom Fields) data
            acf_data = event.get('acf', {})
            event_hero = acf_data.get('event_hero', {}) or {}

            # Extract date and time - MUST have a date to be a valid event.
            # As of the 2026 ACF schema, American Cinematheque stores the
            # screening date/time as human-readable strings under event_hero:
            #   dates -> "FRI JUN 12, 2026", times -> "7:30 PM"
            # We deliberately do NOT fall back to the WordPress post `date`,
            # which is the publish date (always in the past) and would cause
            # every event to be silently dropped by the past-event filter.
            event_date = None

            dates_str = (event_hero.get('dates') or '').strip()
            times_str = (event_hero.get('times') or '').strip()
            if dates_str:
                try:
                    event_date = date_parser.parse(f"{dates_str} {times_str}".strip())
                except Exception as e:
                    self.log(f"Error parsing hero date '{dates_str}' time '{times_str}': {e}")

            # Fallback: legacy flat ACF fields (YYYYMMDD + "11:00 am")
            if not event_date:
                date_str = acf_data.get('event_start_date', '')  # Format: YYYYMMDD
                time_str = acf_data.get('event_start_time', '')  # Format: "11:00 am"
                if date_str:
                    try:
                        if time_str:
                            event_date = date_parser.parse(f"{date_str} {time_str}")
                        else:
                            event_date = datetime.strptime(date_str, '%Y%m%d')
                    except Exception as e:
                        self.log(f"Error parsing date '{date_str}' with time '{time_str}': {e}")

            if not event_date:
                self.log(f"No date found for event: {title}")
                return None

            # Skip past events (older than yesterday)
            if event_date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                return None

            # Extract description
            description = ""
            content = event.get('content', {}).get('rendered', '')
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                description = self.clean_text(soup.get_text())

            # Extract URL
            url = event.get('link', '')

            # Extract image. Prefer event_hero.image_url / hero_image (2026 schema),
            # then the ACF event_card_image, then embedded featured media.
            image_url = ""
            try:
                image_url = event_hero.get('image_url', '') or ''
                if not image_url:
                    hero_image = event_hero.get('hero_image', {})
                    if isinstance(hero_image, dict):
                        image_url = hero_image.get('url', '') or ''
                if not image_url:
                    event_card_image = acf_data.get('event_card_image', {})
                    if isinstance(event_card_image, dict):
                        image_url = event_card_image.get('url', '') or ''
                if not image_url:
                    embedded = event.get('_embedded', {})
                    featured_media = embedded.get('wp:featuredmedia', [])
                    if featured_media and len(featured_media) > 0:
                        image_url = featured_media[0].get('source_url', '')
            except Exception as e:
                self.log(f"Error extracting image: {e}")

            # Extract price info. The 2026 schema exposes a human-readable
            # string under event_hero.pricing, e.g.
            #   "$14.00 (member) ; $19.00 (general admission)"
            is_free = bool(acf_data.get('event_free', False) or acf_data.get('product_free_event', False))
            price = None
            price_note = ""
            pricing_str = (event_hero.get('pricing') or '').strip()
            if 'free' in pricing_str.lower():
                is_free = True
            if is_free:
                price = 0.0
            elif pricing_str:
                amounts = [float(m) for m in re.findall(r'\$\s*(\d+(?:\.\d{1,2})?)', pricing_str)]
                if amounts:
                    price = min(amounts)
            if price is None and not is_free:
                price_note = self.UNKNOWN_PRICE_NOTE

            return self.create_event(
                title=title,
                description=description,
                venue_name=self.VENUE_NAME,
                address=self.VENUE_ADDRESS,
                latitude=self.LATITUDE,
                longitude=self.LONGITUDE,
                event_date=event_date,
                end_date=None,
                url=url,
                image_url=image_url,
                category="Film",
                price=price,
                is_free=is_free,
                price_note=price_note
            )

        except Exception as e:
            self.log(f"Error parsing event: {e}")
            return None


class EgyptianTheatreScraper(AeroTheaterScraper):
    """Egyptian Theatre (Hollywood), American Cinematheque's flagship."""

    REGION = 'beyond'
    SOURCE_NAME = 'Egyptian Theatre'
    LOCATION_ID = 55
    VENUE_NAME = 'Egyptian Theatre'
    VENUE_ADDRESS = '6712 Hollywood Blvd, Los Angeles, CA 90028'
    LATITUDE = 34.1016
    LONGITUDE = -118.3409
    UNKNOWN_PRICE_NOTE = ''
    EMBED_MEDIA = False


class LosFeliz3Scraper(AeroTheaterScraper):
    """Los Feliz 3 Cinema, American Cinematheque's Los Feliz house."""

    REGION = 'beyond'
    SOURCE_NAME = 'Los Feliz 3'
    LOCATION_ID = 102
    VENUE_NAME = 'Los Feliz 3 Cinema'
    VENUE_ADDRESS = '1822 N Vermont Ave, Los Angeles, CA 90027'
    LATITUDE = 34.1068
    LONGITUDE = -118.2915
    UNKNOWN_PRICE_NOTE = ''
    EMBED_MEDIA = False
    MAX_PAGES = 4  # busiest calendar: ~60 upcoming, nearly all in the newest 3 pages

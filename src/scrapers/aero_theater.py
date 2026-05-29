"""
Scraper for Aero Theater (American Cinematheque) events.
Source: https://www.americancinematheque.com/wp-json/wp/v2/event

Note: This site uses WordPress REST API. We fetch events directly from the
event API (not the product API) which includes images via _embed parameter.
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class AeroTheaterScraper(BaseScraper):
    """Scraper for Aero Theater events."""

    def __init__(self):
        super().__init__('Aero Theater')
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
            max_pages = 3  # Cap pages to avoid timeout
            per_page = 50  # Use smaller page size since _embed is slower

            while page <= max_pages:
                params = {
                    'per_page': per_page,
                    'page': page,
                    'event_location': 54,  # Aero Theatre location ID for event API
                    '_embed': 1  # Include embedded media data (images)
                }

                self.log(f"Fetching page {page} from API...")
                response = self.session.get(self.api_url, params=params, timeout=30)

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
                price_note = "TBD"

            # Venue details
            venue_name = "Aero Theatre"
            address = "1328 Montana Ave, Santa Monica, CA 90403"

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
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

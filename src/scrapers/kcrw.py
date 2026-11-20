"""
Scraper for KCRW events.
Source: https://www.kcrw.com/events
"""
from datetime import datetime
from typing import List, Dict, Optional
import json
import re
import threading
import time
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event
from src.utils.geocoding import NEGATIVE_TTL_SECONDS, POSITIVE_TTL_SECONDS


_OVER_BUDGET = object()


class _NoGeocoder:
    """Stands in for the geocoder when a venue has already failed this scrape."""

    def geocode_with_fallback(self, address, venue_name=None):
        return None


class KCRWScraper(BaseScraper):
    """Scraper for KCRW events."""

    def __init__(self):
        super().__init__('KCRW')
        self.base_url = 'https://www.kcrw.com'
        self.events_url = f'{self.base_url}/events'
        self._reset_geocode_budget()

    # Nominatim allows 1 request/s for the whole process, so geocoding is what
    # makes this scraper slow, and in the concurrent run it queues behind every
    # other scraper's lookups. Cap the network lookups per scrape; venues already
    # in the persistent cache cost nothing and are never capped.
    MAX_NEW_GEOCODES = 25
    # A lookup can itself take 30 s+ when Nominatim hangs, and the runner kills
    # the scraper at 120 s, so also stop starting new lookups after this long
    # (measured from the start of the scrape).
    GEOCODE_BUDGET_SECONDS = 70
    # ...and never wait on a lookup past this point, whatever it is doing.
    GEOCODE_DEADLINE_SECONDS = 100

    def _reset_geocode_budget(self):
        self._venue_coords: Dict[str, Optional[tuple]] = {}
        self._new_geocodes = 0
        self._skipped_for_budget = 0
        self._started = time.monotonic()

    def scrape(self) -> List[Event]:
        """
        Scrape events from KCRW website.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []
        self._reset_geocode_budget()

        try:
            # KCRW (kcrw.com) sits behind Vercel's bot challenge for plain
            # requests (HTTP 429 with challenge token). The events list is
            # also rendered client-side by Next.js, so static HTML has no
            # event cards. Use a real browser via Playwright instead.
            html = self.fetch_page_js(
                self.events_url,
                wait_selector='[class*="EventCard_cardContainer__"]',
                timeout=30000
            )
            if not html:
                self.log("Failed to fetch events page (JS render)")
                return events

            soup = self.parse_html(html)

            # Preferred source: the Next.js (RSC) payload embedded in the page
            # carries every upcoming event as structured data (ISO start with
            # timezone, venue, tags, image, slug), independent of CSS class
            # names, and lists far more events than the 16 rendered cards.
            payload_events = self._extract_payload_events(soup)
            if payload_events:
                self.log(f"Found {len(payload_events)} events in page payload")
                for raw in payload_events:
                    try:
                        event = self._parse_payload_event(raw)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing payload event: {e}")
                if self._skipped_for_budget:
                    self.log(f"Skipped {self._skipped_for_budget} events: geocode budget of "
                             f"{self.MAX_NEW_GEOCODES} new lookups used up (they will "
                             f"resolve from the cache on later runs)")
                self.log(f"Successfully scraped {len(events)} events")
                return events
            self.log("No event payload found, falling back to rendered cards")

            # KCRW uses CSS modules with unique class names
            # Event cards have class starting with EventCard_cardContainer__
            event_items = soup.find_all('div', class_=lambda x: x and 'EventCard_cardContainer__' in x)

            # Fallback: CSS module class changes on every Next.js rebuild, use semantic HTML
            if not event_items:
                self.log("Primary CSS module selector failed, trying semantic HTML fallback")
                event_items = soup.find_all('article')
            if not event_items:
                event_items = soup.find_all('li', attrs={'data-testid': True})

            if not event_items:
                self.log("No event cards found on page")
                return events

            self.log(f"Found {len(event_items)} event cards")

            # Detail pages also sit behind Vercel's bot challenge, so
            # plain HTTP prefetching returns HTML challenge pages instead
            # of real content. Skip detail fetching — card data (title,
            # date, venue, tag, image, URL) is sufficient. Running
            # Playwright per detail page would explode runtime (16+ JS
            # navigations) for minimal gain (description text).

            for item in event_items:
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    # Cities that can contain Westside venues. The geo filter in create_event is
    # the authority; this only avoids a (rate-limited, ~1 s) geocode per venue
    # for events plainly elsewhere (Pasadena, Burbank, Kyoto, ...).
    WESTSIDE_CANDIDATE_CITIES = {
        'los angeles', 'santa monica', 'culver city', 'west hollywood',
        'beverly hills', 'venice', 'malibu', 'marina del rey',
        'pacific palisades', 'brentwood', 'westwood', 'playa vista',
        'playa del rey', 'topanga',
    }

    def _extract_payload_events(self, soup) -> List[Dict]:
        """Collect event dicts from the page's Next.js flight data (deduped by id)."""
        chunks = []
        for script in soup.find_all('script'):
            text = script.string or ''
            match = re.match(r'\s*self\.__next_f\.push\((\[.*\])\)\s*;?\s*$', text, re.DOTALL)
            if not match:
                continue
            try:
                part = json.loads(match.group(1))
            except ValueError:
                continue
            if len(part) > 1 and isinstance(part[1], str):
                chunks.append(part[1])
        flight = ''.join(chunks)

        decoder = json.JSONDecoder()
        found = {}
        for match in re.finditer(r'"events":\[', flight):
            try:
                arr, _ = decoder.raw_decode(flight, match.end() - 1)
            except ValueError:
                continue
            for raw in arr:
                if isinstance(raw, dict) and raw.get('title') and raw.get('start') and raw.get('slug'):
                    found[(raw.get('sys') or {}).get('id') or raw['slug']] = raw
        return list(found.values())

    def _parse_payload_event(self, raw: Dict) -> Optional[Event]:
        """Convert one payload event dict into an Event (None if outside the area)."""
        venue = raw.get('venue') or {}
        city = (venue.get('city') or '').strip()
        if city.lower() not in self.WESTSIDE_CANDIDATE_CITIES:
            return None

        title = self.clean_text(raw['title'])
        try:
            start = datetime.fromisoformat(raw['start'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(raw['end'].replace('Z', '+00:00')) if raw.get('end') else None
        except ValueError:
            self.log(f"Skipping '{title}': unparseable start '{raw.get('start')}'")
            return None

        venue_name = self.clean_text(venue.get('name') or '')
        address = ', '.join(p for p in (venue_name, city, venue.get('state')) if p)

        categories = [
            c.get('title', '') for c in ((raw.get('categoriesCollection') or {}).get('items') or [])
        ]
        category = next((c for c in categories if c and c.lower() not in ('featured', 'kcrw presents')), None)

        image_url = (((raw.get('image') or {}).get('asset')) or {}).get('url', '')

        located = self._locate(venue_name, address)
        if located is _OVER_BUDGET:
            self._skipped_for_budget += 1
            return None
        latitude, longitude = located or (None, None)

        # create_event geocodes again when it gets no coordinates; for a venue
        # that just failed, that would repeat the slow lookup.
        real_geocoder = self.geocoding_service
        if located is None:
            self.geocoding_service = _NoGeocoder()
        try:
            return self.create_event(
                title=title,
                description="",
                venue_name=venue_name,
                address=address,
                event_date=start,
                end_date=end,
                url=f"{self.base_url}/events/{raw['slug']}",
                image_url=image_url,
                category=category,
                latitude=latitude,
                longitude=longitude,
            )
        finally:
            self.geocoding_service = real_geocoder

    @staticmethod
    def _is_cached(cache, key: str) -> bool:
        """Whether the persistent cache has a fresh entry for this address."""
        entry = cache.get(key)
        if not isinstance(entry, dict):
            return False
        if 'lat' in entry:  # legacy positive entry
            return True
        cached_at = entry.get('cached_at', 0)
        if not cached_at:  # the service stamps these lazily on first read
            return True
        ttl = NEGATIVE_TTL_SECONDS if entry.get('result') is None else POSITIVE_TTL_SECONDS
        return time.time() - cached_at < ttl

    @classmethod
    def _is_cached_hit(cls, cache, key: str) -> bool:
        """A fresh cache entry that holds coordinates (not a cached miss)."""
        if not cls._is_cached(cache, key):
            return False
        entry = cache[key]
        return 'lat' in entry or entry.get('result') is not None

    def _locate(self, venue_name: str, address: str):
        """Coordinates for a venue, geocoded at most once per scrape.

        Returns (lat, lng), None when the venue cannot be geocoded, or
        _OVER_BUDGET when the venue is not cached and either the lookup count
        or the time budget is spent. Every lookup that is not served from the
        per-scrape or persistent cache counts, whether it succeeds or not.
        """
        key = address.lower().strip()
        if key in self._venue_coords:
            return self._venue_coords[key]
        cache = getattr(self.geocoding_service, 'cache', None)
        # Only a fresh cached hit is free: geocode_with_fallback returns it at
        # once. A cached miss makes it try the normalized/override/venue forms,
        # which hit the network, so that goes through the counted, deadlined path.
        if cache is not None and self._is_cached_hit(cache, key):
            coords = self.geocoding_service.geocode_with_fallback(address, venue_name=venue_name)
            self._venue_coords[key] = coords
            return coords

        if (self._new_geocodes >= self.MAX_NEW_GEOCODES
                or time.monotonic() - self._started >= self.GEOCODE_BUDGET_SECONDS):
            return _OVER_BUDGET
        self._new_geocodes += 1

        # One fallback lookup makes up to four Nominatim calls, each of which can
        # sit through 3 x 30 s timeouts, so gating only its start cannot keep the
        # scraper under the runner's 120 s kill. Run it on a daemon thread and
        # wait no later than the hard deadline. A lookup still running then is
        # abandoned (it finishes in the background and fills the shared cache
        # for the next run) and no further lookups are started this scrape.
        remaining = self.GEOCODE_DEADLINE_SECONDS - (time.monotonic() - self._started)
        result: Dict[str, Optional[tuple]] = {}

        def lookup():
            result['coords'] = self.geocoding_service.geocode_with_fallback(
                address, venue_name=venue_name)

        worker = threading.Thread(target=lookup, name='kcrw-geocode', daemon=True)
        worker.start()
        worker.join(max(1.0, remaining))
        if worker.is_alive():
            self.log(f"Geocoding '{venue_name or address}' still running at the "
                     f"{self.GEOCODE_DEADLINE_SECONDS} s deadline; abandoning lookups this run")
            self._new_geocodes = self.MAX_NEW_GEOCODES
            return _OVER_BUDGET

        coords = result.get('coords')
        self._venue_coords[key] = coords
        return coords

    def _parse_event(self, item) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object
        """
        # Extract title - in EventCard_cardTitle__
        title_elem = item.find('p', class_=lambda x: x and 'EventCard_cardTitle__' in x)
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        # Extract date - in EventCard_date__
        date_elem = item.find('div', class_=lambda x: x and 'EventCard_date__' in x)
        event_date = None
        if date_elem:
            # Date is split into month and day
            date_parts = [s.strip() for s in date_elem.stripped_strings]
            if len(date_parts) >= 2:
                # Construct date string like "Nov 14" and add current year
                from datetime import datetime
                current_year = datetime.now().year
                date_str = f"{date_parts[0]} {date_parts[1]} {current_year}"
                try:
                    event_date = date_parser.parse(date_str)
                except Exception as e:
                    self.log(f"Failed to parse date '{date_str}': {e}")

        # Extract venue - in small-text class
        venue_elem = item.find('p', class_='small-text')
        venue_name = ""
        address = ""
        if venue_elem:
            # Format is typically "Venue Name, City, State"
            full_location = self.clean_text(venue_elem.get_text())
            parts = [p.strip() for p in full_location.split(',')]
            if parts:
                venue_name = parts[0]
                address = full_location

        # Extract category/tags
        tags = item.find_all('div', class_=lambda x: x and 'Tag_tag__' in x)
        category = None
        if tags:
            # Use first meaningful tag as category
            tag_texts = [tag.get_text(strip=True) for tag in tags]
            # Skip generic tags like "Featured"
            for tag in tag_texts:
                if tag.lower() not in ['featured', 'kcrw presents']:
                    category = tag
                    break

        # Extract URL - parent <a> tag wraps the card
        parent_link = item.find_parent('a')
        url = ""
        if parent_link and parent_link.get('href'):
            url = self.normalize_url(parent_link['href'], self.base_url)

        # Extract image
        img_elem = item.find('img')
        image_url = ""
        if img_elem:
            src = img_elem.get('src', '')
            if src:
                image_url = src  # Already full URL from Contentful CDN

        # Detail pages are behind Vercel bot challenge; skip them and
        # rely on card data only.
        description = ""
        end_date = None
        price = None
        is_free = False

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free
        )

    def _fetch_event_details(self, event_url: str) -> Dict:
        """
        Fetch detailed event information from the detail page.

        Args:
            event_url: URL of the event detail page

        Returns:
            Dictionary with event details (description, event_date, end_date, price, etc.)
        """
        details = {
            'description': '',
            'image_url': '',
            'event_date': None,
            'end_date': None,
            'price': None,
            'is_free': False
        }

        try:
            self.log(f"Fetching details from {event_url}")
            html = self.fetch_page(event_url)
            if not html:
                return details

            soup = self.parse_html(html)

            # Extract description paragraphs
            # Strategy: Get first few substantial paragraphs before the donation message
            paragraphs = soup.find_all('p')
            description_parts = []

            for p in paragraphs:
                text = self.clean_text(p.get_text())

                # Skip short paragraphs and footer content
                if len(text) < 50:
                    continue
                if any(keyword in text.lower() for keyword in ['donate to kcrw', 'copyright', 'kcrw member']):
                    break  # Stop at footer content

                # Add this paragraph to description
                description_parts.append(text)

                # Usually descriptions are 1-3 paragraphs
                if len(description_parts) >= 3:
                    break

            details['description'] = ' '.join(description_parts)

            # Extract date and time from page
            # KCRW format: "Tue Nov 11, 2025 • 6:00 PM"
            time_spans = soup.find_all('span', class_='paragraph')
            for span in time_spans:
                text = span.get_text(strip=True)
                # Look for date/time pattern
                if re.search(r'[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+•\s+\d{1,2}:\d{2}\s+[AP]M', text):
                    try:
                        # Remove the bullet separator
                        date_time_str = text.replace('•', '').strip()
                        details['event_date'] = date_parser.parse(date_time_str)
                        self.log(f"Parsed event date/time: {details['event_date']}")
                        break
                    except Exception as e:
                        self.log(f"Could not parse date/time '{text}': {e}")

            # Extract price information
            page_text = soup.get_text()

            # Check for free events
            if re.search(r'\bfree\b', page_text, re.IGNORECASE):
                free_context = re.search(r'(?:admission|entry|event|price|cost|ticket)?\s*(?:is\s*)?free', page_text, re.IGNORECASE)
                if free_context or 'free' in details['description'].lower():
                    details['is_free'] = True
                    details['price'] = None

            # Look for price patterns
            if not details['is_free']:
                price_patterns = [
                    r'\$(\d+)(?:-\$?(\d+))?',  # $25 or $25-$75
                    r'(?:from\s+)?\$(\d+)',     # from $25
                    r'(?:ticket(?:s)?|admission)[:is\s]+\$(\d+)',  # tickets: $25
                ]

                for pattern in price_patterns:
                    price_match = re.search(pattern, page_text, re.IGNORECASE)
                    if price_match:
                        try:
                            details['price'] = float(price_match.group(1))
                            break
                        except (ValueError, TypeError, IndexError):
                            continue

            # Get high-res image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                details['image_url'] = og_image.get('content', '')

            return details

        except Exception as e:
            self.log(f"Error fetching event details: {e}")
            return details

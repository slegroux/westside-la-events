"""
Scraper for Laemmle Monica Film Center.
Source: https://www.laemmle.com/theater/monica-film-center

The site is a Next.js app: film pages (/film/<slug>) are server-rendered with the
title, poster, runtime and rating, but the showtimes are filled in client-side
from a JSON endpoint (/api/showtimes/<film uuid>). We read the film uuid from the
page's embedded data and call that same endpoint, keeping only Monica showtimes.
"""
from datetime import datetime
from typing import List, Optional
import re

from .base import BaseScraper
from src.data.models import Event


class LaemmleMonicaScraper(BaseScraper):
    """Scraper for Laemmle Monica Film Center events."""

    THEATER_SLUG = 'monica'
    # 1332 2nd St, Santa Monica (fixed venue, so no geocoding needed)
    LATITUDE = 34.0149
    LONGITUDE = -118.4963

    def __init__(self):
        super().__init__('Laemmle Monica Film Center')
        self.base_url = 'https://www.laemmle.com'
        self.theater_url = f'{self.base_url}/theater/monica-film-center'
        self.venue_name = 'Laemmle Monica Film Center'
        self.venue_address = '1332 2nd Street, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape movie showtimes from Laemmle Monica Film Center.

        Returns:
            List of Event objects (one per movie, dated at its next Monica showtime)
        """
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.theater_url)
            if not html:
                self.log("Failed to fetch theater page")
                return events

            soup = self.parse_html(html)

            # Unique film pages linked from the theater page
            film_urls = []
            for link in soup.find_all('a', href=re.compile(r'^/film/|laemmle\.com/film/')):
                clean_url = self.normalize_url(link['href'].split('?')[0], self.base_url)
                if clean_url not in film_urls:
                    film_urls.append(clean_url)

            self.log(f"Found {len(film_urls)} unique films")

            if film_urls:
                self.prefetch_pages(film_urls)

            for i, film_url in enumerate(film_urls, 1):
                try:
                    event = self._parse_film(film_url)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(film_urls)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing movie at {film_url}: {e}")

            self.log(f"Successfully scraped {len(events)} movies")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _upcoming_monica_showtimes(self, film_id: str) -> List[dict]:
        """Monica showtimes that haven't started yet, earliest first."""
        data = self.fetch_json(
            f'{self.base_url}/api/showtimes/{film_id}', method='GET'
        )
        if not data:
            return []

        now = datetime.now()
        showtimes = []
        for st in data.get('showtimes', []):
            if st.get('theaterSlug') != self.THEATER_SLUG:
                continue
            try:
                # Naive LA-local, e.g. "2026-11-19T19:30:00"
                starts_at = datetime.fromisoformat(st['startsAt'])
            except (KeyError, ValueError):
                continue
            if starts_at.tzinfo is not None:
                starts_at = starts_at.replace(tzinfo=None)
            if starts_at >= now:
                showtimes.append({**st, 'dt': starts_at})
        return sorted(showtimes, key=lambda s: s['dt'])

    def _parse_film(self, film_url: str) -> Optional[Event]:
        """Build one event from a film page plus its Monica showtimes."""
        film_html = self.fetch_page(film_url)
        if not film_html:
            self.log(f"Failed to fetch film detail page: {film_url}")
            return None

        id_match = re.search(r'filmId\\?":\\?"([0-9a-fA-F-]{36})', film_html)
        if not id_match:
            self.log(f"No film id found on {film_url}")
            return None

        film_soup = self.parse_html(film_html)
        title_elem = film_soup.find('h1', class_='film-title')
        title = self.clean_text(title_elem.get_text()) if title_elem else ''
        if not title:
            return None

        showtimes = self._upcoming_monica_showtimes(id_match.group(1))
        if not showtimes:
            # Not playing at Monica (or nothing upcoming): nothing to list.
            return None

        # Poster
        image_url = ''
        poster = film_soup.select_one('.film-poster img')
        if poster:
            image_url = self.normalize_url(poster.get('src', ''), self.base_url)

        # Rating and runtime, e.g. "Not Rated" and "88 min"
        rating_elem = film_soup.select_one('.badge-rating')
        rating = self.clean_text(rating_elem.get_text()) if rating_elem else ''
        meta_elem = film_soup.select_one('.badge-meta')
        runtime_match = re.search(r'(\d+)\s*min', meta_elem.get_text()) if meta_elem else None
        runtime_rating = ' '.join(
            p for p in [f"{runtime_match.group(1)} min." if runtime_match else '', rating] if p
        )

        synopsis_elem = film_soup.select_one('[data-synopsis-inner]')
        synopsis = self.clean_text(synopsis_elem.get_text(' ')) if synopsis_elem else ''
        if len(synopsis) > 400:
            synopsis = synopsis[:399].rsplit(' ', 1)[0] + '…'

        # Showtimes grouped by day, e.g. "Thu Nov 19: 7:30pm, 9:45pm"
        by_day = {}
        for st in showtimes:
            by_day.setdefault(st['dt'].date(), []).append(st['dt'])
        day_parts = []
        for day, times in list(by_day.items())[:7]:
            clock = ', '.join(f"{t.hour % 12 or 12}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}" for t in times)
            day_parts.append(f"{day.strftime('%a %b')} {day.day}: {clock}")

        description_parts = []
        if runtime_rating:
            description_parts.append(runtime_rating)
        if synopsis:
            description_parts.append(synopsis)
        description_parts.append("Showtimes - " + "; ".join(day_parts))
        if any(st.get('hasQandA') for st in showtimes):
            description_parts.append("Includes a Q&A screening")
        description_parts.append(f"Film screening at {self.venue_name}")
        description = ". ".join(p.rstrip('.') for p in description_parts) + "."

        # Price unknown here: leave price_note empty (CLAUDE.md pricing convention)
        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            latitude=self.LATITUDE,
            longitude=self.LONGITUDE,
            event_date=showtimes[0]['dt'],
            url=film_url,
            image_url=image_url,
            category='Film',
            price=None,
            is_free=False,
            price_note='',
        )

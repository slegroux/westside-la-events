"""
Scraper for Nuart Theatre events.
Source: https://www.landmarktheatres.com/los-angeles/nuart-theatre

The theatre page is a Gatsby app whose home view only shows one hero film. The
full programme comes from the JSON endpoints the site itself calls
(/api/gatsby-source-boxofficeapi/...): `schedule` lists every showtime for the
theatre, `movies` gives titles, posters and synopses. No browser needed.
"""
from datetime import datetime, timedelta
from typing import Dict, List
from urllib.parse import urlencode
import json
import re

from .base import BaseScraper
from src.data.models import Event


class NuartTheatreScraper(BaseScraper):
    """Scraper for Nuart Theatre events."""

    THEATER_ID = 'X00CW'
    DAYS_AHEAD = 90
    # 11272 Santa Monica Blvd (fixed venue, so no geocoding needed)
    LATITUDE = 34.0433
    LONGITUDE = -118.4476

    def __init__(self):
        super().__init__('Nuart Theatre')
        self.base_url = 'https://www.landmarktheatres.com'
        self.theatre_url = f'{self.base_url}/los-angeles/nuart-theatre'
        self.api_url = f'{self.base_url}/api/gatsby-source-boxofficeapi'

    def scrape(self) -> List[Event]:
        """
        Scrape the Nuart's upcoming screenings: one event per film per day.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query = urlencode({
                'from': start.strftime('%Y-%m-%dT%H:%M:%S'),
                'to': (start + timedelta(days=self.DAYS_AHEAD)).strftime('%Y-%m-%dT%H:%M:%S'),
                'theaters': json.dumps(
                    {'id': self.THEATER_ID, 'timeZone': 'America/Los_Angeles'},
                    separators=(',', ':'),
                ),
            })
            data = self.fetch_json(f'{self.api_url}/schedule?{query}', method='GET')
            schedule = ((data or {}).get(self.THEATER_ID) or {}).get('schedule') or {}
            if not schedule:
                self.log("No schedule returned")
                return events

            movies = self._fetch_movies(list(schedule))
            self.log(f"Found {len(schedule)} films with showtimes")

            for movie_id, days in schedule.items():
                movie = movies.get(movie_id)
                if not movie:
                    self.log(f"No movie details for id {movie_id}, skipping")
                    continue
                for day, showtimes in days.items():
                    try:
                        event = self._parse_day(movie, showtimes)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing {movie.get('title')} on {day}: {e}")

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _fetch_movies(self, movie_ids: List[str]) -> Dict[str, dict]:
        """Movie details keyed by id."""
        query = urlencode(
            [('basic', 'false'), ('castingLimit', '3')] + [('ids', i) for i in movie_ids]
        )
        data = self.fetch_json(f'{self.api_url}/movies?{query}', method='GET')
        return {str(m['id']): m for m in (data or []) if m.get('id')}

    def _parse_day(self, movie: dict, showtimes: List[dict]):
        """Build one event for a film's screenings on a single day."""
        now = datetime.now()
        times = set()
        for st in showtimes:
            try:
                starts_at = datetime.fromisoformat(st['startsAt'])
            except (KeyError, ValueError):
                continue
            if starts_at.tzinfo is not None:
                starts_at = starts_at.replace(tzinfo=None)
            if starts_at >= now:
                times.add(starts_at)
        if not times:
            return None
        times = sorted(times)

        title = self.clean_text(movie.get('title', ''))
        if not title:
            return None

        directors = [
            ' '.join(p for p in (n['person'].get('firstName'), n['person'].get('lastName')) if p)
            for n in (movie.get('directors') or {}).get('nodes', [])
            if n.get('person')
        ]
        description_parts = []
        runtime = movie.get('runtime')  # seconds
        rating = movie.get('certificate')
        if runtime:
            description_parts.append(f"{round(runtime / 60)} min." + (f" {rating}" if rating else ''))
        elif rating:
            description_parts.append(rating)
        if directors:
            description_parts.append(f"A film by {', '.join(directors)}")
        synopsis = self.clean_text(movie.get('synopsis') or '')
        if len(synopsis) > 400:
            synopsis = synopsis[:399].rsplit(' ', 1)[0] + '…'
        if synopsis:
            description_parts.append(synopsis)
        clock = ', '.join(f"{t.hour % 12 or 12}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}" for t in times)
        description_parts.append(f"Showtimes - {clock}")
        description = '. '.join(p.rstrip('.') for p in description_parts) + '.'

        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        # One film page serves every day, so a bare URL makes consecutive days
        # look like one event to Database.insert_event (same URL within 24 h).
        # The fragment is ignored by the site and keeps each day distinct.
        url = (
            f"{self.base_url}/movies/{movie['id']}-{slug}/?theater={self.THEATER_ID}"
            f"#{times[0].strftime('%Y-%m-%d')}"
        )

        # Price unknown here: leave price_note empty (CLAUDE.md pricing convention)
        return self.create_event(
            title=title,
            description=description,
            venue_name="Nuart Theatre",
            address="11272 Santa Monica Blvd, Los Angeles, CA 90025",
            latitude=self.LATITUDE,
            longitude=self.LONGITUDE,
            event_date=times[0],
            url=url,
            image_url=movie.get('poster') or '',
            category="Film",
            price=None,
            is_free=False,
            price_note='',
        )

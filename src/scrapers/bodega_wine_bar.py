"""
Scraper for Bodega Wine Bar's weekly specials.
Source: https://bodegawinebar.com/specials

Bodega publishes its recurring specials as poster images with the text baked
into the JPEGs -- the page itself carries no machine-readable schedule. The
schedule below was transcribed from those posters, so it is the one place in
this project where event details are not parsed live.

To keep that from silently rotting, each special names the poster it came
from and is only emitted while that poster is still on the page. When Bodega
swaps a poster, the corresponding special stops being published and the run
logs it, rather than serving a schedule that no longer exists.

The page sits behind a Cloudflare JS challenge, so it needs Playwright.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class BodegaWineBarScraper(BaseScraper):
    """Scraper for Bodega Wine Bar's recurring weekly specials."""

    VENUE_NAME = 'Bodega Wine Bar'
    ADDRESS = '814 Broadway, Santa Monica, CA 90401'

    LOOKAHEAD_DAYS = 56

    # Transcribed from the posters on /specials. `poster` is the image filename
    # the text came from; it doubles as the freshness check.
    # weekday: Monday=0 ... Sunday=6
    SPECIALS = (
        {
            'poster': 'HMsquare.jpg',
            'title': 'Happy Monday',
            'weekday': 0,
            'hour': 16,
            'minute': 0,
            'description': (
                'Every Monday night, 4pm to close: happy hour all night long.'
            ),
            'is_free': True,
            'price': None,
        },
        {
            'poster': 'WINOnologocrop.jpg',
            'title': 'Wino Wednesdays',
            'weekday': 2,
            'hour': 17,
            'minute': 0,
            'description': (
                'Join us every Wednesday: most bottles $30, the fancy ones $40.'
            ),
            'is_free': False,
            'price': 30.0,
        },
        {
            'poster': 'TriviaSquare.jpg',
            'title': 'Sunday Trivia Night',
            'weekday': 6,
            'hour': 18,
            'minute': 30,
            'description': (
                'Free entry, happy hour and prizes. Sign-up from 6pm, '
                'game starts at 6:30 -- arrive early.'
            ),
            'is_free': True,
            'price': None,
        },
    )

    def __init__(self):
        super().__init__('Bodega Wine Bar')
        self.base_url = 'https://bodegawinebar.com'
        self.events_url = f'{self.base_url}/specials'

    def scrape(self) -> List[Event]:
        """Emit weekly occurrences for each special still shown on the page."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page_js(self.events_url, timeout=45000)
            if not html:
                self.log("Failed to fetch specials page (JS render)")
                return events

            for special in self.SPECIALS:
                if special['poster'] not in html:
                    # The poster this schedule was transcribed from is gone, so
                    # the details can no longer be trusted.
                    self.log(
                        f"Poster '{special['poster']}' no longer on the page; "
                        f"skipping '{special['title']}' until it is re-checked"
                    )
                    continue

                for moment in self._weekly_occurrences(
                    special['weekday'], special['hour'], special['minute']
                ):
                    # Every special points at the same /specials page. Dedup
                    # treats a shared URL within 24h as one event, so Sunday
                    # trivia (6:30pm) and Monday happy hour (4pm) -- 21.5h
                    # apart -- collapsed into a single row. Qualify the URL per
                    # occurrence so each stays distinct.
                    slug = special['title'].lower().replace(' ', '-')
                    event = self.create_event(
                        title=special['title'],
                        description=special['description'],
                        venue_name=self.VENUE_NAME,
                        address=self.ADDRESS,
                        event_date=moment,
                        url=f"{self.events_url}#{slug}-{moment:%Y%m%d}",
                        price=special['price'],
                        is_free=special['is_free'],
                        price_note='',
                    )
                    if event:
                        events.append(event)

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _weekly_occurrences(self, weekday: int, hour: int, minute: int) -> List[datetime]:
        now = datetime.now()
        occurrences = []
        cursor = now.date()
        end = (now + timedelta(days=self.LOOKAHEAD_DAYS)).date()
        while cursor <= end:
            if cursor.weekday() == weekday:
                moment = datetime.combine(cursor, datetime.min.time()).replace(
                    hour=hour, minute=minute
                )
                if moment >= now:
                    occurrences.append(moment)
            cursor += timedelta(days=1)
        return occurrences

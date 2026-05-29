"""
Scraper for Old Town Music Hall events.
Source: https://oldtownmusichall.org/

The previous Agile Ticketing URL is now bot-blocked by Imperva/Incapsula. The
venue's main site is a Quasar/Vue SPA hosted by indy-systems and renders the
upcoming-events grid client-side, so we render with Playwright and extract
movie cards from the rendered DOM.

Each card has:
  - a <span class="bg-secondary ...">May 30</span> date label
  - a sibling <div class="movie-info"> containing the title in
    <div class="text-h6 ...ellipsis...">Title</div>
  - a poster <img> from indy-systems.imgix.net

Showtimes are not rendered on the listing tile (they live behind a click on
the card), so we default the time to 8:00 PM local — the venue's standard
evening showtime — which is good enough for the listing.
"""
from datetime import datetime
from typing import List, Optional
import re

from .base import BaseScraper
from src.data.models import Event


# Default showtime when not present on the listing tile. Most Old Town Music
# Hall screenings run at 8:00 PM on Fri/Sat and 2:30 PM Sunday matinee, but
# the listing page only renders the date. 8 PM is the safer default for a
# discovery view.
DEFAULT_HOUR = 20
DEFAULT_MINUTE = 0


class OldTownMusicHallScraper(BaseScraper):
    """Scraper for Old Town Music Hall events."""

    def __init__(self):
        super().__init__('Old Town Music Hall')
        self.base_url = 'https://oldtownmusichall.org'
        self.events_url = f'{self.base_url}/'
        self.venue_name = 'Old Town Music Hall'
        self.venue_address = '140 Richmond Street, El Segundo, CA 90245'

    def scrape(self) -> List[Event]:
        """Scrape upcoming film/event listings from the OTMH SPA."""
        self.log("Starting scrape...")
        events: List[Event] = []

        try:
            # The site is a JS-rendered Quasar SPA, so use Playwright.
            html = self.fetch_page_js(self.events_url, timeout=30000)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Each event card is anchored by a date badge span. Walk up to the
            # nearest wrapper that also contains the movie-info block.
            date_spans = soup.find_all('span', class_=re.compile(r'bg-secondary'))
            self.log(f"Found {len(date_spans)} date badges")

            seen = set()
            for ds in date_spans:
                try:
                    date_text = ds.get_text(strip=True)
                    if not date_text:
                        continue

                    # Walk up to find the card wrapper containing movie-info.
                    card = ds
                    movie_info = None
                    for _ in range(10):
                        card = card.find_parent()
                        if card is None:
                            break
                        movie_info = card.find('div', class_='movie-info')
                        if movie_info is not None:
                            break
                    if movie_info is None:
                        continue

                    # Title from text-h6 inside movie-info
                    title_el = movie_info.find(class_=re.compile(r'text-h6'))
                    if not title_el:
                        continue
                    title = self.clean_text(title_el.get_text())
                    if not title:
                        continue

                    # Dedupe by (title, date) — the SPA sometimes renders the
                    # same event in multiple carousels.
                    key = (title.lower(), date_text.lower())
                    if key in seen:
                        continue
                    seen.add(key)

                    event_date = self._parse_date(date_text)
                    if event_date is None:
                        self.log(f"Skipping event with unparseable date: {title} ({date_text})")
                        continue

                    # Poster image (optional)
                    image_url = ""
                    img = card.find('img')
                    if img and img.get('src'):
                        image_url = img['src']

                    category = self._categorize_event(title)

                    event = self.create_event(
                        title=title,
                        description="",
                        venue_name=self.venue_name,
                        address=self.venue_address,
                        event_date=event_date,
                        url=self.events_url,
                        image_url=image_url,
                        category=category,
                        price_note="TBD",
                    )
                    if event:
                        events.append(event)

                except Exception as e:
                    self.log(f"Error parsing event card: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse short date badge like 'May 30' or 'Jun 6' into a datetime.

        Assumes the upcoming year — if the parsed month is earlier than the
        current month, roll over to next year.
        """
        try:
            now = datetime.now()
            # Try '%b %d' first (Jun 6), fall back to long month name.
            for fmt in ('%b %d', '%B %d'):
                try:
                    parsed = datetime.strptime(date_text, fmt)
                    break
                except ValueError:
                    parsed = None
            if parsed is None:
                return None

            year = now.year
            # If the date already passed this year by more than a day, assume next year.
            candidate = parsed.replace(
                year=year, hour=DEFAULT_HOUR, minute=DEFAULT_MINUTE
            )
            if (now - candidate).days > 1:
                candidate = candidate.replace(year=year + 1)
            return candidate
        except Exception as e:
            self.log(f"Date parse error for '{date_text}': {e}")
            return None

    def _categorize_event(self, title: str) -> str:
        """
        Categorize event based on title.

        Old Town Music Hall hosts classic films and live music performances.
        """
        title_lower = title.lower()
        music_keywords = [
            'concert', 'band', 'orchestra', 'jazz', 'music',
            'parlor boys', 'celebration', 'organ', 'pianist',
            'ragtime', 'sing-along', 'singalong',
        ]
        for keyword in music_keywords:
            if keyword in title_lower:
                return "Music"
        return "Film"

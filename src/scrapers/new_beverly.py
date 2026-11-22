"""
Scraper for the New Beverly Cinema (Fairfax).
Source: https://thenewbev.com/schedule/

The schedule is server-rendered WordPress HTML: one `section.calendar-month`
per month (its <h2> gives "November 2026") holding an `article.event-card` per
program. A program is one date with one or more showtimes (a double feature
lists two), and every card links to its own date-specific page
(/program/november-21-zodiac/), so the URLs are already unique per day.

7165 Beverly Blvd is inside the Westside coverage box
(is_in_coverage_area is True), so this keeps the default region.
"""
from datetime import datetime
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class NewBeverlyScraper(BaseScraper):
    """Scraper for New Beverly Cinema programs."""

    SCHEDULE_URL = 'https://thenewbev.com/schedule/'
    VENUE_NAME = 'New Beverly Cinema'
    VENUE_ADDRESS = '7165 Beverly Blvd, Los Angeles, CA 90036'
    LATITUDE = 34.0762
    LONGITUDE = -118.3541

    def __init__(self):
        super().__init__('New Beverly Cinema')
        self.base_url = 'https://thenewbev.com'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events: List[Event] = []

        html = self.fetch_page(self.SCHEDULE_URL)
        if not html:
            self.log("Failed to fetch schedule page")
            return events

        soup = self.parse_html(html)
        now = datetime.now()
        for month in soup.select('section.calendar-month'):
            heading = month.find('h2')
            try:
                month_start = datetime.strptime(heading.get_text(strip=True), '%B %Y')
            except (AttributeError, ValueError):
                self.log("Skipping a month section without a 'Month YYYY' heading")
                continue
            for card in month.select('article.event-card'):
                try:
                    event = self._parse_card(card, month_start, now)
                except Exception as e:
                    self.log(f"Error parsing card: {e}")
                    continue
                if event:
                    events.append(event)

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _parse_card(self, card, month_start: datetime, now: datetime) -> Optional[Event]:
        title_tag = card.select_one('.event-card__title')
        link = card.find('a', href=True)
        day_tag = card.select_one('.event-card__numb')
        if not (title_tag and link and day_tag):
            return None
        title = self.clean_text(title_tag.get_text(' '))

        times = []
        for tag in card.select('time.event-card__time'):
            try:
                clock = datetime.strptime(tag.get_text(strip=True).lower(), '%I:%M %p')
            except ValueError:
                self.log(f"Skipping '{title}': unreadable showtime '{tag.get_text(strip=True)}'")
                return None
            times.append(clock)
        if not times:
            self.log(f"Skipping '{title}': no showtime listed")
            return None

        day = int(day_tag.get_text(strip=True))
        starts = [month_start.replace(day=day, hour=t.hour, minute=t.minute) for t in times]
        if max(starts) < now:
            return None

        labels = [i.get('aria-label') for i in card.select('i.event-card__label') if i.get('aria-label')]
        status = self.clean_text(card.select_one('.event-card__link').get_text(' ')
                                 if card.select_one('.event-card__link') else '')
        sold_out = status.lower().startswith('sold out')

        clock = ', '.join(f"{s.hour % 12 or 12}:{s.minute:02d}{'am' if s.hour < 12 else 'pm'}" for s in starts)
        description = ('. '.join(labels + [f"Showtimes - {clock}"])) + '.'
        if sold_out:
            description += ' Sold out online; some tickets may be available at the door.'

        img = card.find('img')
        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            latitude=self.LATITUDE,
            longitude=self.LONGITUDE,
            event_date=starts[0],
            url=link['href'],
            image_url=(img.get('src') if img else '') or '',
            category="Film",
            price=None,
            is_free=False,
            price_note='Sold out online (some tickets at door)' if sold_out else '',
        )

"""
Scraper for the UCLA Film & Television Archive (Billy Wilder Theater, Westwood).
Source: https://www.cinema.ucla.edu/events

The events list is a Nuxt app that fills in client-side, so the listing pages
(``?page=N``, ten events each) are rendered with Playwright and the cards are
parsed from the rendered DOM. Only the rendered page is read; the site's
private search index is not queried. Each event's own page is server-rendered,
so it is fetched with plain HTTP for the venue, ticket info and description.
If a detail page can't be fetched, the listing data alone still yields an event.

Billy Wilder Theater is inside the Westside coverage box (default region).
"""
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from .base import BaseScraper
from src.data.models import Event


class UCLAFilmArchiveScraper(BaseScraper):
    """Scraper for UCLA Film & Television Archive screenings."""

    VENUE_NAME = 'Billy Wilder Theater'
    VENUE_ADDRESS = '10899 Wilshire Blvd, Los Angeles, CA 90024'
    VENUE_LAT = 34.0592
    VENUE_LNG = -118.4435

    EVENTS_URL = 'https://www.cinema.ucla.edu/events/'
    PAGE_URL = 'https://www.cinema.ucla.edu/events/?page={page}'

    MAX_PAGES = 5  # ten events a page; the live list is two pages
    LISTING_BUDGET_SECONDS = 60  # stop paging after this; the runner kills a scraper at 120 s
    PAGE_SIZE = 10
    DESCRIPTION_LIMIT = 600

    def __init__(self):
        super().__init__('UCLA Film & Television Archive')
        self.base_url = 'https://www.cinema.ucla.edu'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of UCLA Film & Television Archive...")
        cards = self._listing_cards()
        self.log(f"Found {len(cards)} listed event(s)")
        if not cards:
            return []

        self.prefetch_pages([c['url'] for c in cards])

        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        events: List[Event] = []
        seen = set()
        for card in cards:
            try:
                event = self._build_event(card)
            except Exception as e:
                self.log(f"  x error parsing '{card.get('title', '')}': {e}")
                continue
            if not event:
                continue
            # An untimed event (00:00) is still upcoming all day.
            cutoff = today if event.event_date == event.event_date.replace(hour=0, minute=0) else now
            if event.event_date < cutoff:
                continue
            if event.url in seen:
                continue
            seen.add(event.url)
            events.append(event)

        self.log(f"Scraped {len(events)} upcoming event(s)")
        return events

    # -- listing ---------------------------------------------------------

    def _listing_cards(self) -> List[dict]:
        cards: List[dict] = []
        total_pages = 1
        page = 1
        started = time.monotonic()
        while page <= min(total_pages, self.MAX_PAGES):
            if time.monotonic() - started > self.LISTING_BUDGET_SECONDS:
                self.log("Listing time budget spent; stopping paging")
                break
            url = self.EVENTS_URL if page == 1 else self.PAGE_URL.format(page=page)
            html = self.fetch_page_js(url, wait_selector='li.list-item', timeout=20000)
            if not html:
                self.log(f"Failed to render listing page {page}")
                break
            page_cards = self._parse_cards(html)
            cards.extend(page_cards)
            if page == 1:
                total_pages = self._page_count(html)
            if len(page_cards) < self.PAGE_SIZE:
                break
            page += 1
        return cards

    def _page_count(self, html: str) -> int:
        soup = self.parse_html(html)
        numbers = [
            int(a.get_text(strip=True))
            for a in soup.select('.pagination-numbers a')
            if a.get_text(strip=True).isdigit()
        ]
        return max(numbers) if numbers else 1

    def _parse_cards(self, html: str) -> List[dict]:
        """Event cards from a rendered listing page (empty when the markup differs)."""
        soup = self.parse_html(html)
        cards = []
        for li in soup.select('li.list-item'):
            link = li.select_one('a.title')
            date_el = li.select_one('time.start-date')
            if not link or not link.get('href') or not date_el:
                continue
            time_el = li.select_one('time.parsed-time')
            when = self._parse_when(date_el.get_text(strip=True), time_el.get_text(strip=True) if time_el else '')
            if not when:
                self.log(f"  - skipping undated event: {link.get_text(strip=True)}")
                continue
            img = li.select_one('img')
            category = li.select_one('.category')
            cards.append({
                'title': self.clean_text(link.get_text(' ', strip=True)),
                'url': urljoin(self.base_url, link['href']),
                'when': when,
                'series': self.clean_text(category.get_text(' ', strip=True)) if category else '',
                'image': (img.get('src') or '') if img else '',
            })
        return cards

    @staticmethod
    def _parse_when(date_text: str, time_text: str) -> Optional[datetime]:
        """'Nov 21, 2026' + '7:30 pm' -> naive LA-local datetime (midnight if untimed)."""
        try:
            day = datetime.strptime(date_text.strip(), '%b %d, %Y')
        except ValueError:
            return None
        try:
            t = datetime.strptime(time_text.strip().lower(), '%I:%M %p')
        except ValueError:
            return day
        return day.replace(hour=t.hour, minute=t.minute)

    # -- detail ----------------------------------------------------------

    def _detail(self, url: str) -> Dict[str, str]:
        """Venue, description and ticket lines from the event page ({} if unavailable)."""
        html = self.fetch_page(url, retry=1)
        if not html:
            return {}
        soup = self.parse_html(html)
        venue = soup.select_one('.event-list.location')
        description = soup.select_one('.event-description')
        return {
            'venue': self.clean_text(venue.get_text(' ', strip=True)) if venue else '',
            'description': self.clean_text(description.get_text(' ', strip=True)) if description else '',
            'tickets': ' | '.join(
                li.get_text(' ', strip=True) for li in soup.select('.ticket-info li')
            ),
        }

    @staticmethod
    def _price(tickets: str):
        """(price, is_free) from the ticket-info lines."""
        if re.search(r'free admission', tickets, re.I):
            return None, True
        amounts = [float(m) for m in re.findall(r'\$\s?(\d+(?:\.\d{2})?)', tickets)]
        return (min(amounts), False) if amounts else (None, False)

    def _build_event(self, card: dict) -> Optional[Event]:
        detail = self._detail(card['url'])
        venue = detail.get('venue') or self.VENUE_NAME
        at_home = 'wilder' in venue.lower()

        series = card['series']
        description = detail.get('description', '')[:self.DESCRIPTION_LIMIT]
        if series:
            description = f"{series}. {description}".strip()

        price, is_free = self._price(detail.get('tickets', ''))

        return self.create_event(
            title=card['title'],
            description=description,
            venue_name=self.VENUE_NAME if at_home else venue,
            address=self.VENUE_ADDRESS if at_home else '',
            event_date=card['when'],
            url=card['url'],
            image_url=card['image'],
            category='Film',
            price=price,
            is_free=is_free,
            latitude=self.VENUE_LAT if at_home else None,
            longitude=self.VENUE_LNG if at_home else None,
        )

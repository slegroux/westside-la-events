"""
Scraper for Vino Y Vinyl pop-ups (wine + live music + vinyl).
Source: https://www.universe.com/users/6966c1ee369af8002bc61683

This began as a request for "events at Saba Surf Cafe". Saba publishes no
calendar of its own -- its events are ticketed by outside promoters, and the
one that runs there regularly is Vino Y Vinyl. So the promoter's Universe host
page is the source, and each event's own venue is used rather than assuming
Saba: the series does move (Ticketmaster still lists an August date as Saba
that Universe places at 222 Main St in Venice). Events outside the coverage
area are dropped by the geo filter as usual.

Universe renders client-side, so this needs Playwright.

Caveat worth knowing: this covers one promoter, not the Saba venue. A
different promoter booking Saba would not be picked up here.
"""
import re
from datetime import datetime
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class VinoYVinylScraper(BaseScraper):
    """Scraper for the Vino Y Vinyl promoter's Universe page."""

    HOST_ID = '6966c1ee369af8002bc61683'

    # "Sat, Aug 29, 2026 at 6:30-11:30 PM" / "Sat, May 2, 2026 at 6-11:30 PM"
    _DATE_RE = re.compile(
        r'\w{3},\s*(?P<month>\w{3})\s*(?P<day>\d{1,2}),\s*(?P<year>\d{4})\s*at\s*'
        r'(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?'
        r'(?:\s*[-–]\s*\d{1,2}(?::\d{2})?)?\s*(?P<meridiem>AM|PM)',
        re.IGNORECASE,
    )
    # A street address line: starts with a number, ends with a zip.
    _ADDRESS_RE = re.compile(r'^\d+[^,]*,.*\b\d{5}\b')
    _PRICE_RE = re.compile(r'\$\s*(\d+(?:\.\d{2})?)')

    MONTHS = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }

    MAX_EVENTS = 20

    def __init__(self):
        super().__init__('Vino Y Vinyl')
        self.base_url = 'https://www.universe.com'
        self.events_url = f'{self.base_url}/users/{self.HOST_ID}'

    def scrape(self) -> List[Event]:
        """Read the promoter's upcoming events off their Universe host page."""
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page_js(self.events_url, timeout=45000)
            if not html:
                self.log("Failed to fetch host page (JS render)")
                return events

            urls = self._event_urls(html)
            self.log(f"Found {len(urls)} event links")

            for url in urls[:self.MAX_EVENTS]:
                try:
                    event = self._parse_event_page(url)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing {url}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _event_urls(self, html: str) -> List[str]:
        urls = []
        for path in re.findall(r'/events/[a-z0-9-]+-tickets-[A-Za-z0-9]+', html):
            url = f'{self.base_url}{path}'
            if url not in urls:
                urls.append(url)
        return urls

    def _parse_event_page(self, url: str) -> Optional[Event]:
        html = self.fetch_page_js(url, timeout=45000)
        if not html:
            return None

        soup = self.parse_html(html)
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        lines = [
            line.strip()
            for line in soup.get_text('\n', strip=True).split('\n')
            if line.strip()
        ]

        event_date, date_index = self._find_date(lines)
        if not event_date:
            return None

        # Past listings stay up on Universe long after the show.
        if event_date < datetime.now():
            return None

        # The title is the line immediately above the date block.
        title = ''
        if date_index > 0:
            title = self.clean_text(lines[date_index - 1])
        if not title:
            return None

        address = self._find_address(lines, date_index)
        if not address:
            return None

        price = self._find_price(lines)

        return self.create_event(
            title=title,
            description='',
            venue_name=self._venue_from_address(address),
            address=address,
            event_date=event_date,
            url=url,
            price=price,
            is_free=(price == 0) if price is not None else False,
            price_note='',
        )

    def _find_date(self, lines):
        for index, line in enumerate(lines):
            match = self._DATE_RE.search(line)
            if not match:
                continue
            month = self.MONTHS.get(match.group('month')[:3].lower())
            if not month:
                continue
            hour = int(match.group('hour'))
            minute = int(match.group('minute') or 0)
            if match.group('meridiem').upper() == 'PM' and hour != 12:
                hour += 12
            elif match.group('meridiem').upper() == 'AM' and hour == 12:
                hour = 0
            try:
                moment = datetime(
                    int(match.group('year')), month, int(match.group('day')),
                    hour, minute,
                )
            except ValueError:
                continue
            return moment, index
        return None, -1

    def _find_address(self, lines, date_index: int) -> str:
        """The address renders directly under the date; fall back to a scan."""
        for line in lines[date_index + 1:date_index + 4]:
            if self._ADDRESS_RE.match(line):
                return self.clean_text(line)
        for line in lines:
            if self._ADDRESS_RE.match(line):
                return self.clean_text(line)
        return ''

    def _find_price(self, lines) -> Optional[float]:
        """Lowest advertised price, which is what the card badge shows."""
        prices = []
        for line in lines:
            for raw in self._PRICE_RE.findall(line):
                try:
                    prices.append(float(raw))
                except ValueError:
                    continue
        return min(prices) if prices else None

    def _venue_from_address(self, address: str) -> str:
        """Universe publishes a street address with no venue name attached.

        Saba is the series' usual home, so it is named when the address
        matches; anything else is labelled as a pop-up at that address.
        """
        if address.startswith('12912 Venice'):
            return 'Saba Surf & Cafe'
        street = address.split(',')[0].strip()
        return f'Vino Y Vinyl pop-up — {street}'

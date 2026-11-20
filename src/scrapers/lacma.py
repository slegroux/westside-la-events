"""
Scraper for LACMA (Los Angeles County Museum of Art) events.
Source: https://www.lacma.org/events-calendar  (``/events`` redirects here)

LACMA publishes no JSON API, iCal or RSS feed (``/rss.xml`` errors, ``.ics``
404s, ``?_format=json`` is refused) and its robots.txt disallows the sitemap, so
the listing HTML is the only source. That HTML comes in two layouts, which is
why this scraper stopped finding events in production:

* ``/events-calendar`` renders ``div.views-calendar-results`` blocks, one per
  day, each headed by ``<h3>Today, November 19, 2026</h3>`` -- but only the first
  two days (about 8 events), then an infinite-scroll "Load More" link.
* ``/events-calendar?page=N`` renders ``h4.event-calendar-date-group`` headings
  ("Thursday, November 19", no year) over the same ``.card-event`` cards, 12
  cards per page, and paginates through the whole calendar.

Both are parsed by one walk over ``h3``/``h4`` day headers and ``.card-event``
cards. The paginated layout is tried first because it is the complete listing;
the bare page is the fallback. When neither yields a card, the page's title,
length and text excerpt are logged so the next log shows what we received
(for example a bot-protection page served to a datacenter IP).

Titles in the paginated layout are cut to ~60 characters with a trailing
"..."; the full title is read from the event page's JSON-LD.
"""
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Optional

from bs4 import Tag
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class _DeadlineSession:
    """Clamps each request's timeout to what is left of the scraper's budget.

    The runner discards everything at 120 s, and one request can otherwise run
    for its full 30 s timeout (more when connect and read both stall) after the
    budget check passed. Everything else is passed through to the real session.
    """

    def __init__(self, session, scraper):
        self._session = session
        self._scraper = scraper

    def get(self, url, timeout=None, **kwargs):
        remaining = self._scraper._deadline - time.monotonic()
        if timeout is not None:
            timeout = max(1.0, min(timeout, remaining))
        return self._session.get(url, timeout=timeout, **kwargs)

    def __getattr__(self, name):
        return getattr(self._session, name)


class LACMAScraper(BaseScraper):
    """Scraper for LACMA events."""

    # Paginated calendar: ~12 cards per page, ~8 events/day.
    MAX_PAGES = 14
    HORIZON_DAYS = 30
    MAX_TITLE_LOOKUPS = 25
    # The runner kills a scraper at 120 s and discards everything it collected.
    # A hanging site costs a full request timeout per fetch, so stop paging
    # (and title lookups) once this much time has passed and keep what we have.
    SCRAPE_BUDGET_SECONDS = 80

    # LACMA's fixed location, so no geocoding is needed for in-person events.
    VENUE_LAT = 34.0639
    VENUE_LNG = -118.3592

    def __init__(self):
        super().__init__('LACMA')
        self.base_url = 'https://www.lacma.org'
        self.events_url = f'{self.base_url}/events-calendar'
        self._title_lookups = 0
        self._deadline = float('inf')
        self.session = _DeadlineSession(self.session, self)

    def _over_budget(self) -> bool:
        return time.monotonic() >= self._deadline

    def scrape(self) -> List[Event]:
        """Scrape upcoming events from the LACMA calendar."""
        self.log("Starting scrape...")
        events: List[Event] = []
        self._title_lookups = 0
        self._deadline = time.monotonic() + self.SCRAPE_BUDGET_SECONDS

        try:
            events = self._scrape_paginated()
            if not events and self._over_budget():
                self.log("Time budget spent; not trying the bare calendar page")
            elif not events:
                self.log("Paginated calendar yielded nothing; trying the bare calendar page")
                html = self.fetch_page(self.events_url, retry=1)
                events = self._parse_listing(html, 'bare calendar page')[0]
            self.log(f"Successfully scraped {len(events)} events")
        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _scrape_paginated(self) -> List[Event]:
        events: List[Event] = []
        seen = set()
        horizon = datetime.now() + timedelta(days=self.HORIZON_DAYS)

        for page in range(self.MAX_PAGES):
            if self._over_budget():
                self.log(f"Time budget of {self.SCRAPE_BUDGET_SECONDS}s spent before page {page}; "
                         f"keeping {len(events)} events")
                break
            html = self.fetch_page(f'{self.events_url}?page={page}', retry=1)
            if not html:
                # A failed fetch (timeout, 5xx) is not the end of the calendar:
                # skip the page and keep going while the budget allows.
                continue
            page_events, n_cards = self._parse_listing(html, f'page {page}')
            if n_cards == 0:
                break
            added = 0
            for event in page_events:
                key = (event.url, event.event_date)
                if key in seen:
                    continue
                seen.add(key)
                events.append(event)
                added += 1
            if added == 0:
                break
            dated = [e.event_date for e in page_events if e.event_date]
            if dated and max(dated) > horizon:
                break
        return events

    def _parse_listing(self, html: Optional[str], label: str):
        """Parse one listing page. Returns (events, number_of_cards_found)."""
        if not html:
            self.log(f"Failed to fetch LACMA {label}")
            return [], 0

        soup = self.parse_html(html)
        events: List[Event] = []
        n_cards = 0
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        current_day_text = None

        # Walk in document order so each card is associated with the day header
        # above it. Two layouts: <h3> in div.views-calendar-results, or
        # <h4 class="event-calendar-date-group">.
        for el in soup.descendants:
            if not isinstance(el, Tag):
                continue
            classes = el.get('class') or []
            if el.name == 'h3' or (el.name == 'h4' and 'event-calendar-date-group' in classes):
                current_day_text = self.clean_text(el.get_text())
            elif el.name == 'div' and 'views-row' in classes and el.find(class_='card-event'):
                n_cards += 1
                try:
                    event = self._parse_event(el, current_day_text)
                except Exception as e:
                    self.log(f"Error parsing event: {e}")
                    continue
                if not event:
                    continue
                if event.event_date and event.event_date < today:
                    continue
                events.append(event)

        if n_cards == 0:
            self._log_unrecognised_page(html, label)
        return events, n_cards

    def _log_unrecognised_page(self, html: str, label: str):
        """Say what we got when no event card is found (e.g. a block page)."""
        soup = self.parse_html(html)
        title = self.clean_text(soup.title.get_text()) if soup.title else ''
        text = self.clean_text(soup.get_text(' '))[:200]
        self.log(
            f"No event cards on LACMA {label}: title={title!r}, "
            f"length={len(html)}, calendar_blocks={len(soup.find_all(class_='views-calendar-results'))}, "
            f"text={text!r}"
        )

    def _full_title(self, url: str, truncated: str) -> str:
        """Replace a '...'-truncated card title with the JSON-LD name of its page."""
        if not url or self._title_lookups >= self.MAX_TITLE_LOOKUPS or self._over_budget():
            return truncated
        self._title_lookups += 1
        html = self.fetch_page(url, retry=1)
        if not html:
            return truncated
        for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
            try:
                data = json.loads(m.group(1))
            except ValueError:
                continue
            nodes = data.get('@graph', [data]) if isinstance(data, dict) else data
            for node in nodes:
                if isinstance(node, dict) and node.get('@type') == 'Event' and node.get('name'):
                    full = self.clean_text(node['name'])
                    if full.startswith(truncated.rstrip('. ')):
                        return full
        return truncated

    def _parse_event(self, item, day_header_text: str = None) -> Event:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data (a div.views-row
                wrapping a .card-event block)
            day_header_text: Text from the most recent <h3> day header above
                this event (e.g. "Today, May 29, 2026" or
                "Saturday, May 30, 2026"). Used as the canonical date source
                because the per-card text only has month/day with no year.

        Returns:
            Event object or None
        """
        _re = re

        # Extract title from card-event__name
        title_elem = item.find(class_='card-event__name') or item.find(['h2', 'h3', 'h4'])
        if not title_elem:
            link_elem = item.find('a')
            title_elem = link_elem
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event":
            return None

        link_elem = item.find('a', href=True)
        url = self.normalize_url(link_elem['href'], self.base_url) if link_elem else ""
        if title.endswith('...'):
            title = self._full_title(url, title)

        # Extract description (cards typically have none; fall back to type label)
        desc_elem = item.find('p') or item.find(class_='card-event__type')
        description = self.clean_text(desc_elem.get_text()) if desc_elem else ""

        # Extract date/time. LACMA renders the date inside .card-event__date as
        # two spans, e.g. "Fri May 29" | "11 am". The year is only in the day
        # header above; pull from there when available, else infer with roll-over.
        event_date = None
        date_block = item.find(class_='card-event__date')
        if date_block:
            spans = date_block.find_all('span')
            date_part = self.clean_text(spans[0].get_text()) if len(spans) >= 1 else ''
            time_part = self.clean_text(spans[1].get_text()) if len(spans) >= 2 else ''

            year = None
            if day_header_text:
                ym = _re.search(r'(\d{4})', day_header_text)
                if ym:
                    year = int(ym.group(1))
            if not year:
                year = datetime.now().year

            # date_part looks like "Fri May 29"; strip the leading weekday
            cleaned = _re.sub(r'^[A-Za-z]{3,9}\s+', '', date_part).strip()
            # "11 am PT": drop the zone label (dateutil would warn/ignore it)
            time_part = _re.sub(r'\s*\b(?:PT|PST|PDT)\b', '', time_part).strip()
            candidate = f"{cleaned} {year}"
            if time_part:
                candidate += f" {time_part}"
            try:
                parsed = date_parser.parse(candidate, fuzzy=True)
                # If we had no explicit year and the parsed date is well in the
                # past, roll forward one year.
                if not (day_header_text and _re.search(r'\d{4}', day_header_text or '')):
                    now = datetime.now()
                    if (now - parsed).days > 30:
                        parsed = parsed.replace(year=now.year + 1)
                    elif (parsed - now).days > 335:
                        parsed = parsed.replace(year=now.year - 1)
                event_date = parsed
            except Exception as e:
                self.log(f"Error parsing date '{candidate}': {e}")

        # Fallback: <time> element with datetime attribute
        if not event_date:
            date_elem = item.find('time')
            if date_elem:
                date_str = date_elem.get('datetime', '') or date_elem.get_text()
                try:
                    event_date = date_parser.parse(date_str)
                except Exception:
                    pass

        # Extract location/venue. The location label is usually an internal
        # gallery ("BCAM, Level 2", "Resnick Pavilion | LACMA") at LACMA's own
        # address — keep the canonical street address so it geocodes and passes
        # the Westside geo-fence, and only branch for genuinely online events.
        venue_name = "LACMA"
        address = "5905 Wilshire Blvd, Los Angeles, CA 90036"

        location_elem = item.find(class_=lambda x: x and 'location' in x.lower())
        if location_elem:
            location_text = self.clean_text(location_elem.get_text())
            if location_text and 'online' in location_text.lower():
                venue_name = "LACMA (Online)"
                address = "Online"
            elif location_text and location_text.lower() not in ['lacma', 'los angeles county museum of art']:
                # Show the specific gallery, but keep LACMA's real address.
                # The source sometimes appends a redundant "| LACMA" suffix.
                gallery = _re.sub(r'\s*\|\s*LACMA\s*$', '', location_text).strip()
                if gallery and gallery.lower() != 'lacma':
                    venue_name = f"LACMA — {gallery}"

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            # Try different src attributes (Drupal can use data-src, srcset, etc.)
            image_url = img_elem.get('src', '') or img_elem.get('data-src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info
        # LACMA general admission is required for most events
        is_free = False
        price = None
        price_note = "Museum admission required"

        # Check for free events in text
        text_content = f"{title} {description}".lower()
        if 'free' in text_content or 'no admission' in text_content:
            is_free = True
            price_note = "Free event"

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            price=price,
            is_free=is_free,
            price_note=price_note,
            latitude=None if address == "Online" else self.VENUE_LAT,
            longitude=None if address == "Online" else self.VENUE_LNG,
        )

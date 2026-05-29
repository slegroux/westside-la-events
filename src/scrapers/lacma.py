"""
Scraper for LACMA (Los Angeles County Museum of Art) events.
Source: https://www.lacma.org/events
"""
from datetime import datetime
from typing import List
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class LACMAScraper(BaseScraper):
    """Scraper for LACMA events."""

    def __init__(self):
        super().__init__('LACMA')
        self.base_url = 'https://www.lacma.org'
        self.events_url = f'{self.base_url}/events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from LACMA website.

        LACMA uses a Drupal Views system with AJAX loading capabilities.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the events page
            html = self.fetch_page(self.events_url)
            if not html:
                self.log("Failed to fetch events page")
                return events

            soup = self.parse_html(html)

            # Restrict to the calendar section. The /events page also contains a
            # second listing of static category links (Exhibitions, Film, etc.)
            # that have no dates and would otherwise be returned as undated rows.
            calendar = soup.find('div', class_='views-calendar-results')
            if calendar:
                # Within the calendar, events are grouped under <h3> day headers
                # like "Today, May 29, 2026" or "Saturday, May 30, 2026" and each
                # event card sits inside a div.views-row with a .card-event block.
                current_day_text = None
                # Walk the descendants in order so each event is associated with
                # the most recently seen day header.
                from bs4 import NavigableString, Tag
                for el in calendar.descendants:
                    if not isinstance(el, Tag):
                        continue
                    if el.name == 'h3':
                        current_day_text = self.clean_text(el.get_text())
                    elif el.name == 'div' and el.get('class') and 'views-row' in el.get('class') and el.find(class_='card-event'):
                        try:
                            event = self._parse_event(el, current_day_text)
                            if event:
                                events.append(event)
                        except Exception as e:
                            self.log(f"Error parsing event: {e}")
                            continue
            else:
                self.log("No calendar section found on LACMA events page")

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

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
        import re as _re

        # Extract title from card-event__name
        title_elem = item.find(class_='card-event__name') or item.find(['h2', 'h3', 'h4'])
        if not title_elem:
            link_elem = item.find('a')
            title_elem = link_elem
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"

        if not title or title == "Untitled Event":
            return None

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

        # Extract location/venue
        venue_name = "LACMA"
        address = "5905 Wilshire Blvd, Los Angeles, CA 90036"

        # Check if it's an online or off-site event
        location_elem = item.find(class_=lambda x: x and 'location' in x.lower())
        if location_elem:
            location_text = self.clean_text(location_elem.get_text())
            if location_text and 'online' in location_text.lower():
                venue_name = "LACMA (Online)"
                address = "Online"
            elif location_text and location_text.lower() not in ['lacma', 'los angeles county museum of art']:
                venue_name = location_text
                address = f"{location_text}, Los Angeles, CA"

        # Extract URL
        link_elem = item if item.name == 'a' else item.find('a', href=True)
        url = ""
        if link_elem and link_elem.has_attr('href'):
            url = self.normalize_url(link_elem['href'], self.base_url)

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
            price_note=price_note
        )

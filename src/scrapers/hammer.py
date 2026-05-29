"""
Scraper for Hammer Museum events.
Source: https://hammer.ucla.edu/programs-events
"""
import re
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class HammerScraper(BaseScraper):
    """Scraper for Hammer Museum events."""

    # Cap pages to avoid runaway scraping if the site grows
    MAX_PAGES = 10

    def __init__(self):
        super().__init__('Hammer Museum')
        self.base_url = 'https://hammer.ucla.edu'
        self.events_url = f'{self.base_url}/programs-events'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Hammer Museum website. Follows pagination.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []
        seen_urls = set()

        try:
            for page in range(self.MAX_PAGES):
                page_url = self.events_url if page == 0 else f'{self.events_url}?page={page}'
                html = self.fetch_page(page_url)
                if not html:
                    self.log(f"Failed to fetch page {page}")
                    break

                soup = self.parse_html(html)

                # Hammer renders each event as <article><a class="result-item ..."> ...
                # plus a single featured <article class="node--type-program ...">.
                items = soup.find_all('a', class_=lambda c: c and 'result-item' in c)

                # Also pick up the featured program article on page 0
                featured = soup.find_all(
                    'article',
                    class_=lambda c: c and 'node--type-program' in c
                )

                page_items = list(items) + list(featured)
                self.log(f"Page {page}: found {len(page_items)} event items")

                if not page_items:
                    # No items on this page — stop paging
                    break

                new_on_page = 0
                for item in page_items:
                    try:
                        event = self._parse_event(item)
                        if not event:
                            continue
                        # Dedupe across pages by source URL
                        if event.url and event.url in seen_urls:
                            continue
                        if event.url:
                            seen_urls.add(event.url)
                        events.append(event)
                        new_on_page += 1
                    except Exception as e:
                        self.log(f"Error parsing event: {e}")
                        continue

                # If page yielded zero new events, assume we've reached the end
                if new_on_page == 0 and page > 0:
                    break

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _parse_event(self, item) -> Optional[Event]:
        """
        Parse a single event item.

        Args:
            item: BeautifulSoup element containing event data
                  (either an <a class="result-item"> or a featured <article>)

        Returns:
            Event object or None
        """
        # Extract title
        title_elem = item.find(class_=lambda c: c and 'result-item__title' in c)
        if not title_elem:
            title_elem = item.find(['h2', 'h3', 'h4'])
        if not title_elem and item.name == 'a':
            title_elem = item
        title = self.clean_text(title_elem.get_text()) if title_elem else "Untitled Event"
        if not title or title.lower() == 'featured programs':
            return None

        # Extract description / excerpt
        desc_elem = item.find(class_=lambda c: c and 'result-item__excerpt' in c)
        if not desc_elem:
            desc_elem = item.find(class_=lambda c: c and 'description' in c.lower())
        if not desc_elem:
            desc_elem = item.find('p')
        description = self.clean_text(desc_elem.get_text(' ')) if desc_elem else ""

        # Extract date/time from occurrence block
        event_date = self._extract_date(item)

        # Venue info - Hammer Museum
        venue_name = "Hammer Museum"
        address = "10899 Wilshire Blvd, Los Angeles, CA 90024"

        # Extract URL
        url = ""
        if item.name == 'a' and item.has_attr('href'):
            url = self.normalize_url(item['href'], self.base_url)
        else:
            link_elem = item.find('a', href=True)
            if link_elem:
                url = self.normalize_url(link_elem['href'], self.base_url)

        # Extract image
        image_url = ""
        img_elem = item.find('img')
        if img_elem:
            image_url = img_elem.get('data-src', '') or img_elem.get('src', '')
            if image_url:
                image_url = self.normalize_url(image_url, self.base_url)

        # Price info - Hammer Museum events are typically free
        is_free = True
        price = None
        price_note = "Free admission; timed tickets recommended"

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

    def _extract_date(self, item) -> Optional[datetime]:
        """Extract event date from the occurrence block or any date markup."""
        # Hammer markup: <div class="result-item__occurrence">Fri May 29<span class="occurrence__time">7:30 PM</span></div>
        occ = item.find(class_=lambda c: c and 'result-item__occurrence' in c)
        if occ:
            time_elem = occ.find(class_=lambda c: c and 'occurrence__time' in c)
            time_str = self.clean_text(time_elem.get_text()) if time_elem else ''
            # Date portion is everything in occ minus the time
            date_only = occ.get_text(' ', strip=True)
            if time_str:
                date_only = date_only.replace(time_str, '').strip()
            combined = f"{date_only} {time_str}".strip()
            parsed = self._safe_parse_date(combined)
            if parsed:
                return parsed

        # Fallback: <time datetime="..."> or any element with 'date' in class
        time_elem = item.find('time')
        if time_elem:
            date_str = time_elem.get('datetime', '') or time_elem.get_text()
            parsed = self._safe_parse_date(date_str)
            if parsed:
                return parsed

        date_elem = item.find(class_=lambda c: c and 'date' in c.lower())
        if date_elem:
            parsed = self._safe_parse_date(date_elem.get_text())
            if parsed:
                return parsed

        return None

    def _safe_parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string, defaulting unspecified year to current/next."""
        if not date_str:
            return None
        s = re.sub(r'\s+', ' ', date_str).strip()
        try:
            now = datetime.now()
            # Use today as default so missing year resolves sensibly
            dt = date_parser.parse(s, fuzzy=True, default=now)
            # If parsed date is more than 30 days in the past, assume next year
            if (now - dt).days > 30:
                try:
                    dt = dt.replace(year=dt.year + 1)
                except Exception:
                    pass
            return dt
        except Exception as e:
            self.log(f"Error parsing date '{date_str}': {e}")
            return None

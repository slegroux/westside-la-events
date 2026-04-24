"""
Scraper for Downtown Santa Monica events.
Source: https://downtownsm.com/events-calendar
"""
from datetime import datetime
from typing import List, Optional, Dict
import re

from .base import BaseScraper
from src.data.models import Event


class DowntownSMScraper(BaseScraper):
    """Scraper for Downtown Santa Monica events calendar."""

    def __init__(self):
        super().__init__('Downtown Santa Monica')
        self.base_url = 'https://downtownsm.com'
        self.events_url = f'{self.base_url}/events-calendar'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events = []

        html = self.fetch_page(self.events_url)
        if not html:
            self.log("Failed to fetch events page")
            return events

        soup = self.parse_html(html)

        # Collect (date, url) pairs from the calendar listing
        date_url_pairs = self._parse_calendar_listing(soup)
        self.log(f"Found {len(date_url_pairs)} event occurrences on calendar")

        # Prefetch all unique detail pages concurrently
        unique_urls = list({url for _, url in date_url_pairs})
        self.prefetch_pages(unique_urls)

        # Fetch and cache detail data per URL
        detail_cache: Dict[str, dict] = {}
        for url in unique_urls:
            detail = self._fetch_detail(url)
            if detail:
                detail_cache[url] = detail

        # Create one event per (date, url) occurrence
        seen = set()
        for event_date, url in date_url_pairs:
            detail = detail_cache.get(url)
            if not detail:
                continue
            key = (url, event_date.date() if event_date else None)
            if key in seen:
                continue
            seen.add(key)

            event = self._build_event(event_date, detail)
            if event:
                events.append(event)

        self.log(f"Successfully scraped {len(events)} events")
        return events

    def _parse_calendar_listing(self, soup) -> List[tuple]:
        """Extract (datetime, detail_url) pairs from the calendar page.

        The page renders each event as:
          <div class="item tc m 3 c_XXXXXXXX YYYYMMDD">
            <a href="/events-calendar/{id}/{slug}">  ← date card link
            ...
            <a class="link1 ..." href="/events-calendar/{id}/{slug}">View Event Details</a>
          </div>
        The YYYYMMDD class on the container is the authoritative date.
        """
        pairs = []
        seen = set()

        now = datetime.now()
        current_year = now.year
        current_month = now.month

        for item in soup.find_all('div', class_='item'):
            # Date is in .month and .day divs inside .ical
            month_div = item.find('div', class_='month')
            day_div = item.find('div', class_='day')
            if not month_div or not day_div:
                continue

            try:
                month = int(month_div.get_text(strip=True))
                day = int(day_div.get_text(strip=True))
            except ValueError:
                continue

            # Infer year: if month is before current month, it's next year
            year = current_year if month >= current_month else current_year + 1
            try:
                event_date = datetime(year, month, day, 12, 0)
            except ValueError:
                continue

            link = item.find('a', href=re.compile(r'/events-calendar/\d+/'))
            if not link:
                continue
            href = link['href']
            if not href.startswith('http'):
                href = self.base_url + href

            key = (href, event_date.date())
            if key not in seen:
                seen.add(key)
                pairs.append((event_date, href))

        return pairs

    def _fetch_detail(self, url: str) -> Optional[dict]:
        """Fetch and parse an event detail page."""
        html = self.fetch_page(url)
        if not html:
            return None

        soup = self.parse_html(html)

        # Title is in <title> as "Downtown Santa Monica | Event Title"
        title_tag = soup.find('title')
        if not title_tag:
            return None
        raw_title = title_tag.get_text(strip=True)
        if '|' in raw_title:
            title = self.clean_text(raw_title.split('|', 1)[1])
        else:
            title = self.clean_text(raw_title)
        if not title:
            return None

        page_text = soup.get_text(' ', strip=True)

        # Time: "6:00 pm – 9:00 pm" or "6:00pm - 9:00pm"
        time_match = re.search(
            r'(\d{1,2}:\d{2}\s*[ap]m)\s*[–\-]\s*(\d{1,2}:\d{2}\s*[ap]m)',
            page_text, re.IGNORECASE
        )
        start_time_str = time_match.group(1).strip() if time_match else None
        end_time_str = time_match.group(2).strip() if time_match else None

        # Fallback date from detail page: "Friday, September 13, 2024"
        detail_date = None
        date_match = re.search(
            r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'(January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+(\d{1,2}),?\s+(\d{4})',
            page_text, re.IGNORECASE
        )
        if date_match:
            try:
                detail_date = datetime.strptime(
                    f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}",
                    "%B %d %Y"
                )
            except ValueError:
                pass

        # Address: embedded in PHP data as 'address' => '<p>123 Main St</p> <p>City, CA</p>'
        # or appears in page text as "123 Main St Santa Monica"
        address = 'Santa Monica, CA'
        addr_match = re.search(
            r"'address'\s*=>\s*'(.*?)'",
            html, re.DOTALL
        )
        if addr_match:
            addr_html = addr_match.group(1)
            addr_text = re.sub(r'<[^>]+>', ' ', addr_html).strip()
            addr_text = re.sub(r'\s+', ' ', addr_text).strip()
            if addr_text:
                address = addr_text
        else:
            # Fallback: look for street address in page text
            addr_re = re.search(
                r'(\d{3,5}\s+\w[^,\n]{3,40}(?:Ave|St|Blvd|Dr|Rd|Way|Pl|Ct)\b[^,\n]*)',
                page_text
            )
            if addr_re:
                address = addr_re.group(1).strip()

        # Venue name: look for 'venue' in PHP data or use title's first venue hint
        venue_name = 'Downtown Santa Monica'
        venue_match = re.search(r"'venue'\s*=>\s*'([^']+)'", html)
        if venue_match:
            v = venue_match.group(1).strip()
            if v:
                venue_name = v

        # Description: meta description tag is usually clean
        description = ''
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = self.clean_text(meta_desc['content'])
        if not description:
            for p in soup.find_all('p'):
                text = self.clean_text(p.get_text())
                if len(text) > 60:
                    description = text
                    break

        # Image: look for og:image or a real src
        image_url = ''
        og_img = soup.find('meta', property='og:image')
        if og_img and og_img.get('content', '').startswith('http'):
            image_url = og_img['content']
        else:
            img = soup.find('img', src=re.compile(r'^https?://'))
            if img:
                image_url = img['src']

        return {
            'title': title,
            'start_time_str': start_time_str,
            'end_time_str': end_time_str,
            'detail_date': detail_date,
            'venue_name': venue_name,
            'address': address,
            'description': description,
            'image_url': image_url,
            'url': url,
        }

    def _parse_time(self, date: datetime, time_str: str) -> Optional[datetime]:
        """Apply a time string like '6:00 pm' to a date."""
        if not time_str:
            return None
        time_str = time_str.strip()
        for fmt in ('%I:%M %p', '%I:%M%p'):
            try:
                t = datetime.strptime(time_str.upper(), fmt)
                return date.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            except ValueError:
                continue
        return None

    def _build_event(self, calendar_date: Optional[datetime], detail: dict) -> Optional[Event]:
        """Create an Event from a calendar date and detail data."""
        event_date = calendar_date or detail.get('detail_date')
        if not event_date:
            return None

        # Apply time from detail page to the calendar date
        if detail.get('start_time_str'):
            timed = self._parse_time(event_date, detail['start_time_str'])
            if timed:
                event_date = timed

        end_date = None
        if detail.get('end_time_str'):
            timed = self._parse_time(event_date, detail['end_time_str'])
            if timed:
                end_date = timed

        category = classify_event_category(detail['title'], detail.get('description', ''))

        return self.create_event(
            title=detail['title'],
            description=detail.get('description', ''),
            venue_name=detail.get('venue_name', 'Downtown Santa Monica'),
            address=detail.get('address', 'Santa Monica, CA'),
            event_date=event_date,
            end_date=end_date,
            url=detail['url'],
            image_url=detail.get('image_url', ''),
            category=category,
            price=None,
            is_free=False,
            price_note='TBD',
        )


def classify_event_category(title: str, description: str) -> str:
    text = (title + ' ' + description).lower()
    if any(w in text for w in ('music', 'concert', 'jazz', 'band', 'dj', 'live music')):
        return 'Music'
    if any(w in text for w in ('art', 'gallery', 'exhibit', 'museum')):
        return 'Arts'
    if any(w in text for w in ('food', 'restaurant', 'tasting', 'wine', 'beer', 'farmers market', 'dining')):
        return 'Food & Drink'
    if any(w in text for w in ('film', 'movie', 'cinema', 'screening')):
        return 'Film'
    if any(w in text for w in ('comedy', 'stand-up', 'improv')):
        return 'Comedy'
    if any(w in text for w in ('theater', 'theatre', 'musical', 'play', 'performance')):
        return 'Theater'
    if any(w in text for w in ('yoga', 'fitness', 'run', 'sport', 'surf', 'dance')):
        return 'Sports & Fitness'
    if any(w in text for w in ('family', 'kids', 'children')):
        return 'Family'
    return 'Community'

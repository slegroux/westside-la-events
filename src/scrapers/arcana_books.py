"""
Scraper for Arcana: Books on the Arts events.
Source: https://www.arcanabooks.com/blog/?cat=events
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional, Set

from dateutil import parser as date_parser

from src.utils.dates import named_weekday, resolve_year
from .base import BaseScraper
from src.data.models import Event


class ArcanaBooksScraper(BaseScraper):
    """Scraper for Arcana Books event posts."""

    def __init__(self):
        super().__init__('Arcana Books')
        self.base_url = 'https://www.arcanabooks.com'
        self.events_url = f'{self.base_url}/blog/?cat=events'
        self.venue_name = 'Arcana: Books on the Arts'
        self.venue_address = '8675 Washington Blvd, Culver City, CA 90232'

    def scrape(self) -> List[Event]:
        """Scrape upcoming events from Arcana's events category."""
        self.log("Starting scrape...")
        events: List[Event] = []
        seen_urls: Set[str] = set()

        page_url = self.events_url
        max_pages = 6
        pages_scraped = 0

        while page_url and pages_scraped < max_pages:
            pages_scraped += 1
            self.log(f"Fetching page {pages_scraped}: {page_url}")
            html = self.fetch_page(page_url)
            if not html:
                break

            soup = self.parse_html(html)
            page_events = self._parse_listing_page(soup, seen_urls)
            events.extend(page_events)

            next_url = self._find_next_page_url(soup)
            if not next_url or next_url == page_url:
                break
            page_url = next_url

        self.log(f"Successfully scraped {len(events)} upcoming events")
        return events

    def _parse_listing_page(self, soup, seen_urls: Set[str]) -> List[Event]:
        """Parse events from one category page."""
        events: List[Event] = []

        # Arcana uses div.blog-item as the post container.
        post_nodes = soup.find_all('div', class_='blog-item')

        for node in post_nodes:
            # Title and URL are in h1.blog-title > a
            title_elem = node.find('h1', class_='blog-title')
            link_elem = title_elem.find('a', href=True) if title_elem else None
            if not link_elem:
                continue

            url = self.normalize_url(link_elem.get('href', ''), self.base_url)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = self.clean_text(link_elem.get_text())
            excerpt_elem = node.find('div', class_='blog-excerpt')
            summary = self.clean_text(excerpt_elem.get_text(' ', strip=True)) if excerpt_elem else ''
            event_date = self._extract_event_date(f"{title} {summary}")

            # Arcana's category contains many historical posts; keep only upcoming events.
            if not event_date:
                continue
            if event_date < (datetime.now() - timedelta(days=1)):
                continue

            img_elem = node.find('img', src=True)
            image_url = self.normalize_url(img_elem.get('src', ''), self.base_url) if img_elem else ''

            event = self.create_event(
                title=title,
                description=summary,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=url,
                image_url=image_url,
                category='Art',
                price_note='TBD'
            )
            if event:
                events.append(event)

        return events

    def _find_next_page_url(self, soup) -> Optional[str]:
        """Find pagination link for next page."""
        selectors = [
            {'rel': 'next'},
            {'class': re.compile(r'next', re.I)},
            {'aria-label': re.compile(r'next', re.I)},
        ]

        for attrs in selectors:
            next_link = soup.find('a', attrs=attrs, href=True)
            if next_link:
                return self.normalize_url(next_link['href'], self.base_url)

        # WordPress older posts style.
        older_link = soup.find('a', href=True, string=re.compile(r'older', re.I))
        if older_link:
            return self.normalize_url(older_link['href'], self.base_url)

        return None

    def _extract_event_date(self, text: str) -> Optional[datetime]:
        """Extract event datetime from post text."""
        if not text:
            return None

        cleaned = re.sub(r'(\d)(st|nd|rd|th)\b', r'\1', text, flags=re.I)
        cleaned = cleaned.replace(' at ', ' ')

        # Try explicit month/day/year(+time) patterns first.
        month_pattern = (
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)'
            r'\s+\d{1,2}(?:,\s*\d{4})?(?:,\s*|\s+)?(?:\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))?)'
        )
        match = re.search(month_pattern, cleaned, flags=re.I)
        candidate = match.group(1) if match else cleaned

        # Parse against a neutral default: dateutil fills missing fields from
        # `default`, and passing datetime.now() stamped every event with the
        # scrape's own clock time (and today's date when the text had none).
        neutral = datetime(datetime.now().year, 1, 1, 0, 0)
        try:
            parsed = date_parser.parse(candidate, fuzzy=True, default=neutral)
        except Exception:
            return None

        if re.search(r'\b20\d{2}\b', candidate):
            return parsed

        # No year in the text. Arcana's blog keeps years of past posts, and
        # bumping a stale one to next year resurrected it as a future event
        # ("Saturday 9/27" -- a 2025 Saturday -- became 2026, a Sunday). Use
        # the weekday the post names as a checksum instead.
        weekday = named_weekday(text)
        return resolve_year(
            parsed.month, parsed.day, weekday=weekday,
            hour=parsed.hour, minute=parsed.minute,
        )

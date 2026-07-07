"""
Scraper for Unlikely Collaborators "Spark Salons".
Source: https://www.salons.unlikelycollaborators.com/

Spark Salons are free, curated evening talks (consciousness, neuroscience,
psychology, the arts) held in person in Santa Monica — and simultaneously
streamed online. Each upcoming salon is a standalone Squarespace page linked
from the homepage (e.g. /spark-salon-andrew-holecek), with a consistent layout:

    <h1>  talk title
    <h2>  speaker
    text  "Thursday, June 4, 2026 | 7:00pm PT"
    ...   talk description, schedule, speaker bio

The in-person venue is not published on the site (it is only shown on the
Eventbrite registration page). All salons in the current series are held at
1520 2nd Street, Santa Monica, CA 90401, so the venue is hardcoded here and the
coordinates are passed straight through (no geocoding). Revisit VENUE_* if the
series relocates.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional

from .base import BaseScraper
from src.data.models import Event


class UnlikelyCollaboratorsScraper(BaseScraper):
    """Scraper for Unlikely Collaborators Spark Salons."""

    BASE_URL = 'https://www.salons.unlikelycollaborators.com'

    # Fixed in-person venue (from the Eventbrite listing; not shown on the site).
    VENUE_NAME = 'Unlikely Collaborators'
    VENUE_ADDRESS = '1520 2nd Street, Santa Monica, CA 90401'
    VENUE_LAT = 34.0129862
    VENUE_LNG = -118.4952006

    # Legacy format: "Thursday, June 4, 2026 | 7:00pm PT"
    # Current format: "Saturday, July 18, 2026 5:00 PM 6:00 PM"
    # (Squarespace now separates the date and start time with whitespace
    # instead of "|", uses a narrow no-break space before AM/PM, and appends
    # the end time immediately after with no separator.)
    _DATE_RE = re.compile(
        r'([A-Za-z]+day),\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})'
        r'[\s|]*(\d{1,2}):(\d{2})\s*([APap][Mm])',
    )

    def __init__(self):
        super().__init__('Unlikely Collaborators')

    def scrape(self) -> List[Event]:
        self.log("Starting scrape of Unlikely Collaborators Spark Salons...")
        events: List[Event] = []

        home = self.fetch_page(self.BASE_URL)
        if not home:
            self.log("Failed to fetch the salons homepage")
            return events

        # Upcoming salons are linked from the homepage as /home/<speaker-slug>
        # (the site previously used /spark-salon-<slug>, which it has since
        # dropped in favor of this shorter path). Exclude the "?format=ical"
        # calendar-download variants of the same links.
        slugs = sorted(set(re.findall(r'/home/[a-z0-9-]+', home)))
        urls = [self.BASE_URL + s for s in slugs]
        self.log(f"Found {len(urls)} candidate salon page(s)")
        if not urls:
            return events

        self.prefetch_pages(urls)

        for i, url in enumerate(urls, 1):
            try:
                event = self._parse_salon(url)
                if event:
                    events.append(event)
                    self.log(f"  [{i}/{len(urls)}] ✓ {event.title}")
            except Exception as e:
                self.log(f"  [{i}/{len(urls)}] ✗ error parsing {url}: {e}")

        self.log(f"Scraped {len(events)} upcoming salon(s)")
        return events

    def _parse_salon(self, url: str) -> Optional[Event]:
        html = self.fetch_page(url)
        if not html:
            return None
        soup = self.parse_html(html)

        # A date line is what distinguishes a real salon page from index/404 pages.
        event_date = self._parse_date(soup.get_text(' ', strip=True))
        if not event_date:
            return None

        # Drop past salons (the homepage occasionally still links recent ones).
        if event_date.date() < datetime.now().date():
            return None

        h1 = soup.find('h1')
        title = self.clean_text(h1.get_text(' ', strip=True)) if h1 else ''
        if not title:
            return None

        h2 = soup.find('h2')
        speaker = self.clean_text(h2.get_text(' ', strip=True)) if h2 else ''
        # Keep the speaker out of the title when the talk title already names them.
        if speaker and speaker.lower() not in title.lower():
            title = f"{title} — {speaker}"

        description = self._extract_description(soup)
        image_url = self._extract_image(soup)

        # Program runs ~7–9pm (6pm doors, 8pm book signing/reception).
        end_date = event_date + timedelta(hours=2)

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.VENUE_NAME,
            address=self.VENUE_ADDRESS,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            # Curated public idea-salons — a consistent category beats the
            # auto-classifier, which misfires on these abstract talk topics.
            category='Community',
            is_free=True,
            price_note='Registration required',
            latitude=self.VENUE_LAT,
            longitude=self.VENUE_LNG,
        )

    def _parse_date(self, text: str) -> Optional[datetime]:
        m = self._DATE_RE.search(text)
        if not m:
            return None
        _weekday, month, day, year, hour, minute, ampm = m.groups()
        try:
            return datetime.strptime(
                f"{month} {int(day)} {year} {hour}:{minute} {ampm.upper()}",
                "%B %d %Y %I:%M %p",
            )
        except ValueError:
            return None

    def _extract_description(self, soup) -> str:
        """First few substantial paragraphs (the talk description), cleaned."""
        skip = ('p.m.:', 'a.m.:', 'sign up', 'email address',
                'all rights reserved', 'privacy policy', 'terms of use',
                'complimentary', 'registration is required', 'registration now open')
        parts: List[str] = []
        for p in soup.find_all('p'):
            t = p.get_text(' ', strip=True)
            if len(t) < 50:
                continue
            low = t.lower()
            if any(k in low for k in skip):
                continue
            parts.append(t)
            if sum(len(x) for x in parts) > 700:
                break
        return self.clean_text(' '.join(parts))[:1000]

    def _extract_image(self, soup) -> str:
        tag = soup.find('meta', property='og:image')
        img = tag.get('content', '') if tag else ''
        # Squarespace sometimes emits a protocol-relative or http URL.
        if img.startswith('//'):
            img = 'https:' + img
        elif img.startswith('http://'):
            img = 'https://' + img[len('http://'):]
        return img

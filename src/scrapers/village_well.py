"""
Scraper for Village Well Books & Coffee events.
Source: https://villagewell.com/calendar

Village Well is a Culver City bookstore/cafe running on the Bookmanager
platform (a React SPA, store SAN 9916539). The calendar widget loads events
from Bookmanager's JSON API rather than rendering them server-side, so we call
that API directly:

  1. POST customer/session/get               -> mint a session_id
  2. POST customer/event/v2/list             -> events for a start/end date range

The list endpoint caps each response at ~100 rows, so we page through the
upcoming window in monthly chunks and merge by event id (the id encodes the
occurrence date, so each occurrence of a recurring class is distinct).
"""
import html as _html
import re
from datetime import datetime, date, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class VillageWellScraper(BaseScraper):
    """Scraper for Village Well Books & Coffee events."""

    API_BASE = 'https://api.bookmanager.com/customer'
    STORE_ID = '353209'
    SAN = '9916539'

    def __init__(self):
        super().__init__('Village Well Books & Coffee')
        self.base_url = 'https://villagewell.com'
        self.calendar_url = f'{self.base_url}/calendar'
        self.venue_name = 'Village Well Books & Coffee'
        # No unit number — '#1B' makes the geocoder return no result.
        self.venue_address = '9900 Culver Blvd, Culver City, CA 90232'
        # Bookmanager rejects requests without a matching Origin/Referer.
        self._api_headers = {
            'Origin': self.base_url,
            'Referer': f'{self.base_url}/',
            'Accept': 'application/json',
        }

    def scrape(self) -> List[Event]:
        """Scrape upcoming events from the Bookmanager events API."""
        self.log("Starting scrape...")
        events = []

        try:
            session_id = self._get_session_id()
            if not session_id:
                self.log("Could not establish a Bookmanager session, aborting")
                return events

            # Page through the next ~90 days in <=30-day windows to stay under
            # the API's ~100-row response cap, de-duplicating by occurrence id.
            seen_ids = set()
            today = date.today()
            for offset in (0, 30, 60):
                start = today + timedelta(days=offset)
                end = today + timedelta(days=offset + 29)
                rows = self._fetch_events(session_id, start, end)
                self.log(f"Window {start:%Y-%m-%d}..{end:%Y-%m-%d}: {len(rows)} rows")
                for row in rows:
                    rid = row.get('id')
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    try:
                        event = self._parse_event(row)
                        if event:
                            events.append(event)
                    except Exception as e:
                        self.log(f"Error parsing event {rid}: {e}")

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _get_session_id(self) -> Optional[str]:
        """Mint an anonymous Bookmanager session."""
        resp = self.session.post(
            f'{self.API_BASE}/session/get',
            data={'session_id': '', 'store_id': self.STORE_ID, 'uuid': '', 'log_url': '/'},
            headers=self._api_headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get('session_id')

    def _fetch_events(self, session_id: str, start: date, end: date) -> List[dict]:
        """Fetch event rows for a date range from customer/event/v2/list."""
        # Multipart form fields, mirroring the calendar widget's own request.
        form = {
            'uuid': (None, ''),
            'session_id': (None, session_id),
            'log_url': (None, '/calendar'),
            'store_id': (None, self.STORE_ID),
            'start_date': (None, start.strftime('%Y%m%d')),
            'end_date': (None, end.strftime('%Y%m%d')),
            'calendar_mode': (None, 'true'),
            'categories': (None, '[]'),
        }
        resp = self.session.post(
            f'{self.API_BASE}/event/v2/list?_cb={self.SAN}',
            files=form,
            headers=self._api_headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get('rows', []) if isinstance(data, dict) else []

    def _parse_event(self, row: dict) -> Optional[Event]:
        title = (row.get('title') or '').strip()
        date_str = row.get('date')  # YYYYMMDD
        if not title or not date_str:
            return None

        event_date = self._combine(date_str, row.get('start_time'), row.get('all_day'))
        if not event_date:
            return None

        # Skip occurrences that already happened (recurring classes emit one
        # row per day, including past dates within the requested window).
        if event_date.date() < date.today():
            return None

        end_date = self._combine(
            row.get('end_date') or date_str, row.get('end_time'), row.get('all_day')
        )

        description = self._clean_html(row.get('description') or row.get('summary') or '')

        # location_text is an in-venue room label ("Studio", etc.), not a street
        # address — fold it into the description and always geocode the venue.
        location_text = (row.get('location_text') or '').strip()
        if location_text:
            description = f'Location: {location_text}. {description}'.strip()

        image_url = row.get('image_url') or ''

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=end_date,
            # No server-rendered detail page exists; a fragment keeps each
            # occurrence's URL unique so duplicate detection won't merge
            # different same-day events that would otherwise share /calendar.
            url=f'{self.calendar_url}#event-{row.get("id")}',
            image_url=image_url,
            category=self._categorize(row, title),
            price_note='TBD',
        )

    @staticmethod
    def _combine(date_str: str, time_str: Optional[str], all_day) -> Optional[datetime]:
        """Combine a YYYYMMDD date with an optional HH:MM:SS time (LA-local)."""
        if not date_str:
            return None
        try:
            if time_str and not all_day:
                return datetime.strptime(f'{date_str} {time_str}', '%Y%m%d %H:%M:%S')
            return datetime.strptime(date_str, '%Y%m%d')
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _clean_html(raw: str) -> str:
        if not raw:
            return ''
        text = BeautifulSoup(raw, 'html.parser').get_text(' ')
        return _html.unescape(re.sub(r'\s+', ' ', text)).strip()

    @staticmethod
    def _categorize(row: dict, title: str) -> str:
        """Map the Bookmanager category onto a site category."""
        cat = row.get('category') or {}
        name = (cat.get('name') if isinstance(cat, dict) else str(cat)) or ''
        haystack = f'{name} {title}'.lower()
        if any(w in haystack for w in ('kid', 'storytime', 'family', 'teen')):
            return 'Family'
        if 'comedy' in haystack:
            return 'Comedy'
        if any(w in haystack for w in ('music', 'concert', 'open mic', 'jazz')):
            return 'Music'
        if any(w in haystack for w in ('writ', 'workshop', 'class', 'seminar', 'craft')):
            return 'Education'
        # Author talks, book launches, signings, readings -> community programming.
        return 'Community'

"""
Scraper for IO Music Academy LA (Resident Advisor club #282834).
Source: https://ra.co/clubs/282834

IO Music Academy's LA campus (Hollywood) runs free DJ and music-production
workshops, listed on Resident Advisor. RA's website is Cloudflare-protected
(plain requests / headless browsers are blocked), but its GraphQL API at
https://ra.co/graphql is reachable, so we query the venue's events directly.

The venue is in Hollywood — outside the Westside coverage box — and is included
by the site owner's explicit choice via WESTSIDE_VENUE_ALLOWLIST in
src/utils/geo_filter.py, which lets these events bypass the geo filter.
"""
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event

RA_GRAPHQL_URL = "https://ra.co/graphql"

# Venue + its events. `events` requires a non-null EventQueryType; LATEST returns
# recent + upcoming listings (we drop anything before today).
_VENUE_EVENTS_QUERY = """
query GET_VENUE_EVENTS($id: ID!, $type: EventQueryType!, $limit: Int) {
  venue(id: $id) {
    id
    name
    address
    location { latitude longitude }
    events(type: $type, limit: $limit) {
      id
      title
      date
      startTime
      endTime
      cost
      content
      contentUrl
      flyerFront
      artists { name }
    }
  }
}
"""

_TAG_RE = re.compile(r"<[^>]+>")


class IOMusicAcademyScraper(BaseScraper):
    """Scraper for IO Music Academy LA events via the Resident Advisor API."""

    CLUB_ID = "282834"

    def __init__(self):
        super().__init__("IO Music Academy LA")
        self.base_url = "https://ra.co"
        self.club_url = f"{self.base_url}/clubs/{self.CLUB_ID}"

    def _headers(self) -> dict:
        # RA's GraphQL gateway expects browser-like headers + a content-language.
        return {
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": self.club_url,
            "ra-content-language": "en",
            "Accept": "*/*",
        }

    def scrape(self) -> List[Event]:
        self.log("Starting scrape...")
        events: List[Event] = []

        payload = {
            "operationName": "GET_VENUE_EVENTS",
            "query": _VENUE_EVENTS_QUERY,
            "variables": {"id": self.CLUB_ID, "type": "LATEST", "limit": 50},
        }
        data = self.fetch_json(RA_GRAPHQL_URL, json_body=payload, headers=self._headers())
        if not data:
            self.log("No response from RA GraphQL")
            return events

        venue = ((data.get("data") or {}).get("venue")) or {}
        if not venue:
            self.log(f"No venue data for club {self.CLUB_ID}")
            return events

        venue_name = venue.get("name") or "IO Music Academy LA"
        address = self._format_address(venue.get("address"))
        loc = venue.get("location") or {}
        latitude = loc.get("latitude")
        longitude = loc.get("longitude")

        raw_events = venue.get("events") or []
        self.log(f"Found {len(raw_events)} listings for {venue_name}")

        today = date.today()
        for raw in raw_events:
            try:
                event = self._parse_event(
                    raw, venue_name, address, latitude, longitude, today
                )
                if event:
                    events.append(event)
            except Exception as e:
                self.log(f"Error parsing event {raw.get('id')}: {e}")

        self.log(f"Successfully scraped {len(events)} upcoming events")
        return events

    def _format_address(self, street: Optional[str]) -> str:
        street = (street or "").strip()
        if not street:
            return "Los Angeles, CA"
        if "los angeles" not in street.lower() and ", ca" not in street.lower():
            return f"{street}, Los Angeles, CA"
        return street

    def _parse_event(self, raw: dict, venue_name: str, address: str,
                     latitude, longitude, today: date) -> Optional[Event]:
        title = (raw.get("title") or "").strip()
        if not title:
            return None

        # Prefer the precise startTime; fall back to the date-only field.
        start_raw = raw.get("startTime") or raw.get("date")
        event_date = self._parse_dt(start_raw)
        if not event_date:
            return None

        # Drop past events — LATEST includes recent history.
        if event_date.date() < today:
            return None

        end_date = self._parse_dt(raw.get("endTime"))
        # Guard against RA listings with an implausible end (e.g. a 3-hour
        # workshop tagged as ending the next day) that would otherwise render
        # as a multi-day event. Normal crossing-midnight nights (<14h) are kept.
        if end_date and (end_date <= event_date or (end_date - event_date) > timedelta(hours=14)):
            end_date = None

        content_url = raw.get("contentUrl") or ""
        url = f"{self.base_url}{content_url}" if content_url.startswith("/") else content_url

        # RA "content" may carry HTML; reduce to plain text.
        description = _TAG_RE.sub(" ", raw.get("content") or "").strip()
        artists = ", ".join(a.get("name", "") for a in (raw.get("artists") or []) if a.get("name"))
        if artists and artists.lower() not in description.lower():
            description = f"Lineup: {artists}. {description}".strip()

        image_url = raw.get("flyerFront") or ""

        # cost is a string like "0" / "25" / "" — treat 0/blank as free.
        cost = (raw.get("cost") or "").strip()
        is_free = cost in ("", "0", "0.0", "0.00") or cost.lower() == "free"
        price = None
        if not is_free:
            m = re.search(r"\d+(?:\.\d{1,2})?", cost)
            if m:
                price = float(m.group(0))

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            category="Education",   # free DJ / music-production workshops
            price=price,
            is_free=is_free,
            latitude=latitude,
            longitude=longitude,
        )

    def _parse_dt(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = date_parser.parse(value)
            # RA returns naive local times; strip any tz to match the app's
            # naive-LA-local convention (see scrapers/base.normalize_event_datetime).
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            return None

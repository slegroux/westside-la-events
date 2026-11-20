"""
Scraper for Alliance Française de Los Angeles events.
Source: https://www.afdela.org/calendar.ics (linked from https://www.afdela.org/events)

The site was rebuilt (Next.js) and the per-page schema.org Event JSON-LD the old
scraper read is gone from the listing. The site publishes an iCalendar feed for
its calendar ("Add this calendar to your phone"), which carries every event with
an exact local start/end, location and event-page URL, so we read that.

The feed mixes cultural events (URL under ``/events/``) with language classes
(URL on the school's registration system, recurring weekly). Only the cultural
events are wanted here. A recurring ``/events/`` entry (e.g. an 8-week talk
series) yields only its next occurrence, as the site's own "Upcoming events"
list does. Event flyers are taken from the ``/events`` listing page.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from dateutil import rrule

from .base import BaseScraper
from src.data.models import Event

LA_TZ = ZoneInfo('America/Los_Angeles')


class AFdelaScraper(BaseScraper):
    """Scraper for Alliance Française de Los Angeles events."""

    HOME_VENUE = 'Alliance Française de Los Angeles'
    HOME_ADDRESS = '10390 Santa Monica Blvd, Suite 300, Los Angeles, CA 90025'
    HOME_LAT = 34.0573375
    HOME_LNG = -118.423581

    def __init__(self):
        super().__init__('AFdela')
        self.base_url = 'https://www.afdela.org'
        self.events_url = f'{self.base_url}/events'
        self.calendar_url = f'{self.base_url}/calendar.ics'

    def scrape(self) -> List[Event]:
        """
        Scrape upcoming cultural events from the AFdela iCalendar feed.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events: List[Event] = []

        try:
            ics = self.fetch_page(self.calendar_url)
            if not ics:
                self.log("Failed to fetch calendar feed")
                return events

            components = self._parse_ics(ics)
            self.log(f"Found {len(components)} calendar entries")

            now = datetime.now()
            images = None  # loaded lazily, only if there is an event to enrich
            for comp in components:
                url = comp.get('URL', '')
                if not url.startswith(f'{self.base_url}/events/'):
                    continue  # language classes etc.

                start, end = self._next_occurrence(comp, now)
                if not start:
                    continue

                location = self._unescape(comp.get('LOCATION', ''))
                if location.strip().lower() in ('online', 'zoom'):
                    self.log(f"Skipping online event: {comp.get('SUMMARY')}")
                    continue

                if images is None:
                    images = self._listing_images()
                event = self._build_event(comp, url, location, start, end, images.get(url, ''))
                if event:
                    events.append(event)

            events.sort(key=lambda e: e.event_date)
            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    # -- ICS parsing --------------------------------------------------------

    @staticmethod
    def _parse_ics(text: str) -> List[Dict[str, str]]:
        """Parse VEVENT blocks into {property: raw value} dicts.

        ICS wraps long lines onto continuation lines starting with a space, so
        the text is unfolded first. Parameters stay attached to the key
        (``DTSTART;TZID=...``) and are looked up by prefix.
        """
        unfolded = text.replace('\r\n', '\n').replace('\n ', '').replace('\n\t', '')
        components = []
        for block in re.findall(r'BEGIN:VEVENT\n(.*?)END:VEVENT', unfolded, re.S):
            comp = {}
            for line in block.split('\n'):
                name, sep, value = line.partition(':')
                if sep:
                    key = name.strip()
                    # A series can list its exclusions on several EXDATE lines.
                    if key.startswith('EXDATE') and key in comp:
                        comp[key] += ',' + value.strip()
                    else:
                        comp[key] = value.strip()
            if comp:
                components.append(comp)
        return components

    @staticmethod
    def _get(comp: Dict[str, str], prop: str) -> Optional[str]:
        for key, value in comp.items():
            if key == prop or key.startswith(f'{prop};'):
                return value
        return None

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        """Parse an ICS date/date-time (feed times are America/Los_Angeles)."""
        if not value:
            return None
        raw = value.strip()
        try:
            if raw.endswith('Z'):
                return (datetime.strptime(raw, '%Y%m%dT%H%M%SZ')
                        .replace(tzinfo=ZoneInfo('UTC')).astimezone(LA_TZ).replace(tzinfo=None))
            if 'T' in raw:
                return datetime.strptime(raw, '%Y%m%dT%H%M%S')
            return datetime.strptime(raw, '%Y%m%d')
        except ValueError:
            return None

    def _exdates(self, comp: Dict[str, str], start: datetime) -> List[datetime]:
        """Occurrence starts the feed excludes from a recurring entry.

        Every time in the feed is America/Los_Angeles (all 108 TZID params are),
        and DTSTART is read that way too, so a TZID on EXDATE is not converted;
        revisit both together if the feed ever mixes zones. A date-only EXDATE
        excludes the occurrence on that day.
        """
        found = []
        for key, value in comp.items():
            if key != 'EXDATE' and not key.startswith('EXDATE;'):
                continue
            for raw in value.split(','):
                moment = self._parse_dt(raw)
                if not moment:
                    continue
                if 'T' not in raw:
                    moment = datetime.combine(moment.date(), start.time())
                found.append(moment)
        return found

    def _next_occurrence(self, comp: Dict[str, str], now: datetime):
        """Return (start, end) of the first occurrence not yet over, or (None, None)."""
        start = self._parse_dt(self._get(comp, 'DTSTART'))
        if not start:
            self.log(f"Skipping '{comp.get('SUMMARY')}': no DTSTART")
            return None, None
        end = self._parse_dt(self._get(comp, 'DTEND'))
        duration = (end - start) if end and end > start else None

        rule = comp.get('RRULE')
        if rule:
            try:
                rr = rrule.rrulestr(rule, dtstart=start.replace(tzinfo=LA_TZ), forceset=True)
                for skipped in self._exdates(comp, start):
                    rr.exdate(skipped.replace(tzinfo=LA_TZ))
                # An occurrence that started before `now` is still upcoming
                # until its end, so look back by one duration.
                cutoff = (now - (duration or timedelta(0))).replace(tzinfo=LA_TZ)
                nxt = rr.after(cutoff, inc=True)
            except (ValueError, TypeError) as e:
                self.log(f"Bad RRULE for '{comp.get('SUMMARY')}': {e}")
                return None, None
            if not nxt:
                return None, None
            start = nxt.replace(tzinfo=None)
            end = start + duration if duration else None

        if (end or start) < now:
            return None, None
        return start, end

    @staticmethod
    def _unescape(value: str) -> str:
        return (value.replace('\\n', '\n').replace('\\,', ',')
                .replace('\\;', ';').replace('\\\\', '\\').strip())

    # -- Event construction -------------------------------------------------

    def _build_event(self, comp, url, location, start, end, image_url) -> Optional[Event]:
        title = self.clean_text(self._unescape(comp.get('SUMMARY', '')))
        if not title:
            return None

        # DESCRIPTION is "<blurb>\n<human date line>\n<event url>"; keep the blurb.
        lines = [l.strip() for l in self._unescape(comp.get('DESCRIPTION', '')).split('\n')
                 if l.strip() and not l.strip().startswith('http')]
        if len(lines) > 1:
            lines = lines[:-1]
        description = self.clean_text(' '.join(lines))

        at_home = not location or location.lower().startswith(self.HOME_VENUE.lower())
        kwargs = {}
        if at_home:
            venue, address = self.HOME_VENUE, self.HOME_ADDRESS
            kwargs = {'latitude': self.HOME_LAT, 'longitude': self.HOME_LNG}
        else:
            # "Hammer Museum, Grunwald Center": the venue is the first segment.
            venue, address = location.split(',')[0].strip(), ''

        return self.create_event(
            title=title,
            description=description,
            venue_name=venue,
            address=address,
            event_date=start,
            end_date=end,
            url=url,
            image_url=image_url,
            **kwargs,
        )

    def _listing_images(self) -> Dict[str, str]:
        """Map event-page URL -> flyer image from the /events listing cards."""
        images: Dict[str, str] = {}
        html = self.fetch_page(self.events_url)
        if not html:
            return images
        for article in self.parse_html(html).find_all('article'):
            link = article.find('a', href=re.compile(r'^/events/[^.]+$'))
            img = article.find('img', src=True)
            if link and img:
                images[self.normalize_url(link['href'], self.base_url)] = \
                    self.normalize_url(img['src'], self.base_url)
        return images

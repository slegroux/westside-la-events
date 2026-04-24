"""
Scraper for Santa Monica Daily Press events.
Source: https://www.smdp.com/events/ (RSS feed)
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


RSS_NAMESPACES = {
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'media': 'http://search.yahoo.com/mrss/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}

# Patterns to find an event date mentioned in article body
_DATE_PATTERNS = [
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Z][a-z]+ \d{1,2}(?:,?\s+\d{4})?)',
    r'([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
    r'([A-Z][a-z]+ \d{1,2}(?:st|nd|rd|th)?)',
]

# "at The Broad Stage" / "at 1234 Main St"
_AT_VENUE_PATTERN = re.compile(
    r'\bat\s+([A-Z][^\.,\n]{3,50})(?:[,.]|\s+in\s+|\s+on\s+|$)', re.MULTILINE
)
# Require Title-Case street name to avoid matching phrases like "150 visual artists"
_ADDRESS_PATTERN = re.compile(
    r'\b(\d{3,5}\s+(?:[A-Z][a-zA-Z]+\s+){1,4}(?:Blvd|Ave|St|Dr|Rd|Way|Lane|Ln|Place|Pl)\.?'
    r'(?:,\s*[A-Za-z\s]+,\s*CA(?:\s*\d{5})?)?)'
)


class SMDPScraper(BaseScraper):
    """Scraper for Santa Monica Daily Press events via RSS feed."""

    def __init__(self):
        super().__init__('Santa Monica Daily Press')
        self.base_url = 'https://www.smdp.com'
        self.feed_url = f'{self.base_url}/events/feed/'

    def scrape(self) -> List[Event]:
        self.log("Starting scrape via RSS feed...")
        events = []

        try:
            xml_content = self.fetch_page(self.feed_url)
            if not xml_content:
                self.log("Failed to fetch RSS feed")
                return events

            root = ET.fromstring(xml_content)
            channel = root.find('channel')
            if channel is None:
                self.log("No channel element in RSS feed")
                return events

            items = channel.findall('item')
            self.log(f"Found {len(items)} items in feed")

            for item in items:
                try:
                    event = self._parse_item(item)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.log(f"Error parsing item: {e}")

            self.log(f"Successfully scraped {len(events)} events")

        except ET.ParseError as e:
            self.log(f"XML parse error: {e}")
        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_item(self, item: ET.Element) -> Optional[Event]:
        title = self._text(item, 'title')
        if not title:
            return None

        url = self._text(item, 'link') or ''
        pub_date_str = self._text(item, 'pubDate') or ''
        description = self._strip_html(self._text(item, 'description') or '')

        # Full article HTML for richer extraction
        content_html = self._text(item, 'content:encoded', RSS_NAMESPACES) or ''
        content_text = self._strip_html(content_html)

        # Image from media:content
        image_url = ''
        media_elem = item.find('media:content', RSS_NAMESPACES)
        if media_elem is not None:
            image_url = media_elem.get('url', '')

        # --- Date ---
        event_date = self._extract_date(content_text, pub_date_str)

        # --- Venue / Address ---
        venue_name, address = self._extract_location(content_text)
        if not address:
            address = 'Santa Monica, CA'

        # --- Price ---
        is_free, price, price_note = self._extract_price(content_text)

        return self.create_event(
            title=title,
            description=description or content_text[:400],
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            url=url,
            image_url=image_url,
            is_free=is_free,
            price=price,
            price_note=price_note,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _text(self, elem: ET.Element, tag: str, ns: dict = None) -> Optional[str]:
        if ns:
            prefix, local = tag.split(':', 1)
            child = elem.find(f'{{{ns[prefix]}}}{local}')
        else:
            child = elem.find(tag)
        return child.text if child is not None else None

    def _strip_html(self, html: str) -> str:
        if not html:
            return ''
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_date(self, content_text: str, pub_date_str: str) -> Optional[datetime]:
        # Determine fallback year from pubDate (better than always using current year)
        fallback_year = datetime.now().year
        if pub_date_str:
            try:
                fallback_year = date_parser.parse(pub_date_str).year
            except Exception:
                pass

        # Try to find an explicit date in the article body
        for pattern in _DATE_PATTERNS:
            m = re.search(pattern, content_text)
            if m:
                date_candidate = m.group(1).strip().rstrip('stndrh')
                # Append pubDate's year if no year in the matched string
                if not re.search(r'\d{4}', date_candidate):
                    date_candidate += f' {fallback_year}'
                # Look for time within 60 chars after the match
                time_match = re.search(
                    r'(\d{1,2}(?::\d{2})?\s*[AP]M)',
                    content_text[m.end():m.end() + 80],
                    re.IGNORECASE
                )
                if time_match:
                    date_candidate += ' ' + time_match.group(1)
                try:
                    parsed = date_parser.parse(date_candidate, fuzzy=True)
                    # Sanity check: reject dates more than 1 year old or 2 years out
                    now = datetime.now()
                    if (now - parsed.replace(tzinfo=None)).days < 365 * 2 and \
                       (parsed.replace(tzinfo=None) - now).days < 365 * 2:
                        return parsed
                except Exception:
                    pass

        # Fall back to RSS pubDate
        if pub_date_str:
            try:
                return date_parser.parse(pub_date_str)
            except Exception:
                pass

        return None

    def _extract_location(self, content_text: str):
        venue_name = ''
        address = ''

        # Try to find a street address first
        addr_match = _ADDRESS_PATTERN.search(content_text)
        if addr_match:
            address = addr_match.group(0).strip()
            if not address.lower().endswith(', ca') and 'santa monica' not in address.lower():
                address += ', Santa Monica, CA'

        # Try "at <Venue>" pattern
        _SKIP_VENUE = {'the event', 'the end', 'the same', 'a time', 'least', 'most', 'first', 'last'}
        _VERB_RE = re.compile(r'\b(?:has|have|had|is|are|was|were|will|would|could|should|created|held|said|told)\b')
        for m in _AT_VENUE_PATTERN.finditer(content_text):
            candidate = m.group(1).strip()
            if any(skip in candidate.lower() for skip in _SKIP_VENUE):
                continue
            if _VERB_RE.search(candidate):
                continue
            if len(candidate) < 5:
                continue
            venue_name = candidate
            break

        return venue_name, address

    def _extract_price(self, content_text: str):
        text_lower = content_text.lower()
        is_free = bool(re.search(r'\b(?:free admission|free entry|free event|admission free|no cost|free to attend)\b', text_lower))
        price = None
        price_note = 'TBD'

        if not is_free:
            price_match = re.search(r'\$(\d+(?:\.\d{2})?)', content_text)
            if price_match:
                try:
                    price = float(price_match.group(1))
                    price_note = f'${price_match.group(1)}'
                except ValueError:
                    pass

        if is_free:
            price_note = 'Free'

        return is_free, price, price_note

"""
Scraper for The Venice West venue events.
Source: https://www.thevenicewest.com/calendar

Note: Tixr event pages use DataDome anti-bot protection which prevents automated
price extraction. Automatic Tixr scraping is DISABLED. Manual price overrides
must be added to venice_west_pricing.json for Tixr events.
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import json
import os

from .base import BaseScraper
from src.data.models import Event


class VeniceWestScraper(BaseScraper):
    """Scraper for The Venice West events."""

    def __init__(self):
        super().__init__('The Venice West')
        self.base_url = 'https://www.thevenicewest.com'
        self.calendar_url = f'{self.base_url}/calendar'
        self.venue_name = 'The Venice West'
        self.venue_address = '1910 Lincoln Blvd, Venice, CA 90291'

        # Load pricing overrides
        self.pricing_overrides = self._load_pricing_overrides()

    def _load_pricing_overrides(self) -> dict:
        """Load manual pricing overrides from JSON file."""
        pricing_file = os.path.join(
            os.path.dirname(__file__),
            'venice_west_pricing.json'
        )
        try:
            if os.path.exists(pricing_file):
                with open(pricing_file, 'r') as f:
                    data = json.load(f)
                    return data.get('pricing_overrides', {})
        except Exception as e:
            self.log(f"Error loading pricing overrides: {e}")
        return {}

    def scrape(self) -> List[Event]:
        """
        Scrape events from The Venice West calendar.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the calendar page
            html = self.fetch_page(self.calendar_url)
            if not html:
                self.log("Failed to fetch calendar page")
                return events

            soup = self.parse_html(html)

            # Find all event items (Webflow dynamic items)
            event_items = soup.find_all('div', class_='cal-info-2 w-dyn-item')
            self.log(f"Found {len(event_items)} events on calendar page")

            for i, item in enumerate(event_items, 1):
                try:
                    event = self._parse_event(item)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_items)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_event(self, item) -> Event:
        """
        Parse a single event from a calendar item.

        Args:
            item: BeautifulSoup element containing event data

        Returns:
            Event object
        """
        # Extract title from the b-show div
        title_elem = item.find('div', class_='b-show')
        title = self.clean_text(title_elem.get_text()) if title_elem else 'Untitled Event'

        # Extract date/time from the dates div
        date_elem = item.find('p', class_='b-venue')
        event_date = None
        if date_elem:
            date_text = self.clean_text(date_elem.get_text())
            try:
                # Parse date like "Nov 14, 2025 8:00 PM"
                event_date = date_parser.parse(date_text)
            except Exception as e:
                self.log(f"Could not parse date '{date_text}': {e}")

        # Extract event URL from the background link or buy tickets link
        event_url = self.calendar_url  # Default to calendar
        link_elem = item.find('a', href=True)
        if link_elem:
            href = link_elem.get('href', '')
            if 'tixr.com' in href:
                event_url = href
            else:
                event_url = self.normalize_url(href, self.base_url)

        # Extract image URL from style attribute of cal-container
        image_url = ''
        container = item.find('a', class_='cal-container')
        if container:
            style = container.get('style', '')
            # Extract URL from background-image:url("...")
            if 'background-image:url(' in style:
                start = style.find('url(') + 4
                end = style.find(')', start)
                image_url = style[start:end].strip('"').strip("'")
                # Normalize relative URLs
                if image_url and not image_url.startswith('http'):
                    image_url = self.normalize_url(image_url, self.base_url)

        # Extract categories/tags from filter elements
        category_tags = []
        area_filters = item.find_all('p', class_='areas filter')
        for area in area_filters:
            tag = self.clean_text(area.get_text())
            if tag:
                category_tags.append(tag)

        # Determine category from tags or title
        category = self._determine_category(category_tags, title)

        # Check if it's a free event (RSVP button visible)
        is_free = False
        price = None
        price_note = ""
        rsvp_button = item.find('a', class_='button short')
        buy_button = item.find('a', class_='button short white')

        # If RSVP button exists and is not invisible, it's free
        if rsvp_button and 'w-condition-invisible' not in rsvp_button.get('class', []):
            is_free = True
        elif buy_button:
            # Try to extract price from buy button text
            button_text = self.clean_text(buy_button.get_text())
            import re
            price_match = re.search(r'\$(\d+(?:\.\d{2})?)', button_text)
            if price_match:
                try:
                    price = float(price_match.group(1))
                except ValueError:
                    pass

        # If we have a Tixr URL and no price yet, check manual override only
        # Note: Tixr extraction is disabled due to DataDome anti-bot protection
        if not price and 'tixr.com' in event_url:
                # Extract event ID from URL (handle both short /e/ and long /events/ formats)
                import re
                event_id_match = re.search(r'/(?:events?|e)/([^/?\s]+)', event_url)
                if event_id_match:
                    event_id = event_id_match.group(1)

                    # Check for manual pricing override
                    if event_id in self.pricing_overrides:
                        override = self.pricing_overrides[event_id]
                        price = override.get('min_price')
                        price_note = "Manually verified pricing"
                        self.log(f"Using manual pricing override: ${price}")
                    else:
                        # Tixr extraction is disabled due to anti-bot protection
                        # Set a clear price note for the user
                        price_note = "Check website for pricing"
                        self.log(f"Tixr URL detected - manual pricing override needed for event ID: {event_id}")

        # Build description from available info
        description_parts = []

        # Add event type and title
        if category_tags:
            primary_tag = category_tags[0].title()
            description_parts.append(f"{primary_tag} event featuring {title}")
        else:
            description_parts.append(f"Live event featuring {title}")

        # Add venue info
        description_parts.append(f"at {self.venue_name} in Venice Beach")

        # Add date info if available
        if event_date:
            date_str = event_date.strftime("%A, %B %d at %I:%M %p")
            description_parts.append(f"on {date_str}")

        # Add pricing info to description (only if free or has price)
        if is_free:
            description_parts.append("Free event with RSVP")
        elif price:
            description_parts.append(f"Tickets from ${price:.2f}")

        # Add all tags if multiple
        if len(category_tags) > 1:
            description_parts.append(f"Tags: {', '.join(category_tags)}")

        description = ". ".join(description_parts) + "."

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=event_date,
            end_date=None,
            url=event_url,
            image_url=image_url,
            category=category,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

    def _extract_tixr_pricing(self, tixr_url: str) -> dict:
        """
        Extract pricing information from a Tixr event page.

        Args:
            tixr_url: URL of the Tixr event page

        Returns:
            Dictionary with 'min_price', 'max_price', and 'price_tiers' keys
        """
        import re

        try:
            # Attempt to fetch the Tixr page with JavaScript rendering
            html = self.fetch_page_js(tixr_url, timeout=45000)
            if not html:
                self.log(f"Failed to fetch Tixr page: {tixr_url}")
                return {'min_price': None, 'max_price': None, 'price_tiers': []}

            soup = self.parse_html(html)

            # Look for pricing information in various possible formats
            price_tiers = []

            # Method 1: Find all dollar amounts in the page
            dollar_texts = soup.find_all(string=re.compile(r'\$\s*\d+'))
            prices_found = set()

            for text in dollar_texts:
                # Extract dollar amounts
                matches = re.findall(r'\$\s*(\d+(?:\.\d{2})?)', text)
                for match in matches:
                    try:
                        price = float(match)
                        # Filter out unrealistic prices (likely not ticket prices)
                        if 5 <= price <= 500:
                            prices_found.add(price)
                            # Try to find the tier name near this price
                            parent = text.parent
                            context = parent.get_text(strip=True) if parent else text
                            price_tiers.append({
                                'name': context[:50] if len(context) < 100 else 'General Admission',
                                'price': price
                            })
                    except ValueError:
                        pass

            # Method 2: Look for common ticket-related elements
            ticket_elements = soup.find_all(class_=re.compile(r'(ticket|price|tier|admission)', re.I))
            for elem in ticket_elements:
                text = elem.get_text()
                matches = re.findall(r'\$\s*(\d+(?:\.\d{2})?)', text)
                for match in matches:
                    try:
                        price = float(match)
                        if 5 <= price <= 500:
                            prices_found.add(price)
                    except ValueError:
                        pass

            # Calculate min and max prices
            if prices_found:
                min_price = min(prices_found)
                max_price = max(prices_found)

                # Remove duplicate prices from tiers
                unique_tiers = {}
                for tier in price_tiers:
                    if tier['price'] not in unique_tiers:
                        unique_tiers[tier['price']] = tier
                price_tiers = list(unique_tiers.values())

                self.log(f"Found pricing: ${min_price} - ${max_price} with {len(price_tiers)} tiers")
                return {
                    'min_price': min_price,
                    'max_price': max_price,
                    'price_tiers': price_tiers
                }
            else:
                self.log(f"No pricing found on Tixr page: {tixr_url}")
                return {'min_price': None, 'max_price': None, 'price_tiers': []}

        except Exception as e:
            self.log(f"Error extracting Tixr pricing from {tixr_url}: {e}")
            return {'min_price': None, 'max_price': None, 'price_tiers': []}

    def _determine_category(self, tags: List[str], title: str) -> str:
        """
        Determine event category from tags and title.

        Args:
            tags: List of tag strings
            title: Event title

        Returns:
            Category string
        """
        # Convert to lowercase for matching
        tags_lower = [t.lower() for t in tags]
        title_lower = title.lower()

        # Priority matching based on tags
        if any(tag in tags_lower for tag in ['live music', 'concert']):
            return 'music'
        elif any(tag in tags_lower for tag in ['brunch', 'bottomless mimosas', 'mimosas']):
            return 'food'
        elif any(tag in tags_lower for tag in ['trivia', 'bingo', 'game']):
            return 'entertainment'
        elif any(tag in tags_lower for tag in ['grateful dead', 'jerry garcia']):
            return 'music'
        elif 'line dancing' in title_lower or 'dance' in title_lower:
            return 'entertainment'
        elif 'tribute' in title_lower or 'band' in title_lower:
            return 'music'
        else:
            # Default to music since Venice West is primarily a music venue
            return 'music'

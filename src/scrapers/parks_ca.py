"""
Scraper for California State Parks events.
Source: https://www.parks.ca.gov/Events

Filters events to focus on LA/Westside area parks:
- Angeles District parks (Santa Monica Mountains, Malibu, etc.)
- Specific parks: Malibu Creek SP, Malibu Lagoon SB, Los Angeles SHP, Kenneth Hahn SRA
"""
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class ParksCaliforniaScraper(BaseScraper):
    """Scraper for California State Parks events."""

    def __init__(self):
        super().__init__('California State Parks')
        self.base_url = 'https://www.parks.ca.gov'
        self.events_url = f'{self.base_url}/Events'

        # Focus on LA/Westside area parks
        self.target_parks = [
            'Malibu Creek',
            'Malibu Lagoon',
            'Los Angeles State Historic Park',
            'Los Angeles SHP',
            'Kenneth Hahn',
            'Topanga State Park',
            'Will Rogers State Historic Park',
            'Will Rogers SHP',
            'Santa Monica Mountains'
        ]

        # Known park addresses for geocoding fallback
        self.park_addresses = {
            'Malibu Creek SP': 'Malibu Creek State Park, 1925 Las Virgenes Rd, Calabasas, CA 91302',
            'Malibu Creek State Park': 'Malibu Creek State Park, 1925 Las Virgenes Rd, Calabasas, CA 91302',
            'Malibu Lagoon SB': '23200 Pacific Coast Highway, Malibu, CA 90265',
            'Malibu Lagoon State Beach': '23200 Pacific Coast Highway, Malibu, CA 90265',
            'Will Rogers SHP': 'Will Rogers State Historic Park, 1501 Will Rogers State Park Rd, Pacific Palisades, CA 90272',
            'Will Rogers State Historic Park': 'Will Rogers State Historic Park, 1501 Will Rogers State Park Rd, Pacific Palisades, CA 90272',
            'Topanga State Park': 'Topanga State Park, 20828 Entrada Rd, Topanga, CA 90290',
            'Kenneth Hahn SRA': 'Kenneth Hahn State Recreation Area, 4100 S La Cienega Blvd, Los Angeles, CA 90056',
            'Kenneth Hahn State Recreation Area': 'Kenneth Hahn State Recreation Area, 4100 S La Cienega Blvd, Los Angeles, CA 90056',
        }

    def scrape(self) -> List[Event]:
        """
        Scrape events from California State Parks.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch events filtered by Angeles District
            angeles_url = f'{self.events_url}?district=Angeles%20District'
            html = self.fetch_page(angeles_url)
            if not html:
                self.log("Failed to fetch Angeles District events page")
                return events

            soup = self.parse_html(html)

            # Find event links - they follow the pattern /EventDetails/{id}
            event_links = soup.find_all('a', href=re.compile(r'/EventDetails/\d+'))

            # Get unique event URLs
            event_urls = set()
            for link in event_links:
                href = link.get('href', '')
                if '/EventDetails/' in href:
                    full_url = self.normalize_url(href, self.base_url)
                    event_urls.add(full_url)

            self.log(f"Found {len(event_urls)} event URLs in Angeles District")

            # Prefetch all event detail pages concurrently
            if event_urls:
                self.prefetch_pages(list(event_urls))

            # Process each event detail page
            for i, url in enumerate(event_urls, 1):
                try:
                    event = self._scrape_event_detail(url)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(event_urls)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing event {i} ({url}): {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} events")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _scrape_event_detail(self, url: str) -> Optional[Event]:
        """
        Scrape details from an individual event page.

        Args:
            url: URL of the event detail page

        Returns:
            Event object or None if parsing fails or event is not in target area
        """
        html = self.fetch_page(url)
        if not html:
            return None

        soup = self.parse_html(html)

        # Extract park name first to filter
        park_name = self._extract_park_name(soup)

        # Check if this is a target park (LA/Westside area)
        if not self._is_target_park(park_name):
            self.log(f"Skipping event at non-target park: {park_name}")
            return None

        # Extract title
        title_elem = soup.find('h1')
        if not title_elem:
            title_elem = soup.find('h2')
        title = self.clean_text(title_elem.get_text()) if title_elem else 'Untitled Event'

        # Extract description
        description = self._extract_description(soup)

        # Extract date and time
        event_date, end_date = self._extract_dates(soup, title, description)

        # Extract venue information (use park name as venue)
        venue_name = park_name
        address = self._extract_address(soup, park_name)

        # Extract image
        image_url = self._extract_image(soup)

        # Extract pricing information
        price, is_free, price_note = self._extract_pricing(soup, description)

        # Category will be auto-classified by create_event
        return self.create_event(
            title=title,
            description=description,
            venue_name=venue_name,
            address=address,
            event_date=event_date,
            end_date=end_date,
            url=url,
            image_url=image_url,
            price=price,
            is_free=is_free,
            price_note=price_note
        )

    def _extract_park_name(self, soup) -> str:
        """Extract park name from the page."""
        # Look for park link in h4 (main park name display)
        h4_tags = soup.find_all('h4')
        for h4 in h4_tags:
            park_link = h4.find('a', href=re.compile(r'/\?page_id=\d+'))
            if park_link:
                park_name = self.clean_text(park_link.get_text())
                # Skip "About Us" and similar links
                if park_name and park_name != 'About Us':
                    park_lower = park_name.lower()
                    # Check if it's a park name (contains park indicators)
                    if any(indicator in park_lower for indicator in ['state park', 'shp', ' sb', ' sp', ' sra']):
                        return park_name

        # Fallback: look for any park link
        park_link = soup.find('a', href=re.compile(r'/\?page_id=\d+'))
        if park_link:
            park_name = self.clean_text(park_link.get_text())
            if park_name != 'About Us':
                return park_name

        # Look for park name in page metadata or title
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text()
            # Try to extract park name from title
            match = re.search(r'at\s+([^|]+)', title_text)
            if match:
                return self.clean_text(match.group(1))

        return ''

    def _is_target_park(self, park_name: str) -> bool:
        """
        Check if park is in the target LA/Westside area.

        Args:
            park_name: Name of the park

        Returns:
            True if park is in target area
        """
        if not park_name:
            return False

        park_lower = park_name.lower()

        # Check if any target park name is in the park name
        for target in self.target_parks:
            if target.lower() in park_lower:
                return True

        return False

    def _extract_description(self, soup) -> str:
        """Extract event description from the page."""
        description_parts = []

        # Get all paragraphs and filter for actual content
        paragraphs = soup.find_all('p')
        skip_patterns = [
            'Date of event',
            'Time of event',
            'Location of event',
            'Free Entry',
            'Registration',
            'For more information'
        ]

        for p in paragraphs:
            text = self.clean_text(p.get_text())
            # Skip metadata paragraphs
            if any(pattern in text for pattern in skip_patterns):
                continue
            # Keep substantial content
            if text and len(text) > 30:
                description_parts.append(text)

        # If we got multiple parts, join them
        if description_parts:
            return ' '.join(description_parts[:5])  # Limit to first 5 paragraphs

        # Fallback: look for main content div
        content_div = soup.find('div', class_='event-details')
        if not content_div:
            content_div = soup.find('div', id='content')
        if not content_div:
            content_div = soup.find('div', class_='content')

        if content_div:
            text = self.clean_text(content_div.get_text())
            if text:
                # Limit length and clean up
                return text[:1000]

        return ''

    def _extract_dates(self, soup, title: str, description: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract start and end dates from the page."""
        event_date = None
        end_date = None

        # Look for "Date of Event :" text in paragraphs (case + spacing
        # varies across pages: 'Date of event:', 'Date of Event :', etc.)
        date_label_re = re.compile(r'date\s+of\s+event\s*:', re.IGNORECASE)
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = self.clean_text(p.get_text())
            m = date_label_re.search(text)
            if m:
                date_text = text[m.end():].strip()
                event_date = self._parse_date_text(date_text)
                if event_date:
                    break

        # Look for date/time in meta tags
        if not event_date:
            start_meta = soup.find('meta', {'property': 'event:start_date'})
            if start_meta and start_meta.get('content'):
                try:
                    event_date = date_parser.parse(start_meta['content'])
                except Exception as e:
                    self.log(f"Could not parse start date from meta: {e}")

        end_meta = soup.find('meta', {'property': 'event:end_date'})
        if end_meta and end_meta.get('content'):
            try:
                end_date = date_parser.parse(end_meta['content'])
            except Exception as e:
                self.log(f"Could not parse end date from meta: {e}")

        # Fallback: look for date div or span
        if not event_date:
            date_elem = soup.find('div', class_='event-date')
            if not date_elem:
                date_elem = soup.find('span', class_='date')

            if date_elem:
                date_text = self.clean_text(date_elem.get_text())
                event_date = self._parse_date_text(date_text)

        # Try to extract date from title or description if still not found
        if not event_date:
            text_to_search = f"{title} {description}"
            event_date = self._extract_date_from_text(text_to_search)

        return event_date, end_date

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """Parse date from various text formats."""
        if not date_text:
            return None

        try:
            # Try standard dateutil parser
            return date_parser.parse(date_text)
        except:
            pass

        # Try to handle "Multiple Nov", "14,21,28 Nov" patterns
        # For multiple dates, take the first one
        patterns = [
            r'(\d{1,2})[,\s]+\w{3,9}',  # "14 Nov" or "14, Nov"
            r'(\w{3,9})\s+(\d{1,2})',    # "Nov 14"
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',  # "11/14/2024"
        ]

        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return date_parser.parse(match.group(0))
                except:
                    pass

        return None

    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from free-form text."""
        # Look for common date patterns
        date_patterns = [
            r'\w{3,9}\s+\d{1,2},?\s+\d{4}',  # "November 14, 2024"
            r'\d{1,2}\s+\w{3,9}\s+\d{4}',    # "14 November 2024"
            r'\d{1,2}/\d{1,2}/\d{2,4}',      # "11/14/2024"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return date_parser.parse(match.group(0))
                except:
                    pass

        return None

    def _extract_address(self, soup, park_name: str) -> str:
        """Extract or construct address for the park."""
        extracted_address = None

        # Look for paragraphs with addresses (containing street address pattern)
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = self.clean_text(p.get_text())
            # Look for street address pattern: number + street name + city, state zip
            if re.search(r'\d+\s+[A-Z][a-z]+.*\n.*,\s*CA\s+\d{5}', p.get_text()):
                # Clean up and return just the address part
                lines = p.get_text().strip().split('\n')
                if len(lines) >= 2:
                    extracted_address = self.clean_text(' '.join(lines[:2]))
                    return extracted_address

        # Look for "Location of event" followed by address
        for i, p in enumerate(paragraphs):
            text = self.clean_text(p.get_text())
            if 'Location of event' in text:
                # Extract just the location name after the colon
                location_match = re.search(r'Location of event[:\s]+(.+)', text, re.IGNORECASE)
                if location_match:
                    location_name = location_match.group(1).strip()
                    # Check next paragraph for street address
                    if i + 1 < len(paragraphs):
                        next_text = paragraphs[i + 1].get_text()
                        if re.search(r'\d+.*CA\s+\d{5}', next_text):
                            # Combine location name with address
                            extracted_address = self.clean_text(next_text)
                            return extracted_address
                    # Store the location name but don't return yet (might be vague)
                    extracted_address = location_name if len(location_name) > 10 else None

        # Look for standard address element
        address_elem = soup.find('address')
        if address_elem:
            addr = self.clean_text(address_elem.get_text())
            if addr:
                extracted_address = addr

        # Look for location div/span
        location_elem = soup.find('div', class_='location')
        if not location_elem:
            location_elem = soup.find('span', class_='location')

        if location_elem:
            addr = self.clean_text(location_elem.get_text())
            if addr:
                extracted_address = addr

        # Check if extracted address is too vague (doesn't contain street number or "CA")
        # If so, use the known park address
        if extracted_address:
            has_street_number = bool(re.search(r'\d{3,}', extracted_address))
            has_ca_zip = bool(re.search(r'CA\s+\d{5}', extracted_address))
            # If it looks like a real address, use it
            if has_street_number or has_ca_zip:
                return extracted_address

        # Use known park address if available (best for geocoding)
        if park_name in self.park_addresses:
            return self.park_addresses[park_name]

        # If we have a vague extracted address, return it with park name
        if extracted_address:
            return f"{extracted_address}, {park_name}, CA"

        # Final fallback: construct address from park name + general location
        return f"{park_name}, Los Angeles, CA"

    def _extract_image(self, soup) -> str:
        """Extract event image URL from the page."""
        # Look for og:image meta tag
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']

        # Look for event image
        img_elem = soup.find('div', class_='event-image')
        if img_elem:
            img = img_elem.find('img')
            if img and img.get('src'):
                return self.normalize_url(img['src'], self.base_url)

        # Look for any prominent image
        img = soup.find('img', class_=re.compile(r'featured|hero|main'))
        if img and img.get('src'):
            return self.normalize_url(img['src'], self.base_url)

        return ''

    def _extract_pricing(self, soup, description: str) -> tuple[Optional[float], bool, str]:
        """Extract pricing information from the page."""
        price = None
        is_free = False
        price_note = ''

        # Combine page text for searching
        page_text = (soup.get_text() + ' ' + description).lower()

        # Check if free
        if any(phrase in page_text for phrase in ['free event', 'no fee', 'free admission', 'free to attend']):
            is_free = True
            return price, is_free, price_note

        # Look for price patterns
        price_patterns = [
            r'\$(\d+(?:\.\d{2})?)\s*(?:per\s*person|per\s*participant|fee)',
            r'cost:\s*\$(\d+(?:\.\d{2})?)',
            r'price:\s*\$(\d+(?:\.\d{2})?)',
            r'fee:\s*\$(\d+(?:\.\d{2})?)',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, page_text)
            if match:
                try:
                    price = float(match.group(1))
                    break
                except ValueError:
                    pass

        # Check for parking fees (common for state parks)
        if 'parking fee' in page_text or 'day use fee' in page_text:
            parking_match = re.search(r'\$(\d+(?:\.\d{2})?)\s*(?:parking|day\s*use)', page_text)
            if parking_match:
                parking_fee = parking_match.group(1)
                if price_note:
                    price_note += f" Parking: ${parking_fee}"
                else:
                    price_note = f"Parking: ${parking_fee}"

        # Check for registration requirement
        if any(phrase in page_text for phrase in ['registration required', 'register', 'rsvp']):
            if price_note:
                price_note += ". Registration required"
            else:
                price_note = "Registration required"

        return price, is_free, price_note

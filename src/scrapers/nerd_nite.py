"""
Scraper for Nerd Nite Los Angeles events.
Source: https://la.nerdnite.com
"""
from datetime import datetime
from typing import List, Optional
import re
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class NerdNiteScraper(BaseScraper):
    """Scraper for Nerd Nite LA events."""

    def __init__(self):
        super().__init__('Nerd Nite LA')
        self.base_url = 'https://la.nerdnite.com'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Nerd Nite LA website.

        The site displays the next upcoming event on the homepage with
        full details including date, venue, and speaker presentations.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            html = self.fetch_page(self.base_url)
            if not html:
                self.log("Failed to fetch homepage")
                return events

            soup = self.parse_html(html)

            # Extract the event from homepage
            event = self._parse_homepage_event(soup)
            if event:
                events.append(event)
                self.log(f"Successfully scraped 1 event")
            else:
                self.log("No upcoming events found")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_homepage_event(self, soup) -> Optional[Event]:
        """
        Parse the upcoming event from the homepage.

        Args:
            soup: BeautifulSoup object of homepage

        Returns:
            Event object or None
        """
        try:
            # Get full text content
            page_text = soup.get_text()

            # Extract event date
            # Look for "NEXT NERD NITE LA IS [Month] [Day]"
            date_match = re.search(
                r'NEXT NERD NITE LA IS\s+([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?',
                page_text,
                re.IGNORECASE
            )

            event_date = None
            if date_match:
                month_str = date_match.group(1)
                day_str = date_match.group(2)

                # Construct date string with current year
                # (Nerd Nite events are typically announced for current/next month)
                current_year = datetime.now().year
                date_str = f"{month_str} {day_str} {current_year}"

                try:
                    event_date = date_parser.parse(date_str)

                    # If the parsed date is in the past, assume it's next year
                    if event_date < datetime.now():
                        event_date = event_date.replace(year=current_year + 1)

                    self.log(f"Parsed event date: {event_date}")
                except Exception as e:
                    self.log(f"Failed to parse date '{date_str}': {e}")

            # Extract venue information
            # Format: "Brewyard Beer Company LLC.\n906 Western Ave, Glendale, CA 91201"
            venue_name = ""
            address = ""

            venue_match = re.search(
                r'Brewyard Beer Company[^.]*\.\s*(\d+[^,]+,[^,]+,\s*CA\s*\d{5})',
                page_text,
                re.IGNORECASE | re.DOTALL
            )

            if venue_match:
                venue_name = "Brewyard Beer Company"
                address = venue_match.group(1).strip()
                address = self.clean_text(address)
            else:
                # Fallback: try generic venue pattern
                venue_pattern = re.search(
                    r'([\w\s]+(?:Brewery|Bar|Company|Venue))[^.]*\.\s*(\d+[^,]+,[^,]+,\s*CA\s*\d{5})',
                    page_text,
                    re.IGNORECASE | re.DOTALL
                )
                if venue_pattern:
                    venue_name = self.clean_text(venue_pattern.group(1))
                    address = self.clean_text(venue_pattern.group(2))

            # Extract presentations to build description
            description_parts = []

            # Find all presentations
            presentation_matches = re.finditer(
                r'PRESENTATION\s*#?\d+:\s*([^\n]+)\s*By\s+([^\n]+)',
                page_text,
                re.IGNORECASE
            )

            for match in presentation_matches:
                presentation_title = self.clean_text(match.group(1))
                speaker_name = self.clean_text(match.group(2))
                description_parts.append(f"{presentation_title} by {speaker_name}")

            # Build description
            description = "Nerd Nite is a monthly event during which several folks give 20-minute fun-yet-informative presentations across all disciplines while the audience drinks along."

            if description_parts:
                description += "\n\nThis month's presentations:\n• " + "\n• ".join(description_parts)

            # Add food info if present
            if "tacos" in page_text.lower() or "la prieta" in page_text.lower():
                description += "\n\nTacos provided by La Prieta Mexicana."

            # Build event title
            title = "Nerd Nite LA"
            if event_date:
                title += f" - {event_date.strftime('%B %Y')}"

            # Extract image URL for event poster
            image_url = ""
            # Look for speaker graphic image
            speaker_img = soup.find('img', src=re.compile(r'Speaker-Graphic|speaker|event', re.IGNORECASE))
            if speaker_img and speaker_img.get('src'):
                image_url = self.normalize_url(speaker_img['src'], self.base_url)

            # Set time to 7:00 PM (typical Nerd Nite start time)
            if event_date:
                event_date = event_date.replace(hour=19, minute=0, second=0)

            return self.create_event(
                title=title,
                description=description,
                venue_name=venue_name,
                address=address,
                event_date=event_date,
                url=self.base_url,
                image_url=image_url,
                category="Education",  # Nerd Nite is educational entertainment
                is_free=False  # Typically requires tickets
            )

        except Exception as e:
            self.log(f"Error parsing homepage event: {e}")
            return None

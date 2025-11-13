"""
Scraper for Apero Francophone events.
Source: https://www.eventbrite.com/o/apero-francophone-de-los-angeles-59137584493

Monthly afterwork gatherings for French expats and locals in Los Angeles.
Events feature networking, food, drinks, and DJ entertainment.
"""
from typing import List

from .eventbrite import EventbriteScraper
from src.data.models import Event


class AperoFrancophoneScraper(EventbriteScraper):
    """Scraper for Apero Francophone events on Eventbrite."""

    def __init__(self):
        # Call parent EventbriteScraper.__init__() to set base_url etc
        super().__init__()
        # Override the source name
        self.source = 'Apero Francophone'
        # Set the organizer URL
        self.organizer_url = 'https://www.eventbrite.com/o/apero-francophone-de-los-angeles-59137584493'

    def scrape(self) -> List[Event]:
        """
        Scrape events from Apero Francophone's Eventbrite organizer page.
        Uses the parent class's _scrape_organizer_profile_page method.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")

        # Use the parent class's organizer profile scraper
        events = self._scrape_organizer_profile_page(self.organizer_url)

        self.log(f"Successfully scraped {len(events)} events")
        return events

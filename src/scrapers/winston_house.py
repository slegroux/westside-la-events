"""
Scraper for Winston House venue events.
Source: https://www.winstonhouse.com/schedule

NOTE: Winston House permanently closed after their NYE 2024/2025 event.
This scraper is included for reference but will not return events.
The venue historically directed users to Instagram for event schedules
rather than maintaining structured event data on their website.

Venue Details:
- Location: 23 Windward Avenue, Venice, CA 90291
- Type: Live music venue, social club, restaurant, bar
- Known for: Intimate shows with surprise artist lineups
- Past artists: Janelle Monae, The Shins, Vance Joy, Billie Eilish, Kimbra, Skylar Grey
"""
from datetime import datetime
from typing import List

from .base import BaseScraper
from src.data.models import Event


class WinstonHouseScraper(BaseScraper):
    """Scraper for Winston House events."""

    def __init__(self):
        super().__init__('Winston House')
        self.base_url = 'https://www.winstonhouse.com'
        self.schedule_url = f'{self.base_url}/schedule'
        self.venue_name = 'Winston House'
        self.venue_address = '23 Windward Avenue, Venice, CA 90291'
        self.is_permanently_closed = True

    def scrape(self) -> List[Event]:
        """
        Scrape events from Winston House schedule.

        NOTE: Winston House is permanently closed. This method returns an empty list.
        If you need to add Winston House events manually, use the admin interface.

        Returns:
            Empty list (venue closed)
        """
        self.log("Winston House is permanently closed as of 2025")
        return []

    def _scrape_if_active(self) -> List[Event]:
        """
        Historical implementation showing how scraping would work if venue were active.

        This method demonstrates the approach that would be taken, though Winston House's
        website never had structured event data - they directed users to Instagram instead.

        Returns:
            List of Event objects (currently empty)
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the schedule page
            html = self.fetch_page(self.schedule_url)
            if not html:
                self.log("Failed to fetch schedule page")
                return events

            soup = self.parse_html(html)

            # The Winston House schedule page only contains static text like:
            # "LIVE MUSIC THURSDAY, FRIDAY, AND SATURDAY"
            # "SHOW #1: 7PM - 10PM"
            # "SHOW #2: 10PM - 2AM"
            #
            # There are no structured event listings with artist names, specific dates, etc.
            # The page directs users to check Instagram for the weekly schedule.
            #
            # To actually scrape Winston House events, you would need to:
            # 1. Use Instagram API/scraping (requires authentication, violates ToS)
            # 2. Use Speakeasy (where they list some events)
            # 3. Manually add events through admin interface

            self.log("Winston House website doesn't contain structured event data")
            self.log("Events are announced on Instagram: @winstonhouse")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_generic_schedule(self) -> List[Event]:
        """
        Parse the generic schedule information (recurring weekly shows).

        This would create placeholder events for recurring shows, but without
        specific artist information, these aren't very useful.

        Returns:
            List of generic recurring event templates
        """
        # Example of how you might create recurring event templates
        # (Not implemented since venue is closed and this approach has limited value)
        return []

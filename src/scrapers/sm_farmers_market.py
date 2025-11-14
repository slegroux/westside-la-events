"""
Scraper for Santa Monica Farmers Markets.
Source: https://www.santamonica.gov/categories/programs/farmers-market

Note: Santa Monica has multiple farmers markets with fixed schedules:
- Wednesday Downtown (8:30am-1:30pm, Arizona Ave & 2nd St)
- Saturday Downtown (8:30am-1pm, Arizona Ave & 2nd St)
- Sunday Main Street (8:30am-1pm, Main St between Ocean Park & Ashland)
- Sunday Pico (8am-1pm, Pico Blvd & Cloverfield)
"""
from datetime import datetime, timedelta
from typing import List

from .base import BaseScraper
from src.data.models import Event


class SantaMonicaFarmersMarketScraper(BaseScraper):
    """Scraper for Santa Monica Farmers Markets."""

    # Fixed market schedules
    MARKETS = [
        {
            'name': 'Wednesday Downtown Farmers Market',
            'day': 2,  # Wednesday (0=Monday)
            'time': '8:30am-1:30pm',
            'location': 'Arizona Avenue & 2nd Street',
            'address': '1299 Arizona Ave, Santa Monica, CA 90401'
        },
        {
            'name': 'Saturday Downtown Farmers Market',
            'day': 5,  # Saturday
            'time': '8:30am-1pm',
            'location': 'Arizona Avenue & 2nd Street',
            'address': '1299 Arizona Ave, Santa Monica, CA 90401'
        },
        {
            'name': 'Sunday Main Street Farmers Market',
            'day': 6,  # Sunday
            'time': '8:30am-1pm',
            'location': 'Main Street between Ocean Park & Ashland',
            'address': '2640 Main St, Santa Monica, CA 90405'
        },
        {
            'name': 'Sunday Pico Farmers Market',
            'day': 6,  # Sunday
            'time': '8am-1pm',
            'location': 'Pico Boulevard & Cloverfield',
            'address': '2400 Pico Blvd, Santa Monica, CA 90405'
        }
    ]

    def __init__(self):
        super().__init__('Santa Monica Farmers Markets')
        self.base_url = 'https://www.santamonica.gov'
        self.events_url = f'{self.base_url}/categories/programs/farmers-market'

    def scrape(self) -> List[Event]:
        """
        Generate events for Santa Monica Farmers Markets.
        Since these are recurring weekly events, we'll create events for the next 8 weeks.

        Returns:
            List of Event objects
        """
        self.log("Generating farmers market events...")
        events = []

        try:
            today = datetime.now()
            # Generate events for the next 8 weeks
            for week in range(8):
                for market in self.MARKETS:
                    # Calculate the next occurrence of this market's day
                    days_ahead = market['day'] - today.weekday()
                    if days_ahead < 0:  # Already passed this week
                        days_ahead += 7

                    event_date = today + timedelta(days=days_ahead + (week * 7))

                    # Parse start time from time string
                    import re
                    time_match = re.search(r'(\d{1,2}):?(\d{2})?([ap]m)', market['time'])
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2)) if time_match.group(2) else 0
                        am_pm = time_match.group(3)

                        if am_pm == 'pm' and hour != 12:
                            hour += 12
                        elif am_pm == 'am' and hour == 12:
                            hour = 0

                        event_date = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    # Create event
                    event = self.create_event(
                        title=market['name'],
                        description=f"Weekly farmers market featuring fresh produce, flowers, and artisan goods. {market['time']} at {market['location']}.",
                        venue_name=market['name'],
                        address=market['address'],
                        event_date=event_date,
                        url=self.events_url,
                        image_url="",
                        category="Food & Drink",
                        price=None,
                        is_free=True,
                        price_note="Free admission"
                    )

                    if event:
                        events.append(event)

            self.log(f"Generated {len(events)} farmers market events")

        except Exception as e:
            self.log(f"Error generating events: {e}")
            import traceback
            traceback.print_exc()

        return events

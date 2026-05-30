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

    @staticmethod
    def _parse_time_range(text: str):
        """Parse '8:30am-1:30pm' into ((start_h, start_m), (end_h, end_m))."""
        import re

        def to_24h(h, m, ap):
            h = int(h)
            m = int(m) if m else 0
            if ap == 'pm' and h != 12:
                h += 12
            elif ap == 'am' and h == 12:
                h = 0
            return h, m

        matches = re.findall(r'(\d{1,2}):?(\d{2})?\s*([ap]m)', text.lower())
        if len(matches) >= 2:
            return to_24h(*matches[0]), to_24h(*matches[1])
        return None

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

                    # Parse both start and end times from e.g. "8:30am-1:30pm"
                    # so every market carries real hours (not just a start time).
                    end_date = None
                    times = self._parse_time_range(market['time'])
                    if times:
                        (sh, sm), (eh, em) = times
                        event_date = event_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
                        end_date = event_date.replace(hour=eh, minute=em, second=0, microsecond=0)

                    # Create event
                    event = self.create_event(
                        title=market['name'],
                        description=f"Weekly farmers market featuring fresh produce, flowers, and artisan goods. {market['time']} at {market['location']}.",
                        venue_name=market['name'],
                        address=market['address'],
                        event_date=event_date,
                        end_date=end_date,
                        url=self.events_url,
                        image_url="https://cityofsantamonica.getbynder.com/m/3c685e9639708c15/Desktop_Header-Baskets-of-Multi-Colored-Cherry-Tomatoes.jpg",
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

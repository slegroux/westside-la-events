"""
Scraper for The Victorian events.
Source: https://www.thevictorian.com/what-s-on

The Victorian is a Santa Monica venue featuring recurring weekly events including
comedy shows, music performances, and nightlife events.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


# Recurring weekly events at The Victorian
RECURRING_EVENTS = [
    {
        'title': 'Westside Comedy Open Mic',
        'day': 0,  # Monday
        'time': '19:00',  # 7:00 PM
        'description': 'Weekly open mic comedy night featuring both new and established comedians from the Westside and beyond.',
        'category': 'Comedy',
        'url': 'https://www.thevictorian.com/what-s-on'
    },
    {
        'title': 'The Victorian Comedy Showcase',
        'day': 2,  # Wednesday
        'time': '20:00',  # 8:00 PM
        'description': 'Weekly comedy showcase featuring professional comedians and rising stars.',
        'category': 'Comedy',
        'url': 'https://www.thevictorian.com/what-s-on'
    },
    {
        'title': 'Thursday Night Live Music',
        'day': 3,  # Thursday
        'time': '20:00',  # 8:00 PM
        'description': 'Live music performances featuring local and touring artists.',
        'category': 'Music',
        'url': 'https://www.thevictorian.com/what-s-on'
    },
    {
        'title': 'Weekend Comedy Shows',
        'day': 5,  # Friday
        'time': '20:00',  # 8:00 PM
        'description': 'Weekend comedy shows featuring top comedians.',
        'category': 'Comedy',
        'url': 'https://www.thevictorian.com/what-s-on'
    },
    {
        'title': 'Saturday Night Comedy',
        'day': 6,  # Saturday (changed from 5)
        'time': '20:00',  # 8:00 PM
        'description': 'Saturday night comedy shows with multiple performances.',
        'category': 'Comedy',
        'url': 'https://www.thevictorian.com/what-s-on'
    },
]


class VictorianScraper(BaseScraper):
    """Scraper for The Victorian events."""

    def __init__(self):
        super().__init__('The Victorian')
        self.events_url = 'https://www.thevictorian.com/what-s-on'
        self.venue_name = 'The Victorian'
        self.venue_address = '2640 Main St, Santa Monica, CA 90405'

    def scrape(self) -> List[Event]:
        """
        Generate recurring weekly events for The Victorian.

        Since the website lists recurring weekly events, we generate instances
        for the next 4 weeks.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Generate events for next 4 weeks
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            weeks_ahead = 4

            for event_template in RECURRING_EVENTS:
                for week in range(weeks_ahead):
                    event = self._generate_event_instance(event_template, today, week)
                    if event:
                        events.append(event)

            self.log(f"Generated {len(events)} recurring events for next {weeks_ahead} weeks")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        return events

    def _generate_event_instance(self, template: dict, start_date: datetime, weeks_ahead: int) -> Optional[Event]:
        """
        Generate a single event instance from a recurring event template.

        Args:
            template: Dictionary with event template data
            start_date: Starting date to calculate from
            weeks_ahead: Number of weeks ahead to schedule

        Returns:
            Event object or None
        """
        try:
            # Calculate the next occurrence of this day of week
            days_ahead = template['day'] - start_date.weekday()
            if days_ahead < 0:
                days_ahead += 7

            # Add weeks
            days_ahead += weeks_ahead * 7

            event_date = start_date + timedelta(days=days_ahead)

            # Parse time
            hour, minute = map(int, template['time'].split(':'))
            event_date = event_date.replace(hour=hour, minute=minute)

            # Skip events in the past
            if event_date < datetime.now():
                return None

            # Make URL unique by adding date to prevent deduplication issues
            # Since all events share the same page, we add the date as an anchor
            unique_url = f"{template['url']}#{event_date.strftime('%Y%m%d')}"

            return self.create_event(
                title=template['title'],
                description=template['description'],
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                url=unique_url,
                category=template['category'],
                price_note='TBD'
            )

        except Exception as e:
            self.log(f"Error generating event instance: {e}")
            return None

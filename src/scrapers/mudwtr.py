"""
Scraper for MUD\WTR :gather events.
Source: https://www.mudwtrgather.com/schedule

MUD\WTR :gather is a mushroom cafe and mindfulness studio offering yoga,
meditation, breathwork classes, and special events in Santa Monica/Venice.

Note: The schedule uses Hello Walla API for class scheduling.
This scraper makes direct API calls to retrieve class instances.
"""
import re
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser

from .base import BaseScraper
from src.data.models import Event


class MudWtrScraper(BaseScraper):
    """Scraper for MUD\WTR :gather events."""

    def __init__(self):
        super().__init__("MUD\\WTR :gather")
        self.schedule_url = 'https://www.mudwtrgather.com/schedule'
        self.venue_name = "MUD\\WTR :gather"
        self.venue_address = '2515 Main St, Santa Monica, CA 90405'
        self.api_base_url = 'https://api.hellowalla.com/api/dingo/v1'
        self.location_id = 3721  # MUD\WTR :gather location ID

    def scrape(self) -> List[Event]:
        """
        Scrape events from MUD\WTR :gather using Hello Walla API.

        Fetches class instances for the next 30 days from the Walla API.

        Returns:
            List of Event objects
        """
        self.log("Starting scrape from MUD\\WTR :gather via Walla API...")
        events = []

        try:
            # Get classes for the next 30 days
            start_date = datetime.now()
            end_date = start_date + timedelta(days=30)

            # Fetch class instances from API
            class_instances = self._fetch_class_instances(start_date, end_date)

            self.log(f"Found {len(class_instances)} class instances")

            for instance in class_instances:
                event = self._parse_class_instance(instance)
                if event:
                    events.append(event)
                    self.log(f"Parsed class: {event.title}")

        except Exception as e:
            self.log(f"Error during scrape: {e}")
            import traceback
            traceback.print_exc()

        self.log(f"Total events scraped: {len(events)}")
        return events

    def _fetch_class_instances(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """
        Fetch class instances from Walla API for a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of class instance dictionaries
        """
        all_instances = []

        # Format dates to match the API format: set time to beginning/end of day in UTC
        # API uses UTC timezone, so we need to convert
        start_utc = start_date.replace(hour=8, minute=0, second=0, microsecond=0)  # 8AM UTC = 12AM PST
        end_utc = end_date.replace(hour=7, minute=59, second=59, microsecond=999000)  # 7:59AM UTC = 11:59PM PST

        start_str = start_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_str = end_utc.strftime('%Y-%m-%dT%H:%M:%S.999Z')

        # Build API URL - don't use params dict to avoid URL encoding issues
        url = (
            f"{self.api_base_url}/class_instances?"
            f"page=1&per_page=100&"
            f"sort=class_instances.start_time:asc&"
            f"active=both&"
            f"start_time=between|{start_str}|{end_str}&"
            f"location_ids[]={self.location_id}"
        )

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            records = data.get('records', [])
            all_instances.extend(records)

            # Handle pagination if needed
            total_pages = data.get('total_pages', 1)
            if total_pages > 1:
                for page in range(2, total_pages + 1):
                    page_url = (
                        f"{self.api_base_url}/class_instances?"
                        f"page={page}&per_page=100&"
                        f"sort=class_instances.start_time:asc&"
                        f"active=both&"
                        f"start_time=between|{start_str}|{end_str}&"
                        f"location_ids[]={self.location_id}"
                    )
                    response = self.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    data = response.json()
                    all_instances.extend(data.get('records', []))

        except Exception as e:
            self.log(f"Error fetching class instances: {e}")

        return all_instances

    def _parse_class_instance(self, instance: dict) -> Optional[Event]:
        """
        Parse a class instance from Walla API response.

        Args:
            instance: Dictionary containing class instance data from API

        Returns:
            Event object or None if parsing fails
        """
        try:
            # Extract basic information
            title = instance.get('name', '')
            if not title:
                return None

            # Parse dates
            start_time_str = instance.get('start_time')
            end_time_str = instance.get('end_time')

            if not start_time_str:
                return None

            event_date = date_parser.parse(start_time_str)
            end_date = date_parser.parse(end_time_str) if end_time_str else None

            # Extract instructor name
            staff = instance.get('staff', {})
            instructor = f"{staff.get('first_name', '')} {staff.get('last_name', '')}".strip()

            # Extract course details
            course = instance.get('course', {})
            course_offering = course.get('course_offering', {})
            description_text = course_offering.get('description', '')

            # Build description
            description_parts = []
            if description_text:
                description_parts.append(description_text)
            if instructor:
                description_parts.append(f"Instructor: {instructor}")

            # Add duration
            duration = instance.get('duration_mins')
            if duration:
                description_parts.append(f"Duration: {duration} minutes")

            # Add pricing info
            price_info = self._extract_price_info(instance)
            if price_info:
                description_parts.append(price_info)

            description = '\n\n'.join(description_parts) if description_parts else self._generate_description(title)

            # Extract pricing
            price = None
            is_free = False
            in_person_price = instance.get('in_studio_non_member_price', {})
            if in_person_price:
                cents = in_person_price.get('cents', 0)
                price = cents / 100.0  # Convert cents to dollars

            # Extract image from staff profile
            image_url = staff.get('profile_photo_cdn_url', '')

            # Create event
            return self.create_event(
                title=title,
                description=description,
                venue_name=self.venue_name,
                address=self.venue_address,
                event_date=event_date,
                end_date=end_date,
                url=self.schedule_url,
                image_url=image_url,
                category='Wellness',
                price=price,
                is_free=is_free
            )

        except Exception as e:
            self.log(f"Error parsing class instance: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_price_info(self, instance: dict) -> str:
        """
        Extract pricing information from class instance.

        Args:
            instance: Class instance dictionary

        Returns:
            Formatted price information string
        """
        price_parts = []

        # In-person pricing
        member_price = instance.get('in_studio_member_price', {})
        non_member_price = instance.get('in_studio_non_member_price', {})

        if member_price and member_price.get('cents'):
            member_dollars = member_price['cents'] / 100.0
            price_parts.append(f"Member: ${member_dollars:.2f}")

        if non_member_price and non_member_price.get('cents'):
            non_member_dollars = non_member_price['cents'] / 100.0
            price_parts.append(f"Drop-in: ${non_member_dollars:.2f}")

        # Credits
        member_credits = instance.get('in_studio_member_price_credits')
        if member_credits:
            price_parts.append(f"or {member_credits} credits")

        return ' | '.join(price_parts) if price_parts else ''

    def _generate_description(self, title: str) -> str:
        """
        Generate a description based on the class title.

        Args:
            title: Class title

        Returns:
            Generated description
        """
        # Default descriptions for common class types
        keywords_desc = {
            'yoga': 'A yoga practice combining movement, breath, and mindfulness. Free MUD\\WTR beverage included after class.',
            'meditation': 'A guided meditation session to cultivate presence and inner peace. Free MUD\\WTR beverage included.',
            'breathwork': 'Conscious breathing practice to energize and center the body and mind. Free MUD\\WTR beverage included.',
            'rise': ':rise class - a mashup of yoga, movement, breathwork and meditation. A full mind, body and spirit experience. Free MUD\\WTR beverage included.',
            'workshop': 'A special workshop at MUD\\WTR :gather, your community space for mindfulness and connection.',
            'event': 'A special event at MUD\\WTR :gather featuring world class speakers, music, and community gatherings.',
        }

        title_lower = title.lower()
        for keyword, desc in keywords_desc.items():
            if keyword in title_lower:
                return desc

        # Default description
        return f'{title} at MUD\\WTR :gather - a mushroom cafe and mindfulness studio offering yoga, meditation, breathwork, and community events. Open Wed-Sun, 7 AM to 2 PM.'

    def log(self, message: str):
        """
        Log a message with source name prefix.

        Args:
            message: Message to log
        """
        print(f"[{self.source_name}] {message}")

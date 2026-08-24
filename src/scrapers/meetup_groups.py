"""
Scrapers for specific Meetup groups.

The main MeetupScraper runs a geographic search around Santa Monica, which only
surfaces whatever Meetup chooses to rank into that result set. Groups that
matter to the Westside but don't reliably show up there get their own scraper
here, reading the same Apollo GraphQL state off the group's events page.
"""
from typing import List

from .meetup import MeetupScraper
from src.data.models import Event


class MeetupGroupScraper(MeetupScraper):
    """Base for a single Meetup group's events page.

    Subclasses set GROUP_SLUG and pass a display name; parsing is inherited
    from MeetupScraper, whose Apollo-state reader is group-agnostic.
    """

    GROUP_SLUG: str = ''

    def __init__(self, source_name: str):
        super().__init__()
        self.source_name = source_name
        self.events_url = f'{self.base_url}/{self.GROUP_SLUG}/events/'

    def scrape(self) -> List[Event]:
        """Scrape the group's events page.

        The group page carries past occurrences alongside upcoming ones, and
        create_event does not filter by date, so past events are dropped here.
        """
        from datetime import datetime

        events = super().scrape()
        now = datetime.now()
        upcoming = [e for e in events if e.event_date and e.event_date >= now]
        dropped = len(events) - len(upcoming)
        if dropped:
            self.log(f"Dropped {dropped} past occurrences")
        return upcoming


class PracticalPhilosophyClubScraper(MeetupGroupScraper):
    """Weekly philosophy discussion at Father's Office in Culver City."""

    GROUP_SLUG = 'practical-philosophy-club-los-angeles'

    def __init__(self):
        super().__init__('Practical Philosophy Club')


class EuropeansMingleScraper(MeetupGroupScraper):
    """Social mixers around Santa Monica and the beach cities."""

    GROUP_SLUG = 'europeans-mingle-meetup-group'

    def __init__(self):
        super().__init__('Europeans Mingle')


class SocialLingoLAScraper(MeetupGroupScraper):
    """Language-exchange socials around the Westside."""

    GROUP_SLUG = 'social-lingo-la'

    def __init__(self):
        super().__init__('Social Lingo LA')


class SiliconBeachLocalsScraper(MeetupGroupScraper):
    """Tech and founder meetups in the Silicon Beach corridor."""

    GROUP_SLUG = 'silicon-beach-locals-meetup-group'

    def __init__(self):
        super().__init__('Silicon Beach Locals')


class MeetupGroupRxiwtjjqScraper(MeetupGroupScraper):
    """Meetup group carrying only an auto-generated slug."""

    GROUP_SLUG = 'meetup-group-rxiwtjjq'

    def __init__(self):
        super().__init__('LA Social Meetup')

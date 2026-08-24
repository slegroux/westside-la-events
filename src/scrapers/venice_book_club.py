"""
Scraper for Venice Book Club events.
Source: https://luma.com/venicebookclub

Book club meetups around Venice and Mar Vista, frequently hosted at Saba
Coffee Shop. Backed by a public Luma calendar -- see LumaCalendarScraper.
"""
from .luma import LumaCalendarScraper


class VeniceBookClubScraper(LumaCalendarScraper):
    """Scraper for the Venice Book Club Luma calendar."""

    CALENDAR_API_ID = 'cal-E8al8GRIz3vkQrj'
    DEFAULT_VENUE_NAME = 'Venice Book Club'

    def __init__(self):
        super().__init__('Venice Book Club', 'venicebookclub')

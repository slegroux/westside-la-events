"""
Scraper for The Casual Creative events.
Source: https://luma.com/thecasualcreative

The Casual Creative hosts pop-up experiences and workshops in Los Angeles
that inspire creative play and artistic participation.

Reads the public Luma calendar API rather than the page's JSON-LD: the API
carries resolved coordinates and ticket pricing, which the embedded JSON-LD
does not.
"""
from .luma import LumaCalendarScraper


class CasualCreativeScraper(LumaCalendarScraper):
    """Scraper for The Casual Creative Luma calendar."""

    CALENDAR_API_ID = 'cal-SSay36XBRyiE7GN'
    DEFAULT_VENUE_NAME = 'The Casual Creative'

    def __init__(self):
        super().__init__('The Casual Creative', 'thecasualcreative')

"""
Scraper for 2220 Arts + Archives (Historic Filipinotown).
Source: https://www.2220arts.org/events

This is a "beyond the Westside" source: 2220 Beverly Blvd is outside the
coverage box, so REGION opts it into the separate tab and its events are
validated against LA County instead.

The venue's own events page is a Google Sites shell around a DICE ticketing
widget; events are read from the public DICE venue page (see DiceVenueScraper).
"""
from .dice_venue import DiceVenueScraper


class Arts2220Scraper(DiceVenueScraper):
    """Scraper for 2220 Arts + Archives via its public DICE venue page."""

    REGION = 'beyond'

    VENUE_NAME = '2220 Arts + Archives'
    VENUE_ADDRESS = '2220 Beverly Blvd, Los Angeles, CA 90057'
    VENUE_LAT = 34.0672209
    VENUE_LNG = -118.2723086

    BASE_URL = 'https://www.2220arts.org'
    EVENTS_URL = 'https://www.2220arts.org/events'
    LISTING_URL = 'https://dice.fm/venue/2220-arts--archives-bdyv'

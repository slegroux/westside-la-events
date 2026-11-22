"""
Scraper for Zebulon (Frogtown, Los Angeles).
Source: https://dice.fm/venue/zebulon-y8bv

Adventurous-music club at 2478 Fletcher Dr, outside the Westside coverage box,
so REGION opts it into the "beyond" tab. Events come from the public DICE venue
page (see DiceVenueScraper).
"""
from .dice_venue import DiceVenueScraper


class ZebulonScraper(DiceVenueScraper):
    """Scraper for Zebulon via its public DICE venue page."""

    REGION = 'beyond'

    VENUE_NAME = 'Zebulon'
    VENUE_ADDRESS = '2478 Fletcher Dr, Los Angeles, CA 90039'
    VENUE_LAT = 34.1071933
    VENUE_LNG = -118.2547325

    BASE_URL = 'https://zebulon.la'
    EVENTS_URL = 'https://zebulon.la'
    LISTING_URL = 'https://dice.fm/venue/zebulon-y8bv'

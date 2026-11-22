"""
Scraper for Townhouse & Del Monte (Venice).
Source: https://dice.fm/venue/townhouse-venice-d8ve

Historic Windward Ave bar with live jazz, DJ nights and comedy. Its calendar is
ticketed through DICE, so events come from the public DICE venue page (see
DiceVenueScraper). Venice is inside the Westside coverage box.
"""
from .dice_venue import DiceVenueScraper


class TownhouseVeniceScraper(DiceVenueScraper):
    """Scraper for Townhouse & Del Monte via its public DICE venue page."""

    VENUE_NAME = 'Townhouse & Del Monte'
    VENUE_ADDRESS = '52 Windward Ave, Venice, CA 90291'
    VENUE_LAT = 33.9871405
    VENUE_LNG = -118.4725959

    BASE_URL = 'https://www.townhousevenice.com'
    EVENTS_URL = 'https://www.townhousevenice.com'
    LISTING_URL = 'https://dice.fm/venue/townhouse-venice-d8ve'

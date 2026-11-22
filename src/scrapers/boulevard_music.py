"""
Scraper for Boulevard Music (Culver City).
Source: https://www.boulevardmusic.com/events/

Boulevard Music is a guitar shop and listening room at 4316 Sepulveda Blvd whose
calendar runs on WordPress + The Events Calendar ("Tribe"), so we read the
plugin's REST API rather than parsing the rendered calendar:

    /wp-json/tribe/events/v1/events?start_date=<today>&per_page=50&status=publish

Two quirks of this particular install shape the code:

  * Every event's ``venue`` field is an empty list -- the shop never created a
    Tribe venue record -- so venue name/address/coordinates are fixed constants
    here rather than read from the payload.
  * ``start_date``/``end_date`` come back as naive strings already in
    America/Los_Angeles (``timezone`` confirms it), which is exactly the shape
    create_event() treats as canonical, so no timezone conversion is needed.

The parsing itself lives in the shared TribeEventsScraper base class.
"""
from .tribe_events import TribeEventsScraper


class BoulevardMusicScraper(TribeEventsScraper):
    """Scraper for Boulevard Music events (Tribe Events REST API)."""

    SOURCE_NAME = 'Boulevard Music'
    BASE_URL = 'https://www.boulevardmusic.com'
    EVENTS_URL = f'{BASE_URL}/events/'

    # Single fixed venue (Culver City, inside the coverage area).
    VENUE_NAME = 'Boulevard Music'
    VENUE_ADDRESS = '4316 Sepulveda Blvd, Culver City, CA 90230'
    VENUE_LAT = 34.0043483
    VENUE_LNG = -118.4092163

    # Everything here is a concert unless the shop tags it otherwise, so Music
    # is the default rather than trusting the shared auto-classifier on bare
    # performer names.
    DEFAULT_CATEGORY = 'Music'
    CATEGORY_RULES = (
        ('workshop', 'Education'),
        ('class', 'Education'),
        ('lesson', 'Education'),
        ('comedy', 'Comedy'),
    )

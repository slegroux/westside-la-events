"""
Configuration settings for the LA Events Aggregator.
Loads settings from environment variables or uses defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
BASE_DIR = Path(__file__).parent

# Google Maps API Keys
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
GOOGLE_GEOCODING_API_KEY = os.getenv('GOOGLE_GEOCODING_API_KEY', '')

# Event Platform API Keys
EVENTBRITE_API_TOKEN = os.getenv('EVENTBRITE_API_TOKEN', '')
MEETUP_API_KEY = os.getenv('MEETUP_API_KEY', '')
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN', '')

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/events.db')

# Scraper Configuration
SCRAPER_CONFIG = {
    'user_agent': os.getenv(
        'SCRAPER_USER_AGENT',
        'Mozilla/5.0 (compatible; LAEventsBot/1.0)'
    ),
    'delay_seconds': int(os.getenv('SCRAPER_DELAY_SECONDS', '1')),
    'timeout_seconds': int(os.getenv('SCRAPER_TIMEOUT_SECONDS', '30')),
}

# Scheduler Configuration
SCRAPER_SCHEDULE = os.getenv('SCRAPER_SCHEDULE', '0 3 * * *')  # Daily at 3 AM

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')

# Web Server Configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8000'))
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# Westside LA Geographic Bounds
# Approximate boundaries for filtering events
# Includes: Santa Monica, Venice, Westwood, Brentwood, Pacific Palisades,
#           West LA, Culver City, Inglewood (SoFi Stadium, Intuit Dome, Kia Forum)
WESTSIDE_BOUNDS = {
    'min_lat': 33.94,   # South boundary (includes Inglewood venues)
    'max_lat': 34.15,   # North boundary
    'min_lng': -118.55, # West boundary (Pacific coast)
    'max_lng': -118.25  # East boundary (includes Culver City & Inglewood)
}

# Westside LA Center (for map default)
MAP_CENTER = {
    'lat': 34.0522,
    'lng': -118.4437
}

# Event Categories
CATEGORIES = [
    'Music',
    'Art',
    'Food & Drink',
    'Sports',
    'Family',
    'Theater',
    'Comedy',
    'Film',
    'Nightlife',
    'Wellness',
    'Community',
    'Education',
    'Date Night',
    'Other'
]

# Event Sources Configuration
EVENT_SOURCES = {
    'santa_monica': {
        'name': 'Santa Monica',
        'url': 'https://www.smgov.net/events',
        'enabled': True
    },
    'timeout': {
        'name': 'Timeout LA',
        'url': 'https://www.timeout.com/los-angeles/things-to-do/things-to-do-in-los-angeles-this-week',
        'enabled': True
    },
    'kcrw': {
        'name': 'KCRW',
        'url': 'https://www.kcrw.com/events',
        'enabled': True
    },
    'discover_la': {
        'name': 'Discover LA',
        'url': 'https://www.discoverlosangeles.com/events',
        'enabled': True
    },
    'ucla': {
        'name': 'UCLA',
        'url': 'https://events.ucla.edu',
        'enabled': True
    },
    'hammer': {
        'name': 'Hammer Museum',
        'url': 'https://hammer.ucla.edu/events',
        'enabled': True
    },
    'lacma': {
        'name': 'LACMA',
        'url': 'https://www.lacma.org/events',
        'enabled': True
    },
    # Web-scrapable sources (no API key needed)
    'eventbrite': {
        'name': 'Eventbrite',
        'url': 'https://www.eventbrite.com/d/ca--los-angeles/events/',
        'enabled': True,
        'uses_api': False  # We scrape the public listings
    },
    'meetup': {
        'name': 'Meetup',
        'url': 'https://www.meetup.com/find/events/?location=us--ca--los-angeles',
        'enabled': True,
        'uses_api': False  # We scrape Apollo GraphQL state from Next.js
    },
    'venice_west': {
        'name': 'The Venice West',
        'url': 'https://www.thevenicewest.com/calendar',
        'enabled': True,
        'uses_api': False  # We scrape the Webflow calendar page
    },
    'winston_house': {
        'name': 'Winston House',
        'url': 'https://www.winstonhouse.com/schedule',
        'enabled': False,  # Venue permanently closed as of 2025
        'uses_api': False,
        'note': 'Permanently closed after NYE 2024/2025. Events were announced on Instagram.'
    },
    'westside_comedy': {
        'name': "M.I.'s Westside Comedy Theater",
        'url': 'https://westsidecomedy.com/tickets/',
        'enabled': True,
        'uses_api': False,  # Uses WordPress WFEA plugin for event display
        'note': 'Comedy shows on Santa Monica 3rd Street Promenade'
    },
    'aviator_nation': {
        'name': 'Aviator Nation Dreamland',
        'url': 'https://aviatornationdreamland.com/pages/event-calendar-custom',
        'enabled': False,  # Events captured via Eventbrite scraper instead
        'uses_api': False,
        'note': 'Malibu music venue. Events posted on Eventbrite and Bandsintown. Eventbrite scraper catches these automatically.'
    },
    'gnarwhal': {
        'name': 'Gnarwhal Coffee',
        'url': 'https://www.gnarwhalcoffee.com/events',
        'enabled': True,
        'uses_api': True,  # Uses Squarespace API for event listings
        'note': 'Coffee shop on Main Street Santa Monica with community events'
    },
    'venice_beach': {
        'name': 'Venice Beach Events',
        'url': 'https://www.venicebeach.com/events/',
        'enabled': True
    },
    'weho': {
        'name': 'West Hollywood',
        'url': 'https://www.weho.org/city-government/city-departments/public-facilities/events',
        'enabled': True
    },
    'culver_city': {
        'name': 'Culver City',
        'url': 'https://www.culvercity.org/Services/Events',
        'enabled': True
    }
}

# Geocoding Cache Settings
GEOCODE_CACHE_FILE = 'data/geocode_cache.json'

# Search Settings
DEFAULT_SEARCH_LIMIT = 100
MAX_SEARCH_RESULTS = 500

# Map Settings
MAP_ZOOM_DEFAULT = 11
MAP_MARKER_CLUSTER_THRESHOLD = 50

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
ANALYTICS_DB_PATH = os.getenv('ANALYTICS_DB_PATH', 'data/analytics.db')

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

# Session Configuration
# In production, set this to a strong random key via environment variable
SESSION_SECRET_KEY = os.getenv('SESSION_SECRET_KEY', 'dev-secret-key-change-in-production')

# Analytics Configuration
ENABLE_ANALYTICS = os.getenv('ENABLE_ANALYTICS', 'True').lower() == 'true'
ANALYTICS_RETENTION_DAYS = int(os.getenv('ANALYTICS_RETENTION_DAYS', '365'))  # Keep data for 1 year

# Westside LA Geographic Bounds
# Approximate boundaries for filtering events
# Includes: Santa Monica, Venice, Westwood, Brentwood, Pacific Palisades, Malibu
#           West LA, Culver City, Marina del Rey, Playa Vista, Mar Vista
#           Inglewood (SoFi Stadium, Intuit Dome, Kia Forum)
# Excludes: Downtown LA, Echo Park, Silver Lake, Koreatown, Hollywood
WESTSIDE_BOUNDS = {
    'min_lat': 33.93,   # South boundary (includes Inglewood venues)
    'max_lat': 34.15,   # North boundary (Santa Monica Mountains, includes Malibu)
    'min_lng': -118.75, # West boundary (Pacific coast, includes Malibu)
    'max_lng': -118.33  # East boundary (west of La Cienega, excludes Downtown/Echo Park)
}

# Enable geographic filtering by default
ENABLE_GEOGRAPHIC_FILTERING = os.getenv('ENABLE_GEOGRAPHIC_FILTERING', 'True').lower() == 'true'

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
    'Tech',
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
    'laist': {
        'name': 'LAist',
        'url': 'https://laist.com/events',
        'enabled': True,
        'uses_api': False,
        'note': 'LAist events at The Crawford Family Forum and other venues'
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
    'penmar': {
        'name': 'The Penmar',
        'url': 'https://www.eventbrite.com/o/world-of-sound-productions-34157573931',
        'enabled': True,
        'uses_api': False,  # Scrapes Eventbrite organizer page
        'note': 'Penmar Golf Course venue in Venice hosting Sunset Vibes Silent Disco and Sunset Sessions'
    },
    'itk_la': {
        'name': 'ITK LA',
        'url': 'https://itk.la',
        'enabled': True,
        'uses_api': False,  # Scrapes curated events calendar
        'note': 'Curated LA events calendar covering music, comedy, DJ, art, and misc events citywide'
    },
    'nerd_nite': {
        'name': 'Nerd Nite LA',
        'url': 'https://la.nerdnite.com',
        'enabled': True,
        'uses_api': False,  # Scrapes homepage for next event
        'note': 'Monthly educational entertainment event - 20-minute fun presentations across all disciplines'
    },
    'resident_advisor': {
        'name': 'Resident Advisor',
        'url': 'https://ra.co/events/us/losangeles',
        'enabled': False,  # Blocked by Cloudflare CAPTCHA protection
        'uses_api': False,
        'note': 'Leading electronic music platform. Currently blocked by Cloudflare CAPTCHA - requires CAPTCHA bypass solutions to work.'
    },
    'iic_la': {
        'name': 'IIC Los Angeles',
        'url': 'https://iiclosangeles.esteri.it/en/gli_eventi/calendario/',
        'enabled': True,
        'uses_api': False,
        'note': 'Italian Cultural Institute of Los Angeles - cultural events, film screenings, exhibitions, and Italian language classes'
    },
    'afdela': {
        'name': 'Alliance Française de Los Angeles',
        'url': 'https://www.afdela.org/events/',
        'enabled': True,
        'uses_api': False,
        'note': 'French cultural center offering film screenings, cultural events, workshops, and French language classes'
    },
    'raymond_kabbaz': {
        'name': 'Théâtre Raymond Kabbaz',
        'url': 'https://www.theatreraymondkabbaz.com/upcoming-events',
        'enabled': True,
        'uses_api': False,
        'note': 'Cultural theater venue on Pico Boulevard featuring music, film, dance, and theatrical performances'
    },
    'ucla_botanical': {
        'name': 'UCLA Mathias Botanical Garden',
        'url': 'https://www.botgard.ucla.edu/garden-events-news/',
        'enabled': True,
        'uses_api': False,
        'note': 'UCLA botanical garden featuring workshops, classes, tours, plant sales, and educational events'
    },
    'parks_ca': {
        'name': 'California State Parks',
        'url': 'https://www.parks.ca.gov/Events',
        'enabled': True,
        'uses_api': False,
        'note': 'California State Parks events in Angeles District (Malibu Creek SP, Malibu Lagoon SB, Santa Monica Mountains, etc.)'
    },
    'kinn': {
        'name': 'KINN',
        'url': 'https://luma.com/KINNevents',
        'enabled': True,
        'uses_api': False,
        'note': 'AI and technology community events hosted by KINN, listed on their Luma page'
    },
    'casual_creative': {
        'name': 'The Casual Creative',
        'url': 'https://luma.com/thecasualcreative?k=c',
        'enabled': True,
        'uses_api': False,
        'note': 'Pop-up experiences and creative workshops in Los Angeles, listed on Luma'
    },
    'latechevents': {
        'name': 'LA Tech Events',
        'url': 'https://luma.com/latechevents?k=c',
        'enabled': True,
        'uses_api': False,
        'note': 'LA tech community events calendar hosted on Luma'
    },
    'beyond_baroque': {
        'name': 'Beyond Baroque',
        'url': 'https://www.eventbrite.com/o/beyond-baroque-literary-arts-center-1685240682',
        'enabled': True,
        'uses_api': False,
        'note': 'Venice-based literary arts center featuring poetry, fiction workshops, and book launches'
    },
    'apero_francophone': {
        'name': 'Apero Francophone',
        'url': 'https://www.eventbrite.com/o/apero-francophone-de-los-angeles-59137584493',
        'enabled': True,
        'uses_api': False,
        'note': 'Monthly afterwork gatherings for French expats and locals, featuring networking, food, drinks, and DJ entertainment'
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
    'aero_theater': {
        'name': 'Aero Theater',
        'url': 'https://www.americancinematheque.com/now-showing/?event_location=54',
        'enabled': True,
        'uses_api': False,
        'note': 'American Cinematheque venue in Santa Monica showing classic, independent, and international films'
    },
    'laemmle_monica': {
        'name': 'Laemmle Monica Film Center',
        'url': 'https://www.laemmle.com/theater/monica-film-center',
        'enabled': True,
        'uses_api': False,
        'note': 'Independent and art house cinema on 2nd Street in Santa Monica'
    },
    'mudwtr': {
        'name': 'MUD\\WTR :gather',
        'url': 'https://www.mudwtrgather.com/schedule',
        'enabled': True,
        'uses_api': False,
        'note': 'Mushroom cafe and mindfulness studio offering yoga, meditation, breathwork classes and special events. Schedule via Mindbody integration.'
    },
    'culver_city': {
        'name': 'Culver City',
        'url': 'https://www.culvercity.org/Services/Events',
        'enabled': True
    },
    'getty_center': {
        'name': 'Getty Center',
        'url': 'https://www.getty.edu/visit/calendar/',
        'enabled': True,
        'uses_api': False,
        'note': 'Major art museum in Brentwood featuring exhibitions, film screenings, lectures, and tours. Free admission.'
    },
    'getty_villa': {
        'name': 'Getty Villa',
        'url': 'https://www.getty.edu/visit/calendar/',
        'enabled': True,
        'uses_api': False,
        'note': 'Ancient art museum in Pacific Palisades with exhibitions and educational programs. Free admission with timed tickets.'
    },
    'skirball': {
        'name': 'Skirball Cultural Center',
        'url': 'https://www.skirball.org/programs/public-programs',
        'enabled': True,
        'uses_api': False,
        'note': 'Cultural center in Brentwood featuring film, music, performances, lectures, and special events'
    },
    'geffen_playhouse': {
        'name': 'Geffen Playhouse',
        'url': 'https://geffenplayhouse.org/tickets/',
        'enabled': True,
        'uses_api': False,
        'note': 'Premier theater in Westwood presenting new and classic plays'
    },
    'broad_stage': {
        'name': 'The Broad Stage',
        'url': 'https://www.thebroadstage.org/events',
        'enabled': True,
        'uses_api': False,
        'note': 'Performing arts venue at SMC featuring theater, dance, music, and comedy'
    },
    'nuart_theatre': {
        'name': 'Nuart Theatre',
        'url': 'https://www.landmarktheatres.com/los-angeles/nuart-theatre',
        'enabled': True,
        'uses_api': False,
        'note': 'Classic independent cinema in West LA showing art house and cult films'
    },
    'mccabes': {
        'name': "McCabe's Guitar Shop",
        'url': 'https://www.mccabes.com/concerts-landing/',
        'enabled': True,
        'uses_api': False,
        'note': 'Legendary folk music venue in Santa Monica featuring intimate concerts'
    },
    'bergamot_station': {
        'name': 'Bergamot Station Arts Center',
        'url': 'https://bergamotstation.com/exhibitions',
        'enabled': True,
        'uses_api': False,
        'note': 'Gallery complex in Santa Monica hosting art exhibitions across multiple galleries'
    },
    'fowler_museum': {
        'name': 'UCLA Fowler Museum',
        'url': 'https://fowler.ucla.edu/events/',
        'enabled': True,
        'uses_api': False,
        'note': 'UCLA museum featuring global arts and cultures with lectures, screenings, and workshops'
    },
    'sm_farmers_market': {
        'name': 'Santa Monica Farmers Markets',
        'url': 'https://www.santamonica.gov/categories/programs/farmers-market',
        'enabled': True,
        'uses_api': False,
        'note': 'Weekly farmers markets at multiple Santa Monica locations (Wednesday, Saturday, Sunday)'
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

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
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Session Configuration
# In production, set this to a strong random key via environment variable
SESSION_SECRET_KEY = os.getenv('SESSION_SECRET_KEY', 'dev-secret-key-change-in-production')

# Admin authentication for analytics routes (HTTP Basic Auth).
# Keep disabled by default for now; set ENABLE_ADMIN_AUTH=true to enforce.
ENABLE_ADMIN_AUTH = os.getenv('ENABLE_ADMIN_AUTH', 'False').lower() == 'true'
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '').strip()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '').strip()

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
    'min_lat': 33.90,   # South boundary (includes Inglewood and El Segundo venues)
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
        'enabled': False,  # smgov.net/events redirects to permit info; replaced by santamonica_events
    },
    'santamonica_events': {
        'name': 'Visit Santa Monica',
        'url': 'https://www.santamonica.com/events/',
        'enabled': True,
        'uses_api': False,
        'note': 'Official Visit Santa Monica events calendar'
    },
    'arcana_books': {
        'name': 'Arcana Books',
        'url': 'https://www.arcanabooks.com/blog/?cat=events',
        'enabled': True,
        'uses_api': False,
        'note': 'Arcana: Books on the Arts event announcements'
    },
    'village_well': {
        'name': 'Village Well Books & Coffee',
        'url': 'https://villagewell.com/calendar',
        'enabled': True,
        'uses_api': True,
        'note': 'Culver City bookstore/cafe events via the Bookmanager events API (SAN 9916539)'
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
        'enabled': False,  # Disabled 2026-06-04: events.ucla.edu is ~140 mostly-internal
        # campus-admin items ("End-of-Term Grading", "Career Center Drop-Ins") that also
        # misgeocode (bare "Los Angeles, CA 90095" -> downtown -> filtered out). Public UCLA
        # culture is already covered by hammer / fowler_museum / ucla_botanical / ucla_design.
        # Re-enable only with per-event geocoding + a public/cultural quality filter.
    },
    'ucla_design': {
        'name': 'UCLA Design Media Arts',
        'url': 'https://www.design.ucla.edu/events',
        'enabled': True,
        'uses_api': False,
        'note': 'UCLA Design Media Arts exhibitions, lectures, and events (Broad Art Center, Westwood)'
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
        'name': 'Aviator Nation (Eventbrite)',
        'url': 'https://www.eventbrite.com/o/aviator-nation-77562713843',
        'enabled': True,
        'uses_api': False,
        'note': 'Aviator Nation Venice events via Eventbrite (retail store events).'
    },
    'aviator_dreamland': {
        'name': 'Aviator Nation Dreamland',
        'url': 'https://aviatornationdreamland.com/pages/event-calendar-custom',
        'enabled': True,
        'uses_api': False,
        'note': 'Iconic Malibu music venue featuring live performances and ticketed events. Custom Shopify calendar with tixr.com ticketing.'
    },
    'gnarwhal': {
        'name': 'Gnarwhal Coffee',
        'url': 'https://www.gnarwhalcoffee.com/events',
        'enabled': False,  # Website only shows newsletter signup form — no events calendar
        'uses_api': True,
        'note': 'Coffee shop on Main Street Santa Monica with community events'
    },
    'penmar': {
        'name': 'The Penmar',
        'url': 'https://www.eventbrite.com/o/world-of-sound-productions-34157573931',
        'enabled': True,
        'uses_api': False,  # Scrapes Eventbrite organizer page
        'note': 'Penmar Golf Course venue in Venice hosting Sunset Vibes Silent Disco and Sunset Sessions. Audited 2026-06-04: returns 0 when its current Eventbrite events are in Hermosa Beach (outside the Westside fence) — working, not broken.'
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
        'note': 'Monthly educational entertainment event - 20-minute fun presentations across all disciplines. Audited 2026-06-04: returns 0 when the monthly event is at a non-Westside venue (e.g. Brewyard/Glendale) — working, not broken.'
    },
    'resident_advisor': {
        'name': 'Resident Advisor',
        'url': 'https://ra.co/events/us/losangeles',
        'enabled': False,  # Blocked by Cloudflare CAPTCHA protection
        'uses_api': False,
        'note': 'Leading electronic music platform. Currently blocked by Cloudflare CAPTCHA - requires CAPTCHA bypass solutions to work.'
    },
    'io_music_academy': {
        'name': 'IO Music Academy LA',
        'url': 'https://ra.co/clubs/282834',
        'enabled': True,
        'uses_api': True,
        'note': "Free DJ/music-production workshops at IO Music Academy's Hollywood campus, via the Resident Advisor GraphQL API. Hollywood is outside the Westside box; the venue is allowlisted in geo_filter.WESTSIDE_VENUE_ALLOWLIST by the owner's choice."
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
        'note': 'Pop-up experiences and creative workshops in Los Angeles, listed on Luma. Audited 2026-06-04: returns 0 when its Luma events are outside the Westside fence — working, not broken.'
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
        'url': 'https://www.visitveniceca.com/calendar-2/',
        'enabled': False,  # visitveniceca.com returns empty page — no events calendar available
    },
    'weho': {
        'name': 'West Hollywood',
        'url': 'https://www.weho.org/city-government/city-departments/public-facilities/events',
        'enabled': False,  # weho.org returns 403 for all event endpoints (CloudFlare blocking)
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
    },
    'william_turner': {
        'name': 'William Turner Gallery',
        'url': 'https://www.williamturnergallery.com/events',
        'enabled': True,
        'uses_api': False,
        'note': 'Contemporary art gallery at Bergamot Station featuring exhibitions and art events. Audited 2026-06-04: /events is a past-exhibition archive; returns 0 when no upcoming opening/talk is listed — working, not broken.'
    },
    'sounds_like_la': {
        'name': 'Sounds Like LA',
        'url': 'https://soundslikela.org/calendar/',
        'enabled': True,
        'uses_api': False,
        'note': 'Free public music series in LA parks featuring local artists'
    },
    'old_town_music_hall': {
        'name': 'Old Town Music Hall',
        'url': 'https://prod5.agileticketing.net/websales/pages/list.aspx?epguid=046f24e9-20f3-4095-9ab6-2596f53377e0&',
        'enabled': False,  # Shelved. Two reasons were recorded; only the second still holds:
        # (1) Agile Ticketing sat behind Imperva/Incapsula bot protection (edet=12 JS challenge).
        #     As of 2026-08-10 this no longer blocks -- a direct run returns 59 upcoming events.
        # (2) The venue is in El Segundo, outside the Westside geo-fence. This is the reason it
        #     stays off, so re-enabling is a coverage decision, not a scraper fix.
        'uses_api': False,
        'note': 'Historic cinema and music venue in El Segundo showing classic films and live performances with Wurlitzer organ'
    },
    'papille_gustative': {
        'name': 'Papille Gustative',
        'url': 'https://papillegustativela.com/santa-monica-main-street-santa-monica-papille-gustative-events',
        'enabled': False,  # Domain does not resolve — website appears to be offline
        'uses_api': False,
        'note': 'Farm-to-table cafe-restaurant on Santa Monica Blvd featuring seasonal events and holiday celebrations'
    },
    'recreation_cafe': {
        'name': 'Recreation Cafe',
        'url': 'https://www.recreation.cafe/events-1',
        'enabled': True,
        'uses_api': False,
        'note': 'Social club and cafe in LA offering community events, workshops, and creative meetups'
    },
    'jamesons_pub': {
        'name': "Jameson's Pub - Santa Monica",
        'url': 'https://santamonica.jamesonsirishpub.com/santa-monica-jameson-s-pub-santa-monica-events',
        'enabled': True,
        'uses_api': False,
        'note': 'Authentic Irish pub in Santa Monica featuring sports viewing, holiday celebrations, live music, and pub events'
    },
    'shore_hotel': {
        'name': 'Shore Hotel',
        'url': 'https://www.shorehotel.com/events',
        'enabled': True,
        'uses_api': True,
        'note': 'Oceanfront hotel in Santa Monica curating a local events calendar of concerts, farmers markets, festivals, and more'
    },
    'downtown_sm': {
        'name': 'Downtown Santa Monica',
        'url': 'https://downtownsm.com/events-calendar',
        'enabled': True,
        'uses_api': False,
        'note': 'Official Downtown Santa Monica events calendar covering live music, markets, arts, and community events'
    },
    'smdp': {
        'name': 'Santa Monica Daily Press',
        'url': 'https://www.smdp.com/events/',
        'enabled': False,  # Shelved 2026-05-29: the /events/feed/ RSS is abandoned — newest item
        # is ~175 days old, the rest 1.5-2 years. Scraper correctly refuses to backdate them, so it
        # always yields 0. Re-enable only if SMDP publishes a fresh events feed/listing.
        'uses_api': False,
        'note': 'Santa Monica Daily Press events coverage via RSS feed'
    },
    'bungalow_sm': {
        'name': 'The Bungalow Santa Monica',
        'url': 'https://thebungalow.com/santa-monica/happenings/',
        'enabled': True,
        'uses_api': False,
        'note': 'Popular Santa Monica bar and event venue featuring weekly trivia, DJ nights, themed parties, and community events'
    },
    'fairmont_miramar': {
        'name': 'Fairmont Miramar Hotel',
        'url': 'https://www.fairmont-miramar.com/explore/events-calendar/',
        'enabled': True,
        'uses_api': True,
        'note': 'Landmark oceanfront hotel in Santa Monica offering live music, jazz nights, afternoon tea, holiday events, and seasonal experiences'
    },
    'unlikely_collaborators': {
        'name': 'Unlikely Collaborators',
        'url': 'https://www.salons.unlikelycollaborators.com/',
        'enabled': True,
        'uses_api': False,
        'note': 'Free Spark Salons (consciousness/neuroscience/psychology/arts talks) held in person in Santa Monica (1520 2nd St) and streamed online; venue hardcoded since the site reveals it only on Eventbrite'
    },
    'losangelesfunevents': {
        'name': 'Los Angeles Fun Events',
        'url': 'https://www.losangelesfunevents.com/weary-livers',
        'enabled': True,
        'uses_api': False,
        'note': 'Off the Couch Adventures LLC recurring events (musicians nights, karaoke, comedy, singles socials, watch parties) at Weary Livers, 2819 Pico Blvd, Santa Monica; events parsed from the Wix data blob embedded in the listing page'
    },
    'corner_door': {
        'name': 'The Corner Door',
        'url': 'https://www.the-corner-door.com/upcoming-events',
        'enabled': True,
        'uses_api': False,
        'note': 'Culver City bar (12477 Washington Blvd) with DJ/vinyl nights, comedy, and trivia; events are hand-authored Squarespace content blocks with weekday+month.day dates (year inferred from the weekday)'
    },
    'boulevard_music': {
        'name': 'Boulevard Music',
        'url': 'https://www.boulevardmusic.com/events/',
        'enabled': True,
        'uses_api': True,
        'note': 'Culver City guitar shop and listening room (4316 Sepulveda Blvd); concerts read from The Events Calendar REST API (/wp-json/tribe/events/v1/events). The API carries no venue record, so venue name/address/coordinates are constants in the scraper'
    },
    'culver_steps': {
        'name': 'The Culver Steps',
        'url': 'https://theculversteps.com/happenings/',
        'enabled': True,
        'uses_api': False,
        'note': "Free public programming at the Culver Steps plaza (9300 Culver Blvd): sunset yoga, kids' play mornings, summer concerts. Hand-authored WPBakery cards with undated free-text schedules; years are inferred from the stated weekday and weekly series are expanded per occurrence. Open-ended series with no end date are skipped rather than projected forward"
    },

    # These four shipped with working scrapers, tests and logos but no entry
    # here, so `registry.get_enabled_scraper_names()` -- which reads this dict --
    # silently never ran them. A scraper missing from EVENT_SOURCES is dead code
    # that looks alive: it fails no test and logs no error. All four are Santa
    # Monica venues whose events pass the geo filter.
    'brightside': {
        'name': 'Brightside California Kitchen',
        'url': 'https://brightsidecaliforniakitchen.com/events',
        'enabled': True,
        'uses_api': False,
        'note': 'Santa Monica restaurant (2901 Ocean Park Blvd) hosting live music, trivia and community nights'
    },
    'la_puglia': {
        'name': 'La Puglia',
        'url': 'https://lapuglia.us/events',
        'enabled': True,
        'uses_api': False,
        'note': 'Italian restaurant in Santa Monica (2830 Ocean Park Blvd) with live music and supper-club evenings'
    },
    'tripp': {
        'name': 'Tripp',
        'url': 'https://www.tripsantamonica.com/trip-santa-monica-events',
        'enabled': True,
        'uses_api': False,
        # Reads the "Weekly Shows" page, NOT /calendar. The calendar is an
        # eventscalendar.co widget in an iframe that only loads data with a
        # Wix-signed `instance` token, so /calendar contains no events at all --
        # pointing here is what took this scraper from 0 events to working.
        'note': 'TRiP Santa Monica (2101 Lincoln Blvd), a bar/music room with standing weekly nights (Friday trivia, Monday open mic). Weekly shows are expanded into occurrences over an 8-week horizon since the source gives no end date'
    },
    'victorian': {
        'name': 'The Victorian',
        'url': 'https://www.thevictorian.com/what-s-on',
        'enabled': True,
        'uses_api': False,
        'note': 'Historic Main Street venue in Santa Monica (2640 Main St) hosting music, markets and private events'
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
# The map plots every matching event as a clustered pin, so it is not bound by
# the list view's page size (DEFAULT_SEARCH_LIMIT). Leaflet.markercluster
# handles thousands of markers; this cap just bounds the JSON payload.
MAP_MAX_EVENTS = int(os.getenv('MAP_MAX_EVENTS', '5000'))


# ---------------------------------------------------------------------------
# Startup configuration validation
# ---------------------------------------------------------------------------
def validate_config():
    """Emit warnings for risky or incomplete configuration at startup.

    Non-fatal by design: the app still boots, but operators get a clear signal
    when a security-relevant setting is misconfigured. Called from the web app
    lifespan startup.
    """
    import logging
    logger = logging.getLogger(__name__)
    is_production = os.getenv('ENVIRONMENT') == 'production'

    # Admin auth enabled but credentials missing -> every admin request 401s.
    if ENABLE_ADMIN_AUTH and (not ADMIN_USERNAME or not ADMIN_PASSWORD):
        logger.warning(
            'ENABLE_ADMIN_AUTH is true but ADMIN_USERNAME/ADMIN_PASSWORD are '
            'unset; the admin analytics dashboard will reject ALL requests. '
            'Set both env vars or disable ENABLE_ADMIN_AUTH.'
        )

    # Admin auth disabled in production -> analytics dashboard is public.
    if is_production and not ENABLE_ADMIN_AUTH:
        logger.warning(
            'Running in production with ENABLE_ADMIN_AUTH disabled; '
            '/admin/analytics is publicly accessible. Set ENABLE_ADMIN_AUTH=true '
            'plus ADMIN_USERNAME/ADMIN_PASSWORD to protect it.'
        )

    # Default session secret in production -> session cookies are forgeable.
    if is_production and SESSION_SECRET_KEY == 'dev-secret-key-change-in-production':
        logger.warning(
            'SESSION_SECRET_KEY is using the insecure development default in '
            'production; set a strong random SESSION_SECRET_KEY env var.'
        )

    return True

# Software Design Document (SDD)
## Westside LA Events Aggregator

**Version:** 2.0
**Date:** January 2025
**Author:** Development Team

---

## 1. Overview

### 1.1 Purpose
The Westside LA Events Aggregator is a production-ready web application that aggregates events from 35+ sources across LA's Westside and Malibu, providing a unified search interface with intelligent filtering, map visualization, privacy-friendly analytics, and comprehensive event details.

### 1.2 Scope
- **Audience**: LA Westside and Malibu residents, visitors, and event organizers
- **Geographic Focus**: Santa Monica, West Hollywood, Culver City, Venice, Malibu, UCLA area
- **Event Types**: Music, art, food & drink, sports, family activities, theater, comedy, film, nightlife, wellness, community, education, tech, date night
- **Data Sources**: 35+ event sources including city calendars, venues, cultural institutions, ticketing platforms, and community groups
- **Key Features**: Full-text search, date/category/source filtering, map visualization, event details, calendar export, favorites, analytics dashboard

### 1.3 Technology Stack
- **Backend Framework**: FastHTML (Python-based web framework with HTMX integration)
- **Database**: SQLite with FTS5 (Full-Text Search) + separate analytics database
- **Web Scrapers**: BeautifulSoup4, requests, Playwright (for JavaScript-heavy sites)
- **Geocoding**: Nominatim (OpenStreetMap) - 100% free, no API key required
- **Maps**: Leaflet 1.9.4 + OpenStreetMap tiles (no API key required) with MarkerCluster
- **Frontend**: HTMX 2.0.3 for dynamic updates, minimal custom JavaScript
- **Testing**: pytest, pytest-playwright for E2E tests
- **Environment**: micromamba for Python environment management (`la` environment)

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Web Browser                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │  HTMX    │  │ Leaflet  │  │  Analytics Tracker   │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────┬───────────────────────────────────────────────┘
          │ HTTP/HTMX
┌─────────▼───────────────────────────────────────────────┐
│         FastHTML Web Application (src/web/)             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  app.py      │  │ analytics_   │  │  Components   │ │
│  │  (Routes)    │  │  routes.py   │  │  (FastHTML)   │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘ │
└─────────┼──────────────────┼──────────────────────────┬─┘
          │                  │                          │
┌─────────▼──────────────────▼────────────┐  ┌──────────▼──────┐
│       Business Logic Layer              │  │  Static Files   │
│  ┌────────────┐  ┌──────────────────┐   │  │  (CSS/JS/logos) │
│  │ EventSearch│  │  Utilities       │   │  └─────────────────┘
│  │ (query.py) │  │  - categories.py │   │
│  └────────────┘  │  - geocoding.py  │   │
│                  │  - geo_filter.py │   │
│                  │  - deduplication │   │
│                  │  - logo_scraper  │   │
│                  └──────────────────┘   │
└─────────┬────────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────────┐
│               Data Layer (src/data/)              │
│  ┌──────────────┐  ┌──────────────┐              │
│  │ database.py  │  │ analytics.py │              │
│  │ (events.db)  │  │(analytics.db)│              │
│  │ - events     │  │ - page_views │              │
│  │ - events_fts │  │ - event_     │              │
│  │   (FTS5)     │  │   interactions              │
│  │              │  │ - search_    │              │
│  │              │  │   queries    │              │
│  │              │  │ - sessions   │              │
│  │              │  │ - daily_     │              │
│  │              │  │   metrics    │              │
│  └──────────────┘  └──────────────┘              │
└───────────────────────────────────────────────────┘
          │
┌─────────▼─────────────────────────────────────────┐
│      Data Collection Layer (src/scrapers/)        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  base.py │  │ 35 Active│  │ Disabled │        │
│  │  (Base   │  │ Scrapers │  │ Scrapers │        │
│  │  Class)  │  │          │  │ (3)      │        │
│  └──────────┘  └──────────┘  └──────────┘        │
│                                                    │
│  Parallel execution (ThreadPoolExecutor, 10 max)  │
│  Rate limiting, retry logic, error handling       │
└────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
LA/
├── README.md                    # Project overview and quick start
├── PLAN.md                      # Development roadmap
├── CLAUDE.md                    # AI assistant instructions
├── SDD.md                       # This document
├── config.py                    # Configuration settings
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Dev/test dependencies
├── pytest.ini                   # pytest configuration
├── run_scrapers.py              # Batch scraper execution script
│
├── docs/                        # Technical documentation
│   ├── ANALYTICS.md             # Analytics system documentation
│   ├── EVENT_SOURCES.md         # Event sources guide
│   ├── SCRAPING_GUIDE.md        # Web scraping best practices
│   ├── LOGO_MANAGEMENT.md       # Source logo management
│   ├── QUICK_REFERENCE.md       # FastHTML quick reference
│   ├── GITHUB_WORKFLOW.md       # GitHub issue/milestone workflow
│   ├── fasthtml_analysis.md    # FastHTML implementation analysis
│   ├── TEST_COVERAGE_ANALYSIS.md
│   └── COVERAGE_SUMMARY.md
│
├── src/
│   ├── data/                    # Data models and database
│   │   ├── models.py            # Event dataclass model
│   │   ├── database.py          # SQLite operations (FTS5)
│   │   └── analytics.py         # Analytics tracking (privacy-friendly)
│   │
│   ├── scrapers/                # Event source scrapers (33 total)
│   │   ├── base.py              # Base scraper class
│   │   ├── santa_monica.py      # smgov.net
│   │   ├── timeout.py           # timeout.com/los-angeles
│   │   ├── kcrw.py              # kcrw.com/events
│   │   ├── laist.py             # laist.com/events
│   │   ├── discover_la.py       # discoverlosangeles.com
│   │   ├── eventbrite.py        # eventbrite.com
│   │   ├── meetup.py            # meetup.com (GraphQL)
│   │   ├── ucla.py              # events.ucla.edu
│   │   ├── hammer.py            # hammer.ucla.edu
│   │   ├── lacma.py             # lacma.org
│   │   ├── westside_comedy.py   # westsidecomedy.com
│   │   ├── beyond_baroque.py    # Eventbrite organizer
│   │   ├── apero_francophone.py # Eventbrite organizer
│   │   ├── venice_beach.py      # venicebeach.com/events
│   │   ├── west_hollywood.py    # weho.org
│   │   ├── culver_city.py       # culvercity.org
│   │   ├── kinn.py              # luma.com/KINNevents
│   │   ├── latechevents.py      # luma.com/latechevents
│   │   └── ... (15 more active scrapers)
│   │
│   ├── search/                  # Search functionality
│   │   └── query.py             # EventSearch class
│   │
│   ├── utils/                   # Utility services
│   │   ├── categories.py        # Auto-classification
│   │   ├── geocoding.py         # Nominatim geocoding
│   │   ├── geo_filter.py        # Location validation
│   │   ├── deduplication.py     # Duplicate detection
│   │   └── logo_scraper.py      # Logo downloading
│   │
│   └── web/                     # Web application
│       ├── app.py               # App setup, lifespan, error handlers
│       ├── state.py             # AppState singleton, session/analytics helpers
│       ├── components.py        # All UI component functions
│       ├── services.py          # Business logic (_fetch_events, tallies cache)
│       ├── analytics_routes.py  # Analytics admin dashboard
│       └── routes/              # Route modules
│           ├── main.py          # Home page
│           ├── events.py        # Event list, map, update-all, JSON API
│           ├── filters.py       # Filter tallies, date picker, category
│           ├── favorites.py     # Favorites add/remove
│           └── api.py           # Admin API, static files, favicon
│
├── static/                      # Frontend assets
│   ├── css/
│   │   └── style.css            # Main stylesheet (CSS variables)
│   ├── js/
│   │   ├── map.js               # Leaflet map integration
│   │   ├── filters.js           # Filter collapse state & HTMX handlers
│   │   └── analytics.js         # Client-side analytics tracking
│   ├── logos/                   # Downloaded source logos (cached)
│   │   ├── santa_monica.png
│   │   ├── timeout.png
│   │   └── ... (30+ logos)
│   └── favicon.ico
│
├── tests/                       # Test suite
│   ├── README.md                # Comprehensive testing guide
│   ├── conftest.py              # Shared fixtures (DB, search, mocks)
│   ├── unit/                    # Unit tests
│   │   ├── test_database.py     # Database operations
│   │   ├── test_search.py       # Search functionality
│   │   ├── test_scrapers.py     # Scraper validation
│   │   └── test_web_app.py      # Route testing
│   ├── e2e/                     # End-to-end tests (Playwright)
│   │   ├── test_homepage.py
│   │   ├── test_search_filters.py
│   │   ├── test_event_detail.py
│   │   ├── test_map_interactions.py
│   │   └── test_htmx_interactions.py
│   └── scrapers/                # Scraper-specific tests
│       └── test_kcrw.py
│
├── data/                        # Runtime data
│   ├── events.db                # Main SQLite database
│   ├── analytics.db             # Analytics database
│   └── geocode_cache.json       # Geocoding cache
│
└── .github/                     # GitHub workflows
    ├── workflows/
    └── ISSUE_TEMPLATE/
```

---

## 3. Data Layer

### 3.1 Database Schema

**Database File:** `data/events.db`

**Table: events**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Event ID |
| title | TEXT | NOT NULL | Event title |
| description | TEXT | | Event description (full HTML/text) |
| venue_name | TEXT | | Venue name |
| address | TEXT | | Full address |
| latitude | REAL | | Geographic latitude |
| longitude | REAL | | Geographic longitude |
| event_date | DATETIME | | Event start date/time |
| end_date | DATETIME | | Event end date/time |
| category | TEXT | | Event category (auto-classified) |
| source | TEXT | NOT NULL | Data source name (scraper) |
| url | TEXT | | Original event URL |
| image_url | TEXT | | Event image URL |
| source_logo_url | TEXT | | Source logo path |
| price | REAL | | Ticket price (if known) |
| is_free | BOOLEAN | DEFAULT 0 | Free event flag |
| price_note | TEXT | | Price description/note |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record update time |

**Virtual Table: events_fts (FTS5)**

Full-text search index on:
- `title`
- `description`
- `venue_name`

**Auto-sync triggers** maintain consistency between `events` and `events_fts` tables.

**Indexes:**
- `idx_event_date` on `event_date` (date filtering)
- `idx_category` on `category` (category filtering)
- `idx_source` on `source` (source filtering)
- `idx_location` on `(latitude, longitude)` (map bounds queries)
- `idx_is_free` on `is_free` (free events filter)

### 3.2 Event Model

```python
@dataclass
class Event:
    title: str
    source: str
    id: Optional[int] = None
    description: Optional[str] = None
    venue_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    event_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    category: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source_logo_url: Optional[str] = None
    price: Optional[float] = None
    is_free: bool = False
    price_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### 3.3 Database Operations (database.py)

**Initialization:**
- `init_db()` - Create schema with FTS5 triggers

**CRUD Operations:**
- `insert_event(event: Event) -> int` - Add new event with duplicate detection
- `update_event(event: Event) -> bool` - Update existing event
- `get_event(event_id: int) -> Optional[Event]` - Fetch single event
- `delete_event(event_id: int) -> bool` - Remove event
- `get_all_events(limit: int, offset: int) -> List[Event]` - Paginated retrieval

**Search & Query:**
- `search_events(query_str, filters, limit, offset) -> List[Event]` - Complex search with filters
- `get_upcoming_events(days: int) -> List[Event]` - Filter by future dates
- `get_events_by_date_range(start, end) -> List[Event]` - Date range queries
- `event_exists(url: str, event_date: datetime) -> bool` - Check if event exists
- `find_duplicate_event(event: Event) -> Optional[Event]` - Two-phase duplicate detection

**Category Management:**
- `update_event_category(event_id: int, category: str) -> bool` - Update category

**FTS Security:**
- `sanitize_fts_query(query: str) -> str` - Wrap user input in quotes to prevent operator injection

**Duplicate Detection Logic:**
1. **Phase 1**: Exact URL match + date tolerance (fastest)
2. **Phase 2**: Fuzzy title/venue matching within 24-hour window (fallback)

### 3.4 Analytics Database Schema

**Database File:** `data/analytics.db`

**Tables:**

1. **page_views** - Page load tracking
   - `id`, `session_id`, `path`, `referrer`, `user_agent`, `ip_hash` (SHA256), `created_at`
   - Indexed by: `session_id`, `path`, `created_at`

2. **event_interactions** - User event engagement
   - `id`, `session_id`, `event_id`, `interaction_type` (view/click/favorite/unfavorite/calendar), `source`, `category`, `created_at`
   - Indexed by: `event_id`, `session_id`, `interaction_type`, `created_at`

3. **search_queries** - Search behavior
   - `id`, `session_id`, `query`, `date_filter`, `categories`, `sources`, `free_only`, `results_count`, `created_at`
   - Indexed by: `session_id`, `query`, `created_at`

4. **sessions** - User session aggregation
   - `session_id` (PRIMARY KEY), `first_seen`, `last_seen`, `page_views`, `events_viewed`, `events_clicked`, `searches`
   - Indexed by: `first_seen`, `last_seen`

5. **daily_metrics** - Pre-aggregated daily stats
   - `date` (PRIMARY KEY), `unique_visitors`, `page_views`, `events_viewed`, `events_clicked`, `searches`, `favorites_added`
   - Indexed by: `date`

**Privacy Features:**
- IP addresses hashed with SHA256 (never stored in plaintext)
- No cross-site tracking
- No external analytics services
- Anonymous sessions (UUID-based)
- Configurable data retention (default 365 days)

---

## 4. Search Layer

### 4.1 EventSearch Class (src/search/query.py)

Provides comprehensive search functionality with:
- Full-text search using SQLite FTS5
- Date range filtering (today, tomorrow, this week, this weekend, this month, upcoming, specific date)
- Category filtering (multi-select)
- Source filtering (multi-select)
- Price filtering (free events only)
- Favorites filtering (session-based)
- Combined query builder with dynamic SQL generation
- Result limiting and pagination

### 4.2 Date Filters

| Filter | Description | SQL Condition |
|--------|-------------|---------------|
| `upcoming` | All future events | `event_date >= DATE('now')` |
| `today` | Events today | `DATE(event_date) = DATE('now')` |
| `tomorrow` | Events tomorrow | `DATE(event_date) = DATE('now', '+1 day')` |
| `this_week` | Next 7 days | `event_date BETWEEN now AND now+7 days` |
| `this_weekend` | Upcoming Sat-Sun | Custom weekend calculation (next Sat/Sun or today/tomorrow if weekend) |
| `this_month` | Current month | `strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now')` |
| `specific_date` | User-selected date | `DATE(event_date) = ?` |

### 4.3 Category System

**Predefined Categories (15 total):**

1. **Music** - Concerts, live performances, DJ sets
2. **Art** - Galleries, exhibitions, art walks
3. **Food & Drink** - Tastings, food festivals, dining events
4. **Sports** - Fitness classes, sports events, outdoor activities
5. **Family** - Kid-friendly events, family activities
6. **Theater** - Plays, performances, theater productions
7. **Comedy** - Stand-up, improv, comedy shows
8. **Film** - Screenings, film festivals, cinema events
9. **Nightlife** - Bars, clubs, late-night events
10. **Wellness** - Yoga, meditation, wellness workshops
11. **Community** - Neighborhood events, meetups, civic activities
12. **Education** - Workshops, classes, lectures
13. **Tech** - Tech meetups, hackathons, startup events
14. **Date Night** - Romantic events, couples activities
15. **Other** - Uncategorized events

**Classification:** Automated using weighted keyword matching on title/description with venue-based overrides (see [categories.py:51](src/utils/categories.py#L51)).

---

## 5. Scraper Layer

### 5.1 Base Scraper Architecture (src/scrapers/base.py)

All scrapers inherit from `BaseScraper` which provides:

```python
class BaseScraper:
    def __init__(self, source_name: str, enabled: bool = True)

    # Abstract method (must implement)
    def scrape(self) -> List[Event]

    # HTTP methods
    def fetch_page(self, url: str, retry: int = 3) -> str
    def fetch_page_js(self, url: str, wait_selector: str, timeout: int) -> str

    # Parsing
    def parse_html(self, html: str) -> BeautifulSoup

    # Event creation with auto-features
    def create_event(self, **kwargs) -> Optional[Event]
        # - Automatic geocoding via Nominatim
        # - Automatic category classification
        # - Location validation (Westside/Malibu bounds)
        # - Source logo downloading/caching

    # Utility methods
    def clean_text(self, text: str) -> str
    def normalize_url(self, url: str, base: str) -> str
    def log(self, message: str)
```

**Key Features:**
- **Rate limiting** with configurable delays
- **Retry mechanism** with exponential backoff
- **User-Agent headers** to identify scraper
- **Playwright support** for JavaScript-heavy sites (Meetup, Eventbrite dynamic content)
- **Error handling** with comprehensive logging
- **Graceful degradation** (one scraper failure doesn't block others)

### 5.2 Implemented Scrapers (33 Total, 30 Active)

| # | Scraper | Source | Type | Status | Notes |
|---|---------|--------|------|--------|-------|
| 1 | Santa Monica | smgov.net/events | HTML | ✅ Active | Municipal events |
| 2 | Timeout LA | timeout.com/los-angeles | HTML | ✅ Active | Curated LA events |
| 3 | KCRW | kcrw.com/events | HTML | ✅ Active | Public radio programming |
| 4 | LAist | laist.com/events | HTML | ✅ Active | Local journalism events |
| 5 | Discover LA | discoverlosangeles.com | HTML | ✅ Active | Tourism board |
| 6 | Eventbrite | eventbrite.com (location search) | HTML | ✅ Active | Major ticketing platform |
| 7 | Meetup | meetup.com (GraphQL API) | API | ✅ Active | Community groups |
| 8 | UCLA | events.ucla.edu | HTML | ✅ Active | University events |
| 9 | Hammer Museum | hammer.ucla.edu | HTML | ✅ Active | Art museum |
| 10 | LACMA | lacma.org/events | HTML | ✅ Active | Art museum |
| 11 | Venice West | thevenicewest.com | HTML | ✅ Active | Comedy venue |
| 12 | Westside Comedy | westsidecomedy.com | HTML | ✅ Active | Comedy shows |
| 13 | Gnarwhal Coffee | gnarwhalcoffee.com (Squarespace API) | API | ✅ Active | Coffee shop events |
| 14 | Penmar Golf | eventbrite.com/o/34157573931 | HTML | ✅ Active | Golf course venue |
| 15 | ITK LA | itk.la | HTML | ✅ Active | Curated events |
| 16 | Nerd Nite LA | la.nerdnite.com | HTML | ✅ Active | Monthly talks |
| 17 | IIC Los Angeles | iiclosangeles.esteri.it | HTML | ✅ Active | Italian cultural institute |
| 18 | Alliance Française | afdela.org | HTML | ✅ Active | French cultural center |
| 19 | Théâtre Raymond Kabbaz | theatreraymondkabbaz.com | HTML | ✅ Active | Cultural theater |
| 20 | UCLA Botanical Garden | botgard.ucla.edu | HTML | ✅ Active | Botanical events |
| 21 | California State Parks | parks.ca.gov/Events (Malibu) | HTML | ✅ Active | State park events |
| 22 | KINN | luma.com/KINNevents | HTML | ✅ Active | Tech/AI community |
| 23 | LA Tech Events | luma.com/latechevents | HTML | ✅ Active | Tech community |
| 24 | Beyond Baroque | eventbrite.com/o/1685240682 | HTML | ✅ Active | Literary arts |
| 25 | Apero Francophone | eventbrite.com/o/59137584493 | HTML | ✅ Active | French networking |
| 26 | Venice Beach Events | venicebeach.com/events | HTML | ✅ Active | Beach events |
| 27 | West Hollywood | weho.org | HTML | ✅ Active | City events |
| 28 | Culver City | culvercity.org | HTML | ✅ Active | City events |
| 29 | (Reserved slot) | - | - | - | - |
| 30 | (Reserved slot) | - | - | - | - |
| 31 | Winston House | winstonhouse.com | HTML | ❌ Disabled | Permanently closed (NYE 2024/2025) |
| 32 | Aviator Nation | aviatornationdreamland.com | HTML | ❌ Disabled | Events via Eventbrite instead |
| 33 | Resident Advisor | ra.co | HTML | ❌ Disabled | Cloudflare CAPTCHA blocks access |

**Total Events/Week:** ~500-800 events depending on season

### 5.3 Scraper Execution

**Manual Execution:**
```bash
micromamba run -n la python run_scrapers.py
```

**Parallel Execution:**
- Uses `ThreadPoolExecutor` with max 10 workers
- Scrapers run concurrently for faster execution
- Independent failure handling (one scraper failure doesn't block others)

**Error Handling:**
- Graceful failure with detailed logging
- Retry logic with exponential backoff (3 retries default)
- Exception capture and reporting
- Success/failure tracking per scraper

**Rate Limiting:**
- Configurable delays between requests (default 1 second)
- Per-source rate limits
- Respect robots.txt
- User-Agent identification

**Logging:**
- Timestamped logs per scraper
- Success/failure counts
- Event counts per scraper
- Error messages with stack traces

---

## 6. Web Application Layer

### 6.1 FastHTML Application (src/web/app.py)

**Framework:** FastHTML (Python-based web framework with HTMX integration)

**Key Technologies:**
- **Server-side rendering** with Python functions
- **HTMX 2.0.3** for dynamic updates without full page reloads
- **Component-based architecture** (functions return HTML)
- **Minimal JavaScript** (only map.js and analytics.js)
- **Session management** with secure cookies

### 6.2 Main Routes (src/web/app.py)

| Route | Method | Description | Returns | HTMX |
|-------|--------|-------------|---------|------|
| `/` | GET | Home page with search and filters | HTML | - |
| `/events/list` | GET | Events list (grid of cards) | HTML fragment | ✅ |
| `/filters/tallies` | GET | Updated filter counts | HTML fragment | ✅ |
| `/filters/date-picker` | GET | Conditional date picker | HTML fragment | ✅ |
| `/filters/category/{category}` | GET | Single category filter update | HTML fragment | ✅ |
| `/filters/update-all` | GET | Multi-filter batch update | HTML fragment | ✅ |
| `/view/list` | GET | Switch to list view | HTML fragment | ✅ |
| `/view/map` | GET | Switch to map view | HTML fragment | ✅ |
| `/event/{event_id}` | GET | Event detail page | HTML | - |
| `/event/{event_id}/calendar` | GET | Export event as .ics file | iCal file | - |
| `/favorites/add/{event_id}` | POST | Add to session favorites | HTML fragment | ✅ |
| `/favorites/remove/{event_id}` | DELETE | Remove from favorites | HTML fragment | ✅ |
| `/api/events` | GET | Events JSON API | JSON | - |
| `/api/events/{event_id}` | GET | Single event JSON | JSON | - |
| `/api/track/click/{event_id}` | POST | Track external link click | 204 No Content | - |
| `/static/{filepath:path}` | GET | Static file serving | File (CSS/JS/images) | - |

**Error Handling:**
- Custom 404 page
- Custom 500 page
- General exception handler with debug mode toggle

### 6.3 Analytics Routes (src/web/analytics_routes.py)

| Route | Method | Description | Returns |
|-------|--------|-------------|---------|
| `/admin/analytics` | GET | Analytics dashboard | HTML |
| `/admin/analytics/api` | GET | Analytics data (JSON) | JSON |

**Dashboard Features:**
- Date range selector (last 7/30/90 days)
- Metrics: Unique visitors, page views, events viewed/clicked, CTR, searches
- Session stats: Avg pages/session, avg events/session, bounce rate
- Charts: Daily visitors (Chart.js), event interactions
- Data tables: Top events, popular searches, category popularity, source performance

### 6.4 Components (FastHTML Functions)

**Layout Components:**
- `page_head(title, description)` - HTML head with meta tags, CSS/JS includes
- `page_header()` - Site header with title and subtitle
- `page_footer()` - Site footer with credits
- `htmx_loading_indicator()` - Spinner during async HTMX operations

**Event Components:**
- `event_card(event, is_favorite)` - Single event card with favorite button
- `events_list(events, favorites)` - Grid of event cards
- `event_location_map(event)` - Leaflet map for single event detail page

**Search Components:**
- `search_section(filters, tallies)` - Sidebar with all filters
- `filter_tallies_section(tallies, filters)` - Category/source counts with checkboxes
- `filter_section_collapsible(title, content)` - Expandable filter groups

**Map Components:**
- `map_view(events)` - Leaflet map with clustered markers (MarkerCluster plugin)

### 6.5 Filter System

**Date Filters:**
- Upcoming (default)
- Today
- Tomorrow
- This Week
- This Weekend
- This Month
- Specific Date (date picker)

**Category Filters (Multi-select):**
- 15 predefined categories
- Dynamic counts per category
- Checkbox-based multi-select

**Source Filters (Multi-select):**
- Dynamic list of enabled scrapers
- Source logos displayed
- Checkbox-based multi-select

**Other Filters:**
- Free Events Only (toggle)
- My Favorites Only (session-based)

**HTMX Integration:**
- All filters update dynamically without full page reload
- Debounced search input (500ms)
- Loading indicators during updates
- URL state preservation (query params)

### 6.6 Frontend Technologies

**CSS:**
- Custom styles with CSS variables for theming
- Responsive design (mobile-first)
- Grid layouts for event cards
- Collapsible filter sections

**JavaScript Files:**
1. **map.js** - Leaflet map integration
   - Initialize map with OpenStreetMap tiles
   - Add event markers with popups
   - MarkerCluster plugin for performance
   - Fit bounds to show all markers

2. **analytics.js** - Client-side analytics tracking
   - Track page views
   - Track event clicks
   - Track searches
   - Send data to `/api/track/*` endpoints

**External Libraries:**
- **HTMX 2.0.3** - Dynamic updates (CDN)
- **Leaflet 1.9.4** - Map visualization (CDN)
- **Leaflet.markercluster 1.5.3** - Marker clustering (CDN)
- **Chart.js 4.4.0** - Analytics dashboard charts (CDN)

---

## 7. Utility Services

### 7.1 Geocoding Service (src/utils/geocoding.py)

**Purpose:** Convert addresses to geographic coordinates (latitude/longitude)

**Provider:** Nominatim (OpenStreetMap)
- **100% Free** - No API key required
- **Rate Limit:** 1 request/second (enforced by service)
- **No billing** - Unlimited usage

**Features:**
- Local JSON cache (`data/geocode_cache.json`)
- Automatic rate limiting (1 second delay)
- Error handling with graceful fallback
- Cache hit rate: ~90% after initial scraping

**GeocodingService Class:**
```python
def geocode(address: str) -> Optional[Tuple[float, float]]:
    # Returns (latitude, longitude) or None
    # 1. Check cache first
    # 2. If miss, call Nominatim API
    # 3. Save to cache
    # 4. Return coordinates
```

### 7.2 Geo Filtering (src/utils/geo_filter.py)

**Purpose:** Validate that events are within Westside LA/Malibu geographic bounds

**Method:**
1. **Primary**: Latitude/longitude bounds checking (fast)
2. **Fallback**: Fuzzy matching on venue/address names (when coordinates missing)

**Westside LA Bounds (from config.py):**
- North: 34.08 (Pacific Palisades)
- South: 33.96 (Marina del Rey)
- West: -118.51 (Malibu coast)
- East: -118.36 (West Hollywood)

**Usage:**
- Called automatically by `BaseScraper.create_event()`
- Returns `None` for events outside bounds
- Filters out ~10-15% of scraped events

### 7.3 Category Classifier (src/utils/categories.py)

**Purpose:** Automatically categorize events based on content analysis

**Method:**
- **Weighted keyword matching** on title + description
- **Venue-based overrides** (e.g., "Staples Center" → Music)
- **Strong indicators** for Date Night category (romantic, couples, intimate)

**Category Keywords Map:**
```python
CATEGORY_KEYWORDS = {
    'Music': ['concert', 'music', 'band', 'jazz', 'dj', 'live music', ...],
    'Art': ['art', 'gallery', 'exhibition', 'museum', 'artist', ...],
    'Food & Drink': ['food', 'wine', 'tasting', 'restaurant', 'brewery', ...],
    'Comedy': ['comedy', 'stand-up', 'improv', 'comedian', ...],
    # ... 15 categories total
}
```

**classify_event() Function:**
1. Extract keywords from title + description
2. Score each category based on keyword matches
3. Apply venue overrides
4. Check for strong Date Night indicators
5. Return highest-scoring category (or "Other" if low confidence)

### 7.4 Deduplication (src/utils/deduplication.py)

**Purpose:** Detect and prevent duplicate events from multiple sources

**Two-Phase Detection:**

1. **Phase 1: URL Matching (Primary)**
   - Exact URL match with date tolerance (±24 hours)
   - Fastest method
   - Catches events from same source

2. **Phase 2: Fuzzy Matching (Fallback)**
   - Title similarity (Levenshtein distance)
   - Venue name similarity
   - Date tolerance window (default 24 hours)
   - Catches events from different sources

**Usage:**
```python
duplicate = find_duplicate_event(new_event)
if duplicate:
    update_event(duplicate.id, new_event)
else:
    insert_event(new_event)
```

### 7.5 Logo Scraper (src/utils/logo_scraper.py)

**Purpose:** Download and cache source logos locally

**Features:**
- Downloads logos from event source websites
- Saves to `static/logos/{source_name}.{ext}`
- Fallback to text if logo download fails
- Automatic file extension detection
- Used in event cards to show source attribution

**download_source_logo() Function:**
```python
def download_source_logo(source_name: str, logo_url: str) -> str:
    # Returns local path: /static/logos/{source_name}.png
    # Or empty string if download fails
```

---

## 8. Analytics System (src/data/analytics.py)

### 8.1 Overview

**Philosophy:** Privacy-friendly, local analytics with no third-party services

**Key Principles:**
- ✅ All data stored locally in SQLite
- ✅ No external tracking services (no Google Analytics, etc.)
- ✅ IP addresses hashed (SHA256) - never stored in plaintext
- ✅ Anonymous sessions (UUID-based, no user accounts)
- ✅ No cross-site tracking
- ✅ Configurable data retention (default 365 days)
- ✅ GDPR/CCPA friendly

### 8.2 Tracked Metrics

**Page Views:**
- Session ID, path, referrer, user agent, IP hash, timestamp

**Event Interactions:**
- Session ID, event ID, interaction type (view/click/favorite/unfavorite/calendar)
- Source, category, timestamp

**Search Queries:**
- Session ID, query text, date filter, categories, sources, free_only flag
- Results count, timestamp

**Session Aggregates:**
- Session ID, first seen, last seen
- Page views count, events viewed count, events clicked count, searches count

**Daily Metrics (Pre-aggregated):**
- Date, unique visitors, page views
- Events viewed, events clicked, searches, favorites added

### 8.3 Key Analytics Methods

**Tracking:**
- `track_page_view(session_id, path, referrer, user_agent, ip)` - Record page view
- `track_event_interaction(session_id, event_id, type, source, category)` - Record interaction
- `track_search(session_id, query, date_filter, categories, sources, free_only, results_count)` - Record search

**Reporting:**
- `get_daily_metrics(date)` - Daily stats for specific date
- `get_date_range_metrics(start_date, end_date)` - Multi-day stats
- `get_popular_events(limit, start_date, end_date)` - Top events by views/clicks
- `get_popular_searches(limit, start_date, end_date)` - Most searched queries
- `get_category_popularity(start_date, end_date)` - Category engagement
- `get_source_performance(start_date, end_date)` - Source click-through rates
- `get_session_stats(start_date, end_date)` - Session averages, bounce rate

### 8.4 Analytics Dashboard

**Route:** `/admin/analytics`

**Features:**
- Date range selector (last 7/30/90 days or custom)
- High-level metrics cards
- Session statistics
- Daily visitors chart (Chart.js line chart)
- Event interactions chart (Chart.js bar chart)
- Data tables:
  - Top 20 events by views/clicks
  - Popular searches
  - Category popularity
  - Source performance (impressions, clicks, CTR)

**Security:**
- No authentication (add in production!)
- IP-based access control recommended

---

## 9. Configuration (config.py)

### 9.1 Environment Variables

Stored in `.env` (not committed to git):

```bash
# API Keys (optional, using free alternatives)
GOOGLE_MAPS_API_KEY=           # Not used (using Leaflet + OSM)
GOOGLE_GEOCODING_API_KEY=      # Not used (using Nominatim)
EVENTBRITE_API_TOKEN=          # Optional (scraping works without it)
MEETUP_API_KEY=                # Optional (using GraphQL public API)

# Database
DATABASE_PATH=data/events.db
ANALYTICS_DB_PATH=data/analytics.db

# Web Server
HOST=0.0.0.0
PORT=8000
DEBUG=True

# Analytics
ENABLE_ANALYTICS=True
ANALYTICS_RETENTION_DAYS=365

# Session
SESSION_SECRET_KEY=your-secret-key-here

# Scraper Settings
SCRAPER_DELAY_SECONDS=1
SCRAPER_TIMEOUT_SECONDS=30
SCRAPER_RETRY_COUNT=3
```

### 9.2 Configuration File Structure

**config.py** provides:

**Database Settings:**
- SQLite database paths
- Connection configuration
- FTS5 settings

**Scraper Settings:**
- User agent string
- Delay between requests (1 second default)
- Timeout (30 seconds default)
- Retry count (3 default)
- Enabled/disabled scrapers list

**Web Server Settings:**
- Host (0.0.0.0 for remote access)
- Port (8000 default)
- Debug mode
- Session secret key

**Geographic Bounds:**
- Westside LA bounding box coordinates
- Malibu extension

**Map Settings:**
- Default center (Santa Monica)
- Default zoom level (12)
- Marker clustering enabled

**Categories:**
- 15 predefined category definitions
- Category keywords mapping

**Event Sources:**
- 33 configured scrapers with enable/disable flags
- Source logo URLs
- Source display names

**Analytics:**
- Enable/disable flag
- Data retention period (days)
- Tracking endpoints

---

## 10. Deployment

### 10.1 Environment Setup

**Using micromamba:**

1. Create environment:
   ```bash
   micromamba create -n la python=3.11 -y
   micromamba activate la
   pip install -r requirements.txt
   ```

2. Install Playwright browsers (for JS-heavy scraping):
   ```bash
   micromamba run -n la playwright install chromium
   ```

3. Initialize databases:
   ```bash
   micromamba run -n la python -c "from src.data.database import init_db; from src.data.analytics import init_analytics_db; init_db(); init_analytics_db()"
   ```

### 10.2 Running the Application

**Development Server (with auto-reload):**
```bash
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

**Production Server:**
```bash
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --workers 4
```

**Run Scrapers:**
```bash
micromamba run -n la python run_scrapers.py
```

**Schedule Scrapers (cron example):**
```bash
# Run scrapers daily at 6 AM
0 6 * * * cd /path/to/LA && micromamba run -n la python run_scrapers.py >> /var/log/la-scrapers.log 2>&1
```

### 10.3 Production Considerations

**Docker Deployment:**
- Create Dockerfile with micromamba base image
- Multi-stage build for smaller image
- Include Playwright dependencies
- Environment variable injection

**Web Server:**
- Use nginx as reverse proxy
- SSL/TLS with Let's Encrypt
- Rate limiting on API endpoints
- Static file serving via nginx (bypass FastHTML)

**Database:**
- Regular backups (daily recommended)
- Vacuum database periodically
- Monitor database size
- Consider PostgreSQL for large-scale deployment

**Monitoring:**
- Health check endpoint (`/health`)
- Error tracking (Sentry recommended)
- Uptime monitoring
- Scraper success rate tracking

**Logging:**
- Centralized logging (syslog, CloudWatch, etc.)
- Log rotation
- Error alerting
- Performance metrics

**Security:**
- Add authentication to `/admin/analytics`
- Rate limiting on all endpoints
- CSRF protection
- Input validation and sanitization
- Regular dependency updates

---

## 11. Testing Strategy

### 11.1 Test Suite Overview

**Framework:** pytest with async support (pytest-asyncio)

**Coverage:** ~60-70% code coverage

**Test Types:**
1. **Unit Tests** (`tests/unit/`)
   - Database operations
   - Search functionality
   - Scraper validation
   - Web routes

2. **Integration Tests** (mixed in `tests/unit/`)
   - Full workflow testing
   - Database + search + web integration

3. **E2E Tests** (`tests/e2e/`)
   - Playwright browser automation
   - User flow testing
   - HTMX interaction testing
   - Map functionality testing

4. **Scraper Tests** (`tests/scrapers/`)
   - Scraper-specific validation
   - Mock HTTP responses
   - Data format verification

### 11.2 Shared Fixtures (tests/conftest.py)

**Database Fixtures:**
- `temp_db_path` - Temporary database file (auto-cleanup)
- `db` - Test database instance
- `populated_db` - Database with sample events (music, art, food, past events)

**Search Fixtures:**
- `search` - EventSearch instance for testing

**Sample Data:**
- `sample_event` - Single test event
- `sample_events` - Multiple test events (4 total)

**Mock Services:**
- `mock_geocoding_service` - Mock Nominatim (no actual API calls)
- `temp_geocode_cache` - Temporary cache file

**Web Testing:**
- `app_client` - AsyncClient for FastHTML app
- `base_url` - Test server URL
- `e2e_db` - Populated database for E2E tests

**Playwright:**
- `browser_context_args` - Browser viewport settings (1280x720)
- Automatic browser/page fixtures from pytest-playwright

### 11.3 Running Tests

**All Tests:**
```bash
micromamba run -n la python -m pytest tests/ -v
```

**Unit Tests Only:**
```bash
micromamba run -n la python -m pytest tests/unit/ -v
```

**E2E Tests (requires running server):**
```bash
# Terminal 1: Start server
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Run E2E tests
micromamba run -n la python -m pytest tests/e2e/ -v
```

**Specific Marker:**
```bash
micromamba run -n la python -m pytest -m e2e
```

**With Coverage:**
```bash
micromamba run -n la python -m pytest tests/ --cov=src --cov-report=html
```

**Avoiding ROS Conflicts:**
```bash
# Unset PYTHONPATH to avoid ROS interference
bash -c 'unset PYTHONPATH; micromamba run -n la python -m pytest tests/unit/test_database.py -v'
```

### 11.4 Test Configuration (pytest.ini)

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: Unit tests
    integration: Integration tests
    scraper: Scraper tests
    e2e: End-to-end tests
    slow: Slow-running tests
    requires_network: Tests requiring network access
    requires_db: Tests requiring database
    requires_api: Tests requiring external API

asyncio_mode = auto

# Block problematic plugins
required_plugins = pytest-asyncio pytest-playwright
blocked_plugins = rostest launch_testing dash.testing
```

---

## 12. Security Considerations

### 12.1 Implemented Security Measures

**Input Validation:**
- ✅ FTS query sanitization (user input wrapped in quotes to prevent operator injection)
- ✅ Static file path traversal protection
- ✅ URL normalization in scrapers

**Session Security:**
- ✅ Secure session cookies with configurable secret key
- ✅ HTTP-only cookies (JavaScript cannot access)
- ✅ SameSite cookie attribute

**Analytics Privacy:**
- ✅ IP address hashing (SHA256) - never stored in plaintext
- ✅ No external tracking services
- ✅ Anonymous sessions (UUID-based)
- ✅ No cross-site tracking

**Error Handling:**
- ✅ Custom error pages (404, 500)
- ✅ No sensitive information in error messages
- ✅ Debug mode toggle (disable in production)

**API Security:**
- ✅ JSON API with read-only access
- ✅ No authentication required for public data

### 12.2 Recommended Improvements

**Critical:**
- ⚠️ Add authentication to `/admin/analytics` dashboard
- ⚠️ Implement rate limiting on API endpoints
- ⚠️ Add CSRF protection for forms (favorites, etc.)
- ⚠️ Sanitize HTML in event descriptions (XSS prevention)

**Important:**
- Add Content Security Policy (CSP) headers
- Implement HTTPS-only in production
- Add CORS headers for API endpoints (if needed for external clients)
- Regular security audits of dependencies
- Implement request size limits
- Add honeypot fields to prevent bot submissions

**Best Practices:**
- Rotate session secret key periodically
- Monitor for suspicious activity
- Implement API key rotation (if using external APIs)
- Add logging for security events
- Regular penetration testing

### 12.3 API Key Management

**Current Practice:**
- Store in `.env` file (gitignored)
- Never commit to version control
- Use environment variables in production

**Recommendations:**
- Use secrets management service (AWS Secrets Manager, HashiCorp Vault)
- Rotate keys periodically
- Implement key rotation without downtime
- Audit key usage
- Revoke unused keys

---

## 13. Performance Considerations

### 13.1 Database Optimization

**Implemented:**
- ✅ FTS5 indexes for full-text search (fast)
- ✅ Indexes on frequently queried columns (event_date, category, source, location, is_free)
- ✅ Efficient query structure with proper joins
- ✅ Connection context managers (auto-close)
- ✅ Pagination support (limit/offset)

**Recommendations:**
- Add query result caching (Redis or in-memory)
- Connection pooling for high-traffic scenarios
- Regular VACUUM operations
- Monitor slow queries
- Consider PostgreSQL for large-scale deployment (>100k events)

### 13.2 Frontend Performance

**Implemented:**
- ✅ Server-side rendering (fast initial load)
- ✅ HTMX for partial page updates (no full reload)
- ✅ Minimal JavaScript dependencies
- ✅ Leaflet MarkerCluster for map performance (1000+ markers)
- ✅ CSS variables for theming (single repaint)
- ✅ Debounced search input (500ms)

**Recommendations:**
- Add static file caching headers (Cache-Control, ETag)
- Implement CDN for static assets
- Lazy load images (loading="lazy")
- Service worker for offline support
- Compress responses (gzip/brotli)

### 13.3 Scraping Optimization

**Implemented:**
- ✅ Parallel scraper execution (ThreadPoolExecutor, max 10 workers)
- ✅ Cached geocoding results (~90% cache hit rate)
- ✅ Duplicate detection (avoid re-inserting same events)
- ✅ Retry mechanism with exponential backoff

**Recommendations:**
- Incremental updates (only scrape new events, not full re-scrape)
- Adaptive scheduling (scrape more frequently for frequently-updated sources)
- Distributed scraping (multiple workers for large-scale)
- Monitor scraper performance metrics

### 13.4 Analytics Performance

**Implemented:**
- ✅ Separate database for analytics (doesn't slow down main app)
- ✅ Pre-aggregated daily metrics (fast dashboard loading)
- ✅ Indexed columns for common queries

**Recommendations:**
- Add analytics data archiving (move old data to cold storage)
- Implement data retention policy (auto-delete old analytics)
- Consider time-series database for analytics (InfluxDB, TimescaleDB)

---

## 14. Future Enhancements

### 14.1 Phase 2 Features (Planned)

**User Features:**
- User accounts and authentication (OAuth, email/password)
- Persistent favorites (database-backed, not session-based)
- Email notifications for new events (daily/weekly digest)
- Event recommendations based on preferences and past behavior
- User-submitted events (with moderation)

**Technical Features:**
- Advanced filtering (price range, accessibility, outdoor/indoor)
- Multi-language support (Spanish, Chinese, etc.)
- Mobile app (React Native or Flutter)
- Push notifications
- Social features (comments, ratings, event check-ins)

### 14.2 Phase 3 Features (Future)

**Advanced Features:**
- AI-powered event recommendations (ML model)
- Natural language search ("fun outdoor events this weekend")
- Event similarity matching (find similar events)
- Personalized event discovery
- Integration with calendar apps (Google Calendar, Apple Calendar)
- Real-time event updates (WebSocket/SSE)

**Platform Expansion:**
- Expand to other LA neighborhoods (Downtown, Hollywood, Valley)
- Expand to other cities (San Francisco, New York, etc.)
- API for third-party integrations
- White-label solution for other event aggregators

### 14.3 Technical Improvements

**Architecture:**
- Migrate to PostgreSQL (better performance at scale)
- Add Redis caching layer (fast query results)
- Implement GraphQL API (flexible queries)
- Microservices architecture (separate scraper service, web service, analytics service)
- Event-driven architecture (message queue for scraper results)

**DevOps:**
- Kubernetes deployment (auto-scaling, high availability)
- CI/CD pipeline (GitHub Actions, Jenkins)
- Blue-green deployments (zero downtime)
- Infrastructure as Code (Terraform, CloudFormation)
- Monitoring and observability (Prometheus, Grafana, Datadog)

**Performance:**
- CDN for global distribution (CloudFlare, AWS CloudFront)
- Edge computing (scraping at the edge)
- Database sharding (horizontal scaling)
- Async database operations (asyncio + asyncpg)
- Elasticsearch for advanced search (full-text + faceted search)

---

## 15. Maintenance

### 15.1 Regular Tasks

**Daily:**
- ✅ Monitor scraper execution logs
- ✅ Check for scraper failures (review errors)
- ✅ Verify database integrity
- Review analytics dashboard for anomalies

**Weekly:**
- Review error logs (identify patterns)
- Update geocoding cache (if needed)
- Check database size (ensure not growing unexpectedly)
- Review popular searches (identify user needs)
- Test critical user flows

**Monthly:**
- Update Python dependencies (`pip list --outdated`)
- Review and update scraper selectors (websites change)
- Clean old events from database (remove events >6 months old)
- Rotate analytics data (archive or delete old data)
- Security audit (check for vulnerabilities)
- Performance review (identify bottlenecks)

**Quarterly:**
- Review scraper success rates (identify broken scrapers)
- Add new event sources (expand coverage)
- User feedback review (prioritize features)
- Code refactoring (improve maintainability)
- Update documentation

### 15.2 Scraper Maintenance

**Why Scrapers Break:**
- Website redesigns (HTML structure changes)
- CSS class/ID changes
- JavaScript framework updates (React, Vue, etc.)
- Anti-scraping measures (CAPTCHA, rate limiting, IP blocking)
- Website downtime or domain changes

**Monitoring:**
- ✅ Log all scraper errors
- Track success rates per source (events scraped vs. expected)
- Alert on consecutive failures (3+ failures → notification)
- Monitor scraper execution time (detect slowdowns)

**Fixing Broken Scrapers:**
1. **Identify**: Check logs for errors
2. **Inspect**: Visit website in browser, inspect HTML structure
3. **Update**: Modify CSS selectors, XPath, or scraping logic
4. **Test**: Run scraper locally with `python -c "from src.scrapers.{name} import {Name}Scraper; print(len({Name}Scraper().scrape()))"`
5. **Deploy**: Commit changes to git
6. **Document**: Add comment explaining changes

**Example Fix:**
```python
# Old selector (broken)
events = soup.find_all('div', class_='event-card')

# New selector (after website redesign)
events = soup.find_all('article', class_='event-item')

# Add comment
# Updated 2025-01-15: Website redesigned, changed selector from .event-card to .event-item
```

### 15.3 Database Maintenance

**Routine Tasks:**
- VACUUM database (reclaim space, optimize indexes)
- ANALYZE tables (update query planner statistics)
- Backup database (daily recommended)
- Monitor database size
- Archive old events (>6 months)

**Backup Strategy:**
```bash
# Backup events database
cp data/events.db data/backups/events_$(date +%Y%m%d).db

# Backup analytics database
cp data/analytics.db data/backups/analytics_$(date +%Y%m%d).db

# Keep last 30 days of backups
find data/backups/ -name "*.db" -mtime +30 -delete
```

---

## 16. Documentation

### 16.1 Documentation Structure

**Core Documentation:**
- **[README.md](README.md)** - Project overview and quick start guide
- **[PLAN.md](PLAN.md)** - Development roadmap and implementation phases
- **[SDD.md](SDD.md)** - This document (Software Design Document)
- **[CLAUDE.md](CLAUDE.md)** - AI assistant instructions

**Technical Documentation (docs/):**
- **[ANALYTICS.md](docs/ANALYTICS.md)** - Analytics system documentation and usage guide
- **[EVENT_SOURCES.md](docs/EVENT_SOURCES.md)** - Detailed guide on event sources (API vs scraping)
- **[SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md)** - Web scraping best practices and guidelines
- **[LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)** - Source logo management and troubleshooting
- **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - FastHTML best practices and quick fixes
- **[GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)** - GitHub issue tracking and milestone management
- **[fasthtml_analysis.md](docs/fasthtml_analysis.md)** - In-depth FastHTML implementation analysis
- **[TEST_COVERAGE_ANALYSIS.md](docs/TEST_COVERAGE_ANALYSIS.md)** - Test coverage report and gaps
- **[COVERAGE_SUMMARY.md](docs/COVERAGE_SUMMARY.md)** - Test coverage summary

**Testing Documentation:**
- **[tests/README.md](tests/README.md)** - Comprehensive testing guide

**Project Management:**
- **[scripts/README.md](scripts/README.md)** - Automation scripts documentation (if exists)

### 16.2 When to Use Each Document

| Task | Document(s) to Read |
|------|---------------------|
| Starting development | [README.md](README.md) → [PLAN.md](PLAN.md) |
| Understanding architecture | [SDD.md](SDD.md) (this document) |
| Adding a scraper | [docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) → [docs/LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md) |
| Working with FastHTML | [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) |
| Writing tests | [tests/README.md](tests/README.md) |
| Understanding event sources | [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md) |
| Managing issues/milestones | [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md) |
| Troubleshooting logos | [docs/LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md) |
| Setting up analytics | [docs/ANALYTICS.md](docs/ANALYTICS.md) |
| AI assistant guidance | [CLAUDE.md](CLAUDE.md) |

---

## 17. Support and Contact

**Project Repository:** (Add GitHub URL if applicable)
**Issue Tracking:** (Add GitHub Issues URL if applicable)
**Documentation:** See `docs/` directory

**Key Contact Points:**
- Bug reports: GitHub Issues
- Feature requests: GitHub Issues
- Questions: GitHub Discussions (if enabled)

---

## Appendix A: API Reference

### A.1 JSON API Endpoints

**GET /api/events**
- Query Parameters:
  - `query` (string, optional) - Full-text search query
  - `date_filter` (string, optional) - upcoming/today/tomorrow/this_week/this_weekend/this_month
  - `category` (string[], optional) - Category filter (multi-select)
  - `source` (string[], optional) - Source filter (multi-select)
  - `free_only` (boolean, optional) - Free events only
  - `limit` (int, optional, default 50) - Max results
  - `offset` (int, optional, default 0) - Pagination offset
- Returns: `{ "events": [...], "total": int }`

**GET /api/events/{event_id}**
- Returns: `{ "event": {...} }`
- 404 if event not found

### A.2 Python API Reference

See individual module docstrings:
- `src/data/database.py` - Database operations
- `src/data/analytics.py` - Analytics tracking
- `src/search/query.py` - Search functionality
- `src/scrapers/base.py` - Scraper base class
- `src/utils/geocoding.py` - Geocoding service
- `src/utils/categories.py` - Category classification

---

## Appendix B: Database Migrations

**Current Approach:** Direct SQL in `init_db()` function

**Migration Strategy (Future):**
- Consider adding migration framework (Alembic for SQLAlchemy)
- Version-controlled schema changes
- Rollback capability
- Data migrations (not just schema)

**Manual Migration Example:**
```sql
-- Add new column
ALTER TABLE events ADD COLUMN price_tier TEXT;

-- Update FTS trigger (if FTS columns changed)
DROP TRIGGER IF EXISTS events_fts_insert;
CREATE TRIGGER events_fts_insert AFTER INSERT ON events BEGIN
  INSERT INTO events_fts (rowid, title, description, venue_name)
  VALUES (new.id, new.title, new.description, new.venue_name);
END;
```

---

## Appendix C: Troubleshooting

### C.1 Common Issues

**Issue: "Module not found" errors**
- Solution: Always use `micromamba run -n la python` instead of just `python`
- Ensure running from project root directory

**Issue: Port 8000 already in use**
- Solution: `lsof -ti:8000 | xargs kill -9`

**Issue: Scrapers returning 0 events**
- Solution: Check scraper logs, website may have changed, update selectors

**Issue: Geocoding failures**
- Solution: Check `data/geocode_cache.json` for errors, Nominatim may be rate-limiting

**Issue: Database locked**
- Solution: Close all connections, ensure only one process accessing database

**Issue: Tests failing with ROS imports**
- Solution: `bash -c 'unset PYTHONPATH; micromamba run -n la python -m pytest tests/'`

**Issue: HTMX not updating**
- Solution: Check browser console for errors, verify HTMX attributes (hx-get, hx-target, hx-swap)

**Issue: Map not loading**
- Solution: Check browser console, verify Leaflet CDN links, check for JavaScript errors

### C.2 Debug Mode

**Enable Debug Mode:**
```bash
# In .env file
DEBUG=True
```

**Features:**
- Detailed error pages with stack traces
- Auto-reload on code changes
- Verbose logging

**Disable in Production:**
- Never run with `DEBUG=True` in production (security risk)

---

## Appendix D: Key File Locations

**Entry Points:**
- `src/web/app.py` - Main FastHTML application (line 1)
- `run_scrapers.py` - Batch scraper runner (line 1)
- `config.py` - Configuration defaults (line 1)

**Critical Modules:**
- `src/data/database.py` - Database operations (line 1)
- `src/data/analytics.py` - Analytics tracking (line 1)
- `src/scrapers/base.py` - Scraper framework (line 1)
- `src/search/query.py` - Search logic (line 1)

**Configuration:**
- `config.py` - All settings and API keys
- `.env` - Environment variable overrides (gitignored)
- `pytest.ini` - Test configuration

**Static Assets:**
- `static/css/style.css` - Main stylesheet
- `static/js/map.js` - Leaflet map initialization
- `static/js/analytics.js` - Client-side tracking
- `static/logos/` - Downloaded source logos

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-11 | Initial SDD |
| 2.0 | 2025-01-12 | Comprehensive update to reflect production-ready state: 33 scrapers, analytics system, E2E tests, complete feature set |

---

**Document End**

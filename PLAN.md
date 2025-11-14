# Westside LA Events Aggregator - Implementation Plan

## Project Setup

### Initial Setup
- [ ] Create virtual environment
- [ ] Install dependencies (FastHTML, BeautifulSoup4, requests, playwright, APScheduler)
- [ ] Set up project directory structure
- [ ] Initialize git repository
- [ ] Create `.env.example` for API keys

### Directory Structure
```
LA/
├── src/
│   ├── data/
│   │   ├── __init__.py
│   │   ├── database.py      # Database connection and setup
│   │   └── models.py         # Event model/schema
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py           # Base scraper class
│   │   ├── santa_monica.py
│   │   ├── timeout.py
│   │   ├── dola.py
│   │   ├── kcrw.py
│   │   ├── ucla.py
│   │   ├── hammer.py
│   │   └── lacma.py
│   ├── search/
│   │   ├── __init__.py
│   │   └── query.py          # Search and filter logic
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── geocoding.py      # Geocoding service
│   │   ├── categories.py     # Category classification
│   │   └── deduplication.py  # Event deduplication
│   └── web/
│       ├── __init__.py
│       ├── app.py            # Main FastHTML app
│       ├── routes.py         # Route handlers
│       └── components.py     # Reusable components
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── map.js            # Leaflet + OpenStreetMap integration
│   └── logos/                # Source logos
├── data/
│   └── events.db             # SQLite database
├── logs/
├── config.py                 # Configuration
├── requirements.txt
├── .env.example
├── .gitignore
├── CLAUDE.md
├── PLAN.md
└── README.md
```

## Phase 1: MVP (Week 1-2)

### Step 1: Database Setup ✅ (Completed)
- [x] Design event schema
- [x] Create SQLite database with raw SQL
- [x] Implement basic CRUD operations
- [x] Add full-text search index (FTS5)
- [x] Add analytics database
- [x] Implement deduplication system

**Files**: `src/data/database.py`, `src/data/models.py`

### Step 2: Build Scrapers ✅ (Completed - 35+ scrapers)
Core scrapers implemented:
- [x] **Santa Monica Events**: City events calendar
- [x] **Timeout LA**: Major events and activities
- [x] **KCRW**: Music and cultural events
- [x] **35+ additional scrapers**: Including Eventbrite, Meetup, Discover LA, museums, venues, etc.

For each scraper:
- [x] Analyze website structure
- [x] Implement scraping logic with BaseScraper class
- [x] Extract: title, date, location, description, URL, pricing
- [x] Handle pagination and dynamic content (Playwright)
- [x] Add error handling and logging
- [x] Logo management system

**Files**: `src/scrapers/base.py`, `src/scrapers/santa_monica.py`, etc.

### Step 3: Geocoding Service ✅ (Completed)
- [x] Set up Google Geocoding API client
- [x] Implement address → lat/lng conversion
- [x] Add caching to avoid repeated API calls (geocode_cache.json)
- [x] Handle geocoding failures gracefully

**Files**: `src/utils/geocoding.py`

### Step 4: Web Interface ✅ (Completed)
- [x] Set up FastHTML app structure
- [x] Create home page with search form
- [x] Implement date filter (dropdown: today, this week, this month, custom)
- [x] Implement category filter (checkboxes)
- [x] Display events in grid with detailed cards
- [x] Add modern styling with responsive design
- [x] Event detail pages
- [x] Favorites system with session storage
- [x] Analytics tracking (views, searches, favorites)

**Files**: `src/web/app.py`, `src/web/routes.py`, `src/web/components.py`, `static/css/style.css`

### Step 5: Map Integration ✅ (Completed)
- [x] Set up Leaflet + OpenStreetMap (no API key required)
- [x] Create map component with HTMX integration
- [x] Add markers for each event
- [x] Implement info windows/popups on marker click
- [x] Center map on Westside LA
- [x] Marker clustering for performance
- [x] Toggle between list and map views

**Files**: `static/js/map.js`, map component in FastHTML

### Step 6: Search Functionality ✅ (Completed)
- [x] Build query builder for date filtering
- [x] Add category filtering (multi-select)
- [x] Implement keyword search (FTS5 full-text search)
- [x] Add source filtering
- [x] Add free events filter
- [x] Combine filters with AND logic
- [x] Geographic bounds filtering
- [x] HTMX-powered dynamic updates

**Files**: `src/search/query.py`

## Phase 2: Enhancement ✅ (Mostly Completed)

### Step 7: Add More Scrapers ✅ (Completed)
- [x] DoLA (Discover Los Angeles)
- [x] UCLA Events
- [x] Hammer Museum
- [x] LACMA
- [x] 30+ additional venues and sources implemented
- [x] Resident Advisor (ra.co) - **Note**: Currently disabled due to Cloudflare CAPTCHA protection
- [ ] **Heylo** (heylo.com) - Community group platform with events (Future)
  - **Challenges**: Next.js app with client-side data fetching, requires Playwright for JavaScript rendering
  - **Approach**: Search for "Los Angeles" location, extract group/event listings
  - **Note**: Similar to Meetup - consider API availability first before scraping
  - **Priority**: Low (consider after Meetup or if API becomes available)

### Step 8: Scheduled Scraping ⚠️ (Partially Implemented)
- [x] Manual scraping via run_scrapers.py
- [ ] Set up APScheduler for automated scheduling
- [ ] Configure daily scraping schedule (currently manual/cron)
- [x] Add scraper status monitoring (via logs)
- [x] Log scraping results and errors
- [x] Deduplication system (URL-based and similarity-based)

**Files**: `src/scrapers/scheduler.py`

### Step 9: Advanced Filtering ⚠️ (Partially Implemented)
- [x] Geographic filtering (map bounds)
- [ ] Neighborhood selection (future)
- [ ] Distance-based search (events within X miles) (future)
- [x] Price filtering (free events filter)
- [x] Date range filtering (custom date picker)
- [x] Category multi-select
- [x] Source filtering
- [ ] Time filtering (morning, afternoon, evening) (future)
- [ ] Accessibility options (future)
- [x] Sort functionality (by date ascending)

**Files**: `src/search/query.py`, `src/data/database.py`, `src/web/app.py` (update UI components)

### Step 10: Map Enhancements ✅ (Completed)
- [x] Implement marker clustering for performance (Leaflet.markercluster)
- [x] Interactive map with popups
- [x] Toggle between list and map views
- [x] Mobile responsive design
- [ ] Color-code markers by category (future enhancement)
- [ ] Add legend for marker colors (future)

**Files**: `static/js/map.js`

### Step 11: Category Classification ✅ (Completed)
- [x] Define category taxonomy (Music, Art, Food & Drink, Sports, Family, Theater, etc.)
- [x] Implement rule-based classifier using keywords
- [x] Single category per event (current implementation)
- [x] Display category tags on event cards
- [ ] Allow multiple categories per event (future enhancement)

**Files**: `src/utils/categories.py`

## Phase 3: Polish ⚠️ (In Progress)

### Step 12: Event Deduplication ✅ (Completed)
- [x] Implement fuzzy matching for duplicate detection (Levenshtein distance)
- [x] Compare: title similarity, venue similarity, date proximity, URL matching
- [x] Merge duplicate events from different sources
- [x] Track all source URLs for merged events
- [x] Two-phase approach: URL match first, then similarity matching

**Files**: `src/utils/deduplication.py`

### Step 13: Event Detail Pages ✅ (Completed)
- [x] Create dedicated event detail route (/event/{id})
- [x] Display full event information
- [x] Show source with logo
- [x] Display pricing information
- [x] Favorites button
- [ ] Add "Similar Events" section (future)
- [ ] Include share buttons (future)

**Files**: `src/web/routes.py`, new template

### Step 14: Performance Optimization ✅ (Completed)
- [x] Add database indexing for common queries (event_date, category, source, location, is_free)
- [x] Result limiting (default 100 events)
- [x] Cache geocoding results (geocode_cache.json)
- [x] Optimize map marker rendering with clustering
- [x] HTMX-powered dynamic loading
- [ ] Full pagination UI (future enhancement)

### Step 15: User Experience ✅ (Mostly Completed)
- [x] Responsive design for mobile
- [x] Modern UI with Tailwind-like styling
- [x] Favorites system with session storage
- [x] "No results" messaging
- [x] Analytics tracking (views, searches, favorites)
- [ ] Dark mode toggle (future)
- [ ] Save search preferences in localStorage (future)
- [ ] Improve accessibility (ARIA labels, keyboard navigation) (future)

### Step 16: Deployment ✅ (Completed)
- [x] Create Dockerfile
- [x] Set up production configuration
- [x] Add logging and error monitoring
- [x] Write deployment documentation (docs/DEPLOYMENT.md)
- [x] Deploy to Google Cloud Run (live at: https://westside-events-406046958598.us-west1.run.app)
- [x] Cloud Storage for persistent data
- [x] Cloud Scheduler for automated scraping (daily at 2 AM UTC)

## API Keys Required

- **Google Geocoding API**: For address → coordinates conversion (optional - uses cache)
- **Note**: Map visualization uses Leaflet + OpenStreetMap (NO API key required)

## Dependencies

```txt
python-fasthtml
beautifulsoup4
requests
playwright
apscheduler
sqlalchemy
python-dotenv
geopy
```

## Testing Strategy

### Comprehensive Testing Approach
- **Unit Tests**: Scrapers, geocoding, search queries
- **Integration Tests**: Full scraping → storage → retrieval flow
- **Manual Testing**: Web interface, map interaction, filters

### Scraper Testing (High Priority)
- [ ] Create individual test files for each scraper (see [docs/SCRAPER_TESTING.md](docs/SCRAPER_TESTING.md))
  - [ ] aviator_nation
  - [ ] discover_la
  - [ ] eventbrite
  - [ ] gnarwhal
  - [ ] itk_la
  - [ ] kcrw (example completed in tests/scrapers/test_kcrw.py)
  - [ ] laist
  - [ ] meetup
  - [ ] nerd_nite
  - [ ] penmar
  - [ ] resident_advisor
  - [ ] santa_monica
  - [ ] timeout
  - [ ] venice_west
  - [ ] westside_comedy
  - [ ] winston_house
- [ ] Set up CI/CD for daily scraper health checks
- [ ] Create snapshot directory for HTML baselines
- [ ] Add test runner script for all scrapers at once

**Rationale**: Websites change frequently. Unit tests with mocked HTML catch code regressions, integration tests catch website structure changes, and snapshot tests provide HTML baselines for debugging. See [docs/SCRAPER_TESTING.md](docs/SCRAPER_TESTING.md) for complete strategy.

## Success Metrics

- [ ] Events from at least 5 sources
- [ ] Accurate geocoding (>95%)
- [ ] Search results < 500ms
- [ ] Map loads with 100+ markers smoothly
- [ ] Mobile responsive
- [ ] Daily automated scraping

## Next Steps

1. Set up project structure and dependencies
2. Build database schema and models
3. Implement first scraper (Santa Monica)
4. Create basic FastHTML interface
5. Add Google Maps integration
6. Iterate and expand

## Future Enhancements (Post-MVP)

- User accounts and saved favorites
- Email/SMS notifications for new events
- Event recommendations based on preferences
- Social sharing and comments
- Submit event functionality
- Venue profiles with all upcoming events
- Mobile app (PWA)
- Export to calendar (iCal)
- **Uber Price Estimates Integration**: Add "Get a ride" functionality using Uber's Price Estimates API (`/v1.2/estimates/price`) to show estimated ride costs from user's location to event venues. Requires Uber Developer account and API key. Note: Cannot be used for price comparisons with competitor services per Uber's Terms of Use.

### Real-Time Updates & Background Scraping

**Problem**: Currently scrapers run once daily (3 AM), meaning event data can be up to 24 hours stale.

**Proposed Solutions**:

#### 1. **Background Task Scheduler** (Recommended)
- Use APScheduler (already in dependencies) to run scrapers in background
- Different schedules per source:
  - High-value sources (Discover LA, Timeout): Every 30 minutes
  - Medium-value sources (KCRW): Every 6 hours
  - Low-value sources (others): Every 12-24 hours
- Incremental scraping: Only fetch recent events (last N hours) for faster updates
- Implementation:
  ```python
  from apscheduler.schedulers.background import BackgroundScheduler

  scheduler = BackgroundScheduler()
  scheduler.add_job(run_discover_la_incremental, 'interval', minutes=30)
  scheduler.add_job(run_timeout_incremental, 'interval', hours=6)
  scheduler.start()
  ```

#### 2. **HTMX Live Updates** (Recommended)
- Use HTMX polling to auto-refresh UI without page reloads
- Poll `/events/latest` endpoint every 60-120 seconds
- Smooth user experience with new events appearing automatically
- Implementation:
  ```python
  # HTML with HTMX
  Div(
      id="events-container",
      hx_get="/events/latest",
      hx_trigger="every 60s",  # Poll every minute
      hx_swap="innerHTML"
  )
  ```

#### 3. **Manual Refresh Button**
- Allow users to trigger scraper runs for specific sources
- POST endpoint: `/refresh/{source}`
- Rate-limited to prevent abuse (e.g., once per 5 minutes per source)

#### 4. **WebSocket Real-Time Updates** (Advanced - Future)
- Push updates to connected clients immediately when new events are scraped
- More efficient than polling for high-traffic scenarios
- Requires WebSocket support (FastAPI/Starlette has built-in support)

**Considerations**:
- **Respectful scraping**: Check robots.txt `Crawl-delay` directives
- **Rate limiting**: Don't scrape too aggressively (15-30 min intervals are reasonable)
- **Server resources**: Background scraping uses memory/CPU
- **Production**: Consider Celery + Redis for more robust task queue than APScheduler
- **Caching**: Cache geocoding results and logo downloads to reduce API calls

**Implementation Priority**:
1. Background scheduler for incremental scrapes (Phase 2)
2. HTMX live updates (Phase 2)
3. Manual refresh button (Phase 3)
4. WebSocket updates (Phase 3+)

### Scraper Caching System

**Problem**: Scrapers currently re-fetch all HTML pages on every run, even if content hasn't changed. With 190+ events from multiple sources, full scraping takes several minutes and wastes bandwidth.

**Proposed Multi-Level Caching Strategy**:

#### 1. **Source-Level Scrape Cache** (Highest Priority)
Track when each source was last successfully scraped to avoid redundant scraping:

```sql
CREATE TABLE scraper_cache (
    source TEXT PRIMARY KEY,
    last_scraped_at TIMESTAMP,
    last_success INTEGER,  -- 1 for success, 0 for failure
    cache_duration_hours INTEGER DEFAULT 24,  -- configurable per source
    events_count INTEGER,  -- for monitoring
    last_error TEXT  -- for debugging
)
```

**Implementation**:
```python
def should_scrape(source: str, force: bool = False) -> bool:
    if force:
        return True

    cache_entry = db.get_scraper_cache(source)
    if not cache_entry:
        return True

    hours_since_scrape = (datetime.now() - cache_entry.last_scraped_at).total_seconds() / 3600
    return hours_since_scrape >= cache_entry.cache_duration_hours
```

**Benefits**:
- Skip sources scraped within cache window (default 24 hours)
- Configurable cache duration per source (high-volume sources = shorter cache)
- Force refresh with `--force` flag: `python run_scrapers.py --force`
- Dramatically reduces scraping time from minutes to seconds

#### 2. **Event Freshness Tracking** (Medium Priority)
Track when events were last seen to identify stale/removed events:

```sql
ALTER TABLE events ADD COLUMN last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
```

**Benefits**:
- Mark events as "stale" if not seen in recent scrapes (e.g., 7 days)
- Auto-archive past events that are no longer listed on source websites
- Detect when venues remove/cancel events

#### 3. **HTTP Response Caching** (Lower Priority)
Cache raw HTML responses with ETag/Last-Modified headers:

```python
# Cache structure: data/http_cache/{source}/{url_hash}.json
{
    "url": "https://example.com/events",
    "html": "<html>...",
    "fetched_at": "2025-01-15T10:30:00",
    "etag": "33a64df5",  # from response headers
    "last_modified": "Wed, 15 Jan 2025 09:00:00 GMT",
    "expires_at": "2025-01-15T11:30:00"
}
```

**Implementation**:
- Check cache before HTTP requests
- Use conditional requests (If-None-Match, If-Modified-Since) for 304 Not Modified responses
- Respect Cache-Control headers from servers

**Benefits**:
- Avoid downloading unchanged pages (304 responses are faster)
- Reduce bandwidth and server load
- Respect web server cache policies

#### 4. **Smart Incremental Updates** (Future Enhancement)
For sources with date-based listing pages:
- Only scrape recent events (e.g., last 30 days forward)
- Use date filters in URL parameters when available
- Skip pages that only contain past events

**Configuration**:
```python
# config.py
SCRAPER_CACHE_CONFIG = {
    'santa_monica': {'cache_hours': 24, 'incremental': False},
    'discover_la': {'cache_hours': 6, 'incremental': True},  # high-volume source
    'kcrw': {'cache_hours': 12, 'incremental': False},
    'timeout': {'cache_hours': 24, 'incremental': False},
}
```

**Expected Performance Improvement**:
- First run: Full scrape (~3-5 minutes)
- Subsequent runs within cache window: <10 seconds (just DB checks)
- Force refresh when needed: `python run_scrapers.py --force --source discover_la`

**Implementation Phase**: Phase 2 (Post-MVP)

**Related Enhancements**:
- Add `--force` flag to run_scrapers.py
- Add `--source <name>` flag to scrape specific sources only
- Add scraper status dashboard showing last scrape times and success rates

# Software Design Document (SDD)
## Westside LA Events Aggregator

**Version:** 1.0
**Date:** November 11, 2025
**Author:** Development Team

---

## 1. Overview

### 1.1 Purpose
The Westside LA Events Aggregator is a web application that aggregates events from multiple sources across LA's Westside, providing a unified search interface with date filtering, activity type categorization, and map-based geolocation visualization.

### 1.2 Scope
- **Audience**: LA Westside residents and visitors
- **Geographic Focus**: Santa Monica, West Hollywood, Culver City, UCLA area
- **Event Types**: Music, art, food, sports, family activities, cultural events
- **Data Sources**: Public websites, event platforms, city calendars

### 1.3 Technology Stack
- **Backend Framework**: FastHTML (Python-based)
- **Database**: SQLite with FTS5 (Full-Text Search)
- **Web Scrapers**: BeautifulSoup4, requests, playwright
- **Maps**: Leaflet + OpenStreetMap (no API key required)
- **Scheduling**: APScheduler for periodic scraping
- **Environment**: micromamba for Python environment management

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────┐
│   Web Browser   │
└────────┬────────┘
         │ HTTP
┌────────▼────────────────────────────────────┐
│         FastHTML Web Application           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Routes  │  │Components│  │  Static  │ │
│  └────┬─────┘  └────┬─────┘  └──────────┘ │
└───────┼────────────┼────────────────────────┘
        │            │
┌───────▼────────────▼───────────────────────┐
│         Business Logic Layer               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Search  │  │ Database │  │Geocoding │ │
│  └──────────┘  └──────────┘  └──────────┘ │
└────────────────────────────────────────────┘
        │
┌───────▼────────────────────────────────────┐
│          Data Collection Layer             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Scraper1 │  │ Scraper2 │  │ ScraperN │ │
│  └──────────┘  └──────────┘  └──────────┘ │
└────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
LA/
├── README.md              # Project overview
├── PLAN.md               # Development plan
├── CLAUDE.md             # AI assistant instructions
├── SDD.md                # This document
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── run_scrapers.py       # Scraper execution script
│
├── docs/                 # Technical documentation
│   ├── EVENT_SOURCES.md
│   ├── SCRAPING_GUIDE.md
│   ├── QUICK_REFERENCE.md
│   ├── fasthtml_analysis.md
│   ├── TEST_COVERAGE_ANALYSIS.md
│   └── COVERAGE_SUMMARY.md
│
├── src/
│   ├── data/            # Data models and database
│   │   ├── models.py    # Event model
│   │   └── database.py  # Database operations
│   │
│   ├── scrapers/        # Event source scrapers
│   │   ├── base.py      # Base scraper class
│   │   ├── santa_monica.py
│   │   ├── timeout.py
│   │   ├── kcrw.py
│   │   ├── eventbrite.py
│   │   └── meetup.py
│   │
│   ├── search/          # Search functionality
│   │   └── query.py     # EventSearch class
│   │
│   ├── utils/           # Utility services
│   │   ├── geocoding.py
│   │   └── categories.py
│   │
│   └── web/             # Web application
│       └── app.py       # FastHTML application
│
├── static/              # Frontend assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── map.js       # Leaflet map integration (HTMX handles search)
│
├── tests/               # Test suite
│   ├── README.md        # Testing documentation
│   ├── conftest.py      # Shared fixtures
│   └── unit/
│       ├── test_database.py
│       ├── test_search.py
│       └── test_scrapers.py
│
└── data/                # Runtime data
    └── events.db        # SQLite database
```

---

## 3. Data Layer

### 3.1 Database Schema

**Table: events**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY | Auto-increment ID |
| title | TEXT | NOT NULL | Event title |
| description | TEXT | | Event description |
| venue_name | TEXT | | Venue name |
| address | TEXT | | Full address |
| latitude | REAL | | Geographic latitude |
| longitude | REAL | | Geographic longitude |
| event_date | DATETIME | | Event start date/time |
| end_date | DATETIME | | Event end date/time |
| category | TEXT | | Event category |
| source | TEXT | NOT NULL | Data source name |
| url | TEXT | | Original event URL |
| image_url | TEXT | | Event image URL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record update time |

**Indexes:**
- `idx_event_date` on `event_date`
- `idx_category` on `category`
- `idx_source` on `source`
- FTS5 virtual table on `title` and `description`

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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### 3.3 Database Operations

**Key Methods:**
- `insert_event(event: Event) -> int`
- `get_event(event_id: int) -> Optional[Event]`
- `get_all_events(limit: int) -> List[Event]`
- `search_events(query: str, filters: dict) -> List[Event]`
- `delete_old_events(days: int) -> int`
- `event_exists(title: str, event_date: datetime) -> bool`

---

## 4. Search Layer

### 4.1 EventSearch Class

Provides comprehensive search functionality with:
- Full-text search using SQLite FTS5
- Date range filtering (today, this week, this month, upcoming)
- Category filtering (single or multiple)
- Combined query builder
- Result limiting and pagination

### 4.2 Date Filters

| Filter | Description | SQL Condition |
|--------|-------------|---------------|
| today | Events today | `DATE(event_date) = DATE('now')` |
| this_week | Next 7 days | `event_date BETWEEN now AND now+7 days` |
| this_weekend | Upcoming Sat-Sun | Custom weekend calculation |
| this_month | Current month | `strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now')` |
| upcoming | Future events | `event_date >= DATE('now')` |

### 4.3 Category System

**Predefined Categories:**
- Music
- Art & Culture
- Food & Drink
- Sports & Fitness
- Family & Kids
- Film & Theatre
- Nightlife
- Community
- Education
- Other

**Classification:** Automated using keyword matching on title/description.

---

## 5. Scraper Layer

### 5.1 Base Scraper Architecture

All scrapers inherit from `BaseScraper` which provides:

```python
class BaseScraper:
    def __init__(self, source_name: str)
    def scrape(self) -> List[Event]           # Abstract
    def fetch_page(self, url: str) -> str     # HTTP request
    def parse_html(self, html: str) -> BeautifulSoup
    def create_event(self, **kwargs) -> Event # Auto-geocodes
    def clean_text(self, text: str) -> str
    def normalize_url(self, url: str, base: str) -> str
```

### 5.2 Implemented Scrapers

| Source | Type | Status | Events/Week |
|--------|------|--------|-------------|
| Santa Monica | Web scraping | ✅ Active | ~50 |
| Timeout LA | Web scraping | ✅ Active | ~100 |
| KCRW | Web scraping | ✅ Active | ~30 |
| Eventbrite | API | ✅ Active | ~200 |
| Meetup | API/Scraping | ✅ Active | ~150 |

**Planned Scrapers:**
- Discover LA
- UCLA Events
- Hammer Museum
- LACMA
- Bandsintown (music events)

### 5.3 Scraper Execution

**Scheduling:** APScheduler runs scrapers daily at configurable times

**Error Handling:**
- Graceful failure (one scraper failure doesn't block others)
- Retry logic with exponential backoff
- Comprehensive logging

**Rate Limiting:**
- Configurable delays between requests
- Per-source rate limits
- Respect robots.txt

---

## 6. Web Application Layer

### 6.1 FastHTML Application

**Framework:** FastHTML (Python-based web framework)

**Key Features:**
- Component-based UI architecture
- HTMX for dynamic updates
- Server-side rendering
- Minimal JavaScript

### 6.2 Routes

| Route | Method | Description | Returns |
|-------|--------|-------------|---------|
| `/` | GET | Home page | HTML |
| `/events/list` | GET | HTMX events list | HTML fragment |
| `/event/{id}` | GET | Event detail page | HTML |
| `/api/events` | GET | Events JSON API | JSON |
| `/api/events/{id}` | GET | Single event JSON | JSON |
| `/static/{path}` | GET | Static files | File |

### 6.3 Components

**Layout Components:**
- `page_header()` - Site header
- `page_footer()` - Site footer
- `page_layout()` - Full page wrapper

**Event Components:**
- `event_card(event)` - Single event card
- `events_list(events)` - Grid of event cards
- `search_section()` - Search form and filters

### 6.4 Frontend Technologies

**CSS:** Custom styles with CSS variables for theming

**JavaScript:**
- `map.js` - Leaflet map integration
- HTMX 2.0.3 - Server-side search and filtering (no custom search.js needed)

**Maps:**
- Leaflet 1.9.4
- MarkerCluster for performance
- OpenStreetMap tiles (free)

---

## 7. Utility Services

### 7.1 Geocoding Service

**Purpose:** Convert addresses to coordinates

**Features:**
- Google Geocoding API integration
- Local cache for repeated addresses
- Westside LA boundary checking
- Fallback for missing coordinates

**Caching:**
- JSON file cache: `data/geocoding_cache.json`
- Reduces API calls by ~90%

### 7.2 Category Classifier

**Purpose:** Automatically categorize events

**Method:** Keyword matching on title/description

**Keywords Map:**
```python
CATEGORY_KEYWORDS = {
    'Music': ['concert', 'music', 'band', 'jazz', ...],
    'Art': ['art', 'gallery', 'exhibition', ...],
    'Food': ['food', 'restaurant', 'tasting', ...],
    # ...
}
```

---

## 8. Configuration

### 8.1 Environment Variables

Stored in `.env` (not committed to git):

```bash
# API Keys
GOOGLE_MAPS_API_KEY=...
GOOGLE_GEOCODING_API_KEY=...
EVENTBRITE_API_TOKEN=...
MEETUP_API_KEY=...

# Database
DATABASE_PATH=data/events.db

# Debug Mode
DEBUG=True
```

### 8.2 Configuration File

`config.py` provides:
- Database settings
- API keys
- Scraper configurations
- Category definitions
- Date filter configurations

---

## 9. Deployment

### 9.1 Environment Setup

**Using direnv + micromamba:**

1. Install micromamba environment:
   ```bash
   micromamba create -n la python=3.10 -y
   micromamba activate la
   pip install -r requirements.txt
   ```

2. Configure direnv:
   ```bash
   direnv allow
   ```

3. Environment auto-activates when entering project directory

### 9.2 Running the Application

**Web Server:**
```bash
micromamba run uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
```

**Run Scrapers:**
```bash
micromamba run python run_scrapers.py
```

### 9.3 Production Considerations

- **Docker:** Container for consistent deployment
- **Cron Jobs:** Schedule scraper execution
- **Static Files:** Serve via CDN or nginx
- **Logging:** Centralized logging system
- **Monitoring:** Health checks and error alerts

---

## 10. Security Considerations

### 10.1 Known Issues

**Critical:**
- Path traversal vulnerability in static file serving (needs fix)

**Recommendations:**
- Use `StaticFiles` mount instead of custom route
- Add input validation for all user inputs
- Implement rate limiting on API endpoints
- Add CSRF protection for forms
- Sanitize HTML in event descriptions

### 10.2 API Key Management

- Store in `.env` file (gitignored)
- Never commit to version control
- Use environment variables in production
- Rotate keys periodically

---

## 11. Testing Strategy

### 11.1 Test Suite

**Framework:** pytest with fixtures

**Coverage:**
- Unit tests: Data models, database, search
- Integration tests: Full workflow testing
- Scraper tests: Mock HTTP responses

**Current Status:**
- 51 tests created
- ~60-70% code coverage
- See `docs/TEST_COVERAGE_ANALYSIS.md`

### 11.2 Running Tests

```bash
# All tests
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/ -v

# With coverage
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/ --cov=src --cov-report=html
```

---

## 12. Performance Considerations

### 12.1 Database Optimization

- FTS5 indexes for full-text search
- Indexes on frequently queried columns
- Connection pooling (planned)
- Query result caching (planned)

### 12.2 Frontend Performance

- Minimal JavaScript dependencies
- Server-side rendering
- Leaflet MarkerCluster for map performance
- Static file caching headers (planned)

### 12.3 Scraping Optimization

- Parallel scraper execution
- Cached geocoding results
- Incremental updates (don't re-scrape all)
- Configurable scraping frequency

---

## 13. Future Enhancements

### 13.1 Phase 2 Features

- User accounts and favorites
- Email notifications for new events
- Advanced filtering (price, accessibility)
- Event recommendations based on preferences

### 13.2 Phase 3 Features

- Mobile app (React Native)
- Social features (comments, ratings)
- Event submission by users
- Integration with calendar apps (iCal, Google Calendar)

### 13.3 Technical Improvements

- Async database operations
- Redis caching layer
- Elasticsearch for advanced search
- GraphQL API
- WebSocket for real-time updates

---

## 14. Maintenance

### 14.1 Regular Tasks

**Daily:**
- Monitor scraper execution
- Check for scraper failures

**Weekly:**
- Review error logs
- Update geocoding cache
- Check database size

**Monthly:**
- Update dependencies
- Review and update scraper selectors
- Clean old events from database

### 14.2 Scraper Maintenance

Scrapers break when websites change:

**Monitoring:**
- Log all scraper errors
- Track success rates per source
- Alert on consecutive failures

**Fixing:**
1. Inspect website for changes
2. Update CSS selectors
3. Test scraper locally
4. Deploy fix
5. Document changes in code comments

---

## 15. Documentation

### 15.1 Documentation Structure

- `README.md` - Project overview and quick start
- `PLAN.md` - Development roadmap
- `CLAUDE.md` - AI assistant instructions
- `SDD.md` - This document
- `docs/` - Detailed technical documentation
- `tests/README.md` - Testing guide

### 15.2 Additional Resources

- **Event Sources:** `docs/EVENT_SOURCES.md`
- **Scraping Guide:** `docs/SCRAPING_GUIDE.md`
- **FastHTML Best Practices:** `docs/QUICK_REFERENCE.md`
- **Detailed Analysis:** `docs/fasthtml_analysis.md`
- **Test Coverage:** `docs/TEST_COVERAGE_ANALYSIS.md`

---

## 16. Support and Contact

**Project Repository:** (Add if applicable)
**Issue Tracking:** (Add if applicable)
**Documentation:** See `docs/` directory

---

## Appendix A: API Reference

See individual module docstrings for detailed API documentation.

## Appendix B: Database Migrations

Currently using direct SQL. Consider adding migration framework (e.g., Alembic) for schema changes.

## Appendix C: Troubleshooting

Common issues and solutions documented in `docs/QUICK_REFERENCE.md`.

# Westside LA Events Aggregator

## Project Overview
A FastHTML-powered web application that aggregates events from multiple sources across LA's Westside, providing a unified search interface with date filtering, activity type categorization, and Google Maps geolocation visualization.

## Architecture

### Technology Stack
- **Framework**: FastHTML (Python-based web framework)
- **Database**: SQLite with full-text search
- **Maps**: Leaflet + OpenStreetMap (100% free, no API key required)
- **Scrapers**: BeautifulSoup4, requests, playwright (for dynamic sites)
- **Scheduling**: APScheduler for periodic scraping

### Core Components

#### 1. Data Layer (`src/data/`)
- **Database Schema**: Events table with fields:
  - `id`, `title`, `description`, `venue_name`, `address`
  - `latitude`, `longitude`, `event_date`, `end_date`
  - `category`, `source`, `url`, `image_url`
  - `created_at`, `updated_at`
- **Models**: SQLite/SQLAlchemy models for event storage

#### 2. Scraper Layer (`src/scrapers/`)
Individual scrapers for each data source:
- **Santa Monica Events** (smgov.net/events)
- **Timeout LA** (timeout.com/los-angeles)
- **DoLA** (discoverlosangeles.com)
- **KCRW Events** (kcrw.com/events)
- **UCLA Events** (calendar.ucla.edu)
- **Hammer Museum** (hammer.ucla.edu)
- **LACMA** (lacma.org)
- **Venues**: The Broad, Getty Center, etc.

Each scraper implements:
- `scrape()` method returning standardized event data
- Error handling and rate limiting
- Geocoding for addresses without coordinates

#### 3. Search & Filter Layer (`src/search/`)
- Date range filtering (today, this week, this month, custom)
- Category filtering (music, art, food, sports, family, etc.)
- Geographic filtering (neighborhood, distance from point)
- Full-text search across title/description
- Combined query builder

#### 4. Web Interface (`src/web/`)
FastHTML routes and components:
- **Home Page**: Search bar, filters, map view toggle
- **Results View**: Grid/list of events with map pins
- **Event Detail**: Full event information
- **Map Component**: Google Maps with clustered markers
- **API Endpoints**: JSON responses for AJAX requests

#### 5. Utilities (`src/utils/`)
- Geocoding service (Google Geocoding API)
- Date parsing and normalization
- Category classifier (ML-based or rule-based)
- Data deduplication

## Data Flow

1. **Scheduled Scraping**: Scrapers run daily to fetch new events
2. **Processing**: Events are geocoded, categorized, deduplicated
3. **Storage**: Cleaned events stored in SQLite database
4. **Query**: User searches trigger database queries with filters
5. **Display**: Results rendered via FastHTML with map visualization

## Key Features

### Search Capabilities
- Date range selection
- Multi-category filtering
- Neighborhood/area selection
- Distance-based search
- Keyword search

### Map Visualization
- Interactive Google Maps
- Event markers with info windows
- Marker clustering for performance
- Filter results by map viewport
- Click marker to see event details

### Event Details
- Title, description, date/time
- Venue name and address
- Category tags
- Source link
- Similar events suggestions

## Development Phases

### Phase 1: MVP
- Basic database schema
- 3-5 scrapers (Santa Monica, Timeout, KCRW)
- Simple search by date and category
- Basic map with markers
- FastHTML interface

### Phase 2: Enhancement
- Add remaining scrapers
- Improve geocoding accuracy
- Advanced filters (price, accessibility)
- Marker clustering
- Responsive design

### Phase 3: Polish
- Event deduplication across sources
- User preferences/favorites
- Email notifications
- Performance optimization
- Error monitoring

## Development Environment

### Running Python Scripts
This project uses micromamba for environment management with a dedicated environment called `la`. **Always run Python scripts and commands using `micromamba run -n la`**:

```bash
# Run a Python script
micromamba run -n la python <script.py>

# Run the scrapers
micromamba run -n la python run_scrapers.py

# Use Python module/library commands
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

# Run tests
micromamba run -n la python -m pytest tests/
```

This ensures that all dependencies are available in the correct isolated `la` environment. **Never use `micromamba run` without `-n la`** as it will default to the base environment which doesn't have the project dependencies.

**Important:** Do NOT run Python scripts directly (e.g., `python src/web/app.py`) as this will cause import errors. The project uses module imports that require the project root to be in the Python path.

### Running the Web Application
To start the FastHTML web server:

```bash
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

**Command breakdown:**
- `micromamba run -n la`: Executes command in the `la` micromamba environment
- `uvicorn`: ASGI server for FastHTML/FastAPI apps
- `src.web.app:app`: Python module path to the FastHTML app instance
- `--host 0.0.0.0`: Bind to all network interfaces (broadcast mode for remote access)
- `--port 8000`: Use port 8000
- `--reload`: Auto-reload on code changes (development only)

The application will be available at:
- Local: http://127.0.0.1:8000
- Network: http://<your-ip>:8000

**IMPORTANT:** When restarting the web server, ALWAYS use `--host 0.0.0.0` (broadcast mode) to allow access from remote clients.

### Common Issues

**Module not found errors:**
- Always use `micromamba run python` instead of just `python`
- Use module notation (`src.web.app:app`) not file paths when running with uvicorn
- Ensure you're running commands from the project root directory

**Port already in use:**
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9
```

## Configuration
- `config.py`: API keys, database paths, scraper settings
- Environment variables for sensitive data
- Scraper schedule configuration

## Deployment
- Docker container for easy deployment
- Cron job for scheduled scraping
- Static file serving for performance
- Logging and monitoring setup

## Documentation

The project includes comprehensive documentation:

### Core Documentation
- **[README.md](README.md)** - Project overview and quick start guide
- **[PLAN.md](PLAN.md)** - Development roadmap and implementation phases
- **[SDD.md](SDD.md)** - Software Design Document with architecture details
- **[CLAUDE.md](CLAUDE.md)** - This file (AI assistant instructions)

### Technical Documentation (`docs/`)
- **[EVENT_SOURCES.md](docs/EVENT_SOURCES.md)** - Detailed guide on event sources (API vs scraping)
- **[SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md)** - Web scraping best practices and guidelines
- **[LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)** - Source logo management and troubleshooting
- **[ANALYTICS.md](docs/ANALYTICS.md)** - Analytics system documentation and usage guide
- **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - FastHTML best practices and quick fixes
- **[fasthtml_analysis.md](docs/fasthtml_analysis.md)** - In-depth FastHTML implementation analysis
- **[TEST_COVERAGE_ANALYSIS.md](docs/TEST_COVERAGE_ANALYSIS.md)** - Test coverage report and gaps
- **[COVERAGE_SUMMARY.md](docs/COVERAGE_SUMMARY.md)** - Test coverage summary

### Testing Documentation
- **[tests/README.md](tests/README.md)** - Comprehensive testing guide

### Project Management
- **[docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)** - GitHub issue tracking and milestone management
- **[scripts/README.md](scripts/README.md)** - Automation scripts documentation

### When to Use Each Document
- **Starting development?** Read [README.md](README.md) → [PLAN.md](PLAN.md)
- **Understanding architecture?** Read [SDD.md](SDD.md)
- **Adding a scraper?** Read [docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) → [docs/LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)
- **Working with FastHTML?** Read [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- **Writing tests?** Read [tests/README.md](tests/README.md)
- **Understanding event sources?** Read [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md)
- **Managing issues and milestones?** Read [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)
- **Troubleshooting logos?** Read [docs/LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)
- **Setting up analytics?** Read [docs/ANALYTICS.md](docs/ANALYTICS.md) → [ANALYTICS_IMPLEMENTATION.md](ANALYTICS_IMPLEMENTATION.md)

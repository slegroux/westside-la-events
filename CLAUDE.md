# Westside LA Events Aggregator

## Project Overview
A FastHTML-powered web application that aggregates events from 35+ sources across LA's Westside, providing a unified search interface with date filtering, activity type categorization, and interactive map visualization.

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
  - `category`, `source`, `url`, `image_url`, `source_logo_url`
  - `price`, `is_free`, `price_note`
  - `created_at`, `updated_at`
- **Models**: SQLite models for event storage
- **Analytics**: Separate analytics database for tracking views, searches, favorites

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
- **Pricing convention**: When price information is not available, set `price_note` to `"TBD"` (not "Visit website for pricing" or similar). This provides a consistent user experience across all scrapers.

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
- **Map Component**: Leaflet/OpenStreetMap with clustered markers
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
- Interactive Leaflet + OpenStreetMap maps
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

### Phase 1: MVP ✅ (Completed)
- Basic database schema
- 35+ scrapers (Santa Monica, Timeout, KCRW, and many more)
- Simple search by date and category
- Interactive map with clustered markers
- FastHTML interface with analytics and favorites

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

# Run the scrapers (async optimized by default)
micromamba run -n la python run_scrapers.py

# Run specific scrapers only (faster for development)
micromamba run -n la python run_scrapers.py --scrapers santa_monica timeout kcrw

# Adjust concurrency for performance tuning
micromamba run -n la python run_scrapers.py --max-concurrent 15

# Use Python module/library commands
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

# Run tests
micromamba run -n la python -m pytest tests/
```

This ensures that all dependencies are available in the correct isolated `la` environment. **Never use `micromamba run` without `-n la`** as it will default to the base environment which doesn't have the project dependencies.

**Note**: The scraper runner now uses async/await with concurrent execution for optimal performance (5-10x faster than sequential). The old synchronous version is available as `run_scrapers_old_sync.py` if needed.

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

For production deployment, see **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** which covers:
- **Google Cloud Run** (recommended): Free tier, serverless, persistent storage with Cloud Storage
- **Railway**: Simple GitHub integration, free tier available
- **Other options**: Fly.io, Render, DigitalOcean
- Custom domain setup, monitoring, and cost management

Quick reference for deployed instance:
- **Service URL**: https://westside-events-406046958598.us-west1.run.app
- **Cloud Storage**: gs://westside-la-events-data/
- **Automated Scraping**: Daily at 4 AM PST (12 PM UTC) via Cloud Scheduler

### Updating Production Data

To update the production database with fresh scraped events:

```bash
# Option 1: Run scrapers and sync in one command (recommended)
./scripts/sync_db_to_cloud.sh --run-scrapers --force

# Option 2: Sync existing local database
./scripts/sync_db_to_cloud.sh

# Option 3: Test first with dry-run
./scripts/sync_db_to_cloud.sh --run-scrapers --dry-run
```

The script will:
1. Back up the current production database
2. (Optional) Run scrapers to update local database
3. Upload updated database to Cloud Storage
4. Cloud Run automatically uses the new data on next request

**Note:** This updates only the data, not the code. To deploy code changes, use `./scripts/deploy.sh`

## Documentation

The project includes comprehensive documentation:

### Core Documentation
- **[README.md](README.md)** - Project overview and quick start guide
- **[PLAN.md](PLAN.md)** - Development roadmap and implementation phases
- **[CLAUDE.md](CLAUDE.md)** - This file (AI assistant instructions)

### Technical Documentation (`docs/`)
- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)** - **Local development setup and workflow**
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - **Production deployment guide (Google Cloud Run, Railway, etc.)**
- **[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - **Common issues and solutions**
- **[SDD.md](docs/SDD.md)** - Software Design Document with architecture details
- **[ANALYTICS_IMPLEMENTATION.md](docs/ANALYTICS_IMPLEMENTATION.md)** - Analytics implementation guide
- **[EVENT_SOURCES.md](docs/EVENT_SOURCES.md)** - Detailed guide on event sources (API vs scraping)
- **[SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md)** - Web scraping best practices and guidelines
- **[LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)** - Source logo management and troubleshooting
- **[ANALYTICS.md](docs/ANALYTICS.md)** - Analytics system documentation and usage guide
- **[QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - FastHTML best practices and quick fixes
- **[fasthtml_analysis.md](docs/fasthtml_analysis.md)** - In-depth FastHTML implementation analysis
- **[TEST_COVERAGE_ANALYSIS.md](docs/TEST_COVERAGE_ANALYSIS.md)** - Test coverage report and gaps
- **[COVERAGE_SUMMARY.md](docs/COVERAGE_SUMMARY.md)** - Test coverage summary
- **[CHANGELOG.md](docs/CHANGELOG.md)** - Project changelog
- **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** - Contribution guidelines
- **[E2E_TEST_RESULTS.md](docs/E2E_TEST_RESULTS.md)** - E2E test results
- **[PLAYWRIGHT_SETUP_COMPLETE.md](docs/PLAYWRIGHT_SETUP_COMPLETE.md)** - Playwright setup documentation

### Testing Documentation
- **[tests/README.md](tests/README.md)** - Comprehensive testing guide

### Project Management
- **[docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)** - GitHub issue tracking and milestone management
- **[scripts/README.md](scripts/README.md)** - Automation scripts documentation

### When to Use Each Document
- **Starting development?** Read [README.md](README.md) → [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- **Deploying to production?** Read [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Stuck on an issue?** Read [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Understanding architecture?** Read [docs/SDD.md](docs/SDD.md)
- **Adding a scraper?** Read [docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) → [docs/LOGO_MANAGEMENT.md](docs/LOGO_MANAGEMENT.md)
- **Working with FastHTML?** Read [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)
- **Writing tests?** Read [tests/README.md](tests/README.md)
- **Understanding event sources?** Read [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md)
- **Managing issues and milestones?** Read [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)
- **Setting up analytics?** Read [docs/ANALYTICS.md](docs/ANALYTICS.md) → [docs/ANALYTICS_IMPLEMENTATION.md](docs/ANALYTICS_IMPLEMENTATION.md)

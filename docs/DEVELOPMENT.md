# Development Guide

This guide covers local development setup, adding scrapers, and working with the codebase.

## Table of Contents
- [Environment Setup](#environment-setup)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Adding Scrapers](#adding-scrapers)
- [Database Schema](#database-schema)
- [Testing](#testing)

---

## Environment Setup

### Option 1: Using micromamba (Recommended)

This project uses a micromamba environment named `la`.

**1. Create the environment**:
```bash
micromamba create -n la python=3.11 -y
micromamba activate la
pip install -r requirements.txt -r requirements-dev.txt

# Install Playwright browsers (required for JS-rendered scrapers and E2E tests)
micromamba run -n la playwright install chromium
```

**3. Configure direnv**:
```bash
# Add to ~/.bashrc or ~/.zshrc
eval "$(direnv hook bash)"  # For bash
eval "$(direnv hook zsh)"   # For zsh
```

**4. Allow direnv for this project**:
```bash
direnv allow
```

Now the `la` environment will automatically activate when you enter this directory!

**Benefits:**
- No need to manually activate the environment
- Consistent environment across terminal sessions
- Automatic `.env` loading for API keys
- Clean separation between projects

**5. Set up environment variables**:
```bash
cp .env.example .env
# Edit .env and add your Google API keys
```

**6. Initialize the database**:
```bash
micromamba run -n la python -c "from src.data.database import Database; Database('data/events.db')"
```

### Option 2: Using venv (Alternative)

**Note:** Using micromamba (Option 1) is recommended. All scripts use `micromamba run -n la`.

**1. Create and activate environment**:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**2. Install dependencies**:
```bash
pip install -r requirements.txt -r requirements-dev.txt

# Install Playwright browsers (required for JS-rendered scrapers and E2E tests)
playwright install chromium
```

**3. Set up environment variables**:
```bash
cp .env.example .env
# Edit .env and add your Google API keys
```

**4. Initialize database**:
```bash
python -c "from src.data.database import Database; Database('data/events.db')"
```

**Important:** If using venv, replace `micromamba run -n la python` with just `python` in all commands.

---

## Project Structure

```
LA/
├── src/
│   ├── data/           # Database models and operations
│   │   ├── database.py     # Database connection and operations
│   │   ├── models.py       # Event data model
│   │   └── analytics.py    # Analytics tracking
│   ├── scrapers/       # Event scrapers for each source
│   │   ├── base.py         # Base scraper class
│   │   ├── santa_monica.py
│   │   ├── timeout.py
│   │   ├── kcrw.py
│   │   └── ...             # 30+ scrapers
│   ├── search/         # Search and filter functionality
│   │   └── query.py        # Event search queries
│   ├── utils/          # Utilities (geocoding, categorization)
│   │   ├── geocoding.py
│   │   └── categorizer.py
│   └── web/            # FastHTML web application
│       ├── app.py          # App setup, lifespan, error handlers
│       ├── state.py        # AppState singleton, session helpers
│       ├── components.py   # UI component functions
│       ├── services.py     # Business logic (_fetch_events, tallies)
│       ├── analytics_routes.py
│       └── routes/         # Route modules (events, filters, favorites, api)
├── static/
│   ├── css/           # Stylesheets
│   ├── js/            # JavaScript for map integration
│   └── logos/         # Source logos (30+ logos)
├── tests/             # Test suite
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   ├── scrapers/      # Scraper tests
│   └── e2e/           # End-to-end tests (Playwright)
├── docs/              # Technical documentation
├── scripts/           # Utility scripts
├── data/              # SQLite database and cache files
├── logs/              # Application logs
├── config.py          # Configuration settings
├── run_scrapers.py    # Script to run all scrapers
├── requirements.txt      # Runtime dependencies
└── requirements-dev.txt  # Dev/test dependencies
```

---

## Configuration

### config.py

Edit `config.py` to customize:

```python
# API Keys
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
GOOGLE_GEOCODING_API_KEY = os.getenv('GOOGLE_GEOCODING_API_KEY', '')

# Database
DATABASE_PATH = 'data/events.db'
ANALYTICS_DB_PATH = 'data/analytics.db'

# Scraper Settings
USER_AGENT = 'Mozilla/5.0 ...'
REQUEST_DELAY = 1  # Seconds between requests
REQUEST_TIMEOUT = 30  # Seconds

# Geographic Bounds (Westside LA)
WESTSIDE_BOUNDS = {
    'north': 34.1,
    'south': 33.9,
    'east': -118.3,
    'west': -118.6
}

# Event Categories
CATEGORIES = [
    'Music', 'Art', 'Food & Drink', 'Sports & Fitness',
    'Family & Kids', 'Comedy', 'Theater', 'Film',
    'Outdoors & Recreation', 'Community', 'Other'
]
```

### Environment Variables (.env)

```bash
# Google API Keys (optional for testing)
GOOGLE_MAPS_API_KEY=your_maps_key_here
GOOGLE_GEOCODING_API_KEY=your_geocoding_key_here

# Scraper Authentication (for protected endpoints)
SCRAPER_TOKEN=your_secure_token

# Analytics (optional)
ENABLE_ANALYTICS=true
```

---

## Adding Scrapers

See [docs/SCRAPING_GUIDE.md](SCRAPING_GUIDE.md) for comprehensive scraping best practices.

### Quick Start

**1. Create scraper file** in `src/scrapers/`:

```python
from .base import BaseScraper
from src.data.models import Event
from datetime import datetime
import requests
from bs4 import BeautifulSoup

class NewVenueScraper(BaseScraper):
    def __init__(self):
        super().__init__('New Venue Name')
        self.base_url = 'https://example.com'

    def scrape(self):
        """Scrape events from the venue."""
        events = []

        try:
            response = requests.get(
                f'{self.base_url}/events',
                headers={'User-Agent': self.user_agent},
                timeout=30
            )
            soup = BeautifulSoup(response.content, 'html.parser')

            for event_elem in soup.select('.event-item'):
                event = Event(
                    title=event_elem.select_one('.title').text.strip(),
                    description=event_elem.select_one('.description').text.strip(),
                    venue_name=self.source_name,
                    address='123 Main St, Los Angeles, CA',
                    event_date=self._parse_date(event_elem.select_one('.date').text),
                    category='Music',  # Or use categorizer
                    source=self.source_name,
                    url=event_elem.select_one('a')['href']
                )
                events.append(event)

        except Exception as e:
            self.logger.error(f"Error scraping {self.source_name}: {e}")

        return events
```

**2. Add logo** to `static/logos/new_venue.png` (see [LOGO_MANAGEMENT.md](LOGO_MANAGEMENT.md))

**3. Add to run_scrapers.py**:

```python
from src.scrapers.new_venue import NewVenueScraper

scrapers = [
    # ... existing scrapers ...
    NewVenueScraper(),
]
```

**4. Test the scraper**:

```bash
# Create test file: tests/scrapers/test_new_venue.py
micromamba run -n la python -m pytest tests/scrapers/test_new_venue.py -v
```

---

## Database Schema

### Events Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary key (auto-increment) |
| `title` | TEXT | Event title |
| `description` | TEXT | Event description |
| `venue_name` | TEXT | Venue name |
| `address` | TEXT | Full address |
| `latitude` | REAL | Latitude coordinate |
| `longitude` | REAL | Longitude coordinate |
| `event_date` | TEXT | Start date/time (ISO format) |
| `end_date` | TEXT | End date/time (ISO format) |
| `category` | TEXT | Event category |
| `source` | TEXT | Data source name |
| `url` | TEXT | Original event URL |
| `image_url` | TEXT | Event image URL |
| `created_at` | TEXT | Record creation timestamp |
| `updated_at` | TEXT | Record update timestamp |

### Indexes

- `idx_event_date`: Index on `event_date` for date filtering
- `idx_category`: Index on `category` for category filtering
- `idx_source`: Index on `source` for source filtering
- Full-text search index on `title` and `description`

### Analytics Tables

See [docs/ANALYTICS.md](ANALYTICS.md) for analytics schema details.

---

## Testing

See [tests/README.md](../tests/README.md) for comprehensive testing guide.

### Quick Test Commands

```bash
# Run all tests
micromamba run -n la python -m pytest

# Run unit tests only
micromamba run -n la python -m pytest tests/unit/

# Run scraper tests
micromamba run -n la python -m pytest tests/scrapers/

# Run with coverage
micromamba run -n la python -m pytest --cov=src --cov-report=html

# Run end-to-end tests
micromamba run -n la python -m pytest tests/e2e/
```

### Test a Specific Scraper

```bash
# Run scraper directly
micromamba run -n la python -c "from src.scrapers.timeout import TimeoutScraper; print(TimeoutScraper().scrape())"

# Run scraper test
micromamba run -n la python -m pytest tests/scrapers/test_timeout.py -v
```

---

## Running the Application

### Development Mode

```bash
# Run scrapers to collect events
micromamba run -n la python run_scrapers.py

# Start web server with auto-reload
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

# Open browser
open http://127.0.0.1:8000
```

### Production Mode

See [docs/DEPLOYMENT.md](DEPLOYMENT.md) for production deployment options.

---

## Common Development Tasks

### Inspect Database

```bash
# Count events
micromamba run -n la python -c "from src.data.database import Database; db = Database('data/events.db'); print(f'Total events: {len(db.get_events())}')"

# View recent events
micromamba run -n la python scripts/inspect_db.py
```

### Geocode Missing Locations

```bash
micromamba run -n la python scripts/geocode_missing.py
```

### Check for Duplicates

```bash
micromamba run -n la python scripts/check_duplicates.py
```

### Reclassify Events

```bash
micromamba run -n la python scripts/reclassify_events.py
```

---

## Code Style

- **Python**: Follow PEP 8
- **Docstrings**: Use Google style
- **Type hints**: Use where applicable
- **Imports**: Group stdlib, third-party, local
- **Line length**: 100 characters max

### Example

```python
from typing import List, Optional
from datetime import datetime

def get_events_by_date(
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> List[Event]:
    """Get events within a date range.

    Args:
        start_date: Start of date range
        end_date: End of date range (optional)

    Returns:
        List of Event objects
    """
    pass
```

---

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/new-scraper

# Make changes
git add .
git commit -m "Add new venue scraper"

# Push and create PR
git push origin feature/new-scraper
```

See [docs/CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## Additional Resources

- **[SCRAPING_GUIDE.md](SCRAPING_GUIDE.md)** - Web scraping best practices
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - FastHTML quick reference
- **[SDD.md](SDD.md)** - Software design document
- **[EVENT_SOURCES.md](EVENT_SOURCES.md)** - Event source implementation guide
- **[LOGO_MANAGEMENT.md](LOGO_MANAGEMENT.md)** - Logo management guide

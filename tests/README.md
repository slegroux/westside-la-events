# Testing Guide for LA Events Aggregator

## Overview

This project includes a comprehensive test suite for unit testing the web application, database layer, search functionality, and scrapers.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── unit/                    # Unit tests
│   ├── test_database.py     # Database and Event model tests
│   ├── test_search.py       # Search functionality tests
│   ├── test_scrapers.py     # Base scraper class tests
│   ├── test_all_scrapers.py # Comprehensive tests for all 34 scrapers
│   ├── test_analytics.py    # Analytics system tests
│   ├── test_logos.py        # Logo management tests
│   ├── test_fts_security.py # Full-text search security tests
│   ├── test_setup.py        # Setup and configuration tests
│   └── test_web_app.py      # Web endpoint tests
├── scrapers/                # Individual scraper tests
│   ├── test_kcrw.py         # KCRW scraper tests
│   ├── test_parks_scraper.py # Parks scraper tests
│   ├── test_venice_west_*.py # Venice West scraper tests
│   └── test_*.py            # Other specific scraper tests
├── e2e/                     # End-to-end tests with Playwright
│   ├── README.md            # E2E testing guide
│   ├── test_homepage.py     # Homepage tests
│   ├── test_search_filters.py  # Search and filter tests
│   ├── test_event_detail.py    # Event detail page tests
│   └── test_map_interactions.py  # Map functionality tests
└── integration/             # Integration tests (future)
```

## Running Tests

### Run All Tests
```bash
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/ -v
```

### Run Specific Test File
```bash
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/unit/test_database.py -v
```

### Run Specific Test
```bash
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/unit/test_database.py::TestEvent::test_event_creation -v
```

### Run Tests with Coverage
```bash
PYTHONNOUSERSITE=1 micromamba run python -m pytest tests/ --cov=src --cov-report=html
```

### Run Tests by Marker
```bash
# Run only unit tests
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest -m unit

# Run only E2E tests (requires web server running)
micromamba run -n la python -m pytest -m e2e

# Run only scraper tests (includes all 34 scrapers)
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest -m scraper

# Run comprehensive scraper tests
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py -v

# Skip slow tests
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest -m "not slow"
```

### Run E2E Tests

E2E tests require the web server to be running first:

```bash
# Terminal 1: Start the web server
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Run E2E tests
micromamba run -n la python -m pytest tests/e2e/ -v
```

See [tests/e2e/README.md](e2e/README.md) for detailed E2E testing documentation.

## Comprehensive Scraper Tests

The `test_all_scrapers.py` file provides comprehensive unit tests for all 34 event scrapers in the system:

### Coverage

- **34 scrapers tested**: All scrapers from Aero Theater to Winston House
- **251 total test cases**: Parametrized tests ensure consistent coverage
- **Test categories**:
  - **Initialization**: Verifies proper setup, source names, and configuration
  - **Basic Functionality**: Tests scrape() method, error handling, and empty responses
  - **JavaScript Support**: Validates Playwright integration for dynamic sites
  - **Event Creation**: Tests event validation and location filtering
  - **Utility Methods**: Tests text cleaning, URL normalization, HTML parsing
  - **Error Handling**: Tests malformed HTML and network error resilience
  - **Logging**: Validates logging functionality

### Running Scraper Tests

```bash
# Run all scraper tests (251 tests)
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py -v

# Run specific test class
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py::TestScraperInitialization -v

# Run tests for a specific scraper
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py -k "KCRWScraper" -v

# Run just initialization tests (fast)
PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py::TestScraperInitialization -v
```

### Test Design

- **Mocked Dependencies**: All network calls and geocoding are mocked for speed
- **Parametrized Tests**: Each scraper runs through the same test suite
- **Consistent Validation**: Ensures all scrapers follow the same patterns
- **No External Calls**: Tests run quickly without API dependencies

## Test Fixtures

The test suite includes several useful fixtures defined in `conftest.py`:

### Database Fixtures
- `temp_db_path`: Temporary database file path
- `db`: Test database instance
- `sample_event`: Single test event
- `sample_events`: List of test events
- `populated_db`: Database pre-populated with events

### Search Fixtures
- `search`: EventSearch instance for testing queries

### Scraper Fixtures
- `mock_geocoding_service`: Mocked geocoding service (no API calls)
- `temp_geocode_cache`: Temporary geocoding cache file
- `mock_fetch_page`: Mocked fetch_page to avoid network calls
- `mock_fetch_page_js`: Mocked fetch_page_js to avoid Playwright calls

### Web Fixtures
- `app_client`: Test client for FastHTML application

### Playwright Fixtures (E2E)
- `browser`: Browser instance (session-scoped)
- `context`: Browser context for each test
- `page`: Page instance for each test
- `base_url`: Base URL for the application (default: http://127.0.0.1:8000)
- `browser_context_args`: Browser context configuration (viewport, user agent, etc.)

## Writing Tests

### Example Unit Test

```python
import pytest
from src.data.models import Event

@pytest.mark.unit
class TestMyFeature:
    def test_something(self, db, sample_event):
        """Test description."""
        # Arrange
        event = sample_event

        # Act
        db.insert_event(event)

        # Assert
        assert event.id is not None
```

### Example E2E Test

```python
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.e2e
def test_homepage_loads(page: Page, base_url: str):
    """Test that homepage loads successfully."""
    page.goto(base_url)
    expect(page).to_have_title("Westside LA Events")
```

### Using Markers

```python
@pytest.mark.unit  # Unit test
@pytest.mark.e2e   # End-to-end test
@pytest.mark.slow  # Slow running test
@pytest.mark.requires_network  # Requires network access
```

## Known Issues

1. **Web App Tests Disabled**: The web endpoint tests (`_test_web_app.py.disabled`) require fixing some dependency conflicts with system-installed packages.

2. **Database API**: The tests were written assuming a `save_event` method, but the actual Database class uses `insert_event`. This needs to be fixed.

3. **Geocoding Tests**: Tests that make actual geocoding API calls are slow (1 request/second rate limit). Use mocked fixtures when possible.

## Test Coverage Goals

- **Database Layer**: 90%+
- **Search Functionality**: 85%+
- **Scrapers**: 75%+
- **Web Endpoints**: 80%+

## Continuous Integration

To add CI/CD:

1. Create `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src
```

## Tips

1. **Fast Feedback**: Run tests frequently during development
2. **Isolation**: Each test should be independent
3. **Fixtures**: Use fixtures to avoid code duplication
4. **Mocking**: Mock external services (APIs, geocoding) for faster tests
5. **Coverage**: Aim for high coverage but prioritize critical paths

## Troubleshooting

### Import Errors
Use `PYTHONNOUSERSITE=1` to avoid conflicts with system Python packages:
```bash
PYTHONNOUSERSITE=1 micromamba run python -m pytest
```

### Slow Tests
Skip slow tests during development:
```bash
pytest -m "not slow"
```

### Database Locked
Ensure no other processes are using the test database files.

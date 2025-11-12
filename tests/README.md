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
│   ├── test_scrapers.py     # Scraper tests
│   └── _test_web_app.py.disabled  # Web endpoint tests (needs dependency fixes)
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
PYTHONNOUSERSITE=1 micromamba run python -m pytest -m unit

# Run only scraper tests
PYTHONNOUSERSITE=1 micromamba run python -m pytest -m scraper

# Skip slow tests
PYTHONNOUSERSITE=1 micromamba run python -m pytest -m "not slow"
```

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

### Web Fixtures
- `app_client`: Test client for FastHTML application

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

### Using Markers

```python
@pytest.mark.unit  # Unit test
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

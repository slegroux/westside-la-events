# End-to-End Testing with Playwright

This directory contains end-to-end (E2E) tests using Playwright to test the Westside LA Events Aggregator web application in a real browser environment.

## Overview

E2E tests simulate real user interactions with the application, testing the full stack from frontend to backend to database. These tests ensure that features work correctly from a user's perspective.

## Setup

### 1. Install Playwright Browsers

```bash
micromamba run -n la playwright install chromium
```

### 2. Start the Application

Before running E2E tests, you need to start the web server:

```bash
# Terminal 1: Start the web server
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Run the Tests

```bash
# Terminal 2: Run E2E tests
micromamba run -n la python -m pytest tests/e2e/ -v -m e2e
```

## Test Files

### `test_homepage.py`
Tests for the main homepage:
- Page loads successfully
- Header and footer display
- Search bar is visible and functional
- Date and category filters exist
- Events display or show empty state
- Map container exists
- Responsive layout on various viewports
- No JavaScript errors

### `test_search_filters.py`
Tests for search and filtering functionality:
- Keyword search
- Date filters (Today, This Week, This Month)
- Category filters (Music, Art, Food, etc.)
- Combined search and filters
- Filter persistence on navigation
- No results message
- Search input retention
- Results count updates

### `test_event_detail.py`
Tests for individual event detail pages:
- Event detail page loads
- Displays title, description, date, venue, address
- Shows category and source link
- Back/home navigation
- Browser back button works
- Map display
- Event image display
- Invalid event ID shows 404
- Responsive layout
- External links open in new tab

### `test_map_interactions.py`
Tests for map functionality:
- Map container exists
- Map toggle visibility
- Leaflet/Google Maps loads
- Markers display for events
- Marker click shows popup
- Popup contains event information
- Popup link navigation
- Zoom controls work
- Pan/drag functionality
- Marker clustering (if implemented)
- Map updates with filters
- Mobile responsive
- Attribution display

## Running Tests

### Run All E2E Tests

```bash
micromamba run -n la python -m pytest tests/e2e/ -v
```

### Run Specific Test File

```bash
micromamba run -n la python -m pytest tests/e2e/test_homepage.py -v
```

### Run Specific Test

```bash
micromamba run -n la python -m pytest tests/e2e/test_homepage.py::test_homepage_loads -v
```

### Run with Headed Browser (See What's Happening)

```bash
micromamba run -n la python -m pytest tests/e2e/ --headed
```

### Run in Specific Browser

```bash
# Chromium (default)
micromamba run -n la python -m pytest tests/e2e/ --browser chromium

# Firefox (requires: playwright install firefox)
micromamba run -n la python -m pytest tests/e2e/ --browser firefox

# WebKit (requires: playwright install webkit)
micromamba run -n la python -m pytest tests/e2e/ --browser webkit
```

### Run with Slow Motion (Debugging)

```bash
micromamba run -n la python -m pytest tests/e2e/ --slowmo 1000
```

### Run in Parallel (Faster)

```bash
# Requires pytest-xdist
micromamba run -n la python -m pytest tests/e2e/ -n 4
```

## Configuration

### Base URL

By default, tests expect the app to run on `http://127.0.0.1:8000`. To change this:

```bash
export TEST_BASE_URL=http://localhost:3000
micromamba run -n la python -m pytest tests/e2e/
```

### Viewport Sizes

Tests use various viewport sizes defined in `conftest.py`:
- Desktop: 1920x1080
- Laptop: 1366x768
- Tablet: 768x1024
- Mobile: 375x667

### Browser Context

Browser context is configured in `tests/conftest.py` with:
- Viewport: 1920x1080 (default)
- Ignore HTTPS errors: True
- User agent: Chrome Linux

## Debugging Tests

### 1. Run with Headed Browser

See the browser in action:

```bash
micromamba run -n la python -m pytest tests/e2e/test_homepage.py::test_homepage_loads --headed
```

### 2. Use Playwright Inspector

Interactive debugging:

```bash
PWDEBUG=1 micromamba run -n la python -m pytest tests/e2e/test_homepage.py::test_homepage_loads
```

### 3. Screenshots on Failure

Automatically capture screenshots on failure by adding to `conftest.py`:

```python
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page = item.funcargs.get('page')
        if page:
            page.screenshot(path=f"screenshots/{item.name}.png")
```

### 4. Trace Viewer

Record test execution:

```python
context.tracing.start(screenshots=True, snapshots=True)
# ... run test ...
context.tracing.stop(path="trace.zip")
```

Then view:

```bash
playwright show-trace trace.zip
```

## Best Practices

### 1. Wait for Elements Properly

```python
# Good - explicit wait
expect(page.locator('.event-card')).to_be_visible()

# Bad - hard-coded sleep
page.wait_for_timeout(5000)  # Only use for debugging
```

### 2. Use Semantic Selectors

```python
# Good - semantic and resilient
page.locator('button:has-text("Search")')
page.locator('[aria-label="Close"]')

# Okay - specific
page.locator('.search-button')

# Bad - fragile
page.locator('div > div > button:nth-child(3)')
```

### 3. Handle Optional Elements

```python
# Check if element exists before interacting
if page.locator('.modal').count() > 0:
    page.locator('.modal-close').click()
```

### 4. Test User Flows, Not Implementation

```python
# Good - tests user behavior
def test_user_can_find_music_events(page, base_url):
    page.goto(base_url)
    page.fill('input[type="search"]', 'music')
    page.click('button:has-text("Search")')
    expect(page.locator('.event-card')).to_have_count_greater_than(0)

# Bad - tests implementation details
def test_search_api_returns_results(page, base_url):
    # Testing internal API details
```

### 5. Keep Tests Independent

Each test should be able to run independently:
- Don't rely on state from previous tests
- Use fixtures to set up test data
- Clean up after tests

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install chromium

      - name: Start application
        run: |
          uvicorn src.web.app:app --host 0.0.0.0 --port 8000 &
          sleep 5

      - name: Run E2E tests
        run: pytest tests/e2e/ -v

      - name: Upload screenshots on failure
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-screenshots
          path: screenshots/
```

## Troubleshooting

### "Browser not found"

```bash
micromamba run -n la playwright install chromium
```

### "Connection refused"

Make sure the web server is running:

```bash
micromamba run -n la uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

### "Element not found"

- Check if the element exists in your implementation
- Use `page.wait_for_selector()` to wait for dynamic content
- Run with `--headed` to see what's happening
- Use Playwright Inspector with `PWDEBUG=1`

### Tests are flaky

- Add proper waits: `expect().to_be_visible()` instead of `wait_for_timeout()`
- Wait for network: `page.wait_for_load_state('networkidle')`
- Increase timeouts for slow operations
- Use `page.wait_for_selector()` with timeout

## Further Reading

- [Playwright Documentation](https://playwright.dev/python/)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)
- [Playwright Selectors](https://playwright.dev/python/docs/selectors)
- [Playwright Assertions](https://playwright.dev/python/docs/test-assertions)

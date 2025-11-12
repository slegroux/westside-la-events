# Scraper Testing Strategy

## Overview

Web scrapers are fragile by nature - websites change frequently, and when they do, your scraper breaks. This guide outlines a comprehensive testing strategy to catch these changes early.

## Why Test Scrapers?

1. **Websites change**: HTML structure, CSS classes, and page layouts evolve
2. **Silent failures**: Scrapers often fail silently, returning empty results
3. **Data quality**: Bad scrapes lead to bad data in your database
4. **Early detection**: Tests catch issues before users notice missing events

## Three-Tier Testing Approach

### Tier 1: Unit Tests (Fast, Offline)
**Purpose**: Test scraper logic with mocked HTML responses

**Characteristics**:
- Run on every code change
- No network calls
- Fast execution (< 1 second)
- Use saved HTML snapshots

**Example**:
```python
@pytest.mark.unit
@patch.object(KCRWScraper, 'fetch_page')
def test_scrape_extracts_events(mock_fetch, kcrw_scraper, sample_html):
    mock_fetch.return_value = sample_html
    events = kcrw_scraper.scrape()
    assert len(events) > 0
```

### Tier 2: Integration Tests (Slow, Live)
**Purpose**: Test against live websites to catch structure changes

**Characteristics**:
- Run daily or before releases
- Makes actual HTTP requests
- Slower execution (5-30 seconds per scraper)
- Catches real-world issues

**Example**:
```python
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_network
def test_scrape_live_website(kcrw_scraper):
    events = kcrw_scraper.scrape()
    assert isinstance(events, list)
    if events:
        assert events[0].title is not None
```

### Tier 3: Snapshot Tests (Detective)
**Purpose**: Detect when website HTML structure changes

**Characteristics**:
- Save HTML snapshots periodically
- Compare against baseline
- Alert on structural changes
- Manual review of changes

**Example**:
```python
@pytest.mark.snapshot
def test_html_structure_snapshot(scraper, snapshot_dir):
    html = scraper.fetch_page(scraper.base_url)
    snapshot_file = snapshot_dir / f"snapshot_{date}.html"
    with open(snapshot_file, 'w') as f:
        f.write(html)
```

## Test File Structure

Each scraper should have its own test file:

```
tests/
├── scrapers/
│   ├── __init__.py
│   ├── test_kcrw.py
│   ├── test_timeout.py
│   ├── test_discover_la.py
│   ├── test_santa_monica.py
│   └── snapshots/
│       ├── kcrw/
│       │   └── page_snapshot_20250112.html
│       └── timeout/
│           └── page_snapshot_20250112.html
```

## What to Test

### 1. Initialization
```python
def test_scraper_initialization(scraper):
    assert scraper.source_name == "Expected Name"
    assert scraper.base_url is not None
```

### 2. Error Handling
```python
def test_scrape_handles_network_failure(scraper):
    # Mock network failure
    events = scraper.scrape()
    assert events == []  # Should return empty, not crash
```

### 3. Data Extraction
```python
def test_scrape_extracts_required_fields(scraper, mock_html):
    events = scraper.scrape()
    assert events[0].title is not None
    assert events[0].event_date is not None
    assert events[0].url is not None
```

### 4. URL Normalization
```python
def test_url_normalization(scraper):
    url = scraper.normalize_url("/events/123", "https://site.com")
    assert url == "https://site.com/events/123"
```

### 5. Text Cleaning
```python
def test_text_cleaning(scraper):
    text = scraper.clean_text("  Extra   Spaces  \n")
    assert text == "Extra Spaces"
```

### 6. Live Website Structure
```python
def test_expected_elements_exist(scraper):
    html = scraper.fetch_page(scraper.base_url)
    soup = scraper.parse_html(html)
    # Check for expected elements
    assert soup.find('div', class_='events-list') is not None
```

## Running Tests

### Run all scraper tests
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/ -v
```

### Run unit tests only (fast)
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/ -m unit -v
```

### Run integration tests (slow, live websites)
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/ -m integration -v
```

### Run tests for specific scraper
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/test_kcrw.py -v
```

### Run snapshot tests
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/ -m snapshot -v
```

## Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit              # Fast, offline unit test
@pytest.mark.integration       # Slow, live website test
@pytest.mark.slow              # Takes > 5 seconds
@pytest.mark.requires_network  # Needs internet connection
@pytest.mark.snapshot          # Snapshot/comparison test
```

## When to Run Tests

### On Every Code Change (Pre-commit)
- Unit tests only
- Fast feedback loop
- Catches logic errors

```bash
# Add to .git/hooks/pre-commit
pytest tests/scrapers/ -m unit
```

### Daily (Scheduled)
- Integration tests
- Catches website changes
- Send alerts on failures

```bash
# Cron job
0 6 * * * cd /path/to/project && pytest tests/scrapers/ -m integration
```

### Before Deployment
- All tests
- Ensures everything works
- Blocks deployment on failures

```bash
pytest tests/scrapers/ -v
```

## Monitoring & Alerts

### Set up CI/CD to run tests daily
```yaml
# .github/workflows/scraper-tests.yml
name: Scraper Health Check

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6am
  push:
    paths:
      - 'src/scrapers/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run scraper tests
        run: pytest tests/scrapers/ -v
      - name: Notify on failure
        if: failure()
        run: |
          # Send email/Slack notification
          echo "Scraper tests failed! Website may have changed."
```

### Alert on failures
When integration tests fail:
1. Check if website is down (temporary)
2. Check if HTML structure changed (needs fix)
3. Update scraper code to match new structure
4. Update unit test mocks to match new HTML

## Best Practices

### 1. Keep Mocked HTML Realistic
- Use actual HTML snippets from websites
- Update mocks when websites change
- Keep mocks minimal but representative

### 2. Test Error Cases
- Network failures
- Empty pages
- Malformed HTML
- Missing fields

### 3. Don't Over-Assert
```python
# Bad: Too brittle
assert len(events) == 42

# Good: Flexible
assert len(events) > 0
assert len(events) < 1000
```

### 4. Use Fixtures for Common Setup
```python
@pytest.fixture
def scraper():
    return MyScraper()

@pytest.fixture
def sample_html():
    return Path('tests/fixtures/sample.html').read_text()
```

### 5. Log Useful Debug Info
```python
def test_live_scrape(scraper):
    events = scraper.scrape()
    print(f"\nScraped {len(events)} events")
    if events:
        print(f"Sample: {events[0].title}")
```

## Debugging Failed Tests

### Step 1: Run the test in isolation
```bash
pytest tests/scrapers/test_kcrw.py::test_scrape_live_website -v -s
```

### Step 2: Inspect the HTML
```python
# Add to test
html = scraper.fetch_page(scraper.base_url)
with open('/tmp/debug.html', 'w') as f:
    f.write(html)
print("Saved HTML to /tmp/debug.html")
```

### Step 3: Update the scraper
- Compare current HTML with expected structure
- Update CSS selectors/parsing logic
- Update unit test mocks

### Step 4: Re-run tests
```bash
pytest tests/scrapers/test_kcrw.py -v
```

## Creating Tests for New Scrapers

When adding a new scraper, use this checklist:

- [ ] Create `tests/scrapers/test_<scraper_name>.py`
- [ ] Add unit tests with mocked HTML
- [ ] Add integration test against live site
- [ ] Add snapshot test to track structure
- [ ] Test error handling (network failures, empty pages)
- [ ] Test URL normalization
- [ ] Test text cleaning
- [ ] Add example HTML fixture
- [ ] Document expected HTML structure
- [ ] Run full test suite to verify

## Example: Complete Test File

See [tests/scrapers/test_kcrw.py](../tests/scrapers/test_kcrw.py) for a complete example implementing all three tiers of testing.

## Common Issues

### Tests pass but scraper returns empty results
- Website may require JavaScript (use Playwright)
- Website may block automated requests (add user agent)
- Rate limiting (add delays between requests)

### Integration tests flaky
- Add retries for network requests
- Increase timeouts
- Check if website has rate limiting

### Too many false positives
- Make assertions more flexible
- Don't assert exact counts
- Focus on data structure, not values

## Summary

Good scraper testing:
1. **Prevents silent failures** - Know immediately when scrapers break
2. **Catches website changes** - Integration tests detect HTML changes
3. **Fast feedback** - Unit tests run on every commit
4. **Low maintenance** - Flexible assertions reduce false positives
5. **Confidence** - Deploy knowing your scrapers work

Start with unit tests for all scrapers, add integration tests for critical ones, and run them daily to catch issues early.

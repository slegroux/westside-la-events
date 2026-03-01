# Contributing to Westside LA Events Aggregator

Thank you for your interest in contributing! This guide will help you get started.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Adding a New Scraper](#adding-a-new-scraper)
- [Testing Guidelines](#testing-guidelines)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment
- Report inappropriate behavior to project maintainers

## Getting Started

### Prerequisites
- Python 3.10 or higher
- micromamba (recommended) or venv
- Git
- Basic knowledge of web scraping and FastHTML

### Setup Development Environment

1. **Fork and clone the repository**:
```bash
git clone https://github.com/YOUR_USERNAME/LA.git
cd LA
```

2. **Set up conda environment**:
```bash
conda create -n la python=3.11 -y
conda activate la
pip install -r requirements.txt -r requirements-dev.txt
```

3. **Configure environment variables**:
```bash
cp .env.example .env
# Edit .env with your API keys (optional for local development)
```

4. **Initialize the database**:
```bash
conda run -n la python -c "from src.data.database import Database; Database('data/events.db')"
```

5. **Run tests to verify setup**:
```bash
conda run -n la python -m pytest tests/unit/ --ignore=tests/e2e -v
```

## Development Workflow

### Branch Strategy
- `master` - main branch (stable code)
- `feature/your-feature-name` - new features
- `fix/bug-description` - bug fixes
- `scraper/source-name` - new scrapers

### Standard Workflow
```bash
# Create a feature branch
git checkout -b feature/my-new-feature

# Make your changes
# ... edit files ...

# Run tests
conda run -n la python -m pytest tests/unit/ --ignore=tests/e2e -v

# Commit your changes
git add .
git commit -m "feat: add new feature"

# Push to your fork
git push origin feature/my-new-feature

# Open a pull request on GitHub
```

## Adding a New Scraper

Scrapers are the core of this project! Here's how to add one:

### Step 1: Check Event Source Type

Read [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md) to determine if the source has:
- An official API (preferred)
- Structured data that can be scraped
- Dynamic content requiring Playwright

### Step 2: Create Scraper File

Create `src/scrapers/source_name.py`:

```python
"""
Scraper for [Source Name] events.
Source: https://example.com/events
"""
from typing import List
from datetime import datetime
from bs4 import BeautifulSoup

from .base import BaseScraper
from src.data.models import Event


class SourceNameScraper(BaseScraper):
    """Scraper for [Source Name] events."""

    def __init__(self):
        super().__init__('Source Name')
        self.base_url = 'https://example.com'

    def scrape(self) -> List[Event]:
        """
        Scrape events from [Source Name].

        Returns:
            List of Event objects
        """
        events = []

        try:
            # Fetch the events page
            response = self.session.get(f'{self.base_url}/events', timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Parse events
            event_elements = soup.select('.event-card')

            for element in event_elements:
                try:
                    # Extract event data
                    title = element.select_one('.title').text.strip()
                    description = element.select_one('.description').text.strip()
                    venue_name = element.select_one('.venue').text.strip()
                    address = element.select_one('.address').text.strip()
                    date_str = element.select_one('.date').text.strip()
                    url = element.select_one('a')['href']

                    # Parse date
                    event_date = self.parse_date(date_str)

                    # Geocode address
                    coords = self.geocode_address(address)

                    # Create event
                    event = Event(
                        title=title,
                        description=description,
                        venue_name=venue_name,
                        address=address,
                        latitude=coords['lat'] if coords else None,
                        longitude=coords['lng'] if coords else None,
                        event_date=event_date,
                        source=self.source_name,
                        url=url,
                        source_logo_url=self.source_logo_url
                    )

                    # Validate event is in target area
                    if self.is_in_target_area(event):
                        events.append(event)

                except Exception as e:
                    self.logger.warning(f"Error parsing event: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error scraping {self.source_name}: {e}")

        return events
```

### Step 3: Configure the Scraper

Add to `config.py`:

```python
EVENT_SOURCES = {
    'source_name': {
        'name': 'Source Name',
        'url': 'https://example.com/events',
        'enabled': True
    }
}
```

### Step 4: Register the Scraper

Add to `run_scrapers.py`:

```python
from src.scrapers.source_name import SourceNameScraper

# In the scrapers list
if config.EVENT_SOURCES['source_name']['enabled']:
    scrapers.append(SourceNameScraper())
```

### Step 5: Test Your Scraper

Create `tests/scrapers/test_source_name.py`:

```python
"""Tests for Source Name scraper."""
import pytest
from src.scrapers.source_name import SourceNameScraper


def test_source_name_scraper():
    """Test Source Name scraper."""
    scraper = SourceNameScraper()
    events = scraper.scrape()

    assert len(events) > 0, "Should scrape at least one event"

    for event in events:
        assert event.title, "Event should have a title"
        assert event.source == 'Source Name'
        assert event.url, "Event should have a URL"
```

Run your test:
```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/scrapers/test_source_name.py -v
```

### Step 6: Test Manually

```bash
# Run just your scraper
micromamba run -n la python -c "from src.scrapers.source_name import SourceNameScraper; scraper = SourceNameScraper(); events = scraper.scrape(); print(f'Scraped {len(events)} events')"
```

### Required Reading for Scrapers
- [docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) - Best practices
- [docs/SCRAPER_TESTING.md](docs/SCRAPER_TESTING.md) - Testing guide
- [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md) - API vs scraping

## Testing Guidelines

### Test Requirements
- All new features must include tests
- Maintain or improve test coverage
- Tests must pass before PR approval

### Running Tests
```bash
# All tests
conda run -n la python -m pytest tests/unit/ --ignore=tests/e2e -v

# Specific test file
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/test_database.py -v

# With coverage
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/ --cov=src --cov-report=html
```

### Test Markers
```python
@pytest.mark.unit           # Unit tests
@pytest.mark.integration    # Integration tests
@pytest.mark.scraper        # Scraper tests
@pytest.mark.slow           # Slow tests (skip with -m "not slow")
```

See [tests/README.md](tests/README.md) for detailed testing guide.

## Code Style

### Python Style Guide
- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use docstrings for all classes and functions

### Example
```python
def scrape_events(url: str, limit: int = 10) -> List[Event]:
    """
    Scrape events from a URL.

    Args:
        url: The URL to scrape
        limit: Maximum number of events to return

    Returns:
        List of Event objects

    Raises:
        RequestException: If the request fails
    """
    # Implementation
    pass
```

### Imports
- Standard library imports first
- Third-party imports second
- Local imports last
- Alphabetically sorted within each group

```python
# Standard library
from datetime import datetime
from typing import List, Optional

# Third-party
import requests
from bs4 import BeautifulSoup

# Local
from .base import BaseScraper
from src.data.models import Event
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `EventScraper`)
- Functions/Methods: `snake_case` (e.g., `scrape_events`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Private methods: `_leading_underscore` (e.g., `_parse_date`)

## Pull Request Process

### Before Submitting
1. ✅ Tests pass locally
2. ✅ Code follows style guidelines
3. ✅ Documentation updated (if needed)
4. ✅ Commit messages are clear
5. ✅ Branch is up to date with master

### PR Checklist
- [ ] Title clearly describes the change
- [ ] Description explains what and why
- [ ] Tests included for new features
- [ ] Documentation updated
- [ ] No unrelated changes included
- [ ] Linked to related issue (if any)

### PR Template
```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature (scraper, feature, etc.)
- [ ] Documentation update
- [ ] Refactoring

## Testing
How was this tested?

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Code follows style guide
```

### Review Process
1. Automated tests run on PR
2. Code review by maintainer(s)
3. Address feedback
4. Approval and merge

## Issue Reporting

### Before Creating an Issue
- Search existing issues to avoid duplicates
- Verify the issue in the latest version
- Gather relevant information (logs, screenshots, etc.)

### Issue Types

#### Bug Report
```markdown
**Description**
Clear description of the bug

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.10]
- Browser (if applicable): [e.g., Chrome 120]

**Logs/Screenshots**
Add any relevant logs or screenshots
```

#### Feature Request
```markdown
**Problem/Use Case**
What problem does this solve?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Any other relevant information
```

#### New Scraper Request
```markdown
**Event Source**
Name and URL of the event source

**Source Type**
- [ ] Has official API
- [ ] Requires web scraping
- [ ] Requires JavaScript rendering

**Why This Source?**
Why should this be added?

**Example Events**
Link to 2-3 example events
```

## Getting Help

- **Documentation**: Check [docs/](docs/) for guides
- **Issues**: Search or create GitHub issues
- **Questions**: Open a discussion on GitHub
- **Project Management**: See [docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md)

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- Release notes
- Project README (for significant contributions)

Thank you for contributing to making LA event discovery better! 🎉

# Westside LA Events Aggregator

A FastHTML-powered web application that aggregates events from multiple sources across LA's Westside, providing a unified search interface with date filtering, activity type categorization, and Google Maps geolocation visualization.

## Features

- **Multi-Source Aggregation**: Collects events from Santa Monica, Timeout LA, KCRW, UCLA, museums, and more
- **Advanced Search**: Search by keywords, date range, category, and location
- **Interactive Map**: Google Maps visualization with clustered markers and info windows
- **Smart Categorization**: Automatic event classification into categories (Music, Art, Food & Drink, etc.)
- **Geocoding**: Automatic address-to-coordinates conversion for map display
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Google Maps API key (for map visualization - optional for testing)
- Google Geocoding API key (for address geocoding - optional for testing)
- (Optional) direnv + micromamba for automatic environment activation

**Note:** The scrapers work with **no API keys required**! They use web scraping only. Google API keys are only needed for the map visualization and geocoding features.

### Installation

#### Option 1: Using direnv + micromamba (Recommended)

This project uses **direnv** to automatically activate the **micromamba environment** when you enter the project directory.

1. Install micromamba (if not installed):
```bash
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)
```

2. Create the micromamba environment:
```bash
micromamba create -n la python=3.10 -y
micromamba activate la
pip install -r requirements.txt
```

3. Configure direnv (if not already configured):
```bash
# Add to ~/.bashrc or ~/.zshrc
eval "$(direnv hook bash)"  # For bash
eval "$(direnv hook zsh)"   # For zsh
```

4. Allow direnv for this project:
```bash
direnv allow
```

Now the `la` environment will **automatically activate** when you enter this directory!

**Benefits:**
- No need to manually activate the environment
- Consistent environment across terminal sessions
- Automatic `.env` loading for API keys
- Clean separation between projects

5. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Google API keys
```

5. Initialize the database:
```bash
micromamba run python -c "from src.data.database import Database; Database('data/events.db')"
```

#### Option 2: Using venv (Alternative)

**Note:** Using micromamba (Option 1) is recommended for this project as all documentation and scripts assume micromamba usage.

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your Google API keys
```

4. Initialize the database:
```bash
python -c "from src.data.database import Database; Database('data/events.db')"
```

**Important:** If using venv, replace `micromamba run python` with just `python` and `micromamba run uvicorn` with just `uvicorn` in all commands below.

### Running the Application

1. **Run scrapers to collect events**:
```bash
micromamba run python run_scrapers.py
```

2. **Start the web server**:
```bash
micromamba run uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
```

3. **Open your browser** and navigate to:
```
http://127.0.0.1:8000
```

**Note:** Always use `micromamba run` to ensure the correct environment is activated with all dependencies. The `--reload` flag enables automatic reloading during development.

## Project Structure

```
LA/
├── src/
│   ├── data/           # Database models and operations
│   ├── scrapers/       # Event scrapers for each source
│   ├── search/         # Search and filter functionality
│   ├── utils/          # Utilities (geocoding, categorization)
│   └── web/            # FastHTML web application
├── static/
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript for map integration
├── tests/             # Test suite
│   ├── README.md      # Testing guide
│   └── unit/          # Unit tests
├── docs/              # Technical documentation
│   ├── EVENT_SOURCES.md
│   ├── SCRAPING_GUIDE.md
│   ├── QUICK_REFERENCE.md
│   ├── fasthtml_analysis.md
│   └── TEST_COVERAGE_ANALYSIS.md
├── data/              # SQLite database and cache files
├── logs/              # Application logs
├── config.py          # Configuration settings
├── run_scrapers.py    # Script to run all scrapers
├── requirements.txt   # Python dependencies
├── README.md          # This file
├── PLAN.md            # Implementation roadmap
├── CLAUDE.md          # AI assistant instructions
└── SDD.md             # Software Design Document
```

## Configuration

Edit `config.py` or `.env` to customize:

- **API Keys**: Google Maps and Geocoding API keys
- **Database Path**: Location of SQLite database
- **Scraper Settings**: User agent, delays, timeouts
- **Event Sources**: Enable/disable specific scrapers
- **Geographic Bounds**: Define Westside LA boundaries
- **Categories**: Customize event categories

## Usage

### Search Events

- **Keyword Search**: Enter terms in the search box
- **Date Filters**: Select from predefined ranges (Today, This Week, This Month, etc.)
- **Category Filter**: Filter by event type (Music, Art, Food & Drink, etc.)
- **View Toggle**: Switch between List View and Map View

### Map View

- Click on markers to see event details
- Markers are color-coded by category
- Automatic clustering for better performance
- Click "View Details" to visit the original event page

### Running Scrapers

Run all enabled scrapers:
```bash
micromamba run python run_scrapers.py
```

Run scrapers on a schedule (using cron):
```bash
# Add to crontab for daily scraping at 3 AM
0 3 * * * cd /path/to/LA && micromamba run python run_scrapers.py
```

## Data Sources

Currently implemented scrapers:

- **Santa Monica**: City events and activities
- **Timeout LA**: Curated LA events and things to do
- **KCRW**: Music and cultural events

Planned scrapers:

- Discover LA (DoLA)
- UCLA Events
- Hammer Museum
- LACMA
- The Broad
- Getty Center
- Various concert venues and bars

## Development

### Adding a New Scraper

1. Create a new scraper file in `src/scrapers/`:
```python
from .base import BaseScraper
from src.data.models import Event

class NewSourceScraper(BaseScraper):
    def __init__(self):
        super().__init__('Source Name')
        self.base_url = 'https://example.com'

    def scrape(self):
        # Implement scraping logic
        pass
```

2. Add the source to `config.py`:
```python
EVENT_SOURCES = {
    'new_source': {
        'name': 'New Source',
        'url': 'https://example.com/events',
        'enabled': True
    }
}
```

3. Add to `run_scrapers.py`:
```python
from src.scrapers.new_source import NewSourceScraper

if config.EVENT_SOURCES['new_source']['enabled']:
    scrapers.append(NewSourceScraper())
```

### Database Schema

Events table:
- `id`: Primary key
- `title`: Event title
- `description`: Event description
- `venue_name`: Venue name
- `address`: Full address
- `latitude`, `longitude`: Coordinates
- `event_date`: Start date/time
- `end_date`: End date/time
- `category`: Event category
- `source`: Data source
- `url`: Original event URL
- `image_url`: Event image
- `created_at`, `updated_at`: Timestamps

## API Endpoints

- `GET /`: Home page with search and map
- `GET /api/events`: Get events (supports query parameters: `q`, `date_filter`, `category`)
- `GET /api/events/{id}`: Get single event by ID

## Troubleshooting

### No events showing

1. Run the scrapers first: `micromamba run python run_scrapers.py`
2. Check database: `ls -lh data/events.db`
3. Check logs for errors

### Map not loading

1. Verify Google Maps API key in `.env`
2. Check browser console for errors
3. Ensure API key has Maps JavaScript API enabled

### Geocoding not working

1. Verify Google Geocoding API key in `.env`
2. Check geocoding cache: `cat data/geocode_cache.json`
3. API may have rate limits or require billing enabled

### Scrapers failing

1. Websites may have changed their structure
2. Update selectors in scraper files
3. Check for rate limiting or blocking
4. Inspect target website first

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Event data provided by respective sources
- Built with [FastHTML](https://fastht.ml)
- Maps powered by Google Maps Platform
- Icons and design inspired by modern web standards

## Documentation

- **[README.md](README.md)** - This file (project overview and quick start)
- **[PLAN.md](PLAN.md)** - Development roadmap and implementation plan
- **[SDD.md](SDD.md)** - Software Design Document (architecture and technical details)
- **[CLAUDE.md](CLAUDE.md)** - AI assistant instructions
- **[docs/](docs/)** - Detailed technical documentation
  - [EVENT_SOURCES.md](docs/EVENT_SOURCES.md) - Event source implementation guide
  - [SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) - Web scraping best practices
  - [QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) - FastHTML quick reference
  - [fasthtml_analysis.md](docs/fasthtml_analysis.md) - Detailed FastHTML analysis
  - [TEST_COVERAGE_ANALYSIS.md](docs/TEST_COVERAGE_ANALYSIS.md) - Test coverage report
- **[tests/README.md](tests/README.md)** - Testing guide

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check [SDD.md](SDD.md) for architecture details
- Review [PLAN.md](PLAN.md) for implementation roadmap
- See [docs/](docs/) for detailed technical documentation

---

Made with ❤️ for the LA community

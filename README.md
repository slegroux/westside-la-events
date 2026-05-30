# Westside LA Events Aggregator

> **Live Demo**: https://westside-events-406046958598.us-west1.run.app

A FastHTML-powered web application that aggregates events from 60+ sources across LA's Westside, providing a unified search interface with intelligent filtering, interactive maps, and analytics.

## Features

- **Multi-Source Aggregation**: 60+ scrapers collecting events from venues, museums, cultural centers, and community organizations
- **Smart Search**: Full-text search with date filtering, category tags, and location-based queries
- **Interactive Maps**: Leaflet + OpenStreetMap visualization with clustered markers and detailed event cards
- **Analytics Dashboard**: Track popular events, user engagement, and traffic sources
- **Favorites System**: Save and manage your favorite events across sessions
- **Responsive Design**: Optimized for desktop, tablet, and mobile devices

## Quick Start

### Prerequisites

- Python 3.11+
- Google Geocoding API key (optional - only for address geocoding)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/slegroux/LA.git
cd LA

# 2. Create environment
micromamba create -n la python=3.11 -y
micromamba activate la

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up configuration
cp .env.example .env
# Edit .env to add API keys (optional for testing)

# 5. Initialize database
python -c "from src.data.database import Database; Database('data/events.db')"
```

### Running Locally

```bash
# Collect events
micromamba run -n la python run_scrapers.py

# Start server
micromamba run -n la uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload

# Open browser
open http://127.0.0.1:8000
```

## Data Sources

Currently scraping 60+ sources including:

**Venues & Cultural Centers**
- Santa Monica, West Hollywood, Culver City official sites
- KCRW, UCLA, Venice West, Winston House
- Westside Comedy, Aviator Nation, Gnarwhal

**Museums & Arts**
- Hammer Museum, LACMA, UCLA Botanical Garden
- Beyond Baroque, Raymond Kabbaz

**Event Platforms**
- Timeout LA, Eventbrite, Meetup, Resident Advisor
- LA Tech Events, Nerd Nite, IIC LA

**Specialty**
- Parks California, Aero Theater, ITK LA
- Penmar Golf Course, Casual Creative

See [docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md) for complete list and implementation details.

## Deployment

Deploy your own instance to Google Cloud Run (free tier):

```bash
# Deploy code
./scripts/deploy.sh

# Update production data (after deployment)
./scripts/sync_db_to_cloud.sh --run-scrapers --force
```

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for complete deployment guide covering:
- Google Cloud Run (recommended)
- Railway
- Database syncing workflow
- Custom domains
- Monitoring and cost management

## Documentation

### Getting Started
- **[README.md](README.md)** - This file (project overview)
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Local development setup
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment guide
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Technical Docs
- **[docs/SDD.md](docs/SDD.md)** - Software design document (architecture)
- **[docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md)** - Web scraping best practices
- **[docs/EVENT_SOURCES.md](docs/EVENT_SOURCES.md)** - Event source implementation guide
- **[docs/ANALYTICS.md](docs/ANALYTICS.md)** - Analytics system documentation
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - FastHTML quick reference

### Testing & Contributing
- **[tests/README.md](tests/README.md)** - Testing guide
- **[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)** - Contribution guidelines
- **[scripts/README.md](scripts/README.md)** - Utility scripts documentation

## Project Structure

```
LA/
├── src/
│   ├── data/           # Database models and operations
│   ├── scrapers/       # Event scrapers (60+ sources)
│   ├── search/         # Search and filter functionality
│   ├── utils/          # Geocoding, categorization
│   └── web/            # FastHTML web application
├── static/             # CSS, JavaScript, logos
├── tests/              # Unit, integration, E2E tests
├── docs/               # Technical documentation
├── scripts/            # Utility scripts
└── data/               # SQLite databases and caches
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for detailed project structure.

## Development

### Add a New Scraper

```python
# src/scrapers/new_venue.py
from .base import BaseScraper
from src.data.models import Event

class NewVenueScraper(BaseScraper):
    def __init__(self):
        super().__init__('New Venue Name')

    def scrape(self):
        # Your scraping logic here
        return events
```

See [docs/SCRAPING_GUIDE.md](docs/SCRAPING_GUIDE.md) for complete guide.

### Run Tests

```bash
# All tests
micromamba run -n la python -m pytest

# With coverage
micromamba run -n la python -m pytest --cov=src

# Specific scraper suite
micromamba run -n la python -m pytest tests/unit/test_all_scrapers.py -k "TimeoutScraper" -v
```

See [tests/README.md](tests/README.md) for testing guide.

## Tech Stack

- **Framework**: [FastHTML](https://fastht.ml) - Modern Python web framework
- **Database**: SQLite with full-text search
- **Maps**: Leaflet + OpenStreetMap (no API key required)
- **Scraping**: BeautifulSoup4, requests, Playwright
- **Testing**: pytest, Playwright (E2E)
- **Deployment**: Docker, Google Cloud Run

## Configuration

Key settings in `config.py` and `.env`:

```python
# API Keys (optional - only for geocoding addresses)
GOOGLE_GEOCODING_API_KEY = "your_key"

# Database paths
DATABASE_PATH = "data/events.db"
ANALYTICS_DB_PATH = "data/analytics.db"

# Scraper settings
SCRAPER_CONFIG = {
    'delay_seconds': 1,    # delay between requests
    'timeout_seconds': 30, # per-request timeout
}

# Geographic bounds (Westside LA)
WESTSIDE_BOUNDS = {
    'min_lat': 33.90, 'max_lat': 34.15,
    'min_lng': -118.75, 'max_lng': -118.33
}
```

See [docs/DEVELOPMENT.md#configuration](docs/DEVELOPMENT.md#configuration) for complete configuration guide.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## Roadmap

See [PLAN.md](PLAN.md) for detailed development roadmap.

**Current priorities:**
- [x] Add more venue scrapers (60+ sources and counting)
- [ ] Implement user accounts and personalized recommendations
- [ ] Mobile app (React Native)
- [ ] Email notifications for saved searches
- [ ] Enhanced recommendation engine based on user preferences

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- Event data provided by respective sources
- Built with [FastHTML](https://fastht.ml) by Jeremy Howard
- Maps powered by [Leaflet](https://leafletjs.com) and [OpenStreetMap](https://www.openstreetmap.org)
- Inspired by the vibrant LA Westside community

## Support

- **Issues**: [GitHub Issues](https://github.com/slegroux/LA/issues)
- **Documentation**: [docs/](docs/)
- **Deployment Help**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

**Made with ❤️ for the LA community**

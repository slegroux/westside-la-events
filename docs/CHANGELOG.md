# Changelog

All notable changes to the Westside LA Events Aggregator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Documentation index at [docs/README.md](docs/README.md)
- Comprehensive [CONTRIBUTING.md](CONTRIBUTING.md) guide
- API reference documentation at [docs/API.md](docs/API.md)
- Project changelog
- GitHub workflow automation scripts
- Pull request templates
- Security policy
- New scrapers:
  - Penmar Golf & Tennis
  - Resident Advisor
  - LAist
  - ITK LA
  - Nerd Nite LA
- Scraper testing framework ([docs/SCRAPER_TESTING.md](docs/SCRAPER_TESTING.md))
- URL deduplication enhancement ([docs/URL_DEDUPLICATION_ENHANCEMENT.md](docs/URL_DEDUPLICATION_ENHANCEMENT.md))
- Logo scraping for event sources ([docs/LOGO_IMPLEMENTATION.md](docs/LOGO_IMPLEMENTATION.md))
- Full-text search security improvements ([docs/SECURITY_FTS_FIX.md](docs/SECURITY_FTS_FIX.md))
- Event scheduler documentation ([docs/SCHEDULER.md](docs/SCHEDULER.md))
- Data quality guidelines ([docs/SCRAPER_DATA_QUALITY.md](docs/SCRAPER_DATA_QUALITY.md))
- Issue tracking workflow ([docs/GITHUB_WORKFLOW.md](docs/GITHUB_WORKFLOW.md))

### Changed
- Improved scraper architecture with enhanced error handling
- Enhanced category classification system
- Updated geocoding to use cache-first approach
- Refined geographic filtering for Westside LA boundaries
- Improved date parsing across multiple scrapers

### Fixed
- SQL injection vulnerability in full-text search
- Geocoding cache race conditions
- Event deduplication edge cases
- Date parsing for various date formats

### Documentation
- Reorganized documentation structure
- Added use-case-based documentation navigation
- Enhanced scraping strategy guide
- Improved testing documentation
- Added deployment guide for Railway platform

## [0.1.0] - 2025-01-XX

### Added
- Initial release of Westside LA Events Aggregator
- FastHTML-based web application
- SQLite database with full-text search
- Interactive map with Leaflet + OpenStreetMap
- Event scrapers:
  - Santa Monica events
  - Timeout LA
  - KCRW
  - Discover LA
  - Eventbrite
  - Aviator Nation
  - Venice West
- Core features:
  - Keyword search
  - Date filtering (today, this week, this month, etc.)
  - Category filtering (music, art, food & drink, etc.)
  - Free events filter
  - Map view with markers and clustering
  - Event detail pages
  - iCalendar export
- Geocoding service with caching
- Automatic event categorization
- Geographic boundary filtering for Westside LA
- Responsive design for mobile and desktop
- Error handling and logging
- Configuration management

### Documentation
- Project README with quick start guide
- Software Design Document (SDD)
- Development plan (PLAN.md)
- AI assistant instructions (CLAUDE.md)
- Technical documentation:
  - Event sources guide
  - Web scraping guide
  - FastHTML quick reference
  - FastHTML analysis
  - Test coverage analysis
- Testing guide

### Infrastructure
- micromamba environment setup
- direnv integration for automatic environment activation
- pytest testing framework
- GitHub issue templates
- Railway deployment configuration

## Release Notes

### Version 0.1.0 (Initial Release)

This is the first release of the Westside LA Events Aggregator! 🎉

**Key Features:**
- Aggregates events from 7+ sources across LA's Westside
- Beautiful, responsive web interface built with FastHTML
- Interactive map powered by OpenStreetMap (100% free, no API key required)
- Smart search with date and category filters
- Automatic event categorization and geocoding
- Add events directly to your calendar (iCal format)

**Event Sources:**
- Santa Monica city events
- Timeout LA curated events
- KCRW music and cultural events
- Discover LA tourism events
- Eventbrite public events
- Aviator Nation Venice events
- Venice West events

**For Developers:**
- Well-documented codebase with comprehensive guides
- Easy scraper development framework
- Extensive test coverage
- Clean architecture with separation of concerns

**Known Limitations:**
- Geographic filtering limited to Westside LA (Santa Monica, Venice, Mar Vista, etc.)
- Geocoding requires Google API key (optional, works without it)
- Some event descriptions may not load immediately (lazy loading implemented)
- No user accounts or favorites yet

**Coming Soon:**
- More event sources (UCLA, museums, concert venues)
- Advanced filters (price range, accessibility)
- Event deduplication across sources
- User favorites and notifications
- Performance optimizations

---

## How to Update This Changelog

When making changes to the project, please update the `[Unreleased]` section following these categories:

- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Security fixes

When releasing a new version:

1. Change `[Unreleased]` to the version number and date: `[0.2.0] - 2025-02-15`
2. Add a new `[Unreleased]` section above it
3. Add release notes below the version entries
4. Tag the release in git: `git tag -a v0.2.0 -m "Release version 0.2.0"`

See [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) for more details.

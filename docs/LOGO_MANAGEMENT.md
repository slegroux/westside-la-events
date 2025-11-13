# Logo Management Guide

This document explains how to manage source logos in the Westside LA Events Aggregator.

## Overview

Event cards display logos for their source (e.g., "Discover LA", "KCRW", etc.). The logo system:
- Automatically scrapes logos from source websites
- Falls back to manually configured logo URLs
- Caches logos locally in `static/logos/`
- Stores logo paths in the database (`source_logo_url` field)

## Architecture

### Key Files
- **[src/utils/logo_scraper.py](../src/utils/logo_scraper.py)** - Logo scraping and caching logic
- **[migrate_logos.py](../migrate_logos.py)** - Script to update all events with logos
- **[check_missing_logos.py](../check_missing_logos.py)** - Diagnostic script to find missing mappings
- **[static/logos/](../static/logos/)** - Cached logo files

### Logo Resolution Flow

1. **Manual logos** (highest priority): Check `static/logos/` for manually provided files
2. **Scraping**: Attempt to scrape logo from source website using `SOURCE_URLS`
3. **Fallback**: Use pre-configured URL from `FALLBACK_LOGOS`
4. **None**: Return `None` if no logo found (logs warning)

## Adding a New Source

When you create a new scraper, follow these steps to add logo support:

### 1. Add Source URL Mapping

Edit [src/utils/logo_scraper.py](../src/utils/logo_scraper.py) and add your source to `SOURCE_URLS`:

```python
SOURCE_URLS = {
    'Your Source Name': 'https://www.example.com',
    # ... other sources
}
```

### 2. Add Fallback Logo URL

Add a fallback logo URL to `FALLBACK_LOGOS`:

```python
FALLBACK_LOGOS = {
    'Your Source Name': 'https://www.example.com/logo.png',
    # ... other sources
}
```

**Finding the logo URL:**
- Visit the source's website
- Right-click on their logo → "Inspect Element"
- Copy the image URL (often in header or footer)
- Or check `<meta property="og:image">` tags

### 3. Update Database

Run the migration script to download and cache the logo:

```bash
micromamba run -n la python migrate_logos.py
```

This script:
- Downloads all logos to `static/logos/`
- Updates all existing events with `source_logo_url`

### 4. Verify

Check that your source now has logos:

```bash
micromamba run -n la python check_missing_logos.py
```

## Manual Logo Override

If automatic scraping fails or you want to use a custom logo:

1. Save the logo file to `static/logos/` with the naming pattern:
   ```
   source_name_in_lowercase_with_underscores.png
   ```
   Example: `your_source_name.png`

2. The system will automatically detect and use this file instead of scraping

3. Supported formats: `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`, `.webp`

## Troubleshooting

### Events Missing Logos

**Symptoms:** Event cards show source name as text instead of logo

**Diagnosis:**
```bash
micromamba run -n la python check_missing_logos.py
```

**Solution:**
1. Add missing source to `SOURCE_URLS` and `FALLBACK_LOGOS`
2. Run `migrate_logos.py`

### Logo Not Updating

**Symptoms:** Changed logo URL but events still show old logo

**Solution:**
1. Delete cached logo file in `static/logos/`
2. Run `migrate_logos.py` to re-download

### New Scraper Events Have No Logos

**Symptoms:** New events from a recently added scraper lack logos

**Causes:**
- Source not in `SOURCE_URLS`/`FALLBACK_LOGOS`
- Scraper not inheriting from `BaseScraper` (which auto-fetches logos)

**Solution:**
1. Ensure scraper extends `BaseScraper`
2. Add source to logo mappings
3. Run `migrate_logos.py` for existing events

## Maintenance

### Regular Checks

Run periodically to ensure all sources have logos:

```bash
micromamba run -n la python check_missing_logos.py
```

### Adding Bulk Sources

When adding multiple scrapers:

1. Add all sources to `SOURCE_URLS` and `FALLBACK_LOGOS`
2. Run one migration: `micromamba run -n la python migrate_logos.py`

### Logo Cache Cleanup

To force re-download of all logos:

```bash
# Remove cached logos
rm static/logos/*.{png,jpg,svg,webp}

# Re-download
micromamba run -n la python migrate_logos.py
```

## Implementation Details

### Database Schema

```sql
-- events table
source_logo_url TEXT  -- Local path like "/static/logos/kcrw.png"
```

### BaseScraper Integration

All scrapers inherit from `BaseScraper`, which:
- Initializes `LogoScraper` on construction
- Calls `download_logo(source_name)` to cache logo locally
- Sets `self.source_logo_url` for use when creating events

Example from scraper:

```python
class MySourceScraper(BaseScraper):
    def __init__(self):
        super().__init__("My Source Name")
        # self.source_logo_url is now available

    def scrape(self) -> List[Event]:
        events = []
        # ... scraping logic ...
        event = Event(
            title="Event Title",
            source=self.source_name,
            source_logo_url=self.source_logo_url,  # Use cached logo
            # ... other fields
        )
        events.append(event)
        return events
```

## Best Practices

1. **Always use BASE_SCRAPER**: Inherit from `BaseScraper` to get automatic logo handling
2. **Test locally**: Manually verify logos display correctly in the UI
3. **Fallback URLs**: Always provide a fallback URL in case scraping fails
4. **High-quality logos**: Use at least 200x200px logos for best display
5. **SVG preferred**: Vector logos (SVG) scale better across screen sizes
6. **Run checks**: Use `check_missing_logos.py` before deploying new scrapers

## Related Documentation

- [docs/SCRAPING_GUIDE.md](./SCRAPING_GUIDE.md) - How to create new scrapers
- [src/utils/logo_scraper.py](../src/utils/logo_scraper.py) - Logo scraper implementation
- [src/scrapers/base.py](../src/scrapers/base.py) - Base scraper with logo integration

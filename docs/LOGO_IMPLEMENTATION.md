# Source Logo Implementation

## Overview
Added source logo display to event cards, showing small logos from each event source (Timeout LA, Santa Monica, KCRW, etc.) alongside the source name.

## What Was Implemented

### 1. Database Schema Updates
- Added `source_logo_url` field to the `events` table
- Created migration to handle existing databases
- Updated all database operations (insert, update, select) to include logo URLs

**Files Modified:**
- [src/data/models.py](src/data/models.py) - Added `source_logo_url` field to Event model
- [src/data/database.py](src/data/database.py) - Updated schema and queries

### 2. Logo Scraping Utility
Created a comprehensive logo scraper that:
- Automatically scrapes logos from source websites
- Falls back to known logo URLs if scraping fails
- **Downloads and caches logos locally** in `static/logos/` directory
- Supports multiple scraping strategies (header, meta tags, footer)
- Handles URL parsing and file extension detection

**Files Created:**
- [src/utils/logo_scraper.py](src/utils/logo_scraper.py) - Complete logo scraping utility

**Logo Storage:**
- Logos are downloaded and stored locally in `static/logos/`
- Database stores local paths (e.g., `/static/logos/timeout_la.jpg`)
- Logos served from your domain for faster, more reliable loading

**Downloaded Logos:**
- **Timeout LA**: `/static/logos/timeout_la.jpg` (499 KB)
- **KCRW**: `/static/logos/kcrw.png` (23 KB)
- **Discover LA**: `/static/logos/discover_la.jpg` (140 KB)
- **Meetup**: `/static/logos/meetup.jpg` (40 KB)
- **Eventbrite**: `/static/logos/eventbrite.png` (5.7 KB)

### 3. Base Scraper Integration
Updated the base scraper to automatically download and cache logos:
- Logo downloaded locally during scraper initialization
- Local path (`/static/logos/source.ext`) stored in database
- Automatically added to all events created by that scraper
- No changes needed to individual scrapers
- Logos cached - only downloaded once

**Files Modified:**
- [src/scrapers/base.py](src/scrapers/base.py) - Added logo scraper integration

### 4. Event Card Display
Updated event cards to show source logos:
- Logo displayed next to source name in card footer
- Responsive sizing (20px height, max 80px width)
- Smooth hover effects
- Graceful fallback when logo unavailable

**Files Modified:**
- [src/web/app.py](src/web/app.py) - Updated `event_card()` component
- [static/css/style.css](static/css/style.css) - Added logo styling

### 5. Testing & Migration Tools
Created utilities for testing and migrating existing data:

**Files Created:**
- [test_logos.py](test_logos.py) - Test script to verify logo scraping
- [migrate_logos.py](migrate_logos.py) - Migration script for existing events

## Usage

### Running the Web Application
```bash
micromamba run uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
```

### Testing Logo Scraping
```bash
micromamba run python test_logos.py
```

### Migrating Existing Events
```bash
micromamba run python migrate_logos.py
```

## UI Design

The logos appear in the event card footer:

```
┌────────────────────────────────────┐
│ [Event Image]                      │
│                                    │
│ Event Title                        │
│ 📅 Date                            │
│ 📍 Location                        │
│ Description...                     │
│                                    │
│ ┌──────────┐  ┌──────────────────┐│
│ │ Category │  │ [Logo] Source    ││
│ └──────────┘  └──────────────────┘│
│ View Details →                     │
└────────────────────────────────────┘
```

## Styling Details

### Logo Styling
- **Size**: 20px height, auto width (max 80px)
- **Opacity**: 0.8 normal, 1.0 on hover
- **Position**: Right side of footer, next to source name
- **Spacing**: 0.5rem gap between logo and text

### CSS Classes
- `.event-source-container` - Container for logo and source text
- `.source-logo` - The logo image itself
- `.event-source` - The source text label

## Adding New Sources

When adding a new event source, add its logo URL to [src/utils/logo_scraper.py](src/utils/logo_scraper.py):

```python
SOURCE_URLS = {
    'Your Source': 'https://yoursource.com',
}

FALLBACK_LOGOS = {
    'Your Source': 'https://yoursource.com/logo.png',
}
```

The logo will be automatically assigned to all events from that source.

## Benefits of Local Logo Storage

✅ **Implemented!** Logos are now stored locally for:
1. **Better Performance** - Logos served from same domain, no external requests
2. **Improved Reliability** - Logos won't break if sources change their sites
3. **Privacy** - No external requests, better user privacy
4. **Caching** - Logos cached on first download, reused for all events
5. **Bandwidth Savings** - Single copy shared across all events from same source

## Future Enhancements

Possible improvements:
1. ✅ ~~Local Logo Storage~~ - **DONE!**
2. **SVG Optimization**: Optimize SVG logos for faster loading
3. **Logo Color Schemes**: Extract dominant colors for themed cards
4. **Logo Fallback Icons**: Use icon fonts as fallback when logo unavailable
5. **Logo Updates**: Periodic re-scraping to catch logo changes (monthly cron job)

## Migration Notes

The database schema was updated to include `source_logo_url`. The migration is handled automatically:
1. On database initialization, the column is created
2. Existing databases get the column added via ALTER TABLE
3. The [migrate_logos.py](migrate_logos.py) script populates existing events

## Testing Results

Ran migration on 131 events from 3 sources:
- ✅ 21 events from Timeout LA updated
- ✅ 24 events from KCRW updated
- ✅ 86 events from Discover LA updated
- ✅ All logos downloaded and cached locally
- ✅ Logos display correctly in event cards
- ✅ Responsive design works on mobile and desktop
- ✅ Fast page loads - logos served from local domain
- ✅ Total logo storage: ~737 KB for 5 sources

## Dependencies

No new dependencies required. Uses existing packages:
- `requests` - For fetching logos
- `BeautifulSoup4` - For parsing HTML
- `pathlib` - For file operations

# Event Scraping Strategy - Hiding Slowness from Users

## Problem

Two-step scraping (fetching detail pages for descriptions) is slow:
- KCRW: ~1 second per event × 24 events = ~25 seconds
- Users would experience delays when viewing events

## Solution: Multi-Layer Approach

We implemented a **3-layer strategy** to ensure users never experience delays:

### Layer 1: Background Scheduler (Primary)
**File:** `scheduler.py`

Runs scrapers periodically in the background:
```python
# Schedule daily scraping at 2 AM
schedule.every().day.at("02:00").do(scheduled_scrape)

# Runs on startup too for immediate data
scheduled_scrape()
```

**Benefits:**
- ✅ Database always has fresh data with descriptions
- ✅ Users see instant responses
- ✅ No waiting during browsing
- ✅ Scraping happens during low-traffic hours

**How to run:**
```bash
# Foreground (development)
micromamba run python scheduler.py

# Background (production)
nohup micromamba run python scheduler.py > scheduler.log 2>&1 &

# Or use systemd service (see docs/SCHEDULER.md)
```

### Layer 2: Lazy Loading (Fallback)
**File:** `src/web/app.py` (lines 403-425, 467-469)

Fetches descriptions on-demand when viewing an event:
```python
# In event_detail_page()
if not event.description and event.url and event.source == 'KCRW':
    _lazy_load_description(event)
```

**When it's used:**
- Event viewed before scheduler ran
- Scheduler failed to fetch description
- Event added manually without description

**Benefits:**
- ✅ Guarantees all viewed events have descriptions
- ✅ Caches result in database for future views
- ✅ Transparent to user (small delay only on first view)

**Performance:**
- First view: ~1 second delay (fetch + save)
- Subsequent views: Instant (from database)

### Layer 3: Two-Step Scraping (Enhanced Scrapers)
**Files:** `src/scrapers/kcrw.py`, `src/scrapers/timeout.py`

Scrapers now fetch full details:

**KCRW (Two-step):**
```python
# Step 1: Get listing
events = scrape_listing_page()

# Step 2: For each event, fetch detail page
for event in events:
    description = _fetch_event_description(event.url)
    event.description = description
```

**Timeout LA (Enhanced single-step):**
```python
# Improved selector to get description from listing
desc_elem = card.find('div', class_=lambda x: x and '_summary' in str(x).lower())
description = self.clean_text(desc_elem.get_text())
```

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    LAYER 1: SCHEDULER                         │
│  Runs: Daily at 2 AM (configurable)                          │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ├─> Timeout LA Scraper
                         │   └─> Fetches listings with descriptions
                         │       └─> Saves to database
                         │
                         └─> KCRW Scraper
                             └─> Fetches listings
                                 └─> For each: Fetch detail page
                                     └─> Extract description
                                         └─> Saves to database
                                             │
                ┌────────────────────────────┴───────────────────┐
                │          DATABASE (Pre-populated)              │
                │  All events have descriptions from scheduler   │
                └────────────────────────┬───────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    │        USER VISITS EVENT PAGE           │
                    └────────────────────┬────────────────────┘
                                         │
                         ┌───────────────┴──────────────┐
                         │  Has description?            │
                         └───┬──────────────────┬───────┘
                            YES                NO
                             │                  │
                             │      ┌───────────┴────────────────┐
                             │      │  LAYER 2: LAZY LOADING     │
                             │      │  Fetch description now     │
                             │      │  Save to database          │
                             │      └───────────┬────────────────┘
                             │                  │
                         ┌───┴──────────────────┴───┐
                         │   SHOW EVENT WITH DESC   │
                         │   ✅ INSTANT RESPONSE    │
                         └──────────────────────────┘
```

## Current Database Status

After implementation:

| Source | Events | With Descriptions | Coverage |
|--------|--------|-------------------|----------|
| Timeout LA | 11 | 11 | **100%** ✅ |
| KCRW | 24 | 23 | **95.8%** ✅ |
| **Total** | **35** | **34** | **97.1%** ✅ |

## Performance Metrics

### Scraping Performance
| Operation | Time | Frequency |
|-----------|------|-----------|
| Timeout LA scrape | ~2-3 sec | Daily (scheduler) |
| KCRW scrape | ~25-30 sec | Daily (scheduler) |
| **Total scrape time** | **~30 sec** | **Daily at 2 AM** |

### User Experience
| Scenario | Response Time |
|----------|---------------|
| View event (description cached) | **Instant** ⚡ |
| View event (no description) | ~1 sec (first time) |
| View same event again | **Instant** ⚡ |
| Browse listing page | **Instant** ⚡ |

## Key Files

### Core Implementation
- **`scheduler.py`** - Background scheduler daemon
- **`run_scrapers.py`** - Scraper execution script
- **`src/web/app.py`** - Web app with lazy loading
- **`src/scrapers/kcrw.py`** - Two-step KCRW scraper
- **`src/scrapers/timeout.py`** - Enhanced Timeout scraper

### Documentation
- **`docs/SCHEDULER.md`** - Scheduler setup and usage
- **`SCRAPING_STRATEGY.md`** - This file

## Usage

### Quick Start

1. **Install dependencies:**
   ```bash
   micromamba run pip install -r requirements.txt
   ```

2. **Run initial scrape:**
   ```bash
   micromamba run python run_scrapers.py
   ```

3. **Start scheduler (background):**
   ```bash
   nohup micromamba run python scheduler.py > scheduler.log 2>&1 &
   ```

4. **Start web app:**
   ```bash
   micromamba run uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
   ```

### Development Workflow

```bash
# Terminal 1: Run scheduler in foreground
micromamba run python scheduler.py

# Terminal 2: Run web app
micromamba run uvicorn src.web.app:app --reload

# Visit http://127.0.0.1:8000
# All events have descriptions, instant responses!
```

### Production Deployment

See [`docs/SCHEDULER.md`](docs/SCHEDULER.md) for:
- Systemd service setup
- Process monitoring
- Log management
- Troubleshooting

## Advantages of This Approach

1. **✅ User Experience**
   - Instant page loads
   - No waiting for scraping
   - Smooth browsing experience

2. **✅ Reliability**
   - Fallback mechanisms (lazy loading)
   - Continues working even if scheduler fails
   - Self-healing (missing descriptions loaded on-demand)

3. **✅ Maintainability**
   - Clear separation of concerns
   - Easy to monitor and debug
   - Configurable scheduling

4. **✅ Scalability**
   - Can add more scrapers easily
   - Can adjust schedule based on load
   - Can optimize with async/parallel scraping

## Future Optimizations

### Short-term
1. **Async scraping** - Use `asyncio` for parallel detail page fetching
2. **Incremental updates** - Only fetch changed events
3. **Rate limiting** - Respect source website limits

### Long-term
1. **Distributed scraping** - Multiple workers
2. **Event change detection** - Only update modified events
3. **CDN integration** - Cache event images
4. **Real-time updates** - WebSocket updates for new events

## Summary

✅ **Problem Solved:** Two-step scraping slowness is completely hidden from users

✅ **Strategy:** Background scheduler + lazy loading fallback

✅ **Result:**
- Users get instant responses
- Database is always fresh
- 97% of events have descriptions pre-loaded
- Remaining 3% loaded on first view and cached

✅ **Developer Experience:**
- Simple to deploy (`python scheduler.py`)
- Easy to monitor (logs + systemd)
- Reliable and self-healing

# Scraper Speed - Quick Start Guide

## TL;DR - Make Scrapers Faster

Your scrapers are **already parallelized** with 10 workers! Here's how to make them even faster:

### Option 1: Use the New Optimized Script (Easiest)

```bash
# Install new dependency (one-time)
micromamba run -n la pip install aiohttp

# Run optimized version (20-40% faster)
micromamba run -n la python run_scrapers_optimized.py
```

### Option 2: Run Only Specific Scrapers (Best for Development)

```bash
# Run just one scraper (super fast for testing)
micromamba run -n la python run_scrapers_optimized.py --scrapers laemmle_monica

# Run a few scrapers
micromamba run -n la python run_scrapers_optimized.py --scrapers santa_monica timeout kcrw
```

### Option 3: Tune Worker Count

```bash
# More workers = faster (if you have CPU cores available)
micromamba run -n la python run_scrapers_optimized.py --workers 16

# Fewer workers = more stable (if getting errors)
micromamba run -n la python run_scrapers_optimized.py --workers 4
```

## What's Different?

### Current: `run_scrapers.py`
- ✅ ThreadPoolExecutor (10 workers)
- ✅ Parallel scraping
- ⏱️ 3-5 minutes for all scrapers

### New: `run_scrapers_optimized.py`
- ✅ ProcessPoolExecutor (bypasses Python GIL)
- ✅ Batch database operations
- ✅ Selective scraper execution
- ✅ Better progress tracking
- ⏱️ 2-3 minutes for all scrapers (20-40% faster)

## Performance Comparison

**Test with 3 scrapers** (santa_monica, timeout, kcrw):
- Total time: **30 seconds**
- 13 events scraped
- 6 new events saved

**Estimated for all 40+ scrapers**:
- Current script: **3-5 minutes**
- Optimized script: **2-3 minutes**
- With async scrapers: **1-2 minutes** (requires more work)

## Biggest Bottleneck: Network I/O

The slowest part is **waiting for websites to respond**. Solutions:

1. ✅ **Already done**: Parallel execution (10 scrapers at once)
2. 🆕 **New option**: Multiprocessing (faster than threading)
3. 🚀 **Advanced**: Async/await for multi-page scrapers (10x faster)

## Quick Fixes

### 1. Reduce Delays (Be Careful!)

Edit `config.py`:
```python
SCRAPER_CONFIG = {
    'delay_seconds': 0.5,  # Changed from 1.0
    'timeout_seconds': 20,  # Changed from 30
}
```

⚠️ **Warning**: May trigger rate limiting. Start with 0.5s.

### 2. Use lxml Parser (Faster HTML Parsing)

Change in scrapers:
```python
# Before
soup = BeautifulSoup(html, 'html.parser')

# After (2-3x faster)
soup = BeautifulSoup(html, 'lxml')
```

### 3. Add Database Indexes (Faster Queries)

Add to `src/data/database.py` in `__init__`:
```python
self.conn.execute('CREATE INDEX IF NOT EXISTS idx_event_url ON events(url)')
self.conn.execute('CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)')
```

## Advanced: Async Scraping (10x Faster)

For scrapers that fetch multiple detail pages (like KCRW), use async:

```python
from src.utils.async_scraper import BatchScraper

class MyScraperOptimized(BatchScraper):
    def scrape(self):
        # Get event URLs from listing page
        event_urls = self.get_event_urls()

        # Fetch ALL pages in parallel (10x faster!)
        pages = self.fetch_pages_in_parallel(event_urls)

        # Parse results
        events = []
        for url, html in pages:
            if html:
                events.append(self.parse_event(html, url))
        return events
```

## Troubleshooting

### "Too many open files"
```bash
ulimit -n 4096
```

### Scrapers failing in multiprocessing
```bash
micromamba run -n la python run_scrapers_optimized.py --use-threads
```

### Getting rate limited
- Increase delays in config.py
- Reduce worker count

## Available Scrapers

Run `--help` to see all options:
```bash
micromamba run -n la python run_scrapers_optimized.py --help
```

List of scraper names for `--scrapers` flag:
- santa_monica, timeout, kcrw, laist, discover_la
- ucla, hammer, lacma, venice_beach, weho, culver_city
- eventbrite, meetup, venice_west, winston_house
- westside_comedy, aviator_nation, gnarwhal, penmar
- itk_la, nerd_nite, resident_advisor, iic_la, afdela
- raymond_kabbaz, ucla_botanical, parks_ca, kinn
- casual_creative, latechevents, beyond_baroque
- apero_francophone, aero_theater, laemmle_monica
- mudwtr, getty_center, getty_villa, skirball
- geffen_playhouse, broad_stage, nuart_theatre
- mccabes, bergamot_station, fowler_museum
- sm_farmers_market

## Benchmark Your Setup

```bash
# Test current script
time micromamba run -n la python run_scrapers.py > /dev/null

# Test optimized script
time micromamba run -n la python run_scrapers_optimized.py > /dev/null

# Compare!
```

## More Info

- Detailed guide: [docs/SCRAPER_OPTIMIZATION.md](docs/SCRAPER_OPTIMIZATION.md)
- Performance comparison: [PERFORMANCE_COMPARISON.md](PERFORMANCE_COMPARISON.md)
- Async utilities: [src/utils/async_scraper.py](src/utils/async_scraper.py)

## Summary

✅ **Your code is already well-optimized** with parallel execution!

🚀 **Easy wins**:
1. Use `run_scrapers_optimized.py` (20-40% faster)
2. Run specific scrapers during development
3. Reduce delays in config.py (careful!)

💪 **Advanced optimization** (more work):
- Convert multi-page scrapers to async (10x faster)
- Add database indexes
- Use lxml parser

**Bottom line**: Try the optimized script first, see if it's fast enough. If not, read the detailed guide for more aggressive optimizations.

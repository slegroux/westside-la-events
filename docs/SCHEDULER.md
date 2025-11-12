# Event Scraper Scheduler

This document explains how to set up and run the background scheduler for automatic event scraping.

## Overview

The scheduler runs scrapers periodically to keep the event database fresh with the latest data. This ensures that:
- Users always see up-to-date events
- Event descriptions are pre-loaded (no delays when viewing event details)
- The application is fast and responsive

## Architecture

### Components

1. **`scheduler.py`** - Background daemon that runs scrapers on schedule
2. **`run_scrapers.py`** - Script that executes all enabled scrapers
3. **Lazy Loading** - Fallback mechanism in the web app for missing descriptions

### Data Flow

```
┌─────────────────┐
│   Scheduler     │ Runs daily at 2 AM
│  (scheduler.py) │
└────────┬────────┘
         │
         ├──> Run all scrapers (run_scrapers.py)
         │
         ├──> Timeout LA: Fetch listing + descriptions
         │
         ├──> KCRW: Fetch listing + detail pages
         │
         └──> Save to database
              ↓
         Database is fresh
              ↓
         Web app serves fast responses
```

## Running the Scheduler

### Option 1: Manual Run (Development)

```bash
# Run scheduler in foreground
micromamba run python scheduler.py
```

The scheduler will:
1. Run all scrapers immediately on startup
2. Then wait and run daily at 2:00 AM

Press `Ctrl+C` to stop.

### Option 2: Background Process (Production)

```bash
# Run in background
nohup micromamba run python scheduler.py > scheduler.log 2>&1 &

# Check if running
ps aux | grep scheduler.py

# View logs
tail -f scheduler.log

# Stop scheduler
pkill -f scheduler.py
```

### Option 3: Systemd Service (Recommended for Production)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/la-events-scheduler.service
```

Add the following content (adjust paths):

```ini
[Unit]
Description=LA Events Scraper Scheduler
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/LA
Environment="PATH=/home/your-username/micromamba/envs/la/bin:/usr/bin"
ExecStart=/home/your-username/micromamba/envs/la/bin/python scheduler.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable la-events-scheduler

# Start service
sudo systemctl start la-events-scheduler

# Check status
sudo systemctl status la-events-scheduler

# View logs
sudo journalctl -u la-events-scheduler -f

# Stop service
sudo systemctl stop la-events-scheduler
```

## Schedule Configuration

Edit `scheduler.py` to customize the schedule:

```python
# Default: Daily at 2 AM
schedule.every().day.at("02:00").do(scheduled_scrape)

# Alternative schedules:

# Every 6 hours
schedule.every(6).hours.do(scheduled_scrape)

# Twice daily
schedule.every().day.at("02:00").do(scheduled_scrape)
schedule.every().day.at("14:00").do(scheduled_scrape)

# Every day at specific times
schedule.every().day.at("00:00").do(scheduled_scrape)
schedule.every().day.at("06:00").do(scheduled_scrape)
schedule.every().day.at("12:00").do(scheduled_scrape)
schedule.every().day.at("18:00").do(scheduled_scrape)
```

## Lazy Loading Fallback

Even with the scheduler, the web app has a **lazy loading fallback** for events without descriptions:

```python
# In src/web/app.py - event_detail_page()

if not event.description and event.url and event.source == 'KCRW':
    _lazy_load_description(event)
```

**When it's used:**
- Event is viewed before scheduler has run
- Event was added manually without description
- Scheduler failed to fetch description

**How it works:**
1. User visits event detail page
2. Check if description is missing
3. If missing, fetch from source URL immediately
4. Cache in database for future views

**Performance:**
- First view: ~1 second delay (fetching from source)
- Subsequent views: Instant (from database)

## Manual Scraping

Run scrapers manually without the scheduler:

```bash
# Run all enabled scrapers
micromamba run python run_scrapers.py

# Takes ~25-30 seconds for KCRW (fetches detail pages)
# Takes ~2-3 seconds for Timeout LA
```

## Monitoring

### Check Scheduler Status

```bash
# If using systemd
sudo systemctl status la-events-scheduler

# If using background process
ps aux | grep scheduler.py
```

### View Logs

```bash
# Scheduler logs
tail -f scheduler.log

# Web app logs (for lazy loading)
tail -f app.log
```

### Database Statistics

```bash
micromamba run python -c "
from src.data.database import Database
import config

db = Database(config.DATABASE_PATH)
events = db.get_all_events(limit=10000)

total = len(events)
with_desc = sum(1 for e in events if e.description)

print(f'Total events: {total}')
print(f'With descriptions: {with_desc} ({with_desc/total*100:.1f}%)')
"
```

## Troubleshooting

### Scheduler won't start

```bash
# Check Python environment
micromamba run python --version

# Check dependencies
micromamba run pip install schedule

# Run manually to see errors
micromamba run python scheduler.py
```

### Events not updating

```bash
# Check last scrape time
grep "scheduled scrape" scheduler.log | tail -5

# Run scrapers manually
micromamba run python run_scrapers.py

# Check database
sqlite3 data/events.db "SELECT COUNT(*) FROM events;"
```

### Lazy loading not working

Check web app logs for errors:
```bash
tail -f app.log | grep "lazy load"
```

## Best Practices

1. **Schedule during low traffic**: Default 2 AM is ideal
2. **Monitor logs**: Check for scraping errors regularly
3. **Database backups**: Backup `data/events.db` before each scrape
4. **Rate limiting**: Scrapers include delays to avoid overwhelming sources
5. **Error handling**: Scheduler continues running even if individual scrapers fail

## Performance

### Scraping Times (Approximate)

| Source | Events | Time | Reason |
|--------|--------|------|--------|
| Timeout LA | ~11 | 2-3 sec | Single-step (descriptions on listing) |
| KCRW | ~24 | 25-30 sec | Two-step (fetch detail pages) |
| **Total** | **~35** | **~30 sec** | Sequential scraping |

### Optimization Ideas

1. **Async scraping**: Use `asyncio` and `aiohttp` for parallel requests
2. **Incremental updates**: Only scrape new/changed events
3. **Caching**: Cache detail pages for a few hours
4. **CDN**: Serve event images from CDN

## Summary

✅ **Scheduler runs daily at 2 AM**
✅ **Database always has fresh data**
✅ **Users see instant responses (no waiting)**
✅ **Lazy loading as fallback for edge cases**
✅ **Easy to monitor and maintain**

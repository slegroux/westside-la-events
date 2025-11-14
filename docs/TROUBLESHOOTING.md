# Troubleshooting Guide

Common issues and their solutions.

## Table of Contents
- [Installation Issues](#installation-issues)
- [Application Issues](#application-issues)
- [Scraper Issues](#scraper-issues)
- [Database Issues](#database-issues)
- [Map and Geocoding Issues](#map-and-geocoding-issues)
- [Deployment Issues](#deployment-issues)

---

## Installation Issues

### Micromamba not found

**Symptoms**: `command not found: micromamba`

**Solution**:
```bash
# Install micromamba
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)

# Restart shell or source bashrc
source ~/.bashrc  # or ~/.zshrc
```

### Environment activation fails

**Symptoms**: `EnvironmentLocationNotFound: Not a conda environment`

**Solution**:
```bash
# Create the environment
micromamba create -n la python=3.10 -y

# Activate manually
micromamba activate la

# Verify
which python  # Should show path in micromamba/envs/la/
```

### Missing dependencies

**Symptoms**: `ModuleNotFoundError: No module named 'fasthtml'`

**Solution**:
```bash
# Ensure you're in the correct environment
micromamba activate la

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fasthtml; print(fasthtml.__version__)"
```

---

## Application Issues

### No events showing

**Symptoms**: Website loads but shows "No events found"

**Solution**:
```bash
# 1. Run scrapers first
micromamba run -n la python run_scrapers.py

# 2. Check database exists and has data
ls -lh data/events.db
micromamba run -n la python -c "from src.data.database import Database; db = Database('data/events.db'); print(f'Events: {len(db.get_events())}')"

# 3. Check logs
tail -f logs/app.log
```

### Port already in use

**Symptoms**: `Address already in use` or `OSError: [Errno 48]`

**Solution**:
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
micromamba run -n la uvicorn src.web.app:app --port 8001
```

### Module import errors

**Symptoms**: `ImportError: attempted relative import with no known parent package`

**Solution**:
```bash
# Always use micromamba run from project root
cd /path/to/LA
micromamba run -n la python run_scrapers.py

# NOT: python src/scrapers/timeout.py (will fail)
```

### Static files not loading

**Symptoms**: CSS/JS not loading, 404 errors in console

**Solution**:
```bash
# Verify static files exist
ls -la static/css/
ls -la static/js/

# Check file permissions
chmod -R 755 static/

# Clear browser cache
# Chrome: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)
```

---

## Scraper Issues

### All scrapers failing

**Symptoms**: `run_scrapers.py` completes but no events added

**Solution**:
```bash
# 1. Check internet connection
curl -I https://timeout.com/los-angeles

# 2. Check user agent isn't blocked
micromamba run -n la python -c "import requests; r = requests.get('https://timeout.com/los-angeles', headers={'User-Agent': 'Mozilla/5.0...'}); print(r.status_code)"

# 3. Run scrapers with verbose logging
micromamba run -n la python run_scrapers.py --verbose

# 4. Test individual scraper
micromamba run -n la python -c "from src.scrapers.timeout import TimeoutScraper; print(len(TimeoutScraper().scrape()))"
```

### Specific scraper failing

**Symptoms**: One scraper returns empty list or errors

**Possible causes:**
1. Website structure changed
2. Rate limiting / blocking
3. Network issues
4. Invalid selectors

**Solution**:
```bash
# 1. Inspect the target website manually
open https://example.com/events

# 2. Run scraper test
micromamba run -n la python -m pytest tests/scrapers/test_timeout.py -v

# 3. Check recent scraper changes
git log -- src/scrapers/timeout.py

# 4. Use debug script
micromamba run -n la python scripts/debug_scraper.py timeout
```

### Playwright scrapers failing

**Symptoms**: `playwright._impl._api_types.Error: Executable doesn't exist`

**Solution**:
```bash
# Install Playwright browsers
micromamba run -n la playwright install chromium

# Or install all browsers
micromamba run -n la playwright install
```

### Rate limiting

**Symptoms**: `429 Too Many Requests` or empty responses after initial success

**Solution**:
```python
# In scraper code, add delays
import time
time.sleep(2)  # Wait 2 seconds between requests

# Or in config.py:
REQUEST_DELAY = 2  # seconds
```

---

## Database Issues

### Database locked

**Symptoms**: `sqlite3.OperationalError: database is locked`

**Solution**:
```bash
# 1. Close all connections to database
pkill -f "python.*run_scrapers"
pkill -f "uvicorn.*app"

# 2. Check for stale lock files
ls -la data/events.db-*
rm data/events.db-journal  # If exists and no processes using it

# 3. Enable WAL mode (better concurrency)
micromamba run -n la python -c "import sqlite3; conn = sqlite3.connect('data/events.db'); conn.execute('PRAGMA journal_mode=WAL'); conn.close()"
```

### Database corrupted

**Symptoms**: `sqlite3.DatabaseError: database disk image is malformed`

**Solution**:
```bash
# 1. Backup existing database
cp data/events.db data/events.db.backup

# 2. Try to recover
sqlite3 data/events.db ".recover" | sqlite3 data/events_recovered.db

# 3. If recovery fails, restore from backup or recreate
rm data/events.db
micromamba run -n la python -c "from src.data.database import Database; Database('data/events.db')"
micromamba run -n la python run_scrapers.py
```

### Duplicate events

**Symptoms**: Same event appearing multiple times

**Solution**:
```bash
# Check for duplicates
micromamba run -n la python scripts/check_duplicates.py

# Clean up duplicates
micromamba run -n la python scripts/cleanup_duplicates.py
```

---

## Map and Geocoding Issues

### Map not loading

**Symptoms**: Blank map area or "For development purposes only" watermark

**Possible causes:**
1. Missing or invalid Google Maps API key
2. API key not enabled for Maps JavaScript API
3. Billing not enabled (required even for free tier)

**Solution**:
```bash
# 1. Verify API key in .env
cat .env | grep GOOGLE_MAPS_API_KEY

# 2. Check API key restrictions in Google Cloud Console
# https://console.cloud.google.com/apis/credentials

# 3. Enable Maps JavaScript API
# https://console.cloud.google.com/apis/library/maps-backend.googleapis.com

# 4. Enable billing (required even for free usage)
# https://console.cloud.google.com/billing
```

### Geocoding not working

**Symptoms**: Events appear but without map markers, or "No location" messages

**Solution**:
```bash
# 1. Check Geocoding API key
cat .env | grep GOOGLE_GEOCODING_API_KEY

# 2. Enable Geocoding API in Google Cloud Console
# https://console.cloud.google.com/apis/library/geocoding-backend.googleapis.com

# 3. Check geocoding cache
cat data/geocode_cache.json | jq '.'

# 4. Manually geocode missing locations
micromamba run -n la python scripts/geocode_missing.py

# 5. Check API quotas
# https://console.cloud.google.com/apis/api/geocoding-backend.googleapis.com/quotas
```

### Events outside Westside bounds

**Symptoms**: Events appearing that are not in Westside LA

**Solution**:
```bash
# 1. Check geographic bounds in config.py
grep -A5 "WESTSIDE_BOUNDS" config.py

# 2. Remove non-Westside events
micromamba run -n la python scripts/cleanup_non_westside_events.py

# 3. Update scrapers to filter by location
# See docs/SCRAPING_GUIDE.md
```

---

## Deployment Issues

### Docker build fails

**Symptoms**: `docker build` errors or image won't start

**Solution**:
```bash
# 1. Check Dockerfile syntax
docker build --no-cache -t westside-events .

# 2. Check logs
docker logs <container_id>

# 3. Test locally first
docker run -p 8000:8000 westside-events

# 4. Check for missing files
ls -la Dockerfile requirements.txt
```

### Cloud Run deployment fails

**Symptoms**: Deployment completes but service doesn't start

**Solution**:
```bash
# 1. Check deployment logs
gcloud run logs tail westside-events --region us-west1

# 2. Verify environment variables
gcloud run services describe westside-events --region us-west1 --format="value(spec.template.spec.containers[0].env)"

# 3. Check memory limits
gcloud run services describe westside-events --region us-west1 --format="value(spec.template.spec.containers[0].resources.limits.memory)"

# 4. Redeploy with increased memory
gcloud run deploy westside-events --memory 2Gi --region us-west1
```

For more deployment issues, see [docs/DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting).

---

## Performance Issues

### Slow scraper execution

**Symptoms**: `run_scrapers.py` takes > 10 minutes

**Solution**:
```bash
# 1. Run scrapers in parallel (already enabled)
# Check MAX_WORKERS in run_scrapers.py

# 2. Disable slow scrapers temporarily
# Comment out in run_scrapers.py

# 3. Use caching
# Geocoding cache already implemented

# 4. Profile slow scrapers
micromamba run -n la python -m cProfile -o profile.stats run_scrapers.py
```

### Slow website loading

**Symptoms**: Pages take > 3 seconds to load

**Solution**:
```bash
# 1. Check database size
ls -lh data/events.db

# 2. Add indexes
micromamba run -n la python -c "from src.data.database import Database; db = Database('data/events.db'); db.create_indexes()"

# 3. Limit results
# In src/search/query.py, add LIMIT clause

# 4. Enable caching
# FastHTML has built-in caching
```

---

## Testing Issues

### Tests failing

**Symptoms**: `pytest` returns failures

**Solution**:
```bash
# 1. Run tests with verbose output
micromamba run -n la python -m pytest -v

# 2. Run specific failing test
micromamba run -n la python -m pytest tests/unit/test_database.py::test_get_events -v

# 3. Check test dependencies
pip list | grep pytest

# 4. Clear pytest cache
rm -rf .pytest_cache
micromamba run -n la python -m pytest --cache-clear
```

### Playwright tests failing

**Symptoms**: E2E tests timeout or can't find elements

**Solution**:
```bash
# 1. Run with headed browser (see what's happening)
micromamba run -n la python -m pytest tests/e2e/ --headed

# 2. Increase timeout
# In conftest.py: page.set_default_timeout(30000)

# 3. Take screenshots on failure
# Already configured in conftest.py

# 4. Check browser installation
micromamba run -n la playwright install --dry-run
```

---

## Getting Help

If you're still stuck:

1. **Check logs**: `tail -f logs/app.log`
2. **Search issues**: https://github.com/YOUR_USERNAME/LA/issues
3. **Create issue**: Include error messages, OS, Python version
4. **Documentation**: Review [docs/](../docs/)
5. **Test individually**: Isolate the problem component

---

## API Reference

Quick reference for debugging:

### API Endpoints

```bash
# Get all events
curl http://localhost:8000/api/events

# Search events
curl "http://localhost:8000/api/events?q=music&category=Music"

# Get specific event
curl http://localhost:8000/api/events/123

# Trigger scrapers (production only, requires auth)
curl -X POST http://localhost:8000/api/run-scrapers \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Database Queries

```python
from src.data.database import Database

db = Database('data/events.db')

# Get all events
events = db.get_events()

# Search events
events = db.search_events(query='music', category='Music')

# Get event by ID
event = db.get_event(123)

# Get events by date range
from datetime import datetime, timedelta
start = datetime.now()
end = start + timedelta(days=7)
events = db.get_events_by_date_range(start, end)
```

---

## Useful Commands

```bash
# Check all is working
micromamba run -n la python -c "from src.data.database import Database; from src.scrapers.timeout import TimeoutScraper; print('Database:', Database('data/events.db')); print('Scraper:', TimeoutScraper())"

# Reset database
rm data/events.db data/analytics.db
micromamba run -n la python -c "from src.data.database import Database; from src.data.analytics import Analytics; Database('data/events.db'); Analytics('data/analytics.db')"

# View environment
micromamba run -n la python -c "import sys; print(sys.path)"

# Check Python version
micromamba run -n la python --version
```

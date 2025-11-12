# Web Scraping Guide - No APIs Required!

This project aggregates LA Westside events using **pure web scraping** - no API keys required to get started!

## Current Scrapers (Web-Based Only)

All of these work out of the box with no setup:

| Source | URL | Status | Notes |
|--------|-----|--------|-------|
| Santa Monica Events | smgov.net/events | ✅ Ready | City events, public activities |
| Timeout LA | timeout.com/los-angeles | ✅ Ready | Curated LA events |
| KCRW | kcrw.com/events | ✅ Ready | Music and cultural events |
| Discover LA | discoverlosangeles.com | 🔄 Template ready | Major LA attractions |
| UCLA Events | events.ucla.edu | 🔄 Template ready | Academic, cultural, sports |
| Hammer Museum | hammer.ucla.edu/events | 🔄 Template ready | Art exhibitions, talks |
| LACMA | lacma.org/events | 🔄 Template ready | Museum events |
| Venice Beach | venicebeach.com/events | 🔄 Template ready | Beach community events |
| West Hollywood | weho.org | 🔄 Template ready | City events |
| Culver City | culvercity.org | 🔄 Template ready | City events |

## How Web Scraping Works

### Basic Flow

```python
1. Fetch HTML from website
   └─> requests.get(url)

2. Parse HTML with BeautifulSoup
   └─> BeautifulSoup(html, 'lxml')

3. Find event elements
   └─> soup.find_all('div', class_='event')

4. Extract data
   └─> title, date, location, description

5. Create Event object
   └─> geocode address → lat/lng
   └─> classify category
   └─> save to database
```

### Example Scraper Structure

```python
from .base import BaseScraper
from src.data.models import Event

class MyScraper(BaseScraper):
    def __init__(self):
        super().__init__('Source Name')
        self.base_url = 'https://example.com'

    def scrape(self) -> List[Event]:
        # Fetch the page
        html = self.fetch_page(f'{self.base_url}/events')
        soup = self.parse_html(html)

        events = []
        # Find event containers
        for item in soup.find_all('div', class_='event'):
            event = self._parse_event(item)
            events.append(event)

        return events

    def _parse_event(self, item):
        # Extract data
        title = item.find('h2').get_text()
        date = item.find('time')['datetime']
        venue = item.find('span', class_='venue').get_text()

        # Create event (auto-geocodes and categorizes)
        return self.create_event(
            title=title,
            event_date=datetime.fromisoformat(date),
            venue_name=venue
        )
```

## Best Practices

### 1. Inspect the Website First

Before writing a scraper, inspect the target website:

```bash
# Check robots.txt
curl https://example.com/robots.txt

# View page source
curl https://example.com/events | less
```

Use browser DevTools:
- Right-click → Inspect
- Find the event elements
- Note the HTML structure and CSS classes

### 2. Handle Errors Gracefully

```python
def scrape(self):
    try:
        html = self.fetch_page(url)
        if not html:
            self.log("Failed to fetch page")
            return []

        events = []
        for item in items:
            try:
                event = self._parse_event(item)
                events.append(event)
            except Exception as e:
                self.log(f"Error parsing event: {e}")
                continue  # Skip this event, continue with others

    except Exception as e:
        self.log(f"Error during scrape: {e}")
        return []
```

### 3. Be Respectful

```python
# Built into BaseScraper:
- Automatic delays between requests (1 second default)
- Proper User-Agent header
- Timeout handling
- Connection pooling
```

### 4. Clean Your Data

```python
# Use helper methods:
title = self.clean_text(title_elem.get_text())  # Removes extra whitespace
url = self.normalize_url(href, self.base_url)  # Handles relative URLs
```

## Testing Your Scraper

### Quick Test

```python
# Test a single scraper
python -c "from src.scrapers.santa_monica import SantaMonicaScraper; \
           events = SantaMonicaScraper().scrape(); \
           print(f'Found {len(events)} events')"
```

### Interactive Testing

```python
# Start Python REPL
python

# Import and test
from src.scrapers.santa_monica import SantaMonicaScraper
scraper = SantaMonicaScraper()
events = scraper.scrape()

# Inspect first event
event = events[0]
print(f"Title: {event.title}")
print(f"Date: {event.event_date}")
print(f"Venue: {event.venue_name}")
print(f"Category: {event.category}")
print(f"Coords: {event.latitude}, {event.longitude}")
```

### Add to Database

```python
from src.data.database import Database

db = Database('data/events.db')
event_id = db.insert_event(events[0])
print(f"Saved with ID: {event_id}")
```

## Common Challenges & Solutions

### 1. JavaScript-Rendered Content

**Problem:** Page is blank in `requests`, works in browser

**Solution:** Use Playwright for JavaScript rendering

```python
# Already in requirements.txt!
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url)
    html = page.content()
    browser.close()
```

### 2. Dynamic Loading (Infinite Scroll)

**Problem:** Events load as you scroll

**Solution:** Look for pagination or API calls

```python
# Often there's a hidden API endpoint:
# Check browser Network tab → XHR/Fetch
# You might find: /api/events?page=1&limit=50
```

### 3. Date Parsing

**Problem:** Various date formats

**Solution:** Use `python-dateutil`

```python
from dateutil import parser as date_parser

# Handles many formats automatically
date_str = "March 15, 2024 at 7:00 PM"
event_date = date_parser.parse(date_str)
```

### 4. Missing Addresses

**Problem:** No full address, just venue name

**Solution:** Let geocoding figure it out

```python
# Just provide what you have
address = f"{venue_name}, Los Angeles, CA"

# Geocoding service will find it
event = self.create_event(
    title=title,
    venue_name=venue_name,
    address=address  # Auto-geocoded
)
```

## Monitoring & Maintenance

### Check Scraper Health

```bash
# Run scrapers and check output
python run_scrapers.py

# Look for:
# ✓ "Successfully scraped X events" - Good!
# ✗ "Error during scrape" - Needs fixing
```

### Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "Failed to fetch page" | Network issue or URL changed | Check URL, retry |
| "List index out of range" | HTML structure changed | Update selectors |
| "No events found" | Selectors wrong | Inspect page HTML again |
| Timeout | Slow website | Increase timeout in config |
| CAPTCHA/Cloudflare block | Anti-bot protection | See "Handling CAPTCHA Protection" below |

### Handling CAPTCHA Protection

Some websites use CAPTCHA or Cloudflare protection to block automated scrapers:

**Example**: Resident Advisor (ra.co) returns:
```html
<p>Please enable JS and disable any ad blocker</p>
```

**Solutions** (in order of complexity):

1. **Check robots.txt first**: Some sites explicitly disallow scrapers
   ```bash
   curl https://example.com/robots.txt
   ```

2. **Try different approaches**:
   - Use `fetch_page_js()` with Playwright (handles basic JS)
   - Add realistic delays between requests
   - Use residential proxies (not datacenter IPs)

3. **Advanced solutions** (requires additional setup):
   - Use `undetected-chromedriver` Python library
   - Use CAPTCHA solving services (2captcha, anti-captcha)
   - Use proxy rotation services

4. **Alternative approaches**:
   - Check if the site has an official API
   - Monitor their social media for event announcements
   - Look for RSS feeds or calendar exports

**Important**: If a scraper consistently fails due to CAPTCHA:
- Document the limitation in the scraper file
- Set `enabled: False` in config.py
- Add a note explaining why it's disabled

### When to Update

Scrapers need updates when:
- Website redesigns (HTML structure changes)
- URL changes
- New security measures (CAPTCHA, etc.)
- Consistent failures

**Tip:** Version your selectors in comments:

```python
# Updated 2024-11-11: Changed from 'event-item' to 'eventCard'
event_items = soup.find_all('div', class_='eventCard')
```

## Adding a New Scraper

### Step-by-Step

1. **Create the file**
   ```bash
   touch src/scrapers/new_source.py
   ```

2. **Copy template from existing scraper**
   ```python
   # src/scrapers/new_source.py
   from .base import BaseScraper
   from src.data.models import Event

   class NewSourceScraper(BaseScraper):
       def __init__(self):
           super().__init__('New Source')
           self.base_url = 'https://newsource.com'

       def scrape(self):
           # Implement scraping logic
           pass
   ```

3. **Implement scraping logic**
   - Inspect website
   - Find event containers
   - Extract: title, date, venue, description, URL
   - Return list of Events

4. **Test it**
   ```python
   python -c "from src.scrapers.new_source import NewSourceScraper; \
              NewSourceScraper().scrape()"
   ```

5. **Add to config**
   ```python
   # config.py
   EVENT_SOURCES = {
       'new_source': {
           'name': 'New Source',
           'url': 'https://newsource.com/events',
           'enabled': True
       }
   }
   ```

6. **Add to runner**
   ```python
   # run_scrapers.py
   from src.scrapers.new_source import NewSourceScraper

   if config.EVENT_SOURCES['new_source']['enabled']:
       scrapers.append(NewSourceScraper())
   ```

## Resources

### Documentation
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Requests: https://docs.python-requests.org/
- Playwright: https://playwright.dev/python/

### Tools
- Browser DevTools (F12)
- CSS Selector Tester: https://try.jsoup.org/
- Regex Tester: https://regex101.com/
- HTML Beautifier: https://codebeautify.org/htmlviewer

### Legal
- robots.txt checker: https://en.ryte.com/free-tools/robots-txt/
- ToS; DR: https://tosdr.org/ (Terms of Service summaries)

## Next Steps

1. **Test existing scrapers** - Run `python run_scrapers.py`
2. **Pick a new source** - Choose from the list above
3. **Inspect the website** - Look at HTML structure
4. **Write the scraper** - Follow the template
5. **Test and iterate** - Refine until it works
6. **Share!** - Add more sources to help the community

---

**Remember:** Web scraping is perfectly legal for public data, but always be respectful:
- ✅ Check robots.txt
- ✅ Add delays
- ✅ Don't overload servers
- ✅ Give attribution
- ✅ Link to original sources

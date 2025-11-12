# Event Sources - Implementation Guide

This document outlines the various event sources for the LA Events Aggregator and provides guidance on whether to use APIs or web scraping for each.

## Summary Table

| Platform | Method | Difficulty | Status | Priority |
|----------|--------|------------|--------|----------|
| Santa Monica Events | Scraping | Easy | ✅ Implemented | High |
| Timeout LA | Scraping | Easy | ✅ Implemented | High |
| KCRW | Scraping | Easy | ✅ Implemented | High |
| **Eventbrite** | **API** | **Easy** | **✅ Implemented** | **High** |
| **Meetup** | **API/Scraping** | **Medium** | **✅ Implemented** | **High** |
| Facebook Events | API | Very Hard | ❌ Skip for now | Low |
| Discover LA (DoLA) | Scraping | Medium | 🔄 Planned | Medium |
| UCLA Events | Scraping | Easy | 🔄 Planned | Medium |
| Hammer Museum | Scraping | Easy | 🔄 Planned | Medium |
| LACMA | Scraping | Easy | 🔄 Planned | Medium |
| Bandsintown | API | Easy | 🔄 Recommended | High |
| Dice.fm | Scraping | Medium | 🔄 Optional | Medium |
| LA Weekly | Scraping | Medium | 🔄 Optional | Medium |

## Detailed Platform Analysis

### 1. Eventbrite ✅ IMPLEMENTED
**Recommendation: Use API**

**Pros:**
- Free API with generous rate limits
- Well-documented REST API
- Geographic search built-in
- Category filtering
- High-quality structured data

**Setup:**
1. Create account at https://www.eventbrite.com
2. Go to https://www.eventbrite.com/platform/api
3. Create an app and get OAuth token
4. Add to `.env`: `EVENTBRITE_API_TOKEN=your_token`

**Implementation:** See [src/scrapers/eventbrite.py](src/scrapers/eventbrite.py)

**API Limits:**
- 1000 requests per hour (authenticated)
- 50 requests per hour (anonymous)

---

### 2. Meetup ✅ IMPLEMENTED
**Recommendation: Try API, fallback to scraping**

**Pros:**
- GraphQL API available
- Community-focused events
- Good for tech, professional, and hobby events

**Cons:**
- API access has become more restricted
- May require authentication
- Heavy JavaScript if scraping

**Setup:**
1. Sign up at https://www.meetup.com
2. Check current API status at https://www.meetup.com/api/
3. If available, get API key and add to `.env`

**Implementation:** See [src/scrapers/meetup.py](src/scrapers/meetup.py)

**Alternative:** Web scraping with Playwright for JavaScript rendering

---

### 3. Facebook Events ❌ SKIP FOR NOW
**Recommendation: Skip or use very limited approach**

**Why Skip:**
- Extremely restricted API access
- Requires app review process
- Login required for most content
- Violates ToS if scraping
- Frequent layout changes

**Alternatives:**
- Look for Facebook RSS feeds from public pages
- Use third-party services that aggregate Facebook events
- Focus on other richer sources

---

### 4. Bandsintown 🎵 HIGHLY RECOMMENDED
**Recommendation: Use API**

**Why:**
- Excellent for music events
- Free API for non-commercial use
- Artist and venue tracking
- Geographic search

**Setup:**
1. Register at https://www.bandsintown.com/api/overview
2. Get API key (app_id)
3. Use their Events API

**Example Request:**
```bash
GET https://rest.bandsintown.com/artists/events?app_id=YOUR_APP_ID&location=Los+Angeles,CA&radius=15
```

**Implementation Priority:** HIGH - great LA music scene coverage

---

### 5. Discover LA (DoLA) 🔄 PLANNED
**Recommendation: Web Scraping**

**URL:** https://www.discoverlosangeles.com/events

**Approach:**
- Standard HTML scraping
- Look for event listings
- Extract: title, date, venue, description, image
- Categorize automatically

**Difficulty:** Medium (may use JavaScript for loading)

---

### 6. UCLA Events 🔄 PLANNED
**Recommendation: Web Scraping**

**URL:** https://events.ucla.edu

**Approach:**
- University event calendar
- Academic, cultural, sports events
- Structured calendar format
- Should be straightforward HTML

**Difficulty:** Easy

---

### 7. Museum Events (Hammer, LACMA, Getty, Broad) 🔄 PLANNED
**Recommendation: Web Scraping (each museum)**

**Sources:**
- Hammer: https://hammer.ucla.edu/events
- LACMA: https://www.lacma.org/events
- Getty Center: https://www.getty.edu/visit/cal/
- The Broad: https://www.thebroad.org/visit/calendar

**Approach:**
- Each museum has public event calendar
- Typically well-structured HTML
- Art exhibitions, talks, screenings

**Difficulty:** Easy to Medium per museum

---

### 8. Dice.fm 🎵
**Recommendation: Web Scraping or reverse-engineer API**

**URL:** https://dice.fm/search?q=los%20angeles

**Approach:**
- Concert ticketing platform
- Check network tab for API calls
- May have internal API endpoints
- Focus on electronic/indie music

**Difficulty:** Medium

---

### 9. Resident Advisor 🎵
**Recommendation: Web Scraping**

**URL:** https://ra.co/events/us/losangeles

**Approach:**
- Electronic music events
- Club events, festivals
- International event platform

**Difficulty:** Medium (may require JavaScript rendering)

---

### 10. LA Weekly Events
**Recommendation: Web Scraping**

**URL:** https://www.laweekly.com/events/

**Approach:**
- General entertainment listings
- Concerts, nightlife, art

**Difficulty:** Medium

---

### 11. West Hollywood (WeHo) City Events
**Recommendation: Web Scraping**

**URL:** https://www.weho.org/city-government/city-departments/public-facilities/events

**Approach:**
- Official city events
- Community gatherings
- Usually simple HTML

**Difficulty:** Easy

---

### 12. Culver City Events
**Recommendation: Web Scraping**

**URL:** https://www.culvercity.org/Services/Events

**Approach:**
- City calendar
- Community events

**Difficulty:** Easy

---

## Legal & Ethical Considerations

### Before Scraping ANY Website:

1. **Check robots.txt**
   ```bash
   curl https://example.com/robots.txt
   ```

2. **Read Terms of Service**
   - Look for clauses about automated access
   - Some sites explicitly allow/disallow scraping

3. **Be Respectful**
   - Add delays (1-2 seconds minimum)
   - Use proper User-Agent
   - Don't overload servers
   - Cache results

4. **Attribution**
   - Always link back to original event
   - Credit the source
   - Don't republish copyrighted images without permission

### Example robots.txt Check:
```python
import requests
response = requests.get('https://www.eventbrite.com/robots.txt')
print(response.text)
```

---

## Implementation Priority

### Phase 1 (MVP - Week 1-2):
- [x] Santa Monica
- [x] Timeout LA
- [x] KCRW
- [x] Eventbrite API
- [x] Meetup API/Scraping

### Phase 2 (Expansion - Week 3-4):
- [ ] Bandsintown API (music events)
- [ ] Discover LA
- [ ] UCLA Events
- [ ] Hammer Museum

### Phase 3 (Complete Coverage - Week 5+):
- [ ] LACMA
- [ ] Getty Center
- [ ] The Broad
- [ ] Dice.fm
- [ ] Resident Advisor
- [ ] LA Weekly
- [ ] WeHo/Culver City events

---

## API Key Management

All API keys should be stored in `.env`:

```bash
# Required
GOOGLE_MAPS_API_KEY=...
GOOGLE_GEOCODING_API_KEY=...

# Optional (for richer data)
EVENTBRITE_API_TOKEN=...
MEETUP_API_KEY=...
BANDSINTOWN_APP_ID=...
```

Never commit `.env` to git (already in .gitignore)!

---

## Rate Limiting Strategy

Implement rate limiting per source:

```python
import time
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests, time_window):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    def wait_if_needed(self):
        now = datetime.now()
        # Remove old requests
        self.requests = [r for r in self.requests
                        if now - r < timedelta(seconds=self.time_window)]

        if len(self.requests) >= self.max_requests:
            sleep_time = (self.requests[0] +
                         timedelta(seconds=self.time_window) - now).total_seconds()
            time.sleep(max(0, sleep_time))

        self.requests.append(now)
```

---

## Testing Scrapers

Test each scraper individually:

```python
from src.scrapers.eventbrite import EventbriteScraper

scraper = EventbriteScraper()
events = scraper.scrape()

print(f"Found {len(events)} events")
for event in events[:5]:
    print(f"- {event.title} @ {event.venue_name}")
```

---

## Monitoring & Maintenance

Scrapers will break when websites change. Set up monitoring:

1. **Log all errors**
2. **Track success rates** per source
3. **Alert on failures** (e.g., 3 consecutive failures)
4. **Version selectors** in code comments
5. **Regular manual checks**

---

## Next Steps

1. **Get API Keys**
   - Eventbrite (5 minutes)
   - Bandsintown (5 minutes)
   - Meetup (check availability)

2. **Test Implementations**
   ```bash
   python -c "from src.scrapers.eventbrite import EventbriteScraper; EventbriteScraper().scrape()"
   ```

3. **Add to runner**
   - Update [run_scrapers.py](run_scrapers.py)
   - Enable in [config.py](config.py)

4. **Monitor Results**
   - Check database for events
   - Verify geocoding works
   - Test category classification

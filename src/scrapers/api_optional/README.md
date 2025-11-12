# Optional API-Based Scrapers

This directory contains scrapers that require API keys. These are **optional** and not required for the basic functionality of the LA Events Aggregator.

## Available API Scrapers

- `eventbrite.py` - Eventbrite API integration
- `meetup.py` - Meetup API/GraphQL integration

## Why These Are Optional

The main project uses web scraping for all event sources, which means:
- ✅ **No API keys needed** to get started
- ✅ **No rate limits** to worry about
- ✅ **Immediate functionality** out of the box

API-based scrapers can provide:
- Better data quality
- More reliable (don't break with website changes)
- Faster scraping
- Official support

But they require:
- Obtaining API keys
- Managing rate limits
- Possible costs for high usage

## How to Enable

If you want to use these API scrapers:

1. **Get API keys:**
   - Eventbrite: https://www.eventbrite.com/platform/api
   - Meetup: https://www.meetup.com/api/

2. **Add to `.env`:**
   ```bash
   EVENTBRITE_API_TOKEN=your_token
   MEETUP_API_KEY=your_key
   ```

3. **Update `config.py`:**
   Uncomment the eventbrite/meetup entries

4. **Update `run_scrapers.py`:**
   ```python
   from src.scrapers.api_optional.eventbrite import EventbriteScraper
   from src.scrapers.api_optional.meetup import MeetupScraper

   # Add to scrapers list
   if config.EVENTBRITE_API_TOKEN:
       scrapers.append(EventbriteScraper())
   ```

## Recommendation

**Start without APIs**, get the project working, then optionally add API scrapers later if you want more comprehensive data or better reliability.

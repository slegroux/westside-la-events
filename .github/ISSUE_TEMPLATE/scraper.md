---
name: New Scraper
about: Add a new event source scraper
title: '[SCRAPER] Add [Source Name] scraper'
labels: 'area: scrapers, type: feature'
assignees: ''
---

## Event Source Information

**Source Name:**
**Website URL:**
**Events URL:**

## Analysis
- [ ] Website uses static HTML (BeautifulSoup)
- [ ] Website uses JavaScript rendering (Playwright required)
- [ ] Has API available (preferred)
- [ ] Has RSS/Atom feed
- [ ] Requires authentication
- [ ] Has rate limiting

## Scraper Implementation Tasks
- [ ] Analyze website structure
- [ ] Implement scraper class inheriting from BaseScraper
- [ ] Extract: title, date, location, description, URL, image
- [ ] Handle pagination (if applicable)
- [ ] Implement error handling
- [ ] Add geocoding for addresses
- [ ] Write unit tests with mocked HTML
- [ ] Write integration test with live site
- [ ] Update documentation

## Data Quality Checks
- [ ] All required fields populated
- [ ] Dates parsed correctly
- [ ] Addresses geocoded successfully (>90%)
- [ ] No duplicate events from same source
- [ ] Images load correctly

## Configuration
**Scraping frequency:** Daily / Every 6 hours / Every hour
**Priority:** High / Medium / Low
**Estimated events per scrape:**

## Related Issues
- Part of #27 (Add Additional Scrapers)
- Relates to #

## Additional Notes
Add any specific challenges, API documentation links, or implementation notes

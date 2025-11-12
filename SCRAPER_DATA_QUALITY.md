# Scraper Data Quality Analysis

## Current State

### Data Completeness (as of analysis)

| Source | Total Events | Has Description | Has Venue | Has Coordinates | Has Category |
|--------|-------------|----------------|-----------|-----------------|--------------|
| Timeout LA | 55 | 9% | 90% | 100% | 100% |
| KCRW | 22 | 0% | 100% | 81% | 100% |
| Discover LA | 86 | 0% | 100% | 62% | 100% |

### Data Quality Issues

#### 1. Missing Descriptions
- **Timeout LA**: Listing pages don't include event descriptions
- **KCRW**: Listing pages don't include event descriptions
- **Discover LA**: Listing pages don't include event descriptions

**Cause**: Event listing pages typically only show titles, dates, and brief metadata. Full descriptions require fetching individual event detail pages.

**Impact**: Users can't see what events are about without clicking through

#### 2. Inaccurate Venue Data

**Timeout LA**:
- Current: "Downtown", "Hollywood", "Westwood" (neighborhoods, not venues)
- Actual venue names (like "LEVEL") are only on detail pages
- Address data not available even on detail pages

**KCRW**:
- Current: "The Echo, Los Angeles, CA" (venue + generic city)
- Missing street addresses
- Geocoding works (81% have coordinates) but addresses are incomplete

**Discover LA**:
- Has venue names
- Coordinates missing for 38% of events

## Solutions

### Option 1: Detail Page Scraping (Most Accurate, Slowest)
**Pros:**
- Get full descriptions
- Get actual venue names
- Get complete address data

**Cons:**
- Much slower (1 request per event vs 1 request for all events)
- Higher risk of rate limiting/blocking
- More complex error handling

**Implementation:**
```python
def scrape(self):
    # Fetch listing page
    events_summary = self.fetch_listings()

    # Fetch detail for each event
    for summary in events_summary:
        detail = self.fetch_detail_page(summary.url)
        event = self.merge_data(summary, detail)
        events.append(event)
```

### Option 2: Listing + Selective Detail (Balanced)
**Pros:**
- Fast for initial scrape
- Can fetch details later/on-demand
- Progressive enhancement

**Cons:**
- Two-phase scraping process
- Some data always incomplete

**Implementation:**
```python
# Phase 1: Quick listing scrape (current)
events = self.scrape_listings()
db.insert_events(events)

# Phase 2: Enrich with details (background job)
for event in events_needing_enrichment:
    detail = self.fetch_detail_page(event.url)
    event.description = detail.description
    event.venue_name = detail.venue_name
    db.update_event(event)
```

### Option 3: Improve Listing Extraction (Quick Win)
**Pros:**
- No additional requests
- Fast
- Low complexity

**Cons:**
- Limited improvement (data isn't in HTML)
- Still missing descriptions

**Implementation:**
- Fix venue parsing logic where possible
- Extract all available metadata from listing pages
- Accept limitations for data not present

## Recommendations

### Short Term (Quick Wins)
1. **Fix KCRW venue extraction**: Already has venue name, just format better
2. **Fix Timeout venue extraction**: Parse neighborhood tags correctly (already doing this)
3. **Improve geocoding**: Use venue name + neighborhood for better coordinates
4. **Add data quality markers**: Flag events needing enrichment

### Medium Term (Better Data)
1. **Implement detail page fetching for key fields**:
   - Fetch detail pages for description
   - Extract actual venue names
   - Get full addresses
2. **Rate limit appropriately**: Add delays between detail page requests
3. **Cache detail pages**: Don't re-fetch on every scrape run

### Long Term (Robust System)
1. **Background enrichment job**: Separate process to fill in missing data
2. **Event deduplication**: Match same events from different sources
3. **User-generated improvements**: Let users fix/enhance event data
4. **Alternative data sources**: Look for APIs or feeds with better data

## Current Scraper Behavior

### What We Extract Successfully
- ✅ Event titles
- ✅ Event dates
- ✅ Image URLs
- ✅ Event URLs
- ✅ Categories (auto-classified)
- ✅ Geographic coordinates (via geocoding)

### What Needs Improvement
- ❌ Event descriptions (not on listing pages)
- ⚠️  Venue names (partial/incorrect)
- ⚠️  Addresses (generic city-level)
- ⚠️  Geocoding accuracy (depends on address quality)

## Proposed Next Steps

1. **Immediate** (no code changes):
   - Document current limitations
   - Set user expectations
   - Show "source link" prominently so users can get full details

2. **Quick improvement** (< 1 hour):
   - Fix venue extraction bugs
   - Improve address formatting
   - Better error logging

3. **Significant improvement** (2-4 hours):
   - Add detail page scraping for descriptions
   - Implement proper rate limiting
   - Add caching to avoid re-scraping

4. **Future enhancement** (longer term):
   - Background enrichment system
   - Event deduplication across sources
   - User feedback/corrections system

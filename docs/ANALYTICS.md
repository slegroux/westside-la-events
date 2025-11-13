# Analytics System

## Overview

The Westside LA Events Aggregator includes a comprehensive, privacy-friendly analytics system that tracks user behavior and provides insights into how people use the platform.

## Features

### Tracked Metrics

**User Engagement:**
- Unique visitors (by session)
- Page views
- Session duration
- Bounce rate
- Returning user rate

**Event Interactions:**
- Event detail page views
- External link clicks (to original event pages)
- Favorites added/removed
- Calendar exports

**Search Behavior:**
- Search queries
- Filter usage (date, category, source, free events)
- Search results count
- Most popular searches

**Source Performance:**
- Views per source
- Clicks per source
- Click-through rate (CTR)
- Favorites per source

**Category Performance:**
- Interaction count per category
- Most popular categories
- Category trends over time

### Privacy Features

The analytics system is designed with privacy in mind:

- **No Personal Identification**: We don't store names, emails, or any personally identifiable information
- **IP Hashing**: IP addresses are one-way hashed (SHA-256) for security analysis only
- **No Third-Party Tracking**: All analytics data stays in your database
- **Session-Based**: Tracking uses anonymous session IDs (UUID)
- **User Agent Only**: We only store the browser/device type, not detailed fingerprints
- **No Cookies for Tracking**: Analytics use the existing session cookie (required for favorites anyway)

## Configuration

### Enable/Disable Analytics

In [config.py](../config.py):

```python
# Enable or disable analytics tracking
ENABLE_ANALYTICS = True

# Data retention period (days)
ANALYTICS_RETENTION_DAYS = 365
```

Or via environment variables:

```bash
ENABLE_ANALYTICS=True
ANALYTICS_RETENTION_DAYS=365
```

### Database Location

Analytics data is stored in a separate SQLite database:

```python
ANALYTICS_DB_PATH = 'data/analytics.db'
```

## Accessing the Dashboard

Visit the analytics dashboard at:

```
http://localhost:8000/admin/analytics
```

### Dashboard Features

- **Overview Metrics**: Key performance indicators (KPIs)
- **Date Range Selector**: View data for 7, 30, or 90 days
- **Interactive Charts**:
  - Daily visitor trends
  - Event interaction charts
- **Data Tables**:
  - Top performing events
  - Popular search queries
  - Category popularity
  - Source performance

### API Access

Get analytics data programmatically:

```bash
# Get last 7 days of data
curl http://localhost:8000/admin/analytics/api

# Get last 30 days
curl http://localhost:8000/admin/analytics/api?days=30
```

**Response format:**
```json
{
  "metrics": [
    {
      "date": "2025-01-01",
      "unique_visitors": 42,
      "page_views": 156,
      "events_viewed": 89,
      "events_clicked": 23,
      "searches": 34,
      "favorites_added": 12
    }
  ],
  "session_stats": {
    "total_sessions": 42,
    "avg_page_views": 3.71,
    "avg_events_viewed": 2.12,
    "bounce_rate": 23.81
  },
  "popular_events": [
    [123, 45, 12]  // [event_id, views, clicks]
  ],
  "popular_searches": [
    ["comedy shows", 15],
    ["free events", 12]
  ],
  "category_popularity": [
    ["Music", 89],
    ["Art", 67]
  ],
  "source_performance": [
    {
      "source": "KCRW",
      "total_interactions": 156,
      "views": 123,
      "clicks": 28,
      "favorites": 5,
      "click_through_rate": 22.76
    }
  ]
}
```

## Database Schema

### Tables

**page_views**
- Tracks every page view on the site
- Fields: session_id, path, referrer, user_agent, ip_hash, created_at

**event_interactions**
- Tracks all event-related interactions
- Fields: session_id, event_id, interaction_type, source, category, created_at
- Interaction types: view, click, favorite, unfavorite, calendar

**search_queries**
- Tracks search and filter usage
- Fields: session_id, query, date_filter, categories, sources, free_only, results_count, created_at

**sessions**
- Aggregated session data
- Fields: session_id, first_seen, last_seen, page_views, events_viewed, events_clicked, searches

**daily_metrics**
- Pre-computed daily summaries (optional, for performance)
- Fields: date, unique_visitors, page_views, events_viewed, events_clicked, searches, favorites_added

## Usage Examples

### Python API

```python
from src.data.analytics import Analytics

# Initialize
analytics = Analytics('data/analytics.db')

# Track a page view
analytics.track_page_view(
    session_id='abc-123',
    path='/event/456',
    referrer='https://google.com',
    user_agent='Mozilla/5.0...',
    ip_address='192.168.1.1'
)

# Track an event interaction
analytics.track_event_interaction(
    session_id='abc-123',
    event_id=456,
    interaction_type='view',
    source='KCRW',
    category='Music'
)

# Track a search
analytics.track_search(
    session_id='abc-123',
    query='jazz concerts',
    date_filter='this_week',
    categories=['Music'],
    free_only=True,
    results_count=12
)

# Get metrics
from datetime import datetime, timedelta

today = datetime.now()
week_ago = today - timedelta(days=7)

# Daily metrics
metrics = analytics.get_daily_metrics(today)

# Date range metrics
range_metrics = analytics.get_date_range_metrics(week_ago, today)

# Popular events
top_events = analytics.get_popular_events(limit=10, days=7)

# Popular searches
top_searches = analytics.get_popular_searches(limit=10, days=7)

# Category popularity
categories = analytics.get_category_popularity(days=7)

# Source performance
sources = analytics.get_source_performance(days=7)

# Session stats
stats = analytics.get_session_stats(days=7)
```

## Client-Side Tracking

The system includes privacy-friendly client-side tracking via [static/js/analytics.js](../static/js/analytics.js):

- **External Link Clicks**: Automatically tracked when users click event source links
- **Time on Page**: Measured in 30-second intervals (while tab is active)
- **No Cookies**: Uses existing session storage only

## Data Maintenance

### Manual Cleanup

Remove old analytics data:

```python
from src.data.analytics import Analytics
from datetime import datetime, timedelta

analytics = Analytics('data/analytics.db')

# Calculate cutoff date
cutoff_date = datetime.now() - timedelta(days=365)

with analytics.get_connection() as conn:
    # Delete old page views
    conn.execute("""
        DELETE FROM page_views
        WHERE created_at < ?
    """, (cutoff_date,))

    # Delete old interactions
    conn.execute("""
        DELETE FROM event_interactions
        WHERE created_at < ?
    """, (cutoff_date,))

    # Delete old searches
    conn.execute("""
        DELETE FROM search_queries
        WHERE created_at < ?
    """, (cutoff_date,))

    conn.commit()
```

### Automated Cleanup

Add to a cron job or scheduled task:

```bash
# Run monthly cleanup
0 0 1 * * cd /path/to/LA && python -c "from src.data.analytics import Analytics; from datetime import datetime, timedelta; a = Analytics('data/analytics.db'); # ... cleanup code"
```

## Performance Considerations

- **Indexed Queries**: All analytics tables have appropriate indexes for fast queries
- **Separate Database**: Analytics doesn't slow down main event database
- **Async Tracking**: All tracking is fire-and-forget; errors don't affect user experience
- **Efficient Queries**: Uses aggregations and date-based filtering for dashboard

## GDPR & Privacy Compliance

The analytics system is designed to be GDPR-friendly:

✅ **No PII Collected**: We don't collect names, emails, or identifying data
✅ **Anonymous Sessions**: Session IDs are randomly generated UUIDs
✅ **IP Hashing**: IPs are one-way hashed, can't be reversed
✅ **User Control**: Users can clear their session data by clearing cookies
✅ **Data Retention**: Configurable retention period
✅ **No Third-Party**: Data stays in your control, never shared

## Troubleshooting

### Analytics Not Tracking

1. Check if analytics is enabled:
   ```python
   import config
   print(config.ENABLE_ANALYTICS)  # Should be True
   ```

2. Check if analytics database exists:
   ```bash
   ls -lh data/analytics.db
   ```

3. Check logs for errors:
   ```bash
   tail -f logs/app.log | grep analytics
   ```

### Dashboard Not Loading

1. Verify analytics is initialized:
   ```python
   from src.web.app import state
   print(state.analytics)  # Should not be None
   ```

2. Check database permissions:
   ```bash
   chmod 644 data/analytics.db
   ```

3. Test analytics directly:
   ```python
   from src.data.analytics import Analytics
   a = Analytics('data/analytics.db')
   print(a.get_session_stats(7))
   ```

### Performance Issues

If dashboard is slow:

1. Add date range limits to queries
2. Consider pre-computing daily metrics
3. Archive old data to separate database
4. Add additional indexes if needed

## Future Enhancements

Potential improvements:

- [ ] Real-time dashboard updates (WebSocket/SSE)
- [ ] Geographic visualization (heatmap of visitor locations)
- [ ] Funnel analysis (user journey tracking)
- [ ] A/B testing framework
- [ ] Export reports (PDF, CSV)
- [ ] Email digest reports
- [ ] Anomaly detection (traffic spikes, errors)
- [ ] Mobile app analytics (if app is built)

## Security Notes

**Access Control**: The analytics dashboard is at `/admin/analytics`. In production, you should:

1. Add authentication/authorization
2. Use environment variables for admin credentials
3. Consider IP whitelisting for admin routes
4. Use HTTPS in production

Example authentication (add to [src/web/app.py](../src/web/app.py)):

```python
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware

# Add authentication middleware
# ... implement auth backend
```

## Support

For issues or questions about analytics:

1. Check this documentation
2. Review [src/data/analytics.py](../src/data/analytics.py) source code
3. Check logs for errors
4. Open an issue on GitHub

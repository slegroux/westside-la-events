# API Reference

The Westside LA Events Aggregator provides both a web interface and JSON API endpoints for programmatic access to event data.

## Base URL

```
http://127.0.0.1:8000  (local development)
```

## Authentication

Currently, no authentication is required. The API is open for public access.

## Endpoints

### 1. Get Events (JSON)

Retrieve a list of events with optional filtering.

**Endpoint:** `GET /api/events`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | `""` | Search query (searches title, description, venue) |
| `date_filter` | string | `"upcoming"` | Date filter option (see below) |
| `category` | string[] | `null` | Filter by category (can be multiple) |
| `free_only` | string | `""` | Filter for free events only (`"true"` to enable) |
| `specific_date` | string | `""` | Specific date in YYYY-MM-DD format |

**Date Filter Options:**

- `upcoming` - All future events
- `today` - Events happening today
- `this_week` - Events this week
- `this_weekend` - Events this weekend
- `next_week` - Events next week
- `this_month` - Events this month
- `next_month` - Events next month
- `specific_date` - Requires `specific_date` parameter

**Category Values:**

- `music` - Music, concerts, DJ sets
- `art` - Art exhibitions, galleries, museums
- `food_drink` - Food events, tastings, dining experiences
- `sports` - Sports events, fitness activities
- `family` - Family-friendly activities
- `nightlife` - Bars, clubs, late-night events
- `community` - Community events, meetups
- `theater` - Theater, performances, shows
- `education` - Workshops, classes, lectures
- `other` - Uncategorized events

**Example Requests:**

```bash
# Get all upcoming events
curl "http://127.0.0.1:8000/api/events"

# Search for music events
curl "http://127.0.0.1:8000/api/events?q=concert&category=music"

# Get free events this week
curl "http://127.0.0.1:8000/api/events?date_filter=this_week&free_only=true"

# Get events for a specific date
curl "http://127.0.0.1:8000/api/events?date_filter=specific_date&specific_date=2025-01-15"

# Multiple categories
curl "http://127.0.0.1:8000/api/events?category=music&category=art"
```

**Response Format:**

```json
[
  {
    "id": 123,
    "title": "Jazz Night at The Baked Potato",
    "description": "Live jazz performance featuring local artists...",
    "venue_name": "The Baked Potato",
    "address": "3787 Cahuenga Blvd, Studio City, CA 91604",
    "latitude": 34.1478,
    "longitude": -118.3892,
    "event_date": "2025-01-20T19:00:00",
    "end_date": "2025-01-20T22:00:00",
    "category": "music",
    "source": "KCRW",
    "url": "https://example.com/event/123",
    "image_url": "https://example.com/images/event.jpg",
    "source_logo_url": "/static/logos/kcrw.png",
    "created_at": "2025-01-10T12:00:00",
    "updated_at": "2025-01-10T12:00:00"
  }
]
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique event identifier |
| `title` | string | Event title |
| `description` | string | Event description (may be null) |
| `venue_name` | string | Venue name |
| `address` | string | Full street address |
| `latitude` | float | Latitude coordinate (may be null) |
| `longitude` | float | Longitude coordinate (may be null) |
| `event_date` | string | Event start date/time (ISO 8601) |
| `end_date` | string | Event end date/time (ISO 8601, may be null) |
| `category` | string | Event category |
| `source` | string | Data source name |
| `url` | string | Original event URL |
| `image_url` | string | Event image URL (may be null) |
| `source_logo_url` | string | Source logo URL (may be null) |
| `created_at` | string | Record creation timestamp (ISO 8601) |
| `updated_at` | string | Record update timestamp (ISO 8601) |

**Status Codes:**

- `200 OK` - Success
- `500 Internal Server Error` - Server error

---

### 2. Get Single Event (JSON)

Retrieve detailed information for a specific event.

**Endpoint:** `GET /api/events/{event_id}`

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | integer | Unique event identifier |

**Example Request:**

```bash
curl "http://127.0.0.1:8000/api/events/123"
```

**Response Format:**

Same as individual event object in `/api/events` response (see above).

**Status Codes:**

- `200 OK` - Success
- `404 Not Found` - Event doesn't exist
- `500 Internal Server Error` - Server error

---

### 3. Event Detail Page (HTML)

Human-readable event detail page with map visualization.

**Endpoint:** `GET /event/{event_id}`

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | integer | Unique event identifier |

**Example:**

```
http://127.0.0.1:8000/event/123
```

**Features:**

- Full event details
- Interactive map with venue location
- Add to calendar functionality (iCal format)
- Link to original event page
- Responsive design

---

### 4. Download Calendar Event (iCal)

Download event as an iCalendar (.ics) file for adding to calendar apps.

**Endpoint:** `GET /event/{event_id}/calendar`

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `event_id` | integer | Unique event identifier |

**Example:**

```bash
# Download calendar file
curl -O "http://127.0.0.1:8000/event/123/calendar"
```

**Response:**

- Content-Type: `text/calendar`
- Downloads as `event-{event_id}.ics`
- Compatible with Google Calendar, Apple Calendar, Outlook, etc.

---

### 5. Events List (HTML)

Partial HTML component for event listings (used with HTMX for dynamic updates).

**Endpoint:** `GET /events/list`

**Query Parameters:**

Same as `/api/events` (see above)

**Response:**

Returns HTML event cards for dynamic page updates via HTMX.

---

### 6. Home Page

Main application interface with search, filters, and map.

**Endpoint:** `GET /`

**Features:**

- Search bar with keyword search
- Date filter dropdown
- Category filter checkboxes
- Free events filter
- Interactive map with event markers
- Responsive event grid

---

## Usage Examples

### Python

```python
import requests

# Get all events
response = requests.get('http://127.0.0.1:8000/api/events')
events = response.json()

# Search for music events this weekend
params = {
    'date_filter': 'this_weekend',
    'category': 'music'
}
response = requests.get('http://127.0.0.1:8000/api/events', params=params)
music_events = response.json()

# Get specific event
event_id = 123
response = requests.get(f'http://127.0.0.1:8000/api/events/{event_id}')
event = response.json()
```

### JavaScript

```javascript
// Fetch all events
fetch('http://127.0.0.1:8000/api/events')
  .then(response => response.json())
  .then(events => console.log(events));

// Search with parameters
const params = new URLSearchParams({
  q: 'jazz',
  date_filter: 'this_week',
  category: 'music'
});

fetch(`http://127.0.0.1:8000/api/events?${params}`)
  .then(response => response.json())
  .then(events => console.log(events));

// Get specific event
fetch('http://127.0.0.1:8000/api/events/123')
  .then(response => response.json())
  .then(event => console.log(event));
```

### cURL

```bash
# Get all upcoming events
curl "http://127.0.0.1:8000/api/events"

# Search with multiple filters
curl "http://127.0.0.1:8000/api/events?q=art&date_filter=this_month&category=art&category=music"

# Get free events only
curl "http://127.0.0.1:8000/api/events?free_only=true"

# Download calendar file
curl -O "http://127.0.0.1:8000/event/123/calendar"
```

## Rate Limiting

Currently, there is no rate limiting implemented. Please be respectful and avoid excessive requests.

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200 OK` - Successful request
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

Error responses include HTML error pages (for HTML endpoints) or empty JSON arrays (for JSON endpoints).

## CORS

CORS is not currently configured. If you need cross-origin access, please open an issue.

## Future Enhancements

Planned API improvements:

- [ ] Pagination for large result sets
- [ ] Rate limiting
- [ ] API authentication/keys
- [ ] CORS configuration
- [ ] GraphQL endpoint
- [ ] Webhook notifications for new events
- [ ] Bulk event submission API
- [ ] Advanced search with boolean operators

## Support

For API questions or issues:

- Check [SDD.md](../SDD.md) for architecture details
- Open an issue on GitHub
- See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines

# FastHTML Best Practices - Quick Reference

## Critical Security Issues Found

### 1. PATH TRAVERSAL VULNERABILITY (Critical)
**Location:** `src/web/app.py` lines 289-292
```python
# VULNERABLE - No validation
@rt('/static/{filepath:path}')
def get(filepath: str):
    return FileResponse(f'static/{filepath}')
```

**Attack Vector:**
- `GET /static/../../config.py` → Reads config file
- `GET /static/../../.env` → Reads secrets

**Fix:**
```python
from starlette.staticfiles import StaticFiles
app.mount('/static', StaticFiles(directory='static'), name='static')
```

---

## Code Quality Issues Found

### 2. DUPLICATE FUNCTION NAMES
**Location:** Multiple routes (lines 78, 167, 181, 198, 278, 289)

```python
# ❌ BAD: Multiple functions with same name
@rt('/')
def get():
    pass

@rt('/events/list')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    pass

@rt('/api/events')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    pass
```

**Fix:**
```python
# ✓ GOOD: Descriptive names
@rt('/')
def home():
    pass

@rt('/events/list')
def get_events_list_html(q: str = '', ...):
    pass

@rt('/api/events')
def api_get_events(q: str = '', ...):
    pass
```

---

### 3. ✅ HTMX-BASED SEARCH (FIXED)
**Location:** Python (`app.py`) with HTMX attributes

**Current Implementation:** All HTML is built server-side and returned via HTMX
```python
# Search form with HTMX attributes
def search_section():
    return Form(
        Input(
            hx_get='/events/list',
            hx_target='#events-container',
            hx_trigger='keyup changed delay:500ms'
        ),
        # ... filters with hx_get, hx_trigger, hx_include
    )

# Server endpoint returns HTML fragment
@rt('/events/list')
def get_events_list(q: str = '', date_filter: str = 'this_weekend', ...):
    events = _fetch_events(q, date_filter, ...)
    return HTMLResponse(str(events_list(events)))
```

**Result:** No duplicate HTML building logic - server is single source of truth

---

### 4. NO GLOBAL ERROR HANDLING
**Current State:** Exceptions silently fail or show raw stack traces

```python
# ❌ BAD: Individual error handling in each route
@rt('/event/{event_id}')
def get(event_id: int):
    event = db.get_event(event_id)
    if not event:
        return Html(
            Head(Title('Event Not Found')),
            Body(...)  # Hard to maintain
        )
```

**Fix:** Global error handlers with logging
```python
import logging
logger = logging.getLogger(__name__)

@app.exception_handler(404)
async def not_found_handler(request, exc):
    logger.info(f"404: {request.url.path}")
    return render_error_page(404, "Not found")

@app.exception_handler(500)
async def server_error_handler(request, exc):
    logger.error(f"500: {exc}", exc_info=True)
    return render_error_page(500, "Server error")

def render_error_page(status_code: int, message: str):
    return page_layout(
        f'{status_code} Error',
        Main(Div(H2(f'{status_code}'), P(message)))
    )
```

---

### 5. HARDCODED GLOBAL DATABASE INSTANCE
**Location:** `app.py` lines 35-36

```python
# ❌ BAD: Global instance created at import time
db = Database(config.DATABASE_PATH)
search = EventSearch(db)
```

**Issues:**
- Not thread-safe
- No cleanup on shutdown
- Can't test without side effects
- No startup validation

**Fix:** Use FastHTML lifespan context
```python
from contextlib import asynccontextmanager

database_instance: Optional[Database] = None

@asynccontextmanager
async def lifespan(app):
    global database_instance
    # Startup
    logger.info("Initializing database...")
    database_instance = Database(config.DATABASE_PATH)
    
    # Verify database is accessible
    test = database_instance.get_all_events(limit=1)
    logger.info("Database connection verified")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Closing database...")
    # Cleanup logic here

app.router.lifespan_context = lifespan
```

---

## Missing FastHTML Features

### 6. MINIMAL HTMX USAGE
**Current:** Only 1 HTMX attribute found (Button line 99)
**Missing:** Full reactive form with HTMX

**Before (JavaScript):**
```python
Button('List View', id='list-view-btn', cls='active',
       hx_get='/events/list', hx_target='#events-container', hx_swap='innerHTML'),
```

Plus JavaScript calling fetch():
```javascript
async function searchEvents() {
    const response = await fetch('/api/events?' + params.toString());
    const events = await response.json();
    displayEvents(events);
}
```

**After (Pure HTMX):**
```python
Form(
    Div(
        Input(
            type='text',
            name='q',
            id='search-input',
            placeholder='Search events...',
            hx_trigger='keyup delay:500ms',  # Auto-search on type
            hx_get='/events/search',
            hx_target='#events-container',
            hx_include='[name=date_filter],[name=category]',
            autocomplete='off'
        ),
        Button('Search', type='submit'),
        cls='search-box'
    ),
    Div(
        Label('When', for_='date-filter'),
        Select(
            Option('Upcoming', value='upcoming', selected=True),
            Option('Today', value='today'),
            Option('This Week', value='this_week'),
            name='date_filter',
            id='date-filter',
            hx_trigger='change',  # Filter on change
            hx_get='/events/search',
            hx_target='#events-container',
            hx_include='[name=q],[name=category]',
        ),
    ),
    # ... more filters
    method='get',
    id='search-form'
)
```

No JavaScript needed!

---

### 7. MISSING COMPONENT PROPS SYSTEM
**Current:** Functions accept untyped parameters

```python
# ❌ BAD: No type hints, no validation
def event_card(event):
    event_date_str = event.event_date.strftime("%a, %b %d")  # Can crash
    return Div(...)

# Usage
event_card(None)  # Crashes at runtime
```

**Fix:** Use dataclass props with validation

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class EventCardProps:
    event: Event
    clickable: bool = True
    show_image: bool = True
    
    def validate(self):
        if not isinstance(self.event, Event):
            raise TypeError(f"event must be Event, got {type(self.event)}")

def event_card(props: EventCardProps) -> Div:
    props.validate()  # Validate at component boundary
    
    event = props.event
    event_date_str = event.event_date.strftime("%a, %b %d") if event.event_date else "TBA"
    
    return Div(
        Img(src=event.image_url, alt=event.title) if props.show_image else None,
        H2(event.title),
        Div(f'📅 {event_date_str}'),
        A('View', href=f'/event/{event.id}') if props.clickable else None,
        cls='event-card'
    )

# Usage
event_card(EventCardProps(event=my_event))  # Type-safe
event_card(EventCardProps(event=None))  # Validation error before rendering
```

---

### 8. NO REUSABLE LAYOUT COMPONENTS
**Current:** Header/footer recreated in multiple places

Appears in:
- Home page (lines 85-91)
- Event detail page (lines 228-233)
- Error page (would be added)

**Fix:** Extract to reusable components

```python
def app_header() -> Header:
    """Reusable header component."""
    return Header(
        Div(
            H1('🌴 Westside LA Events'),
            P('Discover the best events...', cls='header-subtitle'),
            cls='header-content container'
        )
    )

def app_footer() -> Footer:
    """Reusable footer component."""
    return Footer(
        Div(
            P('Westside LA Events Aggregator'),
            P('Aggregating events from Santa Monica, Timeout LA, KCRW, and more.'),
            cls='container'
        )
    )

def page_layout(title: str, content, extra_head=None) -> Html:
    """Reusable page layout."""
    return Html(
        Head(
            Title(f'{title} - Westside LA Events'),
            Meta(charset='UTF-8'),
            Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
            Link(rel='stylesheet', href='/static/css/style.css'),
            *(extra_head or [])
        ),
        Body(
            app_header(),
            content,
            app_footer(),
        )
    )

# Usage - now consistent everywhere
@rt('/')
def home():
    return page_layout('Home', Main(...))

@rt('/event/{event_id}')
def event_detail(event_id: int):
    return page_layout(f'{event.title}', Main(...))
```

---

## Priority Roadmap

### Phase 1: Security (1-2 days)
- [ ] Fix path traversal in static files
- [ ] Add error handlers
- [ ] Validate search input
- [ ] Add database health check

### Phase 2: Code Quality (2-3 days)  
- [ ] Rename route functions
- [ ] Extract reusable components
- [ ] Add type hints
- [ ] Remove duplicate HTML logic

### Phase 3: FastHTML Patterns (2-3 days)
- [ ] Full HTMX integration
- [ ] Use StaticFiles mount
- [ ] Implement component props
- [ ] Add global error handling

### Phase 4: Performance (ongoing)
- [ ] Connection pooling
- [ ] Result caching
- [ ] Loading indicators
- [ ] Error notifications

---

## Quick Wins

### Add Meta Tags
```python
def create_app_headers():
    return (
        Meta(charset='UTF-8'),
        Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
        Meta(name='description', content='Discover LA Westside events'),
        Link(rel='stylesheet', href='/static/css/style.css'),
        # ... rest of headers
    )

app, rt = fast_app(live=config.DEBUG, hdrs=create_app_headers())
```

### Add Logging
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.exception_handler(500)
async def handle_error(request, exc):
    logger.error(f"Error: {exc}", exc_info=True)
    return render_error_page(500, "Server error")
```

### Fix Static Files (Immediate)
```python
from starlette.staticfiles import StaticFiles

# Replace the @rt('/static/...') handler with:
app.mount('/static', StaticFiles(directory='static'), name='static')
```

---

## Key Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Lines in app.py | 321 | <150 |
| Route function name collisions | 6 functions named "get()" | 0 |
| Duplicate code | ~50 lines (event card HTML) | 0 |
| HTMX usage | 1 instance | 100% form handling |
| Security vulnerabilities | 1 critical | 0 |
| Error handling coverage | 10% | 100% |
| Type hints on components | 0% | 100% |

---

## File Changes Needed

```
src/web/
├── app.py (refactor, split components)
│   ├── New: components/layout.py (header, footer, page_layout)
│   ├── New: components/events.py (event_card, events_list)
│   ├── New: components/forms.py (search_form)
│   ├── New: middleware/errors.py (error handling)
│   └── Remove: duplicate HTML from routes
│
├── static/
│   ├── css/style.css (keep)
│   └── js/map.js (keep for map - HTMX handles search)
│
└── tests/
    ├── test_components.py (new)
    ├── test_routes.py (new)
    └── test_security.py (new)
```

---

## Testing Checklist

```
Security Tests:
  [ ] curl /static/../../config.py → Should return 404
  [ ] curl /static/../../.env → Should return 404
  [ ] SQL injection in search parameter

Functionality Tests:
  [ ] Search form submission works
  [ ] Category filter works
  [ ] Date filter works
  [ ] Event detail page loads
  [ ] 404 page displays

HTMX Tests:
  [ ] Filter triggers HTMX request
  [ ] Results update in-place
  [ ] Loading state shows
  [ ] Error handling works

Performance Tests:
  [ ] Static file responses < 100ms
  [ ] Search responses < 500ms
  [ ] Multiple concurrent searches
```

---

## Resources

- FastHTML docs: https://docs.fastht.ml/
- HTMX docs: https://htmx.org/reference/
- Starlette docs: https://www.starlette.io/
- SQLite FTS5: https://www.sqlite.org/fts5.html


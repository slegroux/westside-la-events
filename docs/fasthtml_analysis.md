# FastHTML Implementation Analysis
## LA Events Aggregator

**Analysis Date:** November 11, 2025  
**Project:** Westside LA Events Aggregator  
**Technology:** FastHTML Web Framework  

---

## Executive Summary

The current FastHTML implementation demonstrates a functional web application with proper separation of concerns, database integration, and API endpoints. However, there are several areas where FastHTML best practices could be enhanced:

- **Strengths:** Component-based UI architecture, proper use of decorators, database lifecycle management
- **Improvement Areas:** Error handling patterns, form handling, HTMX integration, static file serving, app initialization

---

## 1. FastHTML App Initialization and Configuration

### Current Implementation

**File:** `/home/sylvain/Projects/LA/src/web/app.py` (Lines 13-36)

```python
app, rt = fast_app(
    live=config.DEBUG,
    hdrs=(
        Link(rel='stylesheet', href='/static/css/style.css'),
        # Leaflet CSS
        Link(rel='stylesheet', href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
             integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', crossorigin=''),
        # Leaflet MarkerCluster CSS
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css'),
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css'),
        # Leaflet JS
        Script(src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
               integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=', crossorigin=''),
        # Leaflet MarkerCluster JS
        Script(src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js'),
        # Application JavaScript
        Script(src='/static/js/map.js')
        # Note: Search functionality uses HTMX (no separate search.js)
    )
)
```

**Strengths:**
- ✓ Global header configuration for CSS/JS is properly centralized
- ✓ Uses `fast_app()` factory function with debug mode tied to config
- ✓ CDN resources for third-party libraries
- ✓ Integrity hashes for HTTPS security

**Best Practice Gaps:**

1. **Head/Meta Configuration:** Missing essential meta tags and SEO elements
   - No viewport meta tag in global headers
   - No charset declaration
   - No Open Graph tags
   - No favicon definition

2. **Static Resource Organization:** All headers centralized at app init
   - No separation between critical (above-the-fold) and deferred scripts
   - JavaScript files loaded synchronously
   - No script deferring or async loading strategy

3. **Configuration Hardcoding:** Library versions and URLs hardcoded
   - No version management system
   - No fallback mechanism for CDN failures
   - No service worker or offline support

### Recommended Best Practices

```python
# Create a configuration builder for extensibility
def create_app_headers():
    """Build app headers with proper organization."""
    return (
        # Critical meta tags
        Meta(charset='UTF-8'),
        Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
        Meta(name='description', content='Discover LA Westside events'),
        
        # Preload critical resources
        Link(rel='preload', href='/static/css/style.css', as_='style'),
        
        # Stylesheets (critical rendering path)
        Link(rel='stylesheet', href='/static/css/style.css'),
        Link(rel='stylesheet', href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
             integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', crossorigin=''),
        
        # Defer non-critical scripts
        Script(src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
               integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=',
               crossorigin='', defer=True),
    )

app, rt = fast_app(
    live=config.DEBUG,
    hdrs=create_app_headers()
)
```

---

## 2. Route Definitions and Handlers

### Current Implementation

**Routes Present:**
- `GET /` - Home page with initial events
- `GET /events/list` - HTMX endpoint for filtered events list
- `GET /api/events` - JSON API endpoint for events
- `GET /event/{event_id}` - Event detail page
- `GET /api/events/{event_id}` - JSON API endpoint for single event
- `GET /static/{filepath:path}` - Static file serving

### Current Issues

1. **Route Name Collision:** Multiple `get()` functions with same name

```python
@rt('/events/list')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """HTMX endpoint to get events list HTML."""
    # ...

@rt('/api/events')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """API endpoint to get events."""
    # ...
```

**Problem:** Python function names are not unique; only FastHTML routing system distinguishes them. This reduces code clarity and debuggability.

2. **Missing Request Methods:** Only GET requests supported
   - No POST for search submission
   - No proper form handling
   - No data mutations (would be DELETE, PUT)

3. **Error Handling:** Minimal error handling in routes

```python
@rt('/event/{event_id}')
def get(event_id: int):
    """Event detail page."""
    event = db.get_event(event_id)
    if not event:
        return Html(
            Head(Title('Event Not Found')),
            Body(
                Header(...),
                Main(...)
            )
        )
```

**Issues:**
- Error responses not using standard HTTP patterns
- Full HTML reconstruction for errors (inefficient)
- No logging of errors
- Hard-coded error content in routes

4. **Content-Type Issues:** Mixing HTML and JSON responses

```python
@rt('/api/events')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """API endpoint to get events."""
    from starlette.responses import JSONResponse
    return JSONResponse([event.to_dict() for event in events])
```

**Problem:** Importing JSONResponse inside function; better pattern is error handler middleware.

### Recommended Best Practices

```python
# Use descriptive function names
@rt('/events/list', methods=['get'])
def get_events_list_html(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """Get events list as HTML (for HTMX)."""
    categories = [category] if category and category != 'All Categories' else None
    events = search.search(
        query=q if q else None,
        date_filter=date_filter,
        categories=categories,
        limit=100
    )
    return events_list(events)

@rt('/api/events', methods=['get'])
def api_get_events(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """Get events as JSON."""
    categories = [category] if category and category != 'All Categories' else None
    events = search.search(
        query=q if q else None,
        date_filter=date_filter,
        categories=categories,
        limit=100
    )
    return [event.to_dict() for event in events]

# Centralized error handling
@app.exception_handler(404)
async def not_found_error(request, exc):
    """Handle 404 errors."""
    logger.info(f"404 error: {request.url}")
    return render_error_page(404, "Event not found")

@app.exception_handler(500)
async def server_error(request, exc):
    """Handle 500 errors."""
    logger.error(f"500 error: {exc}", exc_info=True)
    return render_error_page(500, "Server error")

# Shared error page component
def error_page(status_code: int, message: str):
    """Reusable error page component."""
    return Html(
        Head(Title(f'{status_code} - Westside LA Events')),
        Body(
            Header(Div(H1('🌴 Westside LA Events'), cls='header-content container')),
            Main(Div(
                H2(f'{status_code} Error'),
                P(message),
                A('← Back to Events', href='/'),
                cls='container'
            )),
            Footer(...)
        )
    )
```

---

## 3. Component Structure and Reusability

### Current Implementation

**Components Defined:**
- `event_card(event)` - Lines 39-59
- `events_list(events)` - Lines 62-75
- `search_section()` - Lines 123-164

### Strengths

✓ **Good component decomposition:**
```python
def event_card(event):
    """Component to render a single event card."""
    return Div(
        Img(src=event.image_url, ...) if event.image_url else None,
        Div(...),
        cls='event-card'
    )

def events_list(events):
    """Component to render the events grid."""
    if not events:
        return Div(...)
    return Div(
        Div(f'Found {len(events)} event{"s" if len(events) != 1 else ""}', ...),
        Div(*[event_card(e) for e in events], cls='events-grid'),
    )
```

✓ **Proper conditional rendering:**
```python
Img(src=event.image_url, alt=event.title, cls='event-image') if event.image_url else None,
```

### Improvement Areas

1. **No Reusable Base Components:** Header, footer duplicated across templates

Currently, Header/Footer are recreated in multiple routes:
- Home route (lines 85-91)
- Event detail page (lines 228-233)
- Error page (not shown, but would duplicate)

2. **No Component Type System:** Components return mixed Div/None types

```python
# Current - no type hints on components
def event_card(event):
    return Div(...)

def events_list(events):
    if not events:
        return Div(...)
    return Div(...)  # Different structure!
```

3. **✅ Single Source of Truth (FIXED):** HTMX-based approach eliminates duplication

All HTML is built server-side using FastHTML components:

```python
# Server-side rendering only
@rt('/events/list')
def get_events_list(q: str = '', date_filter: str = 'this_weekend', ...):
    events = _fetch_events(q, date_filter, ...)
    return HTMLResponse(str(events_list(events)))  # Single source of truth

# HTMX triggers on user interaction
Input(hx_get='/events/list', hx_target='#events-container', hx_trigger='keyup changed delay:500ms')
```

**Result:** No JavaScript HTML building - server handles all rendering.

### Recommended Best Practices

```python
# Create a layout system with shared components
def page_layout(title: str, content, extra_scripts=None):
    """Reusable page layout with header and footer."""
    return Html(
        Head(
            Title(f'{title} - Westside LA Events'),
            Meta(charset='UTF-8'),
            Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
            Link(rel='stylesheet', href='/static/css/style.css'),
            *(extra_scripts or [])
        ),
        Body(
            app_header(),
            content,
            app_footer(),
        )
    )

def app_header():
    """Reusable header component."""
    return Header(
        Div(
            H1('🌴 Westside LA Events'),
            P('Discover the best events, activities, and experiences across LA\'s Westside', 
              cls='header-subtitle'),
            cls='header-content container'
        )
    )

def app_footer():
    """Reusable footer component."""
    return Footer(
        Div(
            P('Westside LA Events Aggregator'),
            P('Aggregating events from Santa Monica, Timeout LA, KCRW, and more.'),
            cls='container'
        )
    )

# Event card with optional wrapper
def event_card(event: Event) -> Div:
    """Component to render a single event card."""
    event_date_str = event.event_date.strftime("%a, %b %d, %Y at %I:%M %p") if event.event_date else "Date TBA"
    
    return Div(
        Img(src=event.image_url, alt=event.title, cls='event-image') if event.image_url else None,
        Div(
            H2(event.title, cls='event-title'),
            Div(f'📅 {event_date_str}', cls='event-date'),
            Div(f'📍 {event.venue_name}', cls='event-location') if event.venue_name else None,
            P(event.description, cls='event-description') if event.description else None,
            Div(
                Span(event.category, cls='event-category'),
                Span(event.source, cls='event-source'),
                cls='event-footer'
            ),
            A('View Details →', href=f'/event/{event.id}', cls='event-link'),
            cls='event-content'
        ),
        cls='event-card',
        id=f'event-{event.id}'  # Add ID for AJAX targeting
    )

# Strongly typed component returns
def empty_state() -> Div:
    """Empty state when no events found."""
    return Div(
        H2('🔍 No events found'),
        P('Try adjusting your search filters or check back later for new events.'),
        cls='empty-state'
    )

def events_list(events: List[Event]) -> Div:
    """Component to render the events grid with type safety."""
    if not events:
        return empty_state()
    
    count_text = f'Found {len(events)} event{"s" if len(events) != 1 else ""}'
    return Div(
        Div(count_text, style='margin-bottom: 1.5rem; color: var(--text-light); font-size: 1rem; font-weight: 600;'),
        Div(*[event_card(e) for e in events], cls='events-grid', id='events-grid'),
    )
```

---

## 4. Form Handling and HTMX Usage

### Current Implementation

**✅ HTMX Usage (CURRENT):** Full HTMX integration for search and filtering

```python
# Search input with debounced HTMX
Input(
    hx_get='/events/list',
    hx_target='#events-container',
    hx_trigger='keyup changed delay:500ms, search',
    hx_include='[name="date_filter"], [name="category"], [name="free_only"]'
)

# Filters with HTMX
Select(
    hx_get='/events/list',
    hx_target='#events-container',
    hx_trigger='change',
    hx_include='this, [name="q"], [name="category"], [name="free_only"]',
    hx_swap='innerHTML'
)
```

**✅ Current Implementation:** HTMX-based with proper form semantics

```python
def search_section():
    return Form(
        Input(
            type='text',
            name='q',
            placeholder='Search events...',
            hx_get='/events/list',
            hx_target='#events-container',
            hx_trigger='keyup changed delay:500ms'
        ),
        Button('Search', type='submit',
               hx_get='/events/list',
               hx_target='#events-container'),
        # ... filters with HTMX attributes
        hx_get='/events/list',
        hx_target='#events-container',
        hx_trigger='submit'
    )
```

**Benefits:**
- ✅ Proper form submission semantics
- ✅ No inline JavaScript (onclick, onkeyup)
- ✅ Declarative HTMX attributes
- ✅ Server-side rendering only
- ✅ No duplicate HTML building logic

### Recommended Best Practices

```python
# Create a proper form component
def search_form() -> Form:
    """Search and filter form component."""
    return Form(
        Div(
            Input(
                type='text',
                name='q',
                id='search-input',
                placeholder='Search events...',
                hx_trigger='change, keyup delay:500ms',
                hx_get='/events/search',
                hx_target='#events-container',
                hx_include='[name=date_filter],[name=category]',
                autocomplete='off'
            ),
            Button('Search', type='submit', hx_boost='true'),
            cls='search-box'
        ),
        Div(
            Div(
                Label('When', for_='date-filter'),
                Select(
                    Option('Upcoming', value='upcoming', selected=True),
                    Option('Today', value='today'),
                    Option('This Week', value='this_week'),
                    Option('This Weekend', value='this_weekend'),
                    Option('This Month', value='this_month'),
                    name='date_filter',
                    id='date-filter',
                    hx_trigger='change',
                    hx_get='/events/search',
                    hx_target='#events-container',
                    hx_include='[name=q],[name=category]',
                ),
                cls='filter-group'
            ),
            Div(
                Label('Category', for_='category-filter'),
                Select(
                    Option('All Categories', value='', selected=True),
                    *[Option(cat, value=cat) for cat in config.CATEGORIES],
                    name='category',
                    id='category-filter',
                    hx_trigger='change',
                    hx_get='/events/search',
                    hx_target='#events-container',
                    hx_include='[name=q],[name=date_filter]',
                ),
                cls='filter-group'
            ),
            cls='filters'
        ),
        method='get',
        id='search-form'
    )

# Update route to handle form submission
@rt('/events/search', methods=['get'])
def search_events_handler(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    """Handle search via HTMX."""
    try:
        categories = [category] if category and category != 'All Categories' else None
        events = search.search(
            query=q if q else None,
            date_filter=date_filter,
            categories=categories,
            limit=100
        )
        return events_list(events)
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        return error_alert("Search failed. Please try again.", "danger")

def error_alert(message: str, alert_type: str = 'danger') -> Div:
    """HTMX-friendly error message component."""
    return Div(
        Div(message, role='alert', cls=f'alert alert-{alert_type}'),
        id='search-error',
        hx_swap_oob='true'
    )

def loading_spinner() -> Div:
    """Loading state for HTMX requests."""
    return Div(
        Div(cls='spinner'),
        P('Loading events...'),
        id='loading-state',
        cls='loading'
    )
```

---

## 5. Static File Serving

### Current Implementation

```python
@rt('/static/{filepath:path}')
def get(filepath: str):
    """Serve static files."""
    return FileResponse(f'static/{filepath}')
```

### Issues

1. **Path Traversal Vulnerability:** No validation of filepath parameter

```python
# Vulnerable to: /static/../../config.py
# An attacker could request any file on the system
```

2. **No Cache Headers:** Static files served without caching metadata

```python
# No Cache-Control, ETag, or Last-Modified headers
# Browser will re-request static files on every page load
```

3. **No Compression:** Large CSS/JS files not gzip-compressed

```python
# Search.js and map.js loaded uncompressed
# No content-encoding handling
```

4. **No Directory Listing Prevention:** Doesn't prevent `/static/` enumeration

5. **Inefficient Pattern:** Using route handler for static files

FastHTML/Starlette has better mechanisms for this.

### Recommended Best Practices

```python
from pathlib import Path
from starlette.staticfiles import StaticFiles
import mimetypes

# Configure static file serving at app initialization
static_path = Path(__file__).parent.parent.parent / 'static'

# Mount static files properly
if static_path.exists():
    app.mount('/static', StaticFiles(directory=str(static_path)), name='static')
else:
    logger.warning(f"Static directory not found: {static_path}")

# If you need custom static handling:
@rt('/static/{filepath:path}')
def serve_static(filepath: str):
    """Serve static files with security and caching."""
    # Prevent directory traversal
    try:
        file_path = (Path('static') / filepath).resolve()
        base_path = Path('static').resolve()
        
        # Ensure requested file is within static directory
        if not str(file_path).startswith(str(base_path)):
            logger.warning(f"Attempted path traversal: {filepath}")
            return Response('Not Found', status_code=404)
        
        if not file_path.exists():
            return Response('Not Found', status_code=404)
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_extension(filepath)
        
        response = FileResponse(
            file_path,
            media_type=mime_type,
            headers={
                'Cache-Control': 'public, max-age=31536000, immutable',  # 1 year
                'X-Content-Type-Options': 'nosniff',  # Prevent MIME sniffing
                'X-Frame-Options': 'DENY',  # Prevent clickjacking
            }
        )
        return response
        
    except Exception as e:
        logger.error(f"Static file error: {e}")
        return Response('Server Error', status_code=500)
```

---

## 6. Database Connections and Lifecycle

### Current Implementation

**Database Initialization (app.py lines 35-36):**
```python
db = Database(config.DATABASE_PATH)
search = EventSearch(db)
```

**Database Implementation (database.py):**
```python
@contextmanager
def get_connection(self):
    """Context manager for database connections."""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
```

### Strengths

✓ **Context manager pattern for connections**
✓ **Proper rollback/commit handling**
✓ **Row factory for dict-like access**

### Issues

1. **Global Database Instance:** Created at module import time

```python
# app.py - module level
db = Database(config.DATABASE_PATH)
search = EventSearch(db)
```

**Problems:**
- Not ideal for concurrent requests
- Difficult to test
- No connection pooling
- No graceful shutdown

2. **No Connection Pooling:** Each query opens/closes connections

```python
def get_connection(self):
    conn = sqlite3.connect(self.db_path)  # New connection every time
    # ...
    conn.close()  # Closed after use
```

3. **No Health Checks:** No mechanism to verify database is accessible

4. **No Async Support:** All database operations are synchronous

```python
# Routes marked as synchronous
@rt('/events/list')
def get(q: str = '', date_filter: str = 'upcoming', category: str = ''):
    # Blocking database calls
```

### Recommended Best Practices

```python
# Use FastHTML's lifespan context manager for app lifecycle
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Database initialization moved to app startup
database_instance: Optional[Database] = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle.
    
    Startup: Initialize database
    Shutdown: Close connections
    """
    global database_instance
    
    try:
        # Startup
        logger.info("Initializing database...")
        database_instance = Database(config.DATABASE_PATH)
        
        # Verify database is accessible
        test_event = database_instance.get_all_events(limit=1)
        logger.info("Database connection verified")
        
        yield
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        raise
    finally:
        # Shutdown
        logger.info("Closing database...")
        if database_instance:
            # Could add cleanup logic here
            pass

# Application factory pattern
def create_app() -> FastHTML:
    """Create and configure FastHTML application."""
    app, rt = fast_app(
        live=config.DEBUG,
        hdrs=create_app_headers()
    )
    
    # Add lifespan context
    app.router.lifespan_context = lifespan
    
    return app, rt

# In routes, use dependency injection
def get_db() -> Database:
    """Dependency injection for database."""
    if database_instance is None:
        raise RuntimeError("Database not initialized")
    return database_instance

@rt('/events/list', methods=['get'])
def get_events_list_html(
    q: str = '',
    date_filter: str = 'upcoming',
    category: str = '',
    db: Database = Depends(get_db)
):
    """Get events list as HTML."""
    try:
        search = EventSearch(db)
        categories = [category] if category and category != 'All Categories' else None
        events = search.search(
            query=q if q else None,
            date_filter=date_filter,
            categories=categories,
            limit=100
        )
        return events_list(events)
    except ValueError as e:
        logger.warning(f"Invalid search parameters: {e}")
        return error_alert("Invalid search parameters")
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return error_alert("Database error. Please try again later.")

# Connection pool for SQLite (basic example)
class DatabasePool:
    """Simple connection pool for SQLite."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections: List[sqlite3.Connection] = []
        self._init_pool()
    
    def _init_pool(self):
        """Initialize connection pool."""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            self.connections.append(conn)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get connection from pool."""
        if self.connections:
            return self.connections.pop()
        return sqlite3.connect(self.db_path)
    
    def return_connection(self, conn: sqlite3.Connection):
        """Return connection to pool."""
        if len(self.connections) < self.pool_size:
            self.connections.append(conn)
        else:
            conn.close()
    
    def close_all(self):
        """Close all connections."""
        for conn in self.connections:
            conn.close()
        self.connections.clear()
```

---

## 7. Error Handling

### Current Implementation

**Minimal error handling** - Only 404 case handled explicitly:

```python
@rt('/event/{event_id}')
def get(event_id: int):
    """Event detail page."""
    event = db.get_event(event_id)
    if not event:
        return Html(
            Head(Title('Event Not Found')),
            Body(
                Header(...),
                Main(...),
            )
        )
    # ... rest of implementation
```

### Issues

1. **No Global Error Handlers:** Exceptions not caught at app level

2. **No Logging:** Errors silently fail with no audit trail

3. **No User-Friendly Error Messages:** Raw exceptions would leak to frontend

4. **No Error Tracking:** No mechanism to identify problematic operations

5. **Inline Error Pages:** Error response HTML duplicated in route handlers

### Recommended Best Practices

```python
import logging
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Configure logging
logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware to handle and log errors."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except ValueError as e:
            logger.warning(f"Validation error for {request.url.path}: {e}")
            return Response(
                render_error_page(400, "Invalid request"),
                status_code=400,
                media_type='text/html'
            )
        except Exception as e:
            logger.error(f"Unhandled error for {request.url.path}: {e}", exc_info=True)
            return Response(
                render_error_page(500, "Internal server error"),
                status_code=500,
                media_type='text/html'
            )

# Exception handler decorators
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception):
    logger.info(f"404: {request.url.path}")
    return Response(
        render_error_page(404, "Page not found"),
        status_code=404,
        media_type='text/html'
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    logger.error(f"500: {request.url.path} - {exc}", exc_info=True)
    if config.DEBUG:
        # Show error details in development
        return Response(
            render_debug_error_page(exc),
            status_code=500,
            media_type='text/html'
        )
    else:
        # Hide details in production
        return Response(
            render_error_page(500, "Internal server error"),
            status_code=500,
            media_type='text/html'
        )

# Generic error page component
def render_error_page(status_code: int, message: str) -> str:
    """Render error page HTML."""
    return str(page_layout(
        f'{status_code} Error',
        Main(
            Div(
                H2(f'{status_code} Error'),
                P(message),
                A('← Back to Events', href='/', cls='btn btn-primary'),
                cls='container error-container'
            )
        )
    ))

# Custom exceptions for domain logic
class EventNotFoundError(Exception):
    """Raised when an event is not found."""
    pass

class InvalidSearchError(ValueError):
    """Raised when search parameters are invalid."""
    pass

# Using custom exceptions in routes
@rt('/event/{event_id}')
def get_event_detail(event_id: int):
    """Event detail page."""
    try:
        event = db.get_event(event_id)
        if not event:
            raise EventNotFoundError(f"Event {event_id} not found")
        
        return page_layout(
            event.title,
            render_event_detail(event)
        )
    except EventNotFoundError as e:
        logger.info(f"Event not found: {e}")
        return render_error_page(404, "Event not found")
    except Exception as e:
        logger.error(f"Error fetching event: {e}", exc_info=True)
        return render_error_page(500, "Failed to load event")

# Error callback from HTMX
def handle_htmx_error(
    request: Request,
    exc: Exception
):
    """Handle errors in HTMX requests."""
    logger.error(f"HTMX error: {exc}", exc_info=True)
    return Div(
        Div(
            "An error occurred while loading events.",
            role='alert',
            cls='alert alert-danger'
        ),
        id='search-error',
        hx_swap_oob='true'
    )

app.add_middleware(ErrorHandlingMiddleware)
```

---

## 8. Template/Component Patterns

### Current Implementation

Components are defined as Python functions returning FastHTML elements:

```python
def event_card(event):
    return Div(...)

def events_list(events):
    return Div(...)

def search_section():
    return Div(...)
```

### Issues

1. **No Component Composition System:** Components hardcoded into routes

2. **No Props/Arguments Validation:** Components accept untyped parameters

```python
def event_card(event):  # No type hint!
    event_date_str = event.event_date.strftime(...)  # Could fail if event.event_date is None
```

3. **No Slot System:** Can't pass children to components

4. **No Conditional Rendering Abstraction:** If/else logic in components

```python
Img(src=event.image_url, ...) if event.image_url else None,
```

### Recommended Best Practices

```python
from dataclasses import dataclass
from typing import List, Optional, Union

# Component type system
@dataclass
class EventCardProps:
    """Props for event card component."""
    event: Event
    clickable: bool = True
    show_image: bool = True
    
    def validate(self):
        """Validate props."""
        if not isinstance(self.event, Event):
            raise TypeError("event must be an Event instance")
        if not isinstance(self.clickable, bool):
            raise TypeError("clickable must be a boolean")

def event_card(props: EventCardProps) -> Div:
    """Component to render a single event card."""
    props.validate()
    
    event = props.event
    event_date_str = event.event_date.strftime("%a, %b %d, %Y at %I:%M %p") if event.event_date else "Date TBA"
    
    children = [
        render_event_image(event) if props.show_image else None,
        Div(
            H2(event.title, cls='event-title'),
            render_event_date(event_date_str),
            render_event_venue(event),
            render_event_description(event),
            render_event_footer(event),
            render_event_link(event) if props.clickable else None,
            cls='event-content'
        ),
    ]
    
    return Div(*[child for child in children if child is not None], cls='event-card')

# Helper functions for event card parts
def render_event_image(event: Event) -> Optional[Img]:
    """Render event image if available."""
    return Img(src=event.image_url, alt=event.title, cls='event-image') if event.image_url else None

def render_event_date(date_str: str) -> Div:
    """Render event date."""
    return Div(f'📅 {date_str}', cls='event-date')

def render_event_venue(event: Event) -> Optional[Div]:
    """Render event venue if available."""
    return Div(f'📍 {event.venue_name}', cls='event-location') if event.venue_name else None

def render_event_description(event: Event) -> Optional[P]:
    """Render event description if available."""
    return P(event.description, cls='event-description') if event.description else None

def render_event_footer(event: Event) -> Div:
    """Render event footer with category and source."""
    return Div(
        Span(event.category, cls='event-category'),
        Span(event.source, cls='event-source'),
        cls='event-footer'
    )

def render_event_link(event: Event) -> A:
    """Render event detail link."""
    return A('View Details →', href=f'/event/{event.id}', cls='event-link')

# Usage
@rt('/events/list')
def get_events_list_html(...):
    events = search.search(...)
    
    if not events:
        return empty_state()
    
    return events_list_container(
        count=len(events),
        events=[
            event_card(EventCardProps(event=e))
            for e in events
        ]
    )

def events_list_container(count: int, events: List[Div]) -> Div:
    """Render events list container."""
    count_text = f'Found {count} event{"s" if count != 1 else ""}'
    return Div(
        Div(count_text, style='margin-bottom: 1.5rem; ...'),
        Div(*events, cls='events-grid', id='events-grid'),
    )

# Composed complex components
@dataclass
class PageProps:
    """Props for page layout."""
    title: str
    content: Union[Div, str]
    sidebar: Optional[Div] = None
    extra_scripts: Optional[List[Script]] = None

def page(props: PageProps) -> Html:
    """Render full page with layout."""
    props.validate()
    
    return Html(
        Head(
            Title(f'{props.title} - Westside LA Events'),
            Meta(charset='UTF-8'),
            Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
            Link(rel='stylesheet', href='/static/css/style.css'),
            *(props.extra_scripts or [])
        ),
        Body(
            app_header(),
            Div(
                props.content,
                props.sidebar,
                cls='main-container'
            ),
            app_footer(),
        )
    )
```

---

## Summary of Recommendations

### Priority 1: Security & Stability

1. **Fix path traversal vulnerability** in static file serving
2. **Add global error handlers** with logging
3. **Implement CSRF protection** for forms
4. **Add database health checks** at startup

### Priority 2: Code Quality & Maintainability

1. **Use descriptive function names** for routes (not multiple `get()` functions)
2. **Implement component props system** with type hints
3. **Create shared layout components** (header, footer)
4. **Remove duplicate HTML building** between Python and JavaScript

### Priority 3: FastHTML Best Practices

1. **Use HTMX for interactive features** instead of fetch + JavaScript
2. **Implement proper form handling** with semantic HTML
3. **Add database lifecycle management** (startup/shutdown)
4. **Organize scripts with proper defer/async loading**

### Priority 4: Performance & User Experience

1. **Add connection pooling** for database
2. **Implement caching headers** for static files
3. **Use loading indicators** in HTMX requests
4. **Add client-side validation** before form submission

---

## File Structure Recommendations

```
src/web/
├── app.py                 # Main application
├── components/
│   ├── __init__.py
│   ├── layout.py         # Shared layout components
│   ├── events.py         # Event-related components
│   ├── forms.py          # Form components
│   └── errors.py         # Error page components
├── routes/
│   ├── __init__.py
│   ├── events.py         # Event routes
│   ├── search.py         # Search routes
│   ├── api.py            # API routes
│   └── static.py         # Static file serving
├── middleware/
│   ├── __init__.py
│   ├── error_handling.py # Error handling middleware
│   └── logging.py        # Logging middleware
└── config.py             # Web-specific configuration
```

---

## Conclusion

The current implementation provides a solid foundation with proper component-based architecture and database integration. By implementing the recommended best practices, the application will be more maintainable, secure, and performant while better leveraging FastHTML's capabilities.

The key focus should be on:
1. Consolidating error handling
2. Improving component reusability
3. Leveraging HTMX for enhanced UX
4. Properly managing application lifecycle
5. Following FastHTML conventions more closely


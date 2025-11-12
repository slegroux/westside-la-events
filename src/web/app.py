"""
Main FastHTML application for LA Events Aggregator.
"""
from fasthtml.common import *
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List

import config
from src.data.database import Database
from src.data.models import Event
from src.search.query import EventSearch


# Application state
class AppState:
    """Application state container."""
    db: Database = None
    search: EventSearch = None


state = AppState()


@asynccontextmanager
async def lifespan(app):
    """Manage application lifecycle - startup and shutdown."""
    # Startup: Initialize database and search
    state.db = Database(config.DATABASE_PATH)
    state.search = EventSearch(state.db)

    yield

    # Shutdown: Clean up resources (Database uses context managers, no explicit close needed)
    pass


# Initialize FastHTML app with lifespan
# Note: All CSS/JS includes are in page_head() to avoid duplication
app, rt = fast_app(
    live=config.DEBUG,
    lifespan=lifespan
)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors."""
    from starlette.responses import HTMLResponse
    content = str(Html(
        page_head('Page Not Found - Westside LA Events'),
        Body(
            page_header(),
            Main(
                Div(
                    H2('Page Not Found'),
                    P('The page you are looking for does not exist.'),
                    A('← Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=404)


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 errors."""
    import logging
    from starlette.responses import HTMLResponse
    logger = logging.getLogger(__name__)
    logger.error(f'Server error: {exc}', exc_info=True)

    content = str(Html(
        page_head('Server Error - Westside LA Events'),
        Body(
            page_header(),
            Main(
                Div(
                    H2('Something Went Wrong'),
                    P('We encountered an error while processing your request. Please try again later.'),
                    A('← Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=500)


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all handler for unhandled exceptions."""
    import logging
    from starlette.responses import HTMLResponse
    logger = logging.getLogger(__name__)
    logger.error(f'Unhandled exception: {exc}', exc_info=True)

    # In debug mode, let the error propagate to show traceback
    if config.DEBUG:
        raise exc

    content = str(Html(
        page_head('Error - Westside LA Events'),
        Body(
            page_header(),
            Main(
                Div(
                    H2('Something Went Wrong'),
                    P('We encountered an unexpected error. Please try again later.'),
                    A('← Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=500)


def page_head(title: str, description: Optional[str] = None):
    """Shared page head component with meta tags."""
    default_description = 'Discover the best events, activities, and experiences across LA\'s Westside'
    return Head(
        Title(title),
        Meta(charset='UTF-8'),
        Meta(name='viewport', content='width=device-width, initial-scale=1.0'),
        Meta(name='description', content=description or default_description),
        Meta(name='keywords', content='LA events, Westside LA, Santa Monica, activities, concerts, art, food'),
        Meta(property='og:title', content=title),
        Meta(property='og:description', content=description or default_description),
        Meta(property='og:type', content='website'),
        # HTMX for interactive features
        Script(src='https://unpkg.com/htmx.org@2.0.3'),
        # Leaflet CSS
        Link(rel='stylesheet', href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
             integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', crossorigin='anonymous'),
        # Leaflet MarkerCluster CSS
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css'),
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css'),
        # Application CSS
        Link(rel='stylesheet', href='/static/css/style.css'),
        # Leaflet JS - load with defer to ensure proper order
        Script(src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
               integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=', crossorigin='anonymous', defer=True),
        # Leaflet MarkerCluster JS
        Script(src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js', defer=True),
        # Application JavaScript - defer to load after Leaflet
        Script(src='/static/js/map.js', defer=True)
    )


def page_header():
    """Shared page header component."""
    return Header(
        Div(
            H1('🌴 Westside LA Events'),
            P('Discover the best events, activities, and experiences across LA\'s Westside', cls='header-subtitle'),
            cls='header-content container'
        )
    )


def page_footer():
    """Shared page footer component."""
    return Footer(
        Div(
            P('Westside LA Events Aggregator'),
            P('Aggregating events from Santa Monica, Timeout LA, KCRW, and more.'),
            P(
                'Made with love by ',
                A('Sisyphe.ai', href='https://sisyphe.ai', target='_blank', rel='noopener noreferrer')
            ),
            cls='container'
        )
    )


def event_card(event: Event):
    """Component to render a single event card."""
    event_date_str = event.event_date.strftime("%a, %b %d, %Y at %I:%M %p") if event.event_date else "Date TBA"

    # Source logo element
    source_display = Div(
        Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo') if event.source_logo_url else None,
        Span(event.source, cls='event-source'),
        cls='event-source-container'
    )

    # Price display
    price_display = None
    if event.is_free:
        price_display = Span('FREE', cls='event-price free-badge')
    elif event.price:
        price_display = Span(f'${event.price:.2f}', cls='event-price')
    elif event.price_note:
        # Show price note for events where pricing isn't available
        price_display = Span(event.price_note, cls='event-price price-note')

    # Date Night badge
    date_night_badge = None
    if event.category == 'Date Night':
        date_night_badge = Span('💕 DATE NIGHT', cls='event-badge date-night-badge')

    return Div(
        # Make image clickable
        A(
            Img(src=event.image_url, alt=event.title, cls='event-image'),
            href=f'/event/{event.id}'
        ) if event.image_url else None,
        Div(
            # Make title clickable
            Div(
                A(
                    H2(event.title, cls='event-title'),
                    href=f'/event/{event.id}',
                    style='text-decoration: none; color: inherit;'
                ),
                price_display,
                date_night_badge,
                cls='event-header'
            ) if (price_display or date_night_badge) else A(
                H2(event.title, cls='event-title'),
                href=f'/event/{event.id}',
                style='text-decoration: none; color: inherit;'
            ),
            Div(f'📅 {event_date_str}', cls='event-date'),
            Div(f'📍 {event.venue_name}', cls='event-location') if event.venue_name else None,
            P(event.description, cls='event-description') if event.description else None,
            Div(
                Span(event.category, cls='event-category'),
                source_display,
                cls='event-footer'
            ),
            Div(
                A('View Details →', href=f'/event/{event.id}', cls='event-link'),
                A('📅 Add to Calendar', href=f'/event/{event.id}/calendar', cls='calendar-link'),
                cls='event-actions'
            ),
            cls='event-content'
        ),
        cls='event-card'
    )


def events_list(events: List[Event]):
    """Component to render the events grid."""
    if not events:
        return Div(
            H2('🔍 No events found'),
            P('Try adjusting your search filters or check back later for new events.'),
            cls='empty-state'
        )

    count_text = f'Found {len(events)} event{"s" if len(events) != 1 else ""}'
    return Div(
        Div(count_text, style='margin-bottom: 1.5rem; color: var(--text-light); font-size: 1rem; font-weight: 600;'),
        Div(*[event_card(e) for e in events], cls='events-grid'),
    )


@rt('/')
def home_page():
    """Home page with search and map."""
    # Get initial events - default to "upcoming"
    initial_events = state.search.search(date_filter='upcoming', limit=100)

    return Html(
        page_head('Westside LA Events'),
        Body(
            page_header(),
            Div(
                # Search Section
                search_section(),

                # View Toggle
                Div(
                    Button('List View', type='button', id='list-view-btn', cls='active',
                           onclick='showListView()'),
                    Button('Map View', type='button', id='map-view-btn', onclick='showMapView()'),
                    cls='view-toggle container'
                ),

                # Map Container
                Div(id='map', style='display: none;'),

                # Events Grid - Now with server-rendered content
                Div(events_list(initial_events), id='events-container', cls='container'),

                cls='container'
            ),
            page_footer()
        )
    )


def _get_filter_tallies(date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = ''):
    """
    Get category and source tallies based on current filters.

    This function calculates the count of events for each category and source,
    taking into account the current date, category, source, and free_only filters.
    When filtering by category, source counts reflect only those categories.
    When filtering by source, category counts reflect only those sources.
    """
    available_sources = []
    available_categories = {}

    try:
        with state.db.get_connection() as conn:
            # Build WHERE clause based on filters
            conditions = []
            params = []

            # Always filter out NULL sources and categories
            base_conditions = ["source IS NOT NULL", "category IS NOT NULL"]

            # Date filter
            if date_filter == 'specific_date' and specific_date:
                from datetime import datetime, timedelta
                try:
                    date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                    end_date = date_obj + timedelta(days=1)
                    conditions.append("event_date >= ? AND event_date < ?")
                    params.extend([date_obj, end_date])
                except ValueError:
                    # Fall back to upcoming if date parsing fails
                    conditions.append("event_date >= datetime('now')")
            elif date_filter == 'today':
                conditions.append("date(event_date) = date('now')")
            elif date_filter == 'this_week':
                conditions.append("event_date >= date('now') AND event_date < date('now', 'weekday 0', '+7 days')")
            elif date_filter == 'this_weekend':
                conditions.append("date(event_date) IN (date('now', 'weekday 6'), date('now', 'weekday 0', '+7 days'))")
            elif date_filter == 'this_month':
                conditions.append("strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now')")
            else:  # upcoming or default
                conditions.append("event_date >= datetime('now')")

            # Free events filter
            if free_only == 'true':
                conditions.append("is_free = 1")

            # Build full WHERE clause
            where_clause = " AND ".join(base_conditions + conditions)

            # Get category counts (filtered by source if sources are selected)
            category_conditions = list(conditions)  # Copy date and free filters
            if source and len(source) > 0:
                placeholders = ','.join('?' * len(source))
                category_conditions.append(f"source IN ({placeholders})")
                category_params = params + list(source)
            else:
                category_params = params

            category_where = " AND ".join(base_conditions + category_conditions)
            cursor = conn.execute(f"""
                SELECT category, COUNT(*) as count
                FROM events
                WHERE {category_where}
                GROUP BY category
                ORDER BY category
            """, category_params)
            available_categories = {row[0]: row[1] for row in cursor.fetchall()}

            # Get source counts (filtered by category if categories are selected)
            source_conditions = list(conditions)  # Copy date and free filters
            if category and len(category) > 0:
                placeholders = ','.join('?' * len(category))
                source_conditions.append(f"category IN ({placeholders})")
                source_params = params + list(category)
            else:
                source_params = params

            source_where = " AND ".join(base_conditions + source_conditions)
            cursor = conn.execute(f"""
                SELECT source, COUNT(*) as count
                FROM events
                WHERE {source_where}
                GROUP BY source
                ORDER BY source
            """, source_params)
            available_sources = [(row[0], row[1]) for row in cursor.fetchall()]

            # Get free events count (filtered by category and source, but NOT by free_only)
            free_conditions = []
            free_params = []

            # Date filter (reuse the same logic)
            if date_filter == 'specific_date' and specific_date:
                from datetime import datetime, timedelta
                try:
                    date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
                    end_date = date_obj + timedelta(days=1)
                    free_conditions.append("event_date >= ? AND event_date < ?")
                    free_params.extend([date_obj, end_date])
                except ValueError:
                    free_conditions.append("event_date >= datetime('now')")
            elif date_filter == 'today':
                free_conditions.append("date(event_date) = date('now')")
            elif date_filter == 'this_week':
                free_conditions.append("event_date >= date('now') AND event_date < date('now', 'weekday 0', '+7 days')")
            elif date_filter == 'this_weekend':
                free_conditions.append("date(event_date) IN (date('now', 'weekday 6'), date('now', 'weekday 0', '+7 days'))")
            elif date_filter == 'this_month':
                free_conditions.append("strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now')")
            else:
                free_conditions.append("event_date >= datetime('now')")

            # Add category filter if selected
            if category and len(category) > 0:
                placeholders = ','.join('?' * len(category))
                free_conditions.append(f"category IN ({placeholders})")
                free_params.extend(list(category))

            # Add source filter if selected
            if source and len(source) > 0:
                placeholders = ','.join('?' * len(source))
                free_conditions.append(f"source IN ({placeholders})")
                free_params.extend(list(source))

            # Add is_free condition
            free_conditions.append("is_free = 1")

            free_where = " AND ".join(base_conditions + free_conditions)
            cursor = conn.execute(f"""
                SELECT COUNT(*) as count
                FROM events
                WHERE {free_where}
            """, free_params)
            result = cursor.fetchone()
            free_events_count = result[0] if result else 0
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting filter tallies: {e}", exc_info=True)
        # If we can't get sources/categories, just use empty lists
        free_events_count = 0
        pass

    return available_categories, available_sources, free_events_count


def filter_section_collapsible(section_id: str, label: str, checkboxes_content, expanded: bool = False):
    """Render a collapsible filter section with HTMX."""
    return Div(
        Div(
            Label(label, cls='filter-section-label', style='margin: 0;'),
            Button(
                '▲ Hide' if expanded else '▼ Show',
                type='button',
                cls=f'filter-toggle-btn{" expanded" if expanded else ""}',
                hx_get=f'/filters/toggle/{section_id}?expanded={not expanded}',
                hx_target=f'#filter-section-{section_id}',
                hx_swap='outerHTML',
                hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]'
            ),
            cls='filter-header'
        ),
        Div(
            *checkboxes_content,
            cls='category-checkboxes',
            style='display: flex;' if expanded else 'display: none;'
        ),
        cls='filter-group category-filter-group',
        id=f'filter-section-{section_id}'
    )


def filter_tallies_section(date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', categories_expanded: bool = False, sources_expanded: bool = False):
    """Render the category and source filter checkboxes with counts."""
    available_categories, available_sources, free_events_count = _get_filter_tallies(date_filter, category, source, free_only, specific_date)

    # For HTMX requests that update tallies, we also need to preserve the checked state
    # We'll use the provided category/source lists to determine which boxes should be checked
    checked_categories = set(category) if category else set()
    checked_sources = set(source) if source else set()

    # Build category checkboxes
    category_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='category',
                value=cat,
                checked=True if cat in checked_categories else False,
                hx_get='/events/list, /filters/tallies',
                hx_target='#events-container, #filter-tallies',
                hx_trigger='change',
                hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                hx_swap='innerHTML'
            ),
            f' {cat} ({available_categories.get(cat, 0)})',
            cls='category-checkbox-label'
        )
        for cat in config.CATEGORIES
    ]

    # Build source checkboxes
    source_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='source',
                value=source_name,
                checked=True if source_name in checked_sources else False,
                hx_get='/events/list, /filters/tallies',
                hx_target='#events-container, #filter-tallies',
                hx_trigger='change',
                hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                hx_swap='innerHTML'
            ),
            f' {source_name} ({count})',
            cls='category-checkbox-label'
        )
        for source_name, count in available_sources
    ] if available_sources else []

    return Div(
        # Categories filter with toggle
        filter_section_collapsible('categories', 'Categories', category_checkboxes, categories_expanded),
        # Sources filter with toggle
        filter_section_collapsible('sources', 'Sources', source_checkboxes, sources_expanded) if source_checkboxes else None,
        # Free events checkbox with tally
        Div(
            Label(
                Input(
                    type='checkbox',
                    id='free-only-checkbox',
                    name='free_only',
                    value='true',
                    checked=True if free_only == 'true' else False,
                    hx_get='/events/list, /filters/tallies',
                    hx_target='#events-container, #filter-tallies',
                    hx_trigger='change',
                    hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="specific_date"]',
                    hx_swap='innerHTML'
                ),
                f' Free Events Only ({free_events_count})',
                for_='free-only-checkbox',
                cls='checkbox-label'
            ),
            cls='filter-group checkbox-filter',
            style='margin-top: 1rem;'
        ),
        id='filter-tallies'
    )


def search_section():
    """Search and filter section component."""
    return Form(
        H2('Find Events'),
        Div(
            Input(
                type='text',
                id='search-input',
                name='q',
                placeholder='Search events...',
                hx_get='/events/list',
                hx_target='#events-container',
                hx_trigger='keyup changed delay:500ms, search',
                hx_include='[name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]'
            ),
            Button('Search', type='submit', hx_get='/events/list', hx_target='#events-container', hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]'),
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
                    Option('Specific Date', value='specific_date'),
                    id='date-filter',
                    name='date_filter',
                    hx_get='/events/list, /filters/tallies, /filters/date-picker',
                    hx_target='#events-container, #filter-tallies, #date-picker-container',
                    hx_trigger='change',
                    hx_include='this, [name="q"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                    hx_swap='innerHTML'
                ),
                cls='filter-group'
            ),
            # Date picker container - populated dynamically by HTMX
            Div(id='date-picker-container', cls='filter-group calendar-filter'),
            # Filter tallies section that will be dynamically updated
            filter_tallies_section(),
            cls='filters'
        ),
        cls='search-section',
        hx_get='/events/list',
        hx_target='#events-container',
        hx_trigger='submit'
    )


def _fetch_events(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', limit: int = 100) -> List[Event]:
    """
    Helper function to fetch events with consistent filter-building logic.

    Args:
        q: Search query string
        date_filter: Date filter (upcoming, today, this_week, etc.)
        category: List of category filters (from multiple checkboxes)
        source: List of source filters (from multiple checkboxes)
        free_only: Free events filter ('true' or empty string)
        specific_date: Specific date in YYYY-MM-DD format (when date_filter is 'specific_date')
        limit: Maximum number of events to return

    Returns:
        List of Event objects matching the filters
    """
    # Handle category filtering - if no categories selected, show all
    categories = category if category and len(category) > 0 else None

    # Handle source filtering - if no sources selected, show all
    sources = source if source and len(source) > 0 else None

    # Convert free_only to boolean
    is_free = True if free_only == 'true' else None

    # If specific_date is provided and date_filter is 'specific_date', use the specific date
    if date_filter == 'specific_date' and specific_date:
        from datetime import datetime, timedelta
        try:
            # Parse the date and use it as both start and end for that day
            date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
            # Set start to beginning of day and end to beginning of next day
            start = date_obj
            end = date_obj + timedelta(days=1)
            return state.search.search(
                query=q if q else None,
                start_date=start,
                end_date=end,
                categories=categories,
                sources=sources,
                is_free=is_free,
                limit=limit
            )
        except ValueError:
            # If date parsing fails, fall back to regular date_filter
            pass

    return state.search.search(
        query=q if q else None,
        date_filter=date_filter if date_filter != 'specific_date' else 'upcoming',
        categories=categories,
        sources=sources,
        is_free=is_free,
        limit=limit
    )


@rt('/events/list')
def get_events_list(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = ''):
    """HTMX endpoint to get events list HTML fragment."""
    from starlette.responses import HTMLResponse
    events = _fetch_events(q, date_filter, category, source, free_only, specific_date)
    # Return just the HTML fragment without full page wrapper
    result = events_list(events)
    return HTMLResponse(str(result))


@rt('/filters/tallies')
def get_filter_tallies(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', categories_expanded: str = 'false', sources_expanded: str = 'false'):
    """HTMX endpoint to get updated filter tallies HTML fragment."""
    from starlette.responses import HTMLResponse
    result = filter_tallies_section(
        date_filter,
        category,
        source,
        free_only,
        specific_date,
        categories_expanded == 'true',
        sources_expanded == 'true'
    )
    return HTMLResponse(str(result))


@rt('/filters/date-picker')
def get_date_picker(date_filter: str = 'upcoming'):
    """HTMX endpoint to show/hide date picker based on filter selection."""
    from starlette.responses import HTMLResponse

    if date_filter == 'specific_date':
        result = Div(
            Label('Pick a Date', for_='date-picker'),
            Input(
                type='date',
                id='date-picker',
                name='specific_date',
                hx_get='/events/list, /filters/tallies',
                hx_target='#events-container, #filter-tallies',
                hx_trigger='change',
                hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"]',
                hx_swap='innerHTML'
            ),
            id='date-picker-container',
            cls='filter-group calendar-filter'
        )
    else:
        # Return empty container when not specific_date
        result = Div(id='date-picker-container', cls='filter-group calendar-filter')

    return HTMLResponse(str(result))


@rt('/filters/toggle/{section_id}')
def toggle_filter_section(section_id: str, expanded: str = 'false', q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = ''):
    """HTMX endpoint to toggle a filter section."""
    from starlette.responses import HTMLResponse

    # Get the current filter data
    available_categories, available_sources, _ = _get_filter_tallies(date_filter, category, source, free_only, specific_date)
    checked_categories = set(category) if category else set()
    checked_sources = set(source) if source else set()

    is_expanded = expanded == 'true'

    if section_id == 'categories':
        # Build category checkboxes
        checkboxes = [
            Label(
                Input(
                    type='checkbox',
                    name='category',
                    value=cat,
                    checked=True if cat in checked_categories else False,
                    hx_get='/events/list, /filters/tallies',
                    hx_target='#events-container, #filter-tallies',
                    hx_trigger='change',
                    hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                    hx_swap='innerHTML'
                ),
                f' {cat} ({available_categories.get(cat, 0)})',
                cls='category-checkbox-label'
            )
            for cat in config.CATEGORIES
        ]
        result = filter_section_collapsible('categories', 'Categories', checkboxes, is_expanded)
    elif section_id == 'sources':
        # Build source checkboxes
        checkboxes = [
            Label(
                Input(
                    type='checkbox',
                    name='source',
                    value=source_name,
                    checked=True if source_name in checked_sources else False,
                    hx_get='/events/list, /filters/tallies',
                    hx_target='#events-container, #filter-tallies',
                    hx_trigger='change',
                    hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                    hx_swap='innerHTML'
                ),
                f' {source_name} ({count})',
                cls='category-checkbox-label'
            )
            for source_name, count in available_sources
        ]
        result = filter_section_collapsible('sources', 'Sources', checkboxes, is_expanded)
    else:
        return HTMLResponse('Invalid section', status_code=400)

    return HTMLResponse(str(result))


@rt('/api/events')
def get_events_json(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = ''):
    """API endpoint to get events as JSON."""
    events = _fetch_events(q, date_filter, category, source, free_only, specific_date)

    from starlette.responses import JSONResponse
    return JSONResponse([event.to_dict() for event in events])


def _lazy_load_description(event: Event):
    """
    Lazy load description for an event that doesn't have one.
    This is a fallback for events that were scraped without descriptions.

    Args:
        event: Event object to load description for
    """
    try:
        # Import scraper dynamically to avoid circular imports
        if event.source == 'KCRW':
            from src.scrapers.kcrw import KCRWScraper
            scraper = KCRWScraper()
            description = scraper._fetch_event_description(event.url)

            if description:
                # Update event in database
                event.description = description
                state.db.update_event(event)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to lazy load description for event {event.id}: {e}")


def event_location_map(event: Event):
    """Component to render an inline map for a single event location."""
    import json

    # Safely escape strings for JavaScript
    title_json = json.dumps(event.title)
    venue_json = json.dumps(event.venue_name if event.venue_name else "")

    map_id = f'event-map-{event.id}'

    return Div(
        Div(id=map_id, style='width: 100%; height: 300px; border-radius: 0.5rem; margin-bottom: 1.5rem;'),
        Script(f'''
            document.addEventListener('DOMContentLoaded', function() {{
                // Initialize map for event location
                const eventMap = L.map('{map_id}').setView([{event.latitude}, {event.longitude}], 15);

                // Add OpenStreetMap tiles
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                    maxZoom: 19
                }}).addTo(eventMap);

                // Add marker for event location
                const marker = L.marker([{event.latitude}, {event.longitude}]).addTo(eventMap);
                const popupTitle = {title_json};
                const popupVenue = {venue_json};
                const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination={event.latitude},{event.longitude}`;
                marker.bindPopup(`
                    <div>
                        <div style="font-weight: 600; margin-bottom: 0.25rem;">${{popupTitle}}</div>
                        <div style="font-size: 0.9rem; color: #64748b; margin-bottom: 0.5rem;">${{popupVenue}}</div>
                        <a href="${{directionsUrl}}" target="_blank" rel="noopener noreferrer" style="color: #10b981; font-weight: 600; text-decoration: none; font-size: 0.9rem;">🗺️ Get Directions</a>
                    </div>
                `).openPopup();
            }});
        ''')
    )


@rt('/event/{event_id}')
def event_detail_page(event_id: int):
    """Event detail page with lazy description loading."""
    event = state.db.get_event(event_id)
    if not event:
        return Html(
            page_head('Event Not Found - Westside LA Events'),
            Body(
                page_header(),
                Main(
                    Div(
                        A('← Back to Events', href='/', cls='back-link'),
                        Div(
                            H2('Event Not Found'),
                            P('The event you are looking for does not exist.'),
                            cls='empty-state'
                        ),
                        cls='container'
                    )
                ),
                page_footer()
            )
        )

    # Lazy load description if missing (for KCRW events)
    if not event.description and event.url and event.source == 'KCRW':
        _lazy_load_description(event)

    description = f'{event.description[:150]}...' if event.description and len(event.description) > 150 else event.description
    return Html(
        page_head(f'{event.title} - Westside LA Events', description=description),
        Body(
            page_header(),
            Main(
                Div(
                    A('← Back to Events', href='/', cls='back-link'),
                    Div(
                        # Event image
                        Img(src=event.image_url, alt=event.title, cls='event-detail-image') if event.image_url else None,
                        H1(event.title, cls='event-detail-title'),
                        Div(
                            Span(f'📅 {event.event_date.strftime("%A, %B %d, %Y at %I:%M %p") if event.event_date else "Date TBA"}', cls='event-detail-date'),
                            Span(f'📍 {event.venue_name}', cls='event-detail-venue') if event.venue_name else '',
                            # Price display
                            Span('FREE', cls='event-price free-badge', style='margin-left: 1rem;') if event.is_free else (
                                Span(f'${event.price:.2f}', cls='event-price', style='margin-left: 1rem;') if event.price else (
                                    Span(event.price_note, cls='event-price price-note', style='margin-left: 1rem;') if event.price_note else None
                                )
                            ),
                            # Date Night badge
                            Span('💕 DATE NIGHT', cls='event-badge date-night-badge', style='margin-left: 0.5rem;') if event.category == 'Date Night' else None,
                            cls='event-detail-meta'
                        ),
                        # Event summary/description
                        Div(
                            H2('About This Event', cls='section-heading'),
                            P(event.description, cls='event-detail-description'),
                            cls='event-summary-section'
                        ) if event.description else None,
                        # Map showing event location
                        event_location_map(event) if event.latitude and event.longitude else '',
                        Div(
                            Div(
                                Strong('Address: '),
                                A(event.address,
                                  href=f'https://www.google.com/maps/search/?api=1&query={event.latitude},{event.longitude}' if event.latitude and event.longitude else f'https://www.google.com/maps/search/?api=1&query={event.address.replace(" ", "+")}',
                                  target='_blank',
                                  rel='noopener noreferrer',
                                  style='color: #10b981; text-decoration: none; font-weight: 500;')
                            ) if event.address else '',
                            Div(
                                Strong('Category: '),
                                Span(event.category, cls='badge')
                            ) if event.category else '',
                            Div(
                                Strong('Source: '),
                                Div(
                                    Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo') if event.source_logo_url else None,
                                    Span(event.source, cls='event-source'),
                                    cls='event-source-container'
                                )
                            ),
                            cls='event-detail-info'
                        ),
                        Div(
                            A('Visit Original Event Page →', href=event.url, target='_blank', cls='btn-primary') if event.url and not event.url.startswith('https://example.com') else '',
                            A('📅 Add to Calendar', href=f'/event/{event.id}/calendar', cls='btn-secondary calendar-link'),
                            cls='event-detail-actions'
                        ),
                        cls='event-detail-card'
                    ),
                    cls='container'
                )
            ),
            page_footer()
        )
    )


@rt('/event/{event_id}/calendar')
def export_event_calendar(event_id: int):
    """Export event as .ics calendar file."""
    from starlette.responses import Response
    import re

    event = state.db.get_event(event_id)
    if not event:
        return Response('Event not found', status_code=404)

    # Generate .ics content
    from datetime import datetime, timezone, timedelta

    # Format dates for iCalendar (YYYYMMDDTHHMMSSZ format)
    def format_ical_date(dt):
        if dt:
            # Convert to UTC if possible
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime('%Y%m%dT%H%M%SZ')
        return ''

    start_date = format_ical_date(event.event_date) if event.event_date else format_ical_date(datetime.now())
    end_date = format_ical_date(event.end_date) if event.end_date else format_ical_date(
        event.event_date + timedelta(hours=2) if event.event_date else datetime.now()
    )

    # Clean text for iCalendar format (escape special characters)
    def clean_ical_text(text):
        if not text:
            return ''
        text = str(text).replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        return text

    # Create unique ID for the event
    uid = f'event-{event.id}@westsidelaevents.com'

    # Build location string
    location = clean_ical_text(f"{event.venue_name}, {event.address}" if event.venue_name and event.address else event.venue_name or event.address or '')

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Westside LA Events//Event Export//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{format_ical_date(datetime.now())}
DTSTART:{start_date}
DTEND:{end_date}
SUMMARY:{clean_ical_text(event.title)}
DESCRIPTION:{clean_ical_text(event.description)}
LOCATION:{location}
URL:{event.url if event.url else ''}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""

    # Create safe filename from event title
    safe_title = re.sub(r'[^\w\s-]', '', event.title).strip().replace(' ', '_')[:50]
    filename = f'{safe_title}.ics'

    return Response(
        content=ics_content,
        media_type='text/calendar',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@rt('/api/events/{event_id}')
def get_event_json(event_id: int):
    """API endpoint to get a single event."""
    from starlette.responses import JSONResponse
    event = state.db.get_event(event_id)
    if event:
        return JSONResponse(event.to_dict())
    return JSONResponse({'error': 'Event not found'}, status_code=404)


@app.get('/favicon.ico')
def favicon():
    """Serve favicon or return 204 No Content if not found."""
    from pathlib import Path
    from starlette.responses import Response

    favicon_path = Path('static/favicon.ico')
    if favicon_path.exists():
        return FileResponse(favicon_path)

    # Return 204 No Content if favicon doesn't exist
    return Response(status_code=204)


# Serve static files
@rt('/static/{filepath:path}')
def serve_static(filepath: str):
    """Serve static files with path traversal protection."""
    from pathlib import Path
    import os

    # Define the static directory (absolute path)
    static_dir = Path('static').resolve()

    # Resolve the requested file path
    requested_file = (static_dir / filepath).resolve()

    # Security check: ensure the resolved path is within static_dir
    try:
        requested_file.relative_to(static_dir)
    except ValueError:
        # Path traversal attempt detected
        from starlette.responses import Response
        return Response('Forbidden', status_code=403)

    # Check if file exists
    if not requested_file.exists() or not requested_file.is_file():
        from starlette.responses import Response
        return Response('Not Found', status_code=404)

    return FileResponse(requested_file)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'src.web.app:app',
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )

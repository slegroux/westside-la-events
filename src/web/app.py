"""
Main FastHTML application for LA Events Aggregator.
"""
from fasthtml.common import *
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Set

import config
from src.data.database import Database
from src.data.models import Event
from src.data.analytics import Analytics
from src.search.query import EventSearch


# Application state
class AppState:
    """Application state container."""
    db: Database = None
    search: EventSearch = None
    analytics: Analytics = None


state = AppState()


# Session helpers for favorites
def get_favorites(session) -> Set[int]:
    """Get the set of favorited event IDs from the session."""
    return set(session.get('favorites', []))


def add_favorite(session, event_id: int):
    """Add an event ID to favorites in the session."""
    favorites = get_favorites(session)
    favorites.add(event_id)
    session['favorites'] = list(favorites)


def remove_favorite(session, event_id: int):
    """Remove an event ID from favorites in the session."""
    favorites = get_favorites(session)
    favorites.discard(event_id)
    session['favorites'] = list(favorites)


def is_favorited(session, event_id: int) -> bool:
    """Check if an event is favorited."""
    return event_id in get_favorites(session)


# Analytics tracking helpers
def get_session_id(session) -> str:
    """Get or create a session ID for analytics tracking."""
    if 'analytics_session_id' not in session:
        import uuid
        session['analytics_session_id'] = str(uuid.uuid4())
    return session['analytics_session_id']


def track_page_view(request, session, path: Optional[str] = None):
    """Track a page view if analytics is enabled."""
    if not config.ENABLE_ANALYTICS or not state.analytics:
        return

    try:
        session_id = get_session_id(session)
        page_path = path or str(request.url.path)
        referrer = request.headers.get('referer')
        user_agent = request.headers.get('user-agent')

        # Get IP address (handle proxies)
        ip_address = request.headers.get('x-forwarded-for', request.client.host).split(',')[0].strip()

        state.analytics.track_page_view(
            session_id=session_id,
            path=page_path,
            referrer=referrer,
            user_agent=user_agent,
            ip_address=ip_address
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking page view: {e}")


@asynccontextmanager
async def lifespan(app):
    """Manage application lifecycle - startup and shutdown."""
    # Startup: Initialize database and search
    state.db = Database(config.DATABASE_PATH)
    state.search = EventSearch(state.db)

    # Initialize analytics if enabled
    if config.ENABLE_ANALYTICS:
        state.analytics = Analytics(config.ANALYTICS_DB_PATH)

    yield

    # Shutdown: Clean up resources (Database uses context managers, no explicit close needed)
    pass


# Initialize FastHTML app with lifespan
# Note: All CSS/JS includes are in page_head() to avoid duplication
app, rt = fast_app(
    live=config.DEBUG,
    lifespan=lifespan,
    session_cookie='la_events_session',
    secret_key=config.SESSION_SECRET_KEY
)

# Setup analytics routes
from src.web.analytics_routes import setup_analytics_routes
setup_analytics_routes(app, rt, state)


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
        # HTMX Extensions
        Script(src='https://unpkg.com/htmx.org@2.0.3/dist/ext/loading-states.js'),
        Script(src='https://unpkg.com/htmx.org@2.0.3/dist/ext/debug.js') if config.DEBUG else None,
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
        Script(src='/static/js/map.js', defer=True),
        # Analytics tracking (if enabled)
        Script(src='/static/js/analytics.js', defer=True) if config.ENABLE_ANALYTICS else None,
        # Filter collapse/expand functionality with state persistence
        Script('''
            // Get saved collapse state from localStorage (defaults to expanded/open)
            function getCollapseState(sectionId) {
                const saved = localStorage.getItem('filter_collapse_' + sectionId);
                // Default to expanded if no saved state
                if (saved === null) return true;
                return saved === 'expanded';
            }

            // Save collapse state to localStorage
            function saveCollapseState(sectionId, isExpanded) {
                localStorage.setItem('filter_collapse_' + sectionId, isExpanded ? 'expanded' : 'collapsed');
            }

            // Toggle filter section and save state
            function toggleFilterSection(sectionId) {
                const content = document.getElementById(sectionId + '-content');
                const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);
                const icon = button.querySelector('.collapse-icon');

                if (content.style.display === 'none' || content.style.display === '') {
                    content.style.display = 'flex';
                    button.setAttribute('aria-expanded', 'true');
                    icon.textContent = '▼';
                    saveCollapseState(sectionId, true);
                } else {
                    content.style.display = 'none';
                    button.setAttribute('aria-expanded', 'false');
                    icon.textContent = '▶';
                    saveCollapseState(sectionId, false);
                }
            }

            // Restore collapse states on page load and after HTMX swaps
            function restoreCollapseStates() {
                console.log('Restoring collapse states...');
                ['categories', 'sources'].forEach(sectionId => {
                    const content = document.getElementById(sectionId + '-content');
                    const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);

                    if (content && button) {
                        const isExpanded = getCollapseState(sectionId);
                        const icon = button.querySelector('.collapse-icon');
                        console.log(`Section ${sectionId}: isExpanded=${isExpanded}`);

                        if (isExpanded) {
                            content.style.display = 'flex';
                            button.setAttribute('aria-expanded', 'true');
                            if (icon) icon.textContent = '▼';
                        } else {
                            content.style.display = 'none';
                            button.setAttribute('aria-expanded', 'false');
                            if (icon) icon.textContent = '▶';
                        }
                    } else {
                        console.log(`Section ${sectionId}: NOT FOUND (content=${!!content}, button=${!!button})`);
                    }
                });
            }

            // Restore states on initial page load
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOMContentLoaded - restoring states');
                restoreCollapseStates();
            });

            // Restore states after HTMX swaps (when filters update)
            document.body.addEventListener('htmx:afterSwap', function(event) {
                console.log('htmx:afterSwap event fired', event.detail);
                // Restore states after any swap that might affect filter-tallies
                // Use longer setTimeout to ensure DOM is fully updated
                setTimeout(restoreCollapseStates, 100);
            });

            // Also listen for OOB (out-of-band) swaps specifically
            document.body.addEventListener('htmx:oobAfterSwap', function(event) {
                console.log('htmx:oobAfterSwap event fired', event.detail);
                if (event.detail.target && event.detail.target.id === 'filter-tallies') {
                    setTimeout(restoreCollapseStates, 100);
                }
            });
        ''')
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
                A('Sisyphe.ai', href='https://ccrma.stanford.edu/~slegroux/', target='_blank', rel='noopener noreferrer')
            ),
            cls='container'
        )
    )


def htmx_loading_indicator():
    """Global HTMX loading indicator shown during async operations."""
    return Div(
        Div(
            Div(cls='spinner'),
            P('Loading...', style='margin-top: 0.5rem; color: #64748b; font-weight: 500;'),
            cls='loading-content'
        ),
        id='loading-indicator',
        cls='htmx-indicator',
        style='''
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 0.75rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            z-index: 9999;
            display: none;
        '''
    )


def favorite_button(event_id: int, is_fav: bool = False):
    """Component to render a favorite/unfavorite button with HTMX."""
    if is_fav:
        return Button(
            '♥',
            cls='favorite-btn favorited',
            hx_delete=f'/favorites/remove/{event_id}',
            hx_swap='outerHTML',
            hx_target='this',
            title='Remove from favorites'
        )
    else:
        return Button(
            '♡',
            cls='favorite-btn',
            hx_post=f'/favorites/add/{event_id}',
            hx_swap='outerHTML',
            hx_target='this',
            title='Add to favorites'
        )


def event_card(event: Event, session=None):
    """Component to render a single event card."""
    event_date_str = event.event_date.strftime("%a, %b %d, %Y at %I:%M %p") if event.event_date else "Date TBA"

    # Check if event is favorited
    is_fav = is_favorited(session, event.id) if session else False

    # Source logo element - clickable, pointing to original event URL
    source_display = A(
        Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo') if event.source_logo_url else Span(event.source, cls='event-source'),
        href=event.url,
        target='_blank',
        rel='noopener noreferrer',
        cls='event-source-link',
        title=f'View on {event.source}'
    ) if event.url else (
        Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo') if event.source_logo_url else Span(event.source, cls='event-source')
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
    else:
        # Default when no price information is available
        price_display = Span('$TBD', cls='event-price price-tbd')

    return Div(
        # Make image clickable
        A(
            Img(src=event.image_url, alt=event.title, cls='event-image'),
            href=f'/event/{event.id}'
        ) if event.image_url else None,
        Div(
            # Make title clickable with favorite button
            Div(
                Div(
                    A(
                        H2(event.title, cls='event-title'),
                        href=f'/event/{event.id}',
                        style='text-decoration: none; color: inherit;'
                    ),
                    cls='event-title-wrapper'
                ),
                favorite_button(event.id, is_fav),
                price_display,
                cls='event-header'
            ) if (price_display or session) else A(
                H2(event.title, cls='event-title'),
                href=f'/event/{event.id}',
                style='text-decoration: none; color: inherit;'
            ),
            Div(f'📅 {event_date_str}', cls='event-date'),
            Div(f'📍 {event.venue_name}', cls='event-location') if event.venue_name else None,
            P(event.description, cls='event-description') if event.description else None,
            Div(
                A(
                    event.category,
                    cls='event-category event-category-filter',
                    hx_get=f'/filters/category/{event.category}',
                    hx_target='#events-container',
                    hx_indicator='#loading-indicator',
                    hx_swap='innerHTML',
                    href='#',
                    **{
                        'data-category': event.category
                    }
                ),
                A('📅', href=f'/event/{event.id}/calendar', cls='calendar-link-icon', title='Add to Calendar'),
                source_display,
                cls='event-footer'
            ),
            cls='event-content'
        ),
        cls='event-card',
        **{'data-event-id': str(event.id)}
    )


def events_list(events: List[Event], session=None):
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
        Div(*[event_card(e, session) for e in events], cls='events-grid'),
    )


@rt('/')
def home_page(request, session):
    """Home page with search and map."""
    # Track page view
    track_page_view(request, session, '/')

    # Get initial events - default to "upcoming"
    initial_events = state.search.search(date_filter='upcoming', limit=100)

    return Html(
        page_head('Westside LA Events'),
        Body(
            page_header(),
            # Two-column layout wrapper
            Div(
                Div(
                    # Left Sidebar - Search and Filters
                    Div(
                        search_section(),
                        cls='sidebar'
                    ),

                    # Right Main Content Area
                    Div(
                        # View Toggle
                        Div(
                            Button('List View', type='button', id='list-view-btn', cls='view-btn active',
                                   hx_get='/view/list',
                                   hx_target='#view-container',
                                   hx_swap='innerHTML'),
                            Button('Map View', type='button', id='map-view-btn', cls='view-btn',
                                   hx_get='/view/map',
                                   hx_target='#view-container',
                                   hx_swap='innerHTML'),
                            cls='view-toggle',
                            id='view-toggle'
                        ),

                        # View Container (holds either list or map)
                        Div(
                            # Map Container (hidden by default)
                            Div(id='map', style='display: none;'),
                            # Events Grid - Now with server-rendered content
                            Div(events_list(initial_events, session), id='events-container'),
                            id='view-container'
                        ),

                        cls='main-content'
                    ),

                    cls='layout-grid'
                ),
                cls='container'
            ),
            # Global HTMX loading indicator
            htmx_loading_indicator(),
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

            # Apply Westside geographic filtering if enabled
            if config.ENABLE_GEOGRAPHIC_FILTERING:
                base_conditions.append(f"latitude >= {config.WESTSIDE_BOUNDS['min_lat']}")
                base_conditions.append(f"latitude <= {config.WESTSIDE_BOUNDS['max_lat']}")
                base_conditions.append(f"longitude >= {config.WESTSIDE_BOUNDS['min_lng']}")
                base_conditions.append(f"longitude <= {config.WESTSIDE_BOUNDS['max_lng']}")

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
                conditions.append("date(event_date) = date('now', 'localtime')")
            elif date_filter == 'tomorrow':
                conditions.append("date(event_date) = date('now', 'localtime', '+1 day')")
            elif date_filter == 'this_week':
                conditions.append("event_date >= date('now', 'localtime') AND event_date < date('now', 'localtime', 'weekday 0', '+7 days')")
            elif date_filter == 'this_weekend':
                conditions.append("date(event_date) IN (date('now', 'localtime', 'weekday 6'), date('now', 'localtime', 'weekday 0', '+7 days'))")
            elif date_filter == 'this_month':
                conditions.append("strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now', 'localtime')")
            else:  # upcoming or default
                conditions.append("event_date >= datetime('now', 'localtime')")

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
                free_conditions.append("date(event_date) = date('now', 'localtime')")
            elif date_filter == 'this_week':
                free_conditions.append("event_date >= date('now', 'localtime') AND event_date < date('now', 'localtime', 'weekday 0', '+7 days')")
            elif date_filter == 'this_weekend':
                free_conditions.append("date(event_date) IN (date('now', 'localtime', 'weekday 6'), date('now', 'localtime', 'weekday 0', '+7 days'))")
            elif date_filter == 'this_month':
                free_conditions.append("strftime('%Y-%m', event_date) = strftime('%Y-%m', 'now', 'localtime')")
            else:
                free_conditions.append("event_date >= datetime('now', 'localtime')")

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


def filter_section_collapsible(section_id: str, label: str, checkboxes_content, collapsed: bool = False, total_count: int = 0, selected_count: int = 0):
    """Render a collapsible filter section (open by default) with summary info.

    Args:
        section_id: ID for the collapsible section
        label: Label text (e.g., "Categories", "Sources")
        checkboxes_content: List of checkbox elements
        collapsed: Whether section is collapsed by default
        total_count: Total number of filter options available (e.g., number of categories)
        selected_count: Number of events in the selected filters
    """
    # Build summary text
    if selected_count > 0:
        # Show event count when filters are selected
        event_text = "event" if selected_count == 1 else "events"
        summary = f"({selected_count} {event_text})"
    else:
        # Show number of available options when nothing is selected
        option_text = "option" if total_count == 1 else "options"
        summary = f"({total_count} {option_text})"

    return Div(
        Div(
            Label(
                Span(label, cls='filter-section-title'),
                Span(summary, cls='filter-count'),
                cls='filter-section-label'
            ),
            Button(
                Span('▼' if not collapsed else '▶', cls='collapse-icon'),
                type='button',
                cls='collapse-toggle',
                onclick=f"toggleFilterSection('{section_id}')",
                **{'aria-expanded': 'true' if not collapsed else 'false', 'aria-controls': f'{section_id}-content'}
            ),
            cls='filter-header-collapsible'
        ),
        Div(
            *checkboxes_content,
            cls='category-checkboxes',
            id=f'{section_id}-content',
            style='' if not collapsed else 'display: none;'
        ),
        cls='filter-group category-filter-group',
        id=f'filter-section-{section_id}'
    )


def filter_tallies_section(date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', favorites_only: str = ''):
    """Render the category and source filter checkboxes with counts - always visible."""
    available_categories, available_sources, free_events_count = _get_filter_tallies(date_filter, category, source, free_only, specific_date)

    # For HTMX requests that update tallies, we also need to preserve the checked state
    # We'll use the provided category/source lists to determine which boxes should be checked
    checked_categories = set(category) if category else set()
    checked_sources = set(source) if source else set()

    # Build category checkboxes - only show categories with events (count > 0)
    category_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='category',
                value=cat,
                checked=True if cat in checked_categories else False,
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='change',
                hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"], [name="specific_date"]',
                hx_indicator='#loading-indicator'
            ),
            f' {cat} ({available_categories.get(cat, 0)})',
            cls='category-checkbox-label',
            **{'data-category': cat}
        )
        for cat in config.CATEGORIES
        if available_categories.get(cat, 0) > 0  # Only show categories with events
    ]

    # Build source checkboxes
    source_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='source',
                value=source_name,
                checked=True if source_name in checked_sources else False,
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='change',
                hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"], [name="specific_date"]',
                hx_indicator='#loading-indicator'
            ),
            f' {source_name} ({count})',
            cls='source-checkbox-label'
        )
        for source_name, count in available_sources
    ] if available_sources else []

    # Calculate counts for summary info
    # For categories: show total number of visible category options (those with events > 0) vs number of events in selected categories
    total_categories = len(category_checkboxes)  # Use actual number of visible categories
    selected_categories_event_count = sum(available_categories.get(cat, 0) for cat in checked_categories) if checked_categories else 0

    # For sources: show total number of source options vs number of events in selected sources
    total_sources = len(available_sources)
    selected_sources_event_count = sum(count for source_name, count in available_sources if source_name in checked_sources) if checked_sources else 0

    return Div(
        # Free events checkbox with tally - moved to top
        Div(
            Label(
                Input(
                    type='checkbox',
                    id='free-only-checkbox',
                    name='free_only',
                    value='true',
                    checked=True if free_only == 'true' else False,
                    hx_get='/filters/update-all',
                    hx_target='#events-container',
                    hx_trigger='change',
                    hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="favorites_only"], [name="specific_date"]',
                    hx_indicator='#loading-indicator'
                ),
                f' Free Events Only ({free_events_count})',
                for_='free-only-checkbox',
                cls='checkbox-label free-events-checkbox'
            ),
            cls='filter-group checkbox-filter',
        ),
        # Favorites only checkbox
        Div(
            Label(
                Input(
                    type='checkbox',
                    id='favorites-only-checkbox',
                    name='favorites_only',
                    value='true',
                    checked=True if favorites_only == 'true' else False,
                    hx_get='/filters/update-all',
                    hx_target='#events-container',
                    hx_trigger='change',
                    hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="specific_date"]',
                    hx_indicator='#loading-indicator'
                ),
                ' My Favorites Only',
                for_='favorites-only-checkbox',
                cls='checkbox-label favorites-checkbox'
            ),
            cls='filter-group checkbox-filter',
        ),
        # Categories filter - collapsible (open by default) with summary
        filter_section_collapsible('categories', 'Categories', category_checkboxes, collapsed=False, total_count=total_categories, selected_count=selected_categories_event_count),
        # Sources filter - collapsible (open by default) with summary
        filter_section_collapsible('sources', 'Sources', source_checkboxes, collapsed=False, total_count=total_sources, selected_count=selected_sources_event_count) if source_checkboxes else None,
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
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='keyup changed delay:500ms, search',
                hx_include='[name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"], [name="specific_date"]',
                hx_indicator='#loading-indicator',
                hx_ext='loading-states',
                **{'data-loading-class': 'htmx-request'}
            ),
            Button('Search', type='submit',
                   hx_get='/filters/update-all',
                   hx_target='#events-container',
                   hx_include='[name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"], [name="specific_date"]',
                   hx_indicator='#loading-indicator',
                   hx_ext='loading-states',
                   **{'data-loading-disable': 'true'}),
            cls='search-box'
        ),
        Div(
            # Primary filters row (Date and Date Picker)
            Div(
                Div(
                    Label('When', for_='date-filter'),
                    Select(
                        Option('Upcoming', value='upcoming', selected=True),
                        Option('Today', value='today'),
                        Option('Tomorrow', value='tomorrow'),
                        Option('This Week', value='this_week'),
                        Option('This Weekend', value='this_weekend'),
                        Option('This Month', value='this_month'),
                        Option('Specific Date', value='specific_date'),
                        id='date-filter',
                        name='date_filter',
                        hx_get='/filters/update-all',
                        hx_target='#events-container',
                        hx_trigger='change',
                        hx_include='this, [name="q"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"], [name="specific_date"]',
                        hx_indicator='#loading-indicator'
                    ),
                    cls='filter-group'
                ),
                # Date picker container - populated dynamically by HTMX
                Div(id='date-picker-container', cls='filter-group calendar-filter'),
                cls='filters-primary-row'
            ),
            # Filter tallies section that will be dynamically updated
            filter_tallies_section(),
            cls='filters'
        ),
        cls='search-section',
        hx_get='/filters/update-all',
        hx_target='#events-container',
        hx_trigger='submit'
    )


def _fetch_events(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', favorites_only: str = '', session=None, limit: int = 100) -> List[Event]:
    """
    Helper function to fetch events with consistent filter-building logic.

    Args:
        q: Search query string
        date_filter: Date filter (upcoming, today, this_week, etc.)
        category: List of category filters (from multiple checkboxes)
        source: List of source filters (from multiple checkboxes)
        free_only: Free events filter ('true' or empty string)
        specific_date: Specific date in YYYY-MM-DD format (when date_filter is 'specific_date')
        favorites_only: Show favorites only ('true' or empty string)
        session: Session object for accessing favorites
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

    # Fetch events based on filters
    events = []
    if date_filter == 'specific_date' and specific_date:
        from datetime import datetime, timedelta
        try:
            # Parse the date and use it as both start and end for that day
            date_obj = datetime.strptime(specific_date, '%Y-%m-%d')
            # Set start to beginning of day and end to beginning of next day
            start = date_obj
            end = date_obj + timedelta(days=1)
            events = state.search.search(
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
            events = state.search.search(
                query=q if q else None,
                date_filter='upcoming',
                categories=categories,
                sources=sources,
                is_free=is_free,
                limit=limit
            )
    else:
        events = state.search.search(
            query=q if q else None,
            date_filter=date_filter if date_filter != 'specific_date' else 'upcoming',
            categories=categories,
            sources=sources,
            is_free=is_free,
            limit=limit
        )

    # Filter by favorites if requested
    if favorites_only == 'true' and session:
        favorite_ids = get_favorites(session)
        events = [e for e in events if e.id in favorite_ids]

    return events


@rt('/events/list')
def get_events_list(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', favorites_only: str = '', session=None):
    """HTMX endpoint to get events list HTML fragment."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml
    events = _fetch_events(q, date_filter, category, source, free_only, specific_date, favorites_only, session)
    # Return just the HTML fragment without full page wrapper
    result = events_list(events, session)
    return HTMLResponse(to_xml(result))


@rt('/filters/tallies')
def get_filter_tallies(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', favorites_only: str = ''):
    """HTMX endpoint to get updated filter tallies HTML fragment."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml
    result = filter_tallies_section(
        date_filter,
        category,
        source,
        free_only,
        specific_date,
        favorites_only
    )
    return HTMLResponse(to_xml(result))


@rt('/filters/date-picker')
def get_date_picker(date_filter: str = 'upcoming'):
    """HTMX endpoint to show/hide date picker based on filter selection."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    if date_filter == 'specific_date':
        result = Div(
            Label('Pick a Date', for_='date-picker'),
            Input(
                type='date',
                id='date-picker',
                name='specific_date',
                hx_get='/filters/update-all',
                hx_trigger='change',
                hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"]',
                hx_indicator='#loading-indicator'
            ),
            id='date-picker-container',
            cls='filter-group calendar-filter'
        )
    else:
        # Return empty container when not specific_date
        result = Div(id='date-picker-container', cls='filter-group calendar-filter')

    return HTMLResponse(to_xml(result))


@rt('/filters/category/{category}')
def filter_by_category(category: str, session):
    """HTMX endpoint to filter by a single category (exclusive selection)."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Fetch events for this category only
    events = _fetch_events(category=[category], session=session)

    # Get filter tallies with this category selected
    tallies_html = filter_tallies_section(
        date_filter='upcoming',
        category=[category],
        source=None,
        free_only='',
        specific_date='',
        favorites_only=''
    )

    # Combine: main target + OOB swap for tallies
    result = Div(
        events_list(events, session),
        Div(tallies_html, id='filter-tallies', hx_swap_oob='true')
    )

    return HTMLResponse(to_xml(result))


@rt('/view/list')
def get_list_view(session):
    """HTMX endpoint to switch to list view."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Get current events based on filters (default to upcoming)
    events = _fetch_events(date_filter='upcoming', session=session)

    result = Div(
        # Map Container (hidden)
        Div(id='map', style='display: none;'),
        # Events list (visible)
        Div(events_list(events, session), id='events-container'),
        # OOB swap to update button states
        Div(
            Button('List View', type='button', id='list-view-btn', cls='view-btn active',
                   hx_get='/view/list',
                   hx_target='#view-container',
                   hx_swap='innerHTML'),
            Button('Map View', type='button', id='map-view-btn', cls='view-btn',
                   hx_get='/view/map',
                   hx_target='#view-container',
                   hx_swap='innerHTML'),
            cls='view-toggle',
            id='view-toggle',
            hx_swap_oob='true'
        )
    )

    return HTMLResponse(to_xml(result))


@rt('/view/map')
def get_map_view(session):
    """HTMX endpoint to switch to map view."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Get current events based on filters (default to upcoming)
    events = _fetch_events(date_filter='upcoming', session=session)

    result = Div(
        # Map Container (visible) - explicit height required for Leaflet
        Div(id='map', style='display: block !important; height: 600px; width: 100%;'),
        # Events list (hidden)
        Div(events_list(events, session), id='events-container', style='display: none;'),
        # OOB swap to update button states
        Div(
            Button('List View', type='button', id='list-view-btn', cls='view-btn',
                   hx_get='/view/list',
                   hx_target='#view-container',
                   hx_swap='innerHTML'),
            Button('Map View', type='button', id='map-view-btn', cls='view-btn active',
                   hx_get='/view/map',
                   hx_target='#view-container',
                   hx_swap='innerHTML'),
            cls='view-toggle',
            id='view-toggle',
            hx_swap_oob='true'
        ),
        # Force trigger map initialization after DOM settles
        Script('''
            (function() {
                var attempts = 0;
                var maxAttempts = 10;

                function tryLoadMap() {
                    attempts++;
                    if (typeof window.loadMapEvents === 'function') {
                        window.loadMapEvents();
                    } else if (attempts < maxAttempts) {
                        setTimeout(tryLoadMap, 100);
                    }
                }

                setTimeout(tryLoadMap, 100);
            })();
        ''')
    )

    return HTMLResponse(to_xml(result))


@rt('/filters/update-all')
def update_all_filters(q: str = '', date_filter: str = 'upcoming', category: List[str] = None, source: List[str] = None, free_only: str = '', specific_date: str = '', favorites_only: str = '', session=None):
    """HTMX endpoint that updates all filter-related sections using OOB swaps."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Get events list
    events = _fetch_events(q, date_filter, category, source, free_only, specific_date, favorites_only, session)

    # Track search
    if config.ENABLE_ANALYTICS and state.analytics:
        try:
            session_id = get_session_id(session)
            state.analytics.track_search(
                session_id=session_id,
                query=q if q else None,
                date_filter=date_filter,
                categories=category,
                sources=source,
                free_only=(free_only == 'true'),
                results_count=len(events)
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking search: {e}")
    events_html = events_list(events, session)

    # Get filter tallies
    tallies_html = filter_tallies_section(date_filter, category, source, free_only, specific_date, favorites_only)

    # Get date picker
    if date_filter == 'specific_date':
        date_picker_html = Div(
            Label('Pick a Date', for_='date-picker'),
            Input(
                type='date',
                id='date-picker',
                name='specific_date',
                value=specific_date if specific_date else '',
                hx_get='/filters/update-all',
                hx_trigger='change',
                hx_include='this, [name="q"], [name="date_filter"], [name="category"], [name="source"], [name="free_only"], [name="favorites_only"]',
                hx_indicator='#loading-indicator'
            ),
            id='date-picker-container',
            cls='filter-group calendar-filter',
            hx_swap_oob='true'
        )
    else:
        date_picker_html = Div(
            id='date-picker-container',
            cls='filter-group calendar-filter',
            hx_swap_oob='true'
        )

    # Combine: main target + OOB swaps
    result = Div(
        events_html,
        Div(tallies_html, id='filter-tallies', hx_swap_oob='true'),
        date_picker_html
    )

    return HTMLResponse(to_xml(result))


@app.post('/favorites/add/{event_id}')
def add_to_favorites(event_id: int, session):
    """Add an event to favorites and return updated favorite button."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Add to session
    add_favorite(session, event_id)

    # Track favorite interaction
    if config.ENABLE_ANALYTICS and state.analytics:
        try:
            session_id = get_session_id(session)
            event = state.db.get_event(event_id)
            if event:
                state.analytics.track_event_interaction(
                    session_id=session_id,
                    event_id=event_id,
                    interaction_type='favorite',
                    source=event.source,
                    category=event.category
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking favorite: {e}")

    # Return the updated button
    button = favorite_button(event_id, is_fav=True)
    return HTMLResponse(to_xml(button))


@app.delete('/favorites/remove/{event_id}')
def remove_from_favorites(event_id: int, session):
    """Remove an event from favorites and return updated favorite button."""
    from starlette.responses import HTMLResponse
    from fastcore.xml import to_xml

    # Remove from session
    remove_favorite(session, event_id)

    # Track unfavorite interaction
    if config.ENABLE_ANALYTICS and state.analytics:
        try:
            session_id = get_session_id(session)
            event = state.db.get_event(event_id)
            if event:
                state.analytics.track_event_interaction(
                    session_id=session_id,
                    event_id=event_id,
                    interaction_type='unfavorite',
                    source=event.source,
                    category=event.category
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking unfavorite: {e}")

    # Return the updated button
    button = favorite_button(event_id, is_fav=False)
    return HTMLResponse(to_xml(button))


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
def event_detail_page(request, session, event_id: int):
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

    # Track event view
    if config.ENABLE_ANALYTICS and state.analytics:
        try:
            session_id = get_session_id(session)
            state.analytics.track_event_interaction(
                session_id=session_id,
                event_id=event.id,
                interaction_type='view',
                source=event.source,
                category=event.category
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking event view: {e}")

    # Track page view
    track_page_view(request, session, f'/event/{event_id}')

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
                                    Span(event.price_note, cls='event-price price-note', style='margin-left: 1rem;') if event.price_note else Span('$TBD', cls='event-price price-tbd', style='margin-left: 1rem;')
                                )
                            ),
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
                                Span(event.category, cls='badge event-category', **{'data-category': event.category})
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
def export_event_calendar(session, event_id: int):
    """Export event as .ics calendar file."""
    from starlette.responses import Response
    import re

    event = state.db.get_event(event_id)
    if not event:
        return Response('Event not found', status_code=404)

    # Track calendar export
    if config.ENABLE_ANALYTICS and state.analytics:
        try:
            session_id = get_session_id(session)
            state.analytics.track_event_interaction(
                session_id=session_id,
                event_id=event_id,
                interaction_type='calendar',
                source=event.source,
                category=event.category
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking calendar export: {e}")

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

    # Handle start date - use event date or current time if missing
    start_dt = event.event_date if event.event_date else datetime.now()
    start_date = format_ical_date(start_dt)

    # Handle end date - use event end_date, or fallback to start + 2 hours
    if event.end_date:
        end_date = format_ical_date(event.end_date)
    else:
        # Use timedelta to handle late-night events (e.g., 11 PM + 2 hours = 1 AM next day)
        end_dt = start_dt + timedelta(hours=2)
        end_date = format_ical_date(end_dt)

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


@app.post('/api/track/click/{event_id}')
def track_event_click(session, event_id: int):
    """Track an external link click (called from client-side JS)."""
    from starlette.responses import JSONResponse

    if not config.ENABLE_ANALYTICS or not state.analytics:
        return JSONResponse({'status': 'analytics_disabled'})

    try:
        event = state.db.get_event(event_id)
        if event:
            session_id = get_session_id(session)
            state.analytics.track_event_interaction(
                session_id=session_id,
                event_id=event_id,
                interaction_type='click',
                source=event.source,
                category=event.category
            )
            return JSONResponse({'status': 'tracked'})
        return JSONResponse({'error': 'Event not found'}, status_code=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking click: {e}")
        return JSONResponse({'error': 'Internal error'}, status_code=500)


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

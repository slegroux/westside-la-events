"""
Main page route for LA Events Aggregator.
"""
from fasthtml.common import *

from src.web.state import track_page_view
from src.web.components import (
    page_head, page_header, page_footer,
    htmx_loading_indicator, top_filter_bar, filter_tallies_section, events_list
)


def setup_routes(rt, state):
    """Register the home page route."""

    @rt('/')
    def home_page(request, session):
        """Home page with search and map."""
        # Track page view
        track_page_view(request, session, '/')

        # Get initial events - default to "upcoming"
        initial_events = state.search.search(date_filter='upcoming', limit=100)

        # Live counts for the header. Cheap two-row query so the count
        # also includes multi-day events that are currently running today.
        with state.db.get_connection() as conn:
            total_count = conn.execute(
                "SELECT COUNT(*) FROM events "
                "WHERE substr(event_date,1,10) >= date('now','localtime')"
            ).fetchone()[0]
            today_count = conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE substr(event_date,1,10) = date('now','localtime')
                   OR (end_date IS NOT NULL
                       AND substr(event_date,1,10) <= date('now','localtime')
                       AND substr(end_date,1,10) >= date('now','localtime'))
            """).fetchone()[0]

        return Html(
            page_head('Westside LA Events'),
            Body(
                page_header(total_count=total_count, today_count=today_count, show_search=True),
                # Mobile filter bottom sheet overlay
                Div(cls='bottom-sheet-overlay', id='bottom-sheet-overlay', onclick='closeFilterSheet()'),
                # Mobile filter FAB button
                Button(
                    Span(NotStr('<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/></svg>'), cls='filter-fab-icon'),
                    ' Filters',
                    cls='filter-fab',
                    onclick='openFilterSheet()',
                    type='button',
                    id='filter-fab'
                ),
                # Page-spanning filter form: keeps every control (top bar AND
                # sidebar) in one <form> so hx_include='closest form' still
                # captures all active filters wherever a control is placed.
                Div(
                    Form(
                        # Primary filters across the top: search + date + categories
                        top_filter_bar(),
                        # Two-column area below the top bar
                        Div(
                            # Left Sidebar - venues + free/favorites (bottom sheet on mobile)
                            Div(
                                Div(cls='bottom-sheet-handle'),
                                Div(
                                    Span('Filters', cls='bottom-sheet-title'),
                                    Button('\u00d7', cls='bottom-sheet-close', onclick='closeFilterSheet()', type='button'),
                                    cls='bottom-sheet-header'
                                ),
                                filter_tallies_section(),
                                cls='sidebar'
                            ),

                            # Right Main Content Area
                            Main(
                                # View Toggle
                                Div(
                                    Button(Span('\u2630', style='margin-right: 0.4rem; font-size: 1.1em;'), 'List', type='button', id='list-view-btn', cls='view-btn active',
                                           hx_get='/view/list',
                                           hx_target='#view-container',
                                           hx_swap='innerHTML',
                                           hx_include='closest form'),
                                    Button(Span('\U0001F5FA', style='margin-right: 0.4rem; font-size: 1.1em;'), 'Map', type='button', id='map-view-btn', cls='view-btn',
                                           hx_get='/view/map',
                                           hx_target='#view-container',
                                           hx_swap='innerHTML',
                                           hx_include='closest form'),
                                    cls='view-toggle',
                                    id='view-toggle',
                                    role='tablist',
                                    **{'aria-label': 'View mode'}
                                ),

                                # View Container (holds either list or map)
                                Div(
                                    # Map Container (hidden by default)
                                    Div(id='map', style='display: none;'),
                                    # Events Grid - server-rendered + live-updated by HTMX
                                    Div(
                                        events_list(initial_events, session),
                                        id='events-container',
                                        **{
                                            'data-loading': 'skeleton',
                                            'aria-live': 'polite',
                                            'aria-busy': 'false',
                                        },
                                    ),
                                    id='view-container'
                                ),

                                cls='main-content',
                                id='main-content'
                            ),

                            cls='layout-grid'
                        ),
                        id='filter-form',
                        cls='filter-form',
                        hx_get='/filters/update-all',
                        hx_target='#events-container',
                        hx_trigger='submit',
                        hx_indicator='#loading-indicator',
                        onsubmit='return false;'
                    ),
                    cls='container'
                ),
                # Global HTMX loading indicator (kept for backward compatibility but skeleton is preferred)
                htmx_loading_indicator(),
                # Toast notification container
                Div(id='toast-container'),
                # Scroll-to-top button
                Button('\u2191', cls='scroll-to-top', id='scroll-to-top', onclick='window.scrollTo({top: 0, behavior: "smooth"})', type='button', title='Back to top'),
                page_footer(),
                # Add script to show skeleton during HTMX requests + manage aria state
                Script('''
                    document.body.addEventListener('htmx:beforeRequest', function(event) {
                        const target = event.detail.target;
                        if (target && target.id === 'events-container') {
                            target.setAttribute('aria-busy', 'true');
                        }
                    });
                    document.body.addEventListener('htmx:beforeSwap', function(event) {
                        const target = event.detail.target;
                        if (target && target.id === 'events-container') {
                            const skeleton = `
                                <div style="margin-bottom: 1.5rem; color: var(--text-light); font-size: 1rem; font-weight: 600;">Loading events...</div>
                                <div class="events-grid">
                                    ${'<div class="skeleton-card"><div class="skeleton-image"></div><div class="skeleton-content"><div class="skeleton-title"></div><div class="skeleton-text short"></div><div class="skeleton-text medium"></div><div class="skeleton-footer"><div class="skeleton-badge"></div><div class="skeleton-badge"></div></div></div></div>'.repeat(6)}
                                </div>
                            `;
                            if (target.getAttribute('data-loading') === 'skeleton') {
                                target.innerHTML = skeleton;
                            }
                        }
                    });
                    document.body.addEventListener('htmx:afterSwap', function(event) {
                        const target = event.detail.target;
                        if (target && target.id === 'events-container') {
                            target.setAttribute('aria-busy', 'false');
                        }
                    });
                ''')
            )
        )

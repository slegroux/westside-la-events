"""
Main page route for LA Events Aggregator.
"""
from fasthtml.common import *

from src.web.state import track_page_view
from src.web.components import (
    page_head, page_header, page_footer,
    htmx_loading_indicator, search_section, events_list
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

        return Html(
            page_head('Westside LA Events'),
            Body(
                page_header(),
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
                # Two-column layout wrapper
                Div(
                    Div(
                        # Left Sidebar - Search and Filters (becomes bottom sheet on mobile)
                        Div(
                            # Bottom sheet handle & header (hidden on desktop, shown on mobile)
                            Div(cls='bottom-sheet-handle'),
                            Div(
                                Span('Filters', cls='bottom-sheet-title'),
                                Button('\u00d7', cls='bottom-sheet-close', onclick='closeFilterSheet()', type='button'),
                                cls='bottom-sheet-header'
                            ),
                            search_section(),
                            cls='sidebar'
                        ),

                        # Right Main Content Area
                        Div(
                            # View Toggle
                            Div(
                                Button(Span('\u2630', style='margin-right: 0.4rem; font-size: 1.1em;'), 'List', type='button', id='list-view-btn', cls='view-btn active',
                                       hx_get='/view/list',
                                       hx_target='#view-container',
                                       hx_swap='innerHTML',
                                       hx_include='.search-section'),
                                Button(Span('\U0001F5FA', style='margin-right: 0.4rem; font-size: 1.1em;'), 'Map', type='button', id='map-view-btn', cls='view-btn',
                                       hx_get='/view/map',
                                       hx_target='#view-container',
                                       hx_swap='innerHTML',
                                       hx_include='.search-section'),
                                cls='view-toggle',
                                id='view-toggle'
                            ),

                            # View Container (holds either list or map)
                            Div(
                                # Map Container (hidden by default)
                                Div(id='map', style='display: none;'),
                                # Events Grid - Now with server-rendered content
                                Div(events_list(initial_events, session), id='events-container', **{'data-loading': 'skeleton'}),
                                id='view-container'
                            ),

                            cls='main-content'
                        ),

                        cls='layout-grid'
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
                # Add script to show skeleton during HTMX requests
                Script('''
                    // Show skeleton screens during HTMX requests
                    document.body.addEventListener('htmx:beforeSwap', function(event) {
                        const target = event.detail.target;
                        if (target && target.id === 'events-container') {
                            // Show skeleton while loading
                            const skeleton = `
                                <div style="margin-bottom: 1.5rem; color: var(--text-light); font-size: 1rem; font-weight: 600;">Loading events...</div>
                                <div class="events-grid">
                                    ${'<div class="skeleton-card"><div class="skeleton-image"></div><div class="skeleton-content"><div class="skeleton-title"></div><div class="skeleton-text short"></div><div class="skeleton-text medium"></div><div class="skeleton-footer"><div class="skeleton-badge"></div><div class="skeleton-badge"></div></div></div></div>'.repeat(6)}
                                </div>
                            `;
                            // Only show skeleton if we're not already showing content
                            if (target.getAttribute('data-loading') === 'skeleton') {
                                target.innerHTML = skeleton;
                            }
                        }
                    });
                ''')
            )
        )

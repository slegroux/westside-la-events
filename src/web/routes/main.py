"""
Main page route for LA Events Aggregator.
"""
from fasthtml.common import *
from typing import List

import config
from src.web.state import track_page_view
from src.web.services import _fetch_events
from src.web.components import (
    page_head, page_header, page_footer,
    htmx_loading_indicator, top_filter_bar, filter_tallies_section, events_list,
    region_tabs, home_hero, DATE_FILTERS, TIMES_OF_DAY, REGIONS
)

# A shared link names a whole day range; a specific date needs the date picker,
# which only the HTMX flow renders.
_URL_DATE_FILTERS = {value for value, _ in DATE_FILTERS} - {'specific_date'}


def setup_routes(rt, state):
    """Register the home page route."""

    @rt('/')
    def home_page(
        request,
        session,
        region: str = 'westside',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        time_of_day: List[str] = None,
        free_only: str = '',
        q: str = '',
    ):
        """Home page with search and map.

        Takes the same query parameters as /filters/update-all, so a filtered
        view has a shareable URL, e.g.
        /?date_filter=this_weekend&category=Music&category=Comedy&free_only=true.
        Unknown values are dropped rather than producing an empty page.
        """
        # Track page view
        track_page_view(request, session, '/')

        if region not in {value for value, _ in REGIONS}:
            region = 'westside'
        if date_filter not in _URL_DATE_FILTERS:
            date_filter = 'upcoming'
        category = [c for c in (category or []) if c in config.CATEGORIES] or None
        times = {value for value, _ in TIMES_OF_DAY}
        time_of_day = [t for t in (time_of_day or []) if t in times] or None
        free_only = 'true' if free_only.lower() in ('true', '1', 'on', 'yes') else ''
        q = q.strip()

        # Same query the HTMX filter flow runs, so the counts match.
        initial_events = _fetch_events(
            q, date_filter, category, None, None, free_only, '', '', session,
            time_of_day=time_of_day, region=region,
        )

        # Live counts for the hero. Cheap two-row query so the count
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
            source_count = conn.execute(
                "SELECT COUNT(DISTINCT source) FROM events "
                "WHERE substr(event_date,1,10) >= date('now','localtime')"
            ).fetchone()[0]

        return Html(
            page_head('Westside LA Events'),
            Body(
                # Counts live in the hero on the home page, not the nav bar.
                page_header(show_search=True, q=q),
                # Single filter form (no sidebar): search lives in the header;
                # date, time-of-day, categories, free, and venues sit in the top bar.
                Div(
                    home_hero(total_count=total_count, today_count=today_count,
                              source_count=source_count),
                    Form(
                        # Region tab strip sits above the filters; switching it
                        # re-runs the current search against the other region.
                        region_tabs(active=region),
                        # Primary filters across the top: search + date + categories
                        top_filter_bar(region=region, date_filter=date_filter,
                                       time_of_day=time_of_day, category=category,
                                       free_only=free_only),
                        Main(
                                # The List/Map view toggle now lives top-right in
                                # top_filter_bar(); it targets #view-container below.
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

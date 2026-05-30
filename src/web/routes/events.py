"""
Event-related routes for LA Events Aggregator.
Handles list view, map view, filter updates, JSON API, and calendar download.
"""
from fasthtml.common import *
from starlette.responses import HTMLResponse
from fastcore.xml import to_xml
from typing import List
import logging

import config
from src.web.components import events_list, filter_tallies_section
from src.web.services import _fetch_events
from src.web.state import get_session_id


logger = logging.getLogger(__name__)


def setup_routes(rt, state):
    """Register event-related routes."""

    @rt('/events/list')
    def get_events_list(
        request: Request,
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = '',
        session=None
    ):
        """HTMX endpoint to get events list HTML fragment."""
        events = _fetch_events(q, date_filter, category, source, venue, free_only, specific_date, favorites_only, session)
        # Return just the HTML fragment without full page wrapper
        result = events_list(events, session)
        return HTMLResponse(to_xml(result))

    @rt('/view/list')
    def get_list_view(
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = '',
        session=None
    ):
        """HTMX endpoint to switch to list view."""
        # Get current events based on active filters
        events = _fetch_events(q, date_filter, category, source, venue, free_only, specific_date, favorites_only, session)

        result = Div(
            # Map Container (hidden)
            Div(id='map', style='display: none;'),
            # Events list (visible)
            Div(events_list(events, session), id='events-container'),
            # OOB swap to update button states
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
                id='view-toggle',
                hx_swap_oob='true'
            )
        )

        return HTMLResponse(to_xml(result))

    @rt('/view/map')
    def get_map_view(
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = '',
        session=None
    ):
        """HTMX endpoint to switch to map view."""
        # Get current events based on active filters
        events = _fetch_events(q, date_filter, category, source, venue, free_only, specific_date, favorites_only, session)

        result = Div(
            # Map Container (visible) - explicit height required for Leaflet
            Div(id='map', style='display: block !important; height: 600px; width: 100%;'),
            # Events list (hidden)
            Div(events_list(events, session), id='events-container', style='display: none;'),
            # OOB swap to update button states
            Div(
                Button(Span('\u2630', style='margin-right: 0.4rem; font-size: 1.1em;'), 'List', type='button', id='list-view-btn', cls='view-btn',
                       hx_get='/view/list',
                       hx_target='#view-container',
                       hx_swap='innerHTML',
                       hx_include='.search-section'),
                Button(Span('\U0001F5FA', style='margin-right: 0.4rem; font-size: 1.1em;'), 'Map', type='button', id='map-view-btn', cls='view-btn active',
                       hx_get='/view/map',
                       hx_target='#view-container',
                       hx_swap='innerHTML',
                       hx_include='.search-section'),
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
    def update_all_filters(
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = '',
        session=None
    ):
        """HTMX endpoint that updates all filter-related sections using OOB swaps."""
        logger.info(f"Search query: '{q}', date_filter: {date_filter}, categories: {category}, sources: {source}, venues: {venue}")

        # Get events list
        events = _fetch_events(q, date_filter, category, source, venue, free_only, specific_date, favorites_only, session)
        logger.info(f"Found {len(events)} events for query '{q}'")

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
                logger.error(f"Error tracking search: {e}")

        events_html = events_list(events, session)

        # Get filter tallies
        tallies_html = filter_tallies_section(date_filter, category, source, venue, free_only, specific_date, favorites_only)

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
                    hx_include='closest form',
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

    @rt('/event/{event_id}')
    def get_event_detail(event_id: int, session=None):
        """Event detail page."""
        from src.web.components import page_head, page_header, page_footer
        event = state.db.get_event(event_id)

        if config.ENABLE_ANALYTICS and state.analytics and event:
            try:
                session_id = get_session_id(session)
                state.analytics.track_event_view(
                    session_id=session_id,
                    event_id=event_id,
                    source=event.source,
                    category=event.category
                )
            except Exception:
                pass

        if not event:
            return Title('Event Not Found'), Main(
                page_header(),
                Div(
                    H1('Event Not Found'),
                    P('The event you are looking for does not exist or has been removed.'),
                    A('← Back to events', href='/'),
                    cls='container'
                ),
                page_footer()
            )

        return Title(event.title), Main(
            page_header(),
            Div(
                H1(event.title),
                P(event.venue_name) if event.venue_name else None,
                P(event.address) if event.address else None,
                P(event.description) if event.description else None,
                A('← Back to events', href='/'),
                cls='container event-detail'
            ),
            page_footer()
        )

    @rt('/api/events/{event_id}')
    def get_single_event_json(event_id: int):
        """API endpoint to get a single event as JSON."""
        from starlette.responses import JSONResponse
        event = state.db.get_event(event_id)
        if not event:
            return JSONResponse({'error': 'Event not found'}, status_code=404)
        return JSONResponse(event.to_dict())

    @rt('/api/events')
    def get_events_json(
        request: Request,
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = '',
        limit: int = config.MAP_MAX_EVENTS,
        session=None
    ):
        """API endpoint to get events as JSON (consumed by the map).

        Defaults to a high limit so the map shows every matching event as a pin,
        not just the list view's first page. Bounded by MAP_MAX_EVENTS.
        """
        from starlette.responses import JSONResponse
        limit = max(1, min(limit, config.MAP_MAX_EVENTS))
        events = _fetch_events(q, date_filter, category, source, venue,
                               free_only, specific_date, favorites_only, session, limit=limit)
        return JSONResponse([event.to_dict() for event in events])

    @rt('/api/events/{event_id}/calendar')
    def download_event_calendar(event_id: int, session):
        """API endpoint to download event as .ics calendar file."""
        from starlette.responses import Response
        from src.utils.calendar import generate_ics, get_ics_filename

        # Get the event from database
        event = state.db.get_event(event_id)

        if not event:
            return Response('Event not found', status_code=404)

        # Track calendar download interaction
        if config.ENABLE_ANALYTICS and state.analytics:
            try:
                session_id = get_session_id(session)
                state.analytics.track_event_interaction(
                    session_id=session_id,
                    event_id=event_id,
                    interaction_type='calendar_download',
                    source=event.source,
                    category=event.category
                )
            except Exception as e:
                logger.error(f"Error tracking calendar download: {e}")

        # Generate .ics content
        ics_content = generate_ics(event)

        # Generate filename
        filename = get_ics_filename(event)

        # Return as downloadable file
        return Response(
            content=ics_content,
            media_type='text/calendar',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

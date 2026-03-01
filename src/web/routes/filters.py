"""
Filter-related routes for LA Events Aggregator.
Handles filter tallies, date picker, and category filtering.
"""
from fasthtml.common import *
from starlette.responses import HTMLResponse
from fastcore.xml import to_xml
from typing import List

from src.web.components import filter_tallies_section, events_list
from src.web.services import _fetch_events


def setup_routes(rt, state):
    """Register filter-related routes."""

    @rt('/filters/tallies')
    def get_filter_tallies(
        q: str = '',
        date_filter: str = 'upcoming',
        category: List[str] = None,
        source: List[str] = None,
        venue: List[str] = None,
        free_only: str = '',
        specific_date: str = '',
        favorites_only: str = ''
    ):
        """HTMX endpoint to get updated filter tallies HTML fragment."""
        result = filter_tallies_section(
            date_filter,
            category,
            source,
            venue,
            free_only,
            specific_date,
            favorites_only
        )
        return HTMLResponse(to_xml(result))

    @rt('/filters/date-picker')
    def get_date_picker(date_filter: str = 'upcoming'):
        """HTMX endpoint to show/hide date picker based on filter selection."""
        if date_filter == 'specific_date':
            result = Div(
                Label('Pick a Date', for_='date-picker'),
                Input(
                    type='date',
                    id='date-picker',
                    name='specific_date',
                    hx_get='/filters/update-all',
                    hx_trigger='change',
                    hx_include='closest form',
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

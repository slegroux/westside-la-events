"""
Main FastHTML application for LA Events Aggregator.

This module is the thin orchestrator: it initializes the app and wires up
all route modules. Business logic, components, and state live in separate modules.
"""
from fasthtml.common import *
from contextlib import asynccontextmanager
from typing import Optional
import logging

import config
from src.utils.logging import setup_logging
setup_logging()

from src.data.database import Database
from src.data.analytics import Analytics
from src.search.query import EventSearch

# Import state singleton and helpers (re-exported for backward compatibility)
from src.web.state import (
    AppState,
    state,
    get_favorites,
    add_favorite,
    remove_favorite,
    is_favorited,
    get_session_id,
    track_page_view,
)

# Re-export components for backward compatibility (tests import from src.web.app)
from src.web.components import (
    page_head,
    page_header,
    page_footer,
    htmx_loading_indicator,
    favorite_button,
    event_card,
    skeleton_card,
    skeleton_grid,
    events_list,
    filter_section_collapsible,
    filter_tallies_section,
    search_section,
)

# Re-export services for backward compatibility
from src.web.services import _tally_cache, _TALLY_TTL, _get_filter_tallies, _fetch_events


@asynccontextmanager
async def lifespan(app):
    """Manage application lifecycle - startup and shutdown."""
    # Startup: Initialize database and search (preserve injected test state)
    if state.db is None:
        state.db = Database(config.DATABASE_PATH)
    if state.search is None:
        state.search = EventSearch(state.db)

    # Initialize analytics if enabled
    if config.ENABLE_ANALYTICS and state.analytics is None:
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

# Starlette imports
from starlette.responses import JSONResponse, HTMLResponse


# Setup analytics routes
from src.web.analytics_routes import setup_analytics_routes
setup_analytics_routes(app, rt, state)

# Register route modules
from src.web.routes.main import setup_routes as setup_main
setup_main(rt, state)

from src.web.routes.events import setup_routes as setup_events
setup_events(rt, state)

from src.web.routes.filters import setup_routes as setup_filters
setup_filters(rt, state)

from src.web.routes.favorites import setup_routes as setup_favorites
setup_favorites(rt, state)

from src.web.routes.api import setup_routes as setup_api
setup_api(rt, state)


# Error handlers
async def not_found_handler(request, exc):
    content = str(Html(
        page_head('Page Not Found - Westside LA Events'),
        Body(
            page_header(),
            Main(
                Div(
                    H2('Page Not Found'),
                    P('The page you are looking for does not exist.'),
                    A('\u2190 Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=404)


async def server_error_handler(request, exc):
    logging.getLogger(__name__).error(f'Server error: {exc}', exc_info=True)
    content = str(Html(
        page_head('Server Error - Westside LA Events'),
        Body(
            page_header(),
            Main(
                Div(
                    H2('Something Went Wrong'),
                    P('We encountered an error while processing your request. Please try again later.'),
                    A('\u2190 Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=500)


app.exception_handlers[404] = not_found_handler
app.exception_handlers[500] = server_error_handler


async def general_exception_handler(request, exc):
    logging.getLogger(__name__).error(f'Unhandled exception: {exc}', exc_info=True)
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
                    A('\u2190 Back to Home', href='/', cls='back-link'),
                    cls='container empty-state'
                )
            ),
            page_footer()
        )
    ))
    return HTMLResponse(content=content, status_code=500)


app.exception_handlers[Exception] = general_exception_handler


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'src.web.app:app',
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )

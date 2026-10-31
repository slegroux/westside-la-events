"""
Main FastHTML application for LA Events Aggregator.

This module is the thin orchestrator: it initializes the app and wires up
all route modules. Business logic, components, and state live in separate modules.
"""
from fasthtml.common import *
from typing import Optional
import logging
import os

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


logger = logging.getLogger(__name__)


def _open_events_db():
    """
    Open the events database, from a local copy when DATABASE_LOCAL_DIR is set.

    Returns (database, mirror). mirror is None when reading DATABASE_PATH
    directly, either by configuration or because the first copy failed.
    """
    if not config.DATABASE_LOCAL_DIR:
        return Database(config.DATABASE_PATH), None

    try:
        from src.data.local_mirror import LocalDbMirror
        # prepare=Database applies schema migrations to each copy before it is
        # published, so a published copy is always ready to serve.
        mirror = LocalDbMirror(
            config.DATABASE_PATH, config.DATABASE_LOCAL_DIR, prepare=Database
        )
        local_path = mirror.refresh()
    except Exception as e:
        logger.error(
            f"Could not copy {config.DATABASE_PATH} to local disk ({e}); "
            f"reading it in place instead"
        )
        return Database(config.DATABASE_PATH), None
    logger.info(f"Serving events from local copy {local_path}")
    return Database(local_path), mirror


async def _keep_events_db_fresh(db: Database, mirror, interval: int):
    """Re-copy the events database when the source changes (e.g. daily scrape)."""
    import asyncio
    while True:
        await asyncio.sleep(interval)
        try:
            new_path = await asyncio.to_thread(mirror.refresh)
        except Exception as e:
            logger.warning(f"Events database refresh failed, keeping current copy: {e}")
            continue
        if new_path:
            # Readers open a connection per request from db.db_path, so this
            # moves every reader (search included) to the new copy. The mirror
            # keeps the previous copy on disk for requests already reading it.
            db.db_path = new_path
            _tally_cache.clear()
            logger.info(f"Switched to refreshed events database {new_path}")


async def lifespan(app):
    """Manage application lifecycle - startup and shutdown."""
    import asyncio
    refresh_task = None

    # Startup: Initialize database and search (preserve injected test state)
    if state.db is None:
        state.db, mirror = _open_events_db()
        if mirror is not None and config.DATABASE_REFRESH_SECONDS > 0:
            refresh_task = asyncio.create_task(
                _keep_events_db_fresh(state.db, mirror, config.DATABASE_REFRESH_SECONDS)
            )
    if state.search is None:
        state.search = EventSearch(state.db)

    # Initialize analytics if enabled
    if config.ENABLE_ANALYTICS and state.analytics is None:
        state.analytics = Analytics(config.ANALYTICS_DB_PATH)

    # Surface risky/incomplete configuration as warnings (non-fatal)
    config.validate_config()

    yield

    # Shutdown: Database uses context managers, so only the refresher needs stopping
    if refresh_task is not None:
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
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
from starlette.middleware.base import BaseHTTPMiddleware


class StaticCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith('/static/fonts/'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        elif path.startswith('/static/'):
            response.headers['Cache-Control'] = 'public, max-age=3600'
        return response


app.add_middleware(StaticCacheMiddleware)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security response headers to every response.

    A Content-Security-Policy is intentionally omitted: the UI relies on inline
    handlers and CDN scripts (HTMX/Leaflet from unpkg) that a strict policy
    would break. These headers are safe defaults without that trade-off. HSTS
    is only emitted in production, where traffic is HTTPS.
    """
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        if os.getenv('ENVIRONMENT') == 'production':
            response.headers.setdefault(
                'Strict-Transport-Security', 'max-age=31536000; includeSubDomains'
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)


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

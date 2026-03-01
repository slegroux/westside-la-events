"""
Application state and session helpers for LA Events Aggregator.
"""
from typing import Set, Optional
import os
import config
from src.data.database import Database
from src.data.analytics import Analytics
from src.search.query import EventSearch


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
    # Keep unit/integration tests deterministic and fast.
    if os.getenv('PYTEST_CURRENT_TEST'):
        return

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

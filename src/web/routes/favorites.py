"""
Favorites routes for LA Events Aggregator.
Handles adding and removing events from user favorites.
"""
from fasthtml.common import *
from starlette.responses import HTMLResponse
from fastcore.xml import to_xml
import logging

import config
from src.web.components import favorite_button
from src.web.state import add_favorite, remove_favorite, get_session_id


logger = logging.getLogger(__name__)


def setup_routes(rt, state):
    """Register favorites routes."""

    @rt('/favorites/add/{event_id}')
    def post(event_id: int, session):
        """Add an event to favorites and return updated favorite button."""
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
                logger.error(f"Error tracking favorite: {e}")

        # Return the updated button
        button = favorite_button(event_id, is_fav=True)
        return HTMLResponse(to_xml(button))

    @rt('/favorites/remove/{event_id}')
    def delete(event_id: int, session):
        """Remove an event from favorites and return updated favorite button."""
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
                logger.error(f"Error tracking unfavorite: {e}")

        # Return the updated button
        button = favorite_button(event_id, is_fav=False)
        return HTMLResponse(to_xml(button))

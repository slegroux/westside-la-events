"""
Service layer functions for LA Events Aggregator.
Handles business logic for fetching events and computing filter tallies.
"""
import hashlib
import time
import logging
from typing import List, Optional
from datetime import datetime, timedelta

import config
from src.data.models import Event
from src.web.state import state, get_favorites


logger = logging.getLogger(__name__)


# In-memory TTL cache for filter tallies (avoids 3 GROUP BY queries per HTMX update)
_tally_cache: dict = {}
_TALLY_TTL = 30  # seconds


def _get_filter_tallies(
    date_filter: str = 'upcoming',
    category: List[str] = None,
    source: List[str] = None,
    venue: List[str] = None,
    free_only: str = '',
    specific_date: str = ''
):
    """
    Get category and venue tallies based on current filters.

    This function calculates the count of events for each category and venue,
    taking into account the current date, category, venue, and free_only filters.
    When filtering by category, venue counts reflect only those categories.
    When filtering by venue, category counts reflect only those venues.
    """
    # Check TTL cache before running DB queries
    cache_key = hashlib.md5(
        repr(sorted({
            'date_filter': date_filter,
            'category': sorted(category) if category else [],
            'source': sorted(source) if source else [],
            'venue': sorted(venue) if venue else [],
            'free_only': free_only,
            'specific_date': specific_date,
        }.items())).encode()
    ).hexdigest()

    cached = _tally_cache.get(cache_key)
    if cached and time.time() - cached['ts'] < _TALLY_TTL:
        return cached['value']

    available_venues = []
    available_categories = {}

    try:
        available_categories, available_venues, free_events_count = state.db.get_filter_tallies(
            date_filter=date_filter,
            categories=category,
            sources=source,
            free_only=free_only,
            specific_date=specific_date,
            min_venue_count=3
        )
    except Exception as e:
        logger.error(f"Error getting filter tallies: {e}", exc_info=True)
        free_events_count = 0

    result = (available_categories, available_venues, free_events_count)
    _tally_cache[cache_key] = {'value': result, 'ts': time.time()}
    return result


def _fetch_events(
    q: str = '',
    date_filter: str = 'upcoming',
    category: List[str] = None,
    source: List[str] = None,
    venue: List[str] = None,
    free_only: str = '',
    specific_date: str = '',
    favorites_only: str = '',
    session=None,
    time_of_day: List[str] = None,
    limit: int = 100
) -> List[Event]:
    """
    Helper function to fetch events with consistent filter-building logic.

    Args:
        q: Search query string
        date_filter: Date filter (upcoming, today, this_week, etc.)
        category: List of category filters (from multiple checkboxes)
        source: List of source filters (from multiple checkboxes)
        venue: List of venue name filters (from multiple checkboxes)
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

    # Handle venue filtering - if no venues selected, show all
    venues = venue if venue and len(venue) > 0 else None

    # Convert free_only to boolean
    is_free = True if free_only == 'true' else None

    # Time-of-day buckets (morning/afternoon/evening/night); None = all times
    times_of_day = time_of_day if time_of_day and len(time_of_day) > 0 else None

    # Fetch events based on filters
    events = []
    if date_filter == 'specific_date' and specific_date:
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
                venues=venues,
                is_free=is_free,
                times_of_day=times_of_day,
                limit=limit
            )
        except ValueError:
            # If date parsing fails, fall back to regular date_filter
            events = state.search.search(
                query=q if q else None,
                date_filter='upcoming',
                categories=categories,
                sources=sources,
                venues=venues,
                is_free=is_free,
                times_of_day=times_of_day,
                limit=limit
            )
    else:
        events = state.search.search(
            query=q if q else None,
            date_filter=date_filter if date_filter != 'specific_date' else 'upcoming',
            categories=categories,
            sources=sources,
            venues=venues,
            is_free=is_free,
            times_of_day=times_of_day,
            limit=limit
        )

    # For today/tomorrow filters, adjust multi-day events' display date
    # so exhibitions show "today" instead of their original start date.
    if date_filter in ('today', 'tomorrow') and events:
        now = datetime.now()
        if date_filter == 'today':
            target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        for event in events:
            if event.event_date and event.end_date:
                # Strip tzinfo for safe comparison (all dates are LA local)
                evt_date = event.event_date.replace(tzinfo=None) if hasattr(event.event_date, 'tzinfo') and event.event_date.tzinfo else event.event_date
                if evt_date < target:
                    event.event_date = target
        # Re-sort so adjusted events don't appear before today's events
        def _sort_key(e):
            d = e.event_date if e.event_date else datetime.max
            return d.replace(tzinfo=None) if hasattr(d, 'tzinfo') and d.tzinfo else d
        events.sort(key=_sort_key)

    # Filter by favorites if requested
    if favorites_only == 'true' and session:
        favorite_ids = get_favorites(session)
        events = [e for e in events if e.id in favorite_ids]

    return events

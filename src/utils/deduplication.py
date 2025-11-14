"""
Event deduplication utilities.

This module provides functions to detect and handle duplicate events
from different sources.
"""
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from src.data.models import Event


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity ratio between two strings.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def normalize_title(title: str) -> str:
    """
    Normalize event title for comparison.

    Removes common variations like quotes, extra whitespace, etc.

    Args:
        title: Event title

    Returns:
        Normalized title
    """
    if not title:
        return ""

    # Convert to lowercase
    normalized = title.lower()

    # Remove different types of quotes
    for quote in ['"', "'", '"', '"', "'", "'"]:
        normalized = normalized.replace(quote, "")

    # Remove special characters but keep alphanumeric and spaces
    import re
    normalized = re.sub(r'[^\w\s]', ' ', normalized)

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def normalize_venue(venue: str) -> str:
    """
    Normalize venue name for comparison.

    Args:
        venue: Venue name

    Returns:
        Normalized venue name
    """
    if not venue:
        return ""

    # Convert to lowercase
    normalized = venue.lower()

    # Remove common suffixes
    suffixes = [
        ' - los angeles', ' los angeles', ' la',
        ' theater', ' theatre', ' museum', ' gallery',
        ' center', ' centre'
    ]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def events_are_duplicates(
    event1: Event,
    event2: Event,
    title_threshold: float = 0.85,
    venue_threshold: float = 0.80,
    date_tolerance_hours: int = 24
) -> Tuple[bool, dict]:
    """
    Determine if two events are duplicates.

    Two events are considered duplicates if:
    1. Same URL (exact match) - HIGHEST PRIORITY, checked first
    2. OR (They occur on the same or very close dates AND one of the following):
       a. Titles are highly similar (>= title_threshold)
       b. Titles are somewhat similar (>= 0.7) AND venues match (>= venue_threshold)

    Args:
        event1: First event
        event2: Second event
        title_threshold: Minimum title similarity to consider duplicates (0-1)
        venue_threshold: Minimum venue similarity when combined with title (0-1)
        date_tolerance_hours: How many hours apart events can be (default 24)

    Returns:
        Tuple of (is_duplicate: bool, scores: dict with similarity metrics)
    """
    scores = {
        'title_similarity': 0.0,
        'venue_similarity': 0.0,
        'date_diff_hours': None,
        'same_url': False,
        'same_source': False,
        'match_method': None  # Track which method detected the duplicate
    }

    # PRIORITY 1: Check for exact URL match FIRST (most reliable indicator)
    # This is checked before everything else to avoid expensive comparisons
    if event1.url and event2.url and event1.url.strip() == event2.url.strip():
        scores['same_url'] = True
        scores['same_source'] = event1.source == event2.source
        scores['match_method'] = 'url'
        # Same URL = same event, regardless of source or date
        return True, scores

    # Check if both events have dates
    if not event1.event_date or not event2.event_date:
        return False, scores

    # Calculate date difference
    # Handle timezone-aware vs naive datetimes
    try:
        date_diff = abs((event1.event_date - event2.event_date).total_seconds() / 3600)
    except TypeError:
        # If one is naive and one is aware, convert both to naive
        date1 = event1.event_date.replace(tzinfo=None) if event1.event_date.tzinfo else event1.event_date
        date2 = event2.event_date.replace(tzinfo=None) if event2.event_date.tzinfo else event2.event_date
        date_diff = abs((date1 - date2).total_seconds() / 3600)

    scores['date_diff_hours'] = date_diff

    # Must be within date tolerance
    if date_diff > date_tolerance_hours:
        return False, scores

    # Check if same source (we don't dedupe within same source for non-URL matches)
    scores['same_source'] = event1.source == event2.source
    if scores['same_source']:
        return False, scores

    # PRIORITY 2: Calculate title similarity
    title1 = normalize_title(event1.title)
    title2 = normalize_title(event2.title)
    scores['title_similarity'] = calculate_similarity(title1, title2)

    # Calculate venue similarity if both have venues
    if event1.venue_name and event2.venue_name:
        venue1 = normalize_venue(event1.venue_name)
        venue2 = normalize_venue(event2.venue_name)
        scores['venue_similarity'] = calculate_similarity(venue1, venue2)

    # Decision logic:
    # 1. Very similar titles = duplicate
    if scores['title_similarity'] >= title_threshold:
        scores['match_method'] = 'title'
        return True, scores

    # 2. Somewhat similar titles + matching venues = duplicate
    if scores['title_similarity'] >= 0.7 and scores['venue_similarity'] >= venue_threshold:
        scores['match_method'] = 'title_venue'
        return True, scores

    return False, scores


def find_duplicate(
    event: Event,
    existing_events: List[Event],
    title_threshold: float = 0.85,
    venue_threshold: float = 0.80,
    date_tolerance_hours: int = 24
) -> Optional[Tuple[Event, dict]]:
    """
    Find if an event is a duplicate of any in the existing list.

    Args:
        event: Event to check
        existing_events: List of existing events to check against
        title_threshold: Minimum title similarity threshold
        venue_threshold: Minimum venue similarity threshold
        date_tolerance_hours: Date tolerance in hours

    Returns:
        Tuple of (duplicate_event, scores) if found, None otherwise
    """
    for existing in existing_events:
        is_dup, scores = events_are_duplicates(
            event, existing,
            title_threshold=title_threshold,
            venue_threshold=venue_threshold,
            date_tolerance_hours=date_tolerance_hours
        )
        if is_dup:
            return existing, scores

    return None


def merge_event_data(primary: Event, secondary: Event) -> Event:
    """
    Merge data from two duplicate events, preferring non-empty values.

    The primary event is kept as the base, but missing fields are filled
    from the secondary event.

    Args:
        primary: Primary event (will be updated)
        secondary: Secondary event (source of additional data)

    Returns:
        Merged event
    """
    # Keep primary's ID and source
    merged = Event(
        id=primary.id,
        title=primary.title or secondary.title,
        description=primary.description or secondary.description,
        venue_name=primary.venue_name or secondary.venue_name,
        address=primary.address or secondary.address,
        latitude=primary.latitude if primary.latitude is not None else secondary.latitude,
        longitude=primary.longitude if primary.longitude is not None else secondary.longitude,
        event_date=primary.event_date or secondary.event_date,
        end_date=primary.end_date or secondary.end_date,
        category=primary.category or secondary.category,
        source=primary.source,  # Keep primary source
        url=primary.url or secondary.url,
        image_url=primary.image_url or secondary.image_url,
        source_logo_url=primary.source_logo_url or secondary.source_logo_url,
        price=secondary.price if secondary.price is not None else primary.price,
        is_free=secondary.is_free if secondary.is_free is not None else primary.is_free,
        price_note=secondary.price_note,  # Always use secondary's price_note (may be empty to clear old value)
        created_at=primary.created_at,
        updated_at=datetime.now()
    )

    # Prefer longer description
    if secondary.description and len(secondary.description) > len(primary.description or ""):
        merged.description = secondary.description

    return merged

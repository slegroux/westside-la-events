"""
Date helpers shared by scrapers.

Sources routinely publish a month and day with no year ("Saturday, November
22"). Guessing that year wrongly is how past listings get resurrected as
future events, so the helpers here resolve it from evidence -- chiefly the
weekday the source names, which acts as a checksum -- and return None rather
than guess when the evidence doesn't settle it.
"""
import re
from datetime import datetime
from typing import Optional

WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}

_WEEKDAY_RE = re.compile(r'\b(' + '|'.join(WEEKDAYS) + r')s?\b', re.IGNORECASE)

# How far into the past a date may fall and still be treated as current rather
# than as last year's listing.
_PAST_GRACE_DAYS = 2


def named_weekday(text: str) -> Optional[int]:
    """The weekday a listing names, if it names exactly one."""
    if not text:
        return None
    found = {WEEKDAYS[m.group(1).lower()] for m in _WEEKDAY_RE.finditer(text)}
    return found.pop() if len(found) == 1 else None


def resolve_year(month: int, day: int, weekday: Optional[int] = None,
                 hour: int = 0, minute: int = 0,
                 now: Optional[datetime] = None,
                 years_ahead: int = 2) -> Optional[datetime]:
    """Resolve a year-less month/day into a real future datetime.

    When the source names a weekday, only a year whose calendar agrees is
    accepted -- that is what distinguishes "Saturday, November 22" meaning last
    year (a stale post) from this year. With no weekday to check against, a
    date that has already passed is treated as stale rather than rolled
    forward, because rolling it forward invents an event that was never
    scheduled.

    Returns None when nothing can be established.
    """
    now = now or datetime.now()

    # With no weekday to verify against, only the current year may be assumed.
    # Searching later years would silently convert a listing that has already
    # happened into a future event, which is the failure this helper exists to
    # prevent.
    horizon = years_ahead if weekday is not None else 0

    for offset in range(0, horizon + 1):
        year = now.year + offset
        try:
            candidate = datetime(year, month, day, hour, minute)
        except ValueError:
            continue  # e.g. Feb 29 in a non-leap year

        if (now - candidate).days > _PAST_GRACE_DAYS:
            continue

        if weekday is not None and candidate.weekday() != weekday:
            continue

        return candidate

    return None

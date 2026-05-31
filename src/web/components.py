"""
Reusable UI component functions for LA Events Aggregator.
"""
import json
import os
import re
from datetime import datetime
from fasthtml.common import *
from typing import List, Optional
from zoneinfo import ZoneInfo

import config
from src.data.models import Event
from src.web.state import is_favorited


_LA_TZ = ZoneInfo("America/Los_Angeles")


_TRAILING_STATE_ZIP_RE = re.compile(
    r',\s*(California|CA)\s*,?\s*\d{5}(-\d{4})?\s*$'
    r'|,\s*(California|CA)\s*$'
    r'|,\s*\d{5}(-\d{4})?\s*$',
    re.IGNORECASE,
)


def _compact_address(address: str) -> str:
    """Strip trailing US state + zip noise from a display address.

    The full address is still stored on the venue link's data-address
    attribute for the map modal — this just shortens what the card shows
    so a long '…, California, 90094' tail doesn't dominate the row.
    """
    if not address:
        return ''
    cleaned = _TRAILING_STATE_ZIP_RE.sub('', address.strip())
    return cleaned.strip().rstrip(',').strip()


def _compute_asset_version() -> str:
    """Cache-busting token for locally-served static assets (JS/CSS).

    /static is cached for an hour, so a deploy that fixes a script wouldn't
    reach returning visitors until their cache expired. Cloud Run sets
    K_REVISION (unique per deploy), so appending it as ?v= makes each deploy
    serve fresh assets immediately. Locally, fall back to map.js's mtime so
    editing an asset busts its cache too.
    """
    rev = os.getenv('K_REVISION')
    if rev:
        return rev
    try:
        return str(int(os.path.getmtime(config.BASE_DIR / 'static' / 'js' / 'map.js')))
    except OSError:
        return 'dev'


ASSET_VERSION = _compute_asset_version()


def _iso_la(dt: datetime) -> str:
    """Render a stored LA-local datetime as an ISO 8601 string with an LA offset.

    Event datetimes persist naive (see scrapers/base.normalize_event_datetime),
    but schema.org expects an unambiguous offset on startDate/endDate.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LA_TZ)
    return dt.isoformat()


_HTML_TAG_RE = re.compile(r'<[^>]+>')
_WS_COLLAPSE_RE = re.compile(r'\s+')


def _strip_html_to_text(html: str) -> str:
    """Reduce HTML markup in scraped fields to plain text.

    Scrapers occasionally store leftover markup in event.description.
    Plain text only; collapsed whitespace.
    """
    if not html:
        return ''
    text = _HTML_TAG_RE.sub(' ', html)
    return _WS_COLLAPSE_RE.sub(' ', text).strip()


def _safe_json_in_html(payload: dict) -> str:
    """Serialize for embedding inside a <script> tag.

    json.dumps doesn't escape characters that would let a JSON value break
    out of the surrounding HTML context — most notably '<' (which could
    end a <script> early via '</script>'). Apply OWASP's JSON-in-HTML
    escapes so the payload is safe even with adversarial scraper content.
    """
    encoded = json.dumps(payload, ensure_ascii=False)
    return (
        encoded
        .replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
        .replace(' ', '\\u2028')
        .replace(' ', '\\u2029')
    )


def _event_json_ld(event: Event) -> Optional[str]:
    """Build a schema.org Event JSON-LD payload for an event, or None if it
    lacks the required fields (name + startDate + location)."""
    if not event.title or not event.event_date:
        return None
    location_name = event.venue_name or event.address
    if not location_name:
        return None

    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "startDate": _iso_la(event.event_date),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": event.venue_name or location_name,
        },
    }
    if event.end_date:
        data["endDate"] = _iso_la(event.end_date)
    if event.address:
        data["location"]["address"] = event.address
    if event.latitude is not None and event.longitude is not None:
        data["location"]["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": event.latitude,
            "longitude": event.longitude,
        }
    if event.image_url:
        data["image"] = event.image_url
    if event.description:
        data["description"] = _strip_html_to_text(event.description)[:500]
    if event.url:
        data["url"] = event.url

    if event.is_free or event.price is not None:
        offer = {
            "@type": "Offer",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }
        offer["price"] = "0" if event.is_free else f"{event.price:.2f}"
        if event.url:
            offer["url"] = event.url
        data["offers"] = offer

    return _safe_json_in_html(data)


def page_head(title: str, description: Optional[str] = None):
    """Shared page head component with meta tags."""
    default_description = 'Discover the best events, activities, and experiences across LA\'s Westside'
    return Head(
        Title(title),
        Meta(charset='UTF-8'),
        Meta(name='viewport', content='width=device-width, initial-scale=1.0, viewport-fit=cover'),
        Meta(name='description', content=description or default_description),
        Meta(name='keywords', content='LA events, Westside LA, Santa Monica, activities, concerts, art, food'),
        Meta(property='og:title', content=title),
        Meta(property='og:description', content=description or default_description),
        Meta(property='og:type', content='website'),
        # Resource hints for performance - preconnect to external domains
        Link(rel='preconnect', href='https://unpkg.com'),
        Link(rel='dns-prefetch', href='https://unpkg.com'),
        # HTMX for interactive features
        Script(src='https://unpkg.com/htmx.org@2.0.3'),
        # HTMX Extensions
        Script(src='https://unpkg.com/htmx.org@2.0.3/dist/ext/loading-states.js'),
        Script(src='https://unpkg.com/htmx.org@2.0.3/dist/ext/debug.js') if config.DEBUG else None,
        # Leaflet CSS - must be a real stylesheet. A previous rel="preload"
        # optimization rendered as the invalid attribute `as-="style"` (FastHTML
        # turns the `as_` kwarg into `as-`), so the onload swap never fired and
        # the stylesheet never applied — leaving tiles position:static (broken
        # tile grid) and unstyled cluster markers. Load it render-blocking.
        Link(rel='stylesheet', href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
             integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', crossorigin='anonymous'),
        # Leaflet MarkerCluster CSS
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css'),
        Link(rel='stylesheet', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css'),
        # Application CSS
        Link(rel='stylesheet', href=f'/static/css/style.css?v={ASSET_VERSION}'),
        # Leaflet JS - load with defer to ensure proper order
        Script(src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
               integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=', crossorigin='anonymous', defer=True),
        # Leaflet MarkerCluster JS
        Script(src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js', defer=True),
        # Application JavaScript - defer to load after Leaflet
        Script(src=f'/static/js/map.js?v={ASSET_VERSION}', defer=True),
        # Toast notification system
        Script(src=f'/static/js/toast.js?v={ASSET_VERSION}', defer=True),
        # Analytics tracking (if enabled)
        Script(src=f'/static/js/analytics.js?v={ASSET_VERSION}', defer=True) if config.ENABLE_ANALYTICS else None,
        # Filter collapse/expand functionality with state persistence
        Script(src=f'/static/js/filters.js?v={ASSET_VERSION}', defer=True),
    )


def page_header(total_count: Optional[int] = None, today_count: Optional[int] = None,
                show_search: bool = False):
    """Slim sticky nav-style header: wordmark · search · live counter · Tonight.

    Counts are optional — when omitted the counter section is hidden,
    keeping the header usable on routes that don't compute stats.
    """
    counter_parts: list = []
    if total_count is not None:
        counter_parts.extend([
            Span(f'{total_count:,}', cls='header-stat-num'),
            Span('events', cls='header-stat-label'),
        ])
    if today_count is not None and total_count is not None:
        counter_parts.extend([
            Span('·', cls='header-stat-sep', **{'aria-hidden': 'true'}),
            Span(f'{today_count}', cls='header-stat-num'),
            Span('today', cls='header-stat-label'),
        ])
    counter = Div(*counter_parts, cls='header-stats') if counter_parts else None

    tonight = A(
        'Tonight',
        href='#',
        cls='header-tonight',
        onclick=(
            "const sel=document.getElementById('date-filter');"
            "if(sel){sel.value='today';"
            "sel.dispatchEvent(new Event('change',{bubbles:true}));"
            "window.scrollTo({top:0,behavior:'smooth'});}"
            "return false;"
        ),
        title='Show events happening today',
    )

    # Global search lives in the nav bar (find-a-specific-event), keeping the
    # filter bar below as a pure browse zone. It sits outside the filter <form>,
    # so it pulls the active filters in via hx_include='#filter-form'; the in-form
    # controls reciprocate by including '#header-search'.
    search = Div(
        Span(NotStr(_SEARCH_SVG), cls='header-search-icon', **{'aria-hidden': 'true'}),
        Input(
            type='search', id='header-search', name='q',
            placeholder='Search events…',
            hx_get='/filters/update-all', hx_target='#events-container',
            hx_trigger='input changed delay:500ms, search',
            hx_include='#filter-form', hx_indicator='#loading-indicator',
            **{'aria-label': 'Search events'},
        ),
        cls='header-search',
    ) if show_search else None

    return Header(
        Div(
            H1(A('Westside LA Events', href='/'), cls='header-wordmark'),
            search,
            counter,
            tonight,
            cls='header-content container'
        )
    )


def page_footer():
    """Shared page footer component."""
    return Footer(
        Div(
            P('Westside LA Events', cls='footer-title'),
            P('Aggregating events from Santa Monica, Timeout LA, KCRW, and 30+ sources.', cls='footer-sources'),
            P(
                'Made with \u2764 by ',
                A('Sisyphe.ai', href='https://ccrma.stanford.edu/~slegroux/', target='_blank', rel='noopener noreferrer'),
                cls='footer-credit'
            ),
            cls='container'
        )
    )


def htmx_loading_indicator():
    """Global HTMX loading indicator shown during async operations."""
    return Div(
        Div(
            Div(cls='spinner'),
            P('Loading...', style='margin-top: 0.5rem; color: #64748b; font-weight: 500;'),
            cls='loading-content'
        ),
        id='loading-indicator',
        cls='htmx-indicator',
        style='''
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 2rem;
            border-radius: 0.75rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            z-index: 9999;
            display: none;
        '''
    )


def favorite_button(event_id: int, is_fav: bool = False):
    """Component to render a favorite/unfavorite button with HTMX."""
    if is_fav:
        return Button(
            '\u2665',
            cls='favorite-btn favorited',
            hx_delete=f'/favorites/remove/{event_id}',
            hx_swap='outerHTML',
            hx_target='this',
            title='Remove from favorites'
        )
    else:
        return Button(
            '\u2661',
            cls='favorite-btn',
            hx_post=f'/favorites/add/{event_id}',
            hx_swap='outerHTML',
            hx_target='this',
            title='Add to favorites'
        )


def _format_event_time(event: Event) -> str:
    """Return time-of-day for the metadata row (e.g. '7:30 PM').

    Empty string when the event has no event_date or when the stored time
    is exactly midnight — many scrapers use 00:00 as a placeholder for
    date-only events, so showing '12:00 AM' would be misleading.
    """
    dt = event.event_date
    if not dt or (dt.hour == 0 and dt.minute == 0):
        return ""
    return dt.strftime('%-I:%M %p')


# Inline SVG icons (stroke uses currentColor so CSS controls the tint).
# Crisp and identical across platforms, unlike emoji glyphs.
_PIN_SVG = (
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>'
    '<circle cx="12" cy="10" r="3"/></svg>'
)

_SEARCH_SVG = (
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
)


def _event_meta_row(event: Event):
    """Single-line metadata row: '7:30 PM · FREE · 📍 Venue Name'.

    The chip on the image conveys the date; this row carries the rest of
    the at-a-glance facts: time-of-day, price, and the clickable venue.
    """
    # Time now lives in the date chip on the image, so it's omitted here to
    # avoid showing it twice. This row carries price + the clickable venue.
    parts = []

    price = _price_badge(event)
    if price is not None:
        parts.append(price)
    if event.venue_name or event.address:
        # Show the venue name as the primary label and the address as a
        # smaller secondary line. Skip the address line when it just echoes
        # the venue (some scrapers store "Venue Name, City, State" as the
        # address verbatim).
        venue = event.venue_name or ''
        address = event.address or ''
        display_address = _compact_address(address)
        show_address = bool(display_address) and (
            not venue or not display_address.lower().startswith(venue.lower())
        )
        primary = venue or display_address
        place_children = [Span(primary, cls='event-meta-venue')]
        if show_address and venue:
            place_children.append(Span(display_address, cls='event-meta-address'))
        venue_link = A(
            Span(NotStr(_PIN_SVG), cls='event-meta-pin', **{'aria-hidden': 'true'}),
            Span(*place_children, cls='event-meta-place'),
            href='#',
            cls='venue-location-link',
            **{
                'data-venue-name': venue,
                'data-latitude': str(event.latitude) if event.latitude else '',
                'data-longitude': str(event.longitude) if event.longitude else '',
                'data-address': address,
            },
            title=f'View {venue or primary} on map',
        )
        if parts:
            parts.append(Span('·', cls='event-meta-sep', **{'aria-hidden': 'true'}))
        parts.append(venue_link)
    if not parts:
        return None
    return Div(*parts, cls='event-meta-row')


def _format_event_date(event: Event) -> str:
    """Render an event's date for display, collapsing multi-day spans into a range."""
    if not event.event_date:
        return "Date TBA"
    start = event.event_date
    end = event.end_date
    if end and end.date() > start.date():
        # Include the start year only when the span crosses a year boundary,
        # so same-year ranges stay compact ("May 29 – May 30, 2026") while
        # cross-year ranges stay unambiguous ("Dec 29, 2025 – Jan 02, 2026").
        if start.year != end.year:
            return f'{start.strftime("%b %d, %Y")} – {end.strftime("%b %d, %Y")}'
        return f'{start.strftime("%b %d")} – {end.strftime("%b %d, %Y")}'
    return start.strftime("%a, %b %d, %Y at %I:%M %p")


def _date_chip(event: Event):
    """Date pill that sits over the event card image.

    Clicking the chip downloads the .ics file from /api/events/{id}/calendar.
    Keeps its compact inline-flex layout intact — the CSS scopes the
    .event-card-media > a fallback so it doesn't override this anchor.
    """
    if not event.event_date:
        return Div(Span('TBA', cls='event-date-chip-day'), cls='event-date-chip')

    start = event.event_date
    end = event.end_date
    if end and end.date() > start.date():
        # Two-line stack reads better than a compressed 'MAY 30 → NOV 9' pill.
        chip_inner = (
            Span(start.strftime('%b %-d').upper(), cls='event-date-chip-range-line'),
            Span(end.strftime('%b %-d').upper(), cls='event-date-chip-range-line'),
        )
        chip_cls = 'event-date-chip event-date-chip-range'
    else:
        chip_inner = [
            Span(start.strftime('%a').upper(), cls='event-date-chip-dow'),
            Span(start.strftime('%-d'), cls='event-date-chip-day'),
            Span(start.strftime('%b').upper(), cls='event-date-chip-mon'),
        ]
        # Append the start time below the date when one is known (skips the
        # midnight default). The meta row drops time so it isn't shown twice.
        time_str = _format_event_time(event)
        if time_str:
            chip_inner.append(Span(time_str, cls='event-date-chip-time'))
        chip_inner = tuple(chip_inner)
        chip_cls = 'event-date-chip'

    if event.id is not None:
        return A(
            *chip_inner,
            href=f'/api/events/{event.id}/calendar',
            cls=chip_cls,
            title='Add to calendar',
            **{'aria-label': f'Add {event.title or "event"} to calendar'},
        )
    return Div(*chip_inner, cls=chip_cls)


# price_note text patterns that should promote to a FREE badge even when
# is_free=False (some scrapers write 'Free admission' instead of setting the flag).
_FREE_NOTE_PATTERNS = ('free', 'no charge', 'no cost', 'gratis', 'complimentary')


def _is_free_note(note: str) -> bool:
    lower = note.lower()
    # Guard against price_note like 'Free for members, $20 otherwise' which is
    # not really free — only promote when the note is dominated by the keyword.
    if any(p in lower for p in ('$', 'otherwise', 'after', 'except', 'member')):
        return False
    return any(kw in lower for kw in _FREE_NOTE_PATTERNS)


def _price_badge(event: Event):
    """Return the price/FREE Span for an event card, or None to render nothing."""
    if event.is_free:
        return Span('FREE', cls='event-price free-badge')
    if event.price:
        return Span(f'${event.price:.2f}', cls='event-price')
    if event.price_note:
        note = event.price_note.strip()
        if not note or note.upper() == 'TBD':
            return None
        if _is_free_note(note):
            return Span('FREE', cls='event-price free-badge')
        return Span(note, cls='event-price price-note')
    return None


def event_card(event: Event, session=None):
    """Component to render a single event card."""

    # Check if event is favorited
    is_fav = is_favorited(session, event.id) if session else False

    # Source logo element - clickable, pointing to original event URL
    # Wrap logo and label in a container
    if event.url:
        source_display = A(
            Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo', loading='lazy') if event.source_logo_url else None,
            Span(event.source, cls='source-label'),
            href=event.url,
            target='_blank',
            rel='noopener noreferrer',
            cls='event-source-link',
            title=f'View on {event.source}'
        )
    else:
        source_display = Div(
            Img(src=event.source_logo_url, alt=f'{event.source} logo', cls='source-logo', loading='lazy') if event.source_logo_url else None,
            Span(event.source, cls='source-label'),
            cls='event-source-container'
        )

    # Create link attributes for external event URL
    link_attrs = {
        'href': event.url,
        'target': '_blank',
        'rel': 'noopener noreferrer',
        'style': 'text-decoration: none; color: inherit;'
    } if event.url else {
        'style': 'text-decoration: none; color: inherit; cursor: default;'
    }

    # Always render image slot — real image or category-colored placeholder
    img_element = (
        Img(src=event.image_url, alt=event.title, cls='event-image', loading='lazy')
        if event.image_url else
        Div(Span(event.category or 'Event', cls='placeholder-label'),
            cls='event-image-placeholder',
            **{'data-category': event.category or ''})
    )

    json_ld = _event_json_ld(event)
    json_ld_script = (
        Script(NotStr(json_ld), type='application/ld+json')
        if json_ld else None
    )

    return Div(
        json_ld_script,
        Div(
            A(img_element, **link_attrs),
            _date_chip(event),
            cls='event-card-media',
        ),
        Div(
            # Title clickable to event URL; favorite button on the right when
            # there's a session. Price has moved to the metadata row.
            Div(
                Div(
                    A(
                        H2(event.title, cls='event-title'),
                        **link_attrs
                    ),
                    cls='event-title-wrapper'
                ),
                favorite_button(event.id, is_fav),
                cls='event-header'
            ) if session else A(
                H2(event.title, cls='event-title'),
                **link_attrs
            ),
            _event_meta_row(event),
            (A(
                P(event.description, cls='event-description'),
                **link_attrs,
                title='Click to view full event details'
            ) if event.description else None),
            Div(
                Span(
                    event.category,
                    cls='event-category',
                    **{'data-category': event.category}
                ),
                source_display,
                cls='event-footer'
            ),
            cls='event-content'
        ),
        cls='event-card',
        **{'data-event-id': str(event.id), 'data-category': event.category}
    )


def skeleton_card():
    """Component to render a skeleton loading card."""
    return Div(
        Div(cls='skeleton-image'),
        Div(
            Div(cls='skeleton-title'),
            Div(cls='skeleton-text short'),
            Div(cls='skeleton-text medium'),
            Div(
                Div(cls='skeleton-badge'),
                Div(cls='skeleton-badge'),
                cls='skeleton-footer'
            ),
            cls='skeleton-content'
        ),
        cls='skeleton-card'
    )


def skeleton_grid(count: int = 6):
    """Component to render a grid of skeleton cards during loading."""
    return Div(
        Div('Loading events...', style='margin-bottom: 1.5rem; color: var(--text-light); font-size: 1rem; font-weight: 600;'),
        Div(*[skeleton_card() for _ in range(count)], cls='events-grid'),
    )


def _date_bucket(event: Event, today):
    """Return (ordinal, label) for grouping. Lower ordinal sorts earlier."""
    dt = event.event_date
    if not dt:
        return (99, 'Date TBA')
    d = dt.date() if hasattr(dt, 'date') else dt
    diff = (d - today).days
    if diff <= 0:
        return (0, 'Today')
    if diff == 1:
        return (1, 'Tomorrow')
    days_to_sunday = 6 - today.weekday()  # Mon=0 .. Sun=6
    if diff <= days_to_sunday:
        return (2, 'This Week')
    if diff <= days_to_sunday + 7:
        return (3, 'Next Week')
    return (4, 'Later')


def events_list(events: List[Event], session=None):
    """Component to render the events grid."""
    if not events:
        return Div(
            H2('No events found'),
            P('Try adjusting your search filters or check back later for new events.'),
            Span('Tip: Clear all filters to see upcoming events', cls='empty-hint'),
            cls='empty-state'
        )

    count_text = f'Found {len(events)} event{"s" if len(events) != 1 else ""}'
    today = datetime.now(_LA_TZ).date()

    # Group events by date bucket. When everything lands in a single bucket
    # (e.g. a 'today' filter), render flat so we don't show a redundant
    # 'Today' header above its own list.
    groups: dict = {}
    for e in events:
        key = _date_bucket(e, today)
        groups.setdefault(key, []).append(e)

    if len(groups) <= 1:
        return Div(
            Div(count_text, cls='results-header'),
            Div(*[event_card(e, session) for e in events], cls='events-grid'),
        )

    ordered = sorted(groups.items(), key=lambda kv: kv[0][0])
    return Div(
        Div(count_text, cls='results-header'),
        *[
            Div(
                H2(label, cls='date-group-title'),
                Div(*[event_card(e, session) for e in group_events], cls='events-grid'),
                cls='date-group',
            )
            for (_ordinal, label), group_events in ordered
        ],
    )


def filter_section_collapsible(
    section_id: str,
    label: str,
    checkboxes_content,
    collapsed: bool = False,
    total_count: int = 0,
    selected_count: int = 0
):
    """Render a collapsible filter section (open by default) with summary info.

    Args:
        section_id: ID for the collapsible section
        label: Label text (e.g., "Categories", "Sources")
        checkboxes_content: List of checkbox elements
        collapsed: Whether section is collapsed by default
        total_count: Total number of filter options available (e.g., number of categories)
        selected_count: Number of events in the selected filters
    """
    # Build summary text
    if selected_count > 0:
        # Show event count when filters are selected
        event_text = "event" if selected_count == 1 else "events"
        summary = f"({selected_count} {event_text})"
    else:
        # Show number of available options when nothing is selected
        option_text = "option" if total_count == 1 else "options"
        summary = f"({total_count} {option_text})"

    return Div(
        Div(
            Label(
                Span(label, cls='filter-section-title'),
                Span(summary, cls='filter-count'),
                cls='filter-section-label'
            ),
            Button(
                # Always render collapsed icon - JavaScript will fix it immediately based on localStorage
                Span('\u25b6', cls='collapse-icon'),
                type='button',
                cls='collapse-toggle',
                onclick=f"toggleFilterSection('{section_id}')",
                # Always set aria-expanded to false initially - JavaScript will update it
                **{'aria-expanded': 'false', 'aria-controls': f'{section_id}-content'}
            ),
            cls='filter-header-collapsible'
        ),
        Div(
            *checkboxes_content,
            cls='category-checkboxes',
            id=f'{section_id}-content',
            # Don't set inline style - let JavaScript manage display state via localStorage
            # This prevents server-rendered state from overriding user's manual collapse/expand actions
        ),
        cls='filter-group category-filter-group',
        id=f'filter-section-{section_id}'
    )


def filter_tallies_section(
    date_filter: str = 'upcoming',
    category: List[str] = None,
    source: List[str] = None,
    venue: List[str] = None,
    free_only: str = '',
    specific_date: str = '',
    favorites_only: str = ''
):
    """Render the category and venue filter checkboxes with counts - always visible."""
    from src.web.services import _get_filter_tallies
    available_categories, available_venues, free_events_count = _get_filter_tallies(
        date_filter, category, source, venue, free_only, specific_date
    )

    # For HTMX requests that update tallies, we also need to preserve the checked state
    # We'll use the provided category/venue lists to determine which boxes should be checked
    checked_categories = set(category) if category else set()
    checked_venues = set(venue) if venue else set()

    # Build category checkboxes - only show categories with events (count > 0)
    category_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='category',
                value=cat,
                checked=True if cat in checked_categories else False,
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='change',
                hx_include='closest form, #header-search',
                hx_indicator='#loading-indicator'
            ),
            f' {cat}',
            cls='category-checkbox-label',
            **{'data-category': cat}
        )
        for cat in config.CATEGORIES
        if available_categories.get(cat, 0) > 0  # Only show categories with events
    ]

    # Build venue checkboxes - only show venues with events (count >= 3)
    venue_checkboxes = [
        Label(
            Input(
                type='checkbox',
                name='venue',
                value=venue_name,
                checked=True if venue_name in checked_venues else False,
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='change',
                hx_include='closest form, #header-search',
                hx_indicator='#loading-indicator'
            ),
            f' {venue_name} ({count})',
            cls='source-checkbox-label'
        )
        for venue_name, count in available_venues
    ] if available_venues else []

    # Calculate counts for summary info
    # For categories: show total number of visible category options (those with events > 0) vs number of events in selected categories
    total_categories = len(category_checkboxes)  # Use actual number of visible categories
    selected_categories_event_count = sum(available_categories.get(cat, 0) for cat in checked_categories) if checked_categories else 0

    # For venues: show total number of venue options vs number of events in selected venues
    total_venues = len(available_venues)
    selected_venues_event_count = sum(count for venue_name, count in available_venues if venue_name in checked_venues) if checked_venues else 0

    return Div(
        # Free events checkbox with tally - moved to top
        Div(
            Label(
                Input(
                    type='checkbox',
                    id='free-only-checkbox',
                    name='free_only',
                    value='true',
                    checked=True if free_only == 'true' else False,
                    hx_get='/filters/update-all',
                    hx_target='#events-container',
                    hx_trigger='change',
                    hx_include='closest form, #header-search',
                    hx_indicator='#loading-indicator'
                ),
                f' Free Events Only ({free_events_count})',
                for_='free-only-checkbox',
                cls='checkbox-label free-events-checkbox'
            ),
            cls='filter-group checkbox-filter',
        ),
        # Favorites only checkbox
        Div(
            Label(
                Input(
                    type='checkbox',
                    id='favorites-only-checkbox',
                    name='favorites_only',
                    value='true',
                    checked=True if favorites_only == 'true' else False,
                    hx_get='/filters/update-all',
                    hx_target='#events-container',
                    hx_trigger='change',
                    hx_include='closest form, #header-search',
                    hx_indicator='#loading-indicator'
                ),
                ' My Favorites Only',
                for_='favorites-only-checkbox',
                cls='checkbox-label favorites-checkbox'
            ),
            cls='filter-group checkbox-filter',
        ),
        # Categories now live in the top filter bar (see category_filter_bar).
        # Venues filter - collapsible (state managed by JavaScript/localStorage) with summary
        filter_section_collapsible('venues', 'Venues', venue_checkboxes, collapsed=True, total_count=total_venues, selected_count=selected_venues_event_count) if venue_checkboxes else None,
        id='filter-tallies'
    )


def category_filter_bar(
    date_filter: str = 'upcoming',
    category: List[str] = None,
    source: List[str] = None,
    venue: List[str] = None,
    free_only: str = '',
    specific_date: str = '',
    favorites_only: str = '',
    oob: bool = False
):
    """Horizontal category pill row for the top filter bar.

    Pass oob=True when returning it from /filters/update-all so HTMX swaps the
    live #category-filter-bar in place (keeps the counts current).
    """
    from src.web.services import _get_filter_tallies
    available_categories, _venues, _free = _get_filter_tallies(
        date_filter, category, source, venue, free_only, specific_date
    )
    checked_categories = set(category) if category else set()
    pills = [
        Label(
            Input(
                type='checkbox', name='category', value=cat,
                checked=True if cat in checked_categories else False,
                hx_get='/filters/update-all', hx_target='#events-container',
                hx_trigger='change', hx_include='closest form, #header-search',
                hx_indicator='#loading-indicator'
            ),
            f' {cat}',
            cls='category-checkbox-label',
            **{'data-category': cat}
        )
        for cat in config.CATEGORIES
        if available_categories.get(cat, 0) > 0
    ]
    attrs = {'id': 'category-filter-bar', 'cls': 'category-filter-bar'}
    if oob:
        attrs['hx_swap_oob'] = 'true'
    return Div(*pills, **attrs)


def top_filter_bar():
    """Primary filter bar above the results: search + date + category pills.

    Lives inside the page-spanning filter <form> (see the home route) so every
    control still shares one form for `hx_include='closest form, #header-search'`.
    """
    return Div(
        Div(
            Div(
                Label('When', for_='date-filter'),
                Select(
                    Option('Upcoming', value='upcoming', selected=True),
                    Option('Today', value='today'),
                    Option('Tomorrow', value='tomorrow'),
                    Option('This Week', value='this_week'),
                    Option('This Weekend', value='this_weekend'),
                    Option('This Month', value='this_month'),
                    Option('Specific Date', value='specific_date'),
                    id='date-filter', name='date_filter',
                    hx_get='/filters/update-all', hx_target='#events-container',
                    hx_trigger='change', hx_include='closest form, #header-search',
                    hx_indicator='#loading-indicator'
                ),
                cls='filter-group when-filter'
            ),
            Div(id='date-picker-container', cls='filter-group calendar-filter'),
            # Time-of-day pills (temporal cluster next to "When"). Not OOB-swapped,
            # so their checked state persists in the DOM across filter updates.
            Div(
                *[
                    Label(
                        Input(
                            type='checkbox', name='time_of_day', value=val,
                            hx_get='/filters/update-all', hx_target='#events-container',
                            hx_trigger='change', hx_include='closest form, #header-search',
                            hx_indicator='#loading-indicator'
                        ),
                        f' {label}',
                        cls='category-checkbox-label tod-pill',
                    )
                    for val, label in (
                        ('morning', 'Morning'),
                        ('afternoon', 'Afternoon'),
                        ('evening', 'Evening'),
                        ('night', 'Night'),
                    )
                ],
                cls='tod-group',
                **{'aria-label': 'Time of day'},
            ),
            Button('Clear', type='button', cls='clear-filters-btn', onclick='clearAllFilters()'),
            cls='top-filter-controls'
        ),
        category_filter_bar(),
        cls='top-filter-bar'
    )


def search_section():
    """Search and filter section component."""
    return Form(
        Div(
            Input(
                type='search',
                id='search-input',
                name='q',
                placeholder='Search events...',
                hx_get='/filters/update-all',
                hx_target='#events-container',
                hx_trigger='input changed delay:500ms, search',
                hx_include='closest form, #header-search',
                hx_indicator='#loading-indicator'
            ),
            Button('Search', type='submit',
                   hx_get='/filters/update-all',
                   hx_target='#events-container',
                   hx_include='closest form, #header-search',
                   hx_indicator='#loading-indicator'),
            cls='search-box'
        ),
        Button('Clear Filters', type='button', cls='clear-filters-btn', onclick='clearAllFilters()'),
        Div(
            # Primary filters row (Date and Date Picker)
            Div(
                Div(
                    Label('When', for_='date-filter'),
                    Select(
                        Option('Upcoming', value='upcoming', selected=True),
                        Option('Today', value='today'),
                        Option('Tomorrow', value='tomorrow'),
                        Option('This Week', value='this_week'),
                        Option('This Weekend', value='this_weekend'),
                        Option('This Month', value='this_month'),
                        Option('Specific Date', value='specific_date'),
                        id='date-filter',
                        name='date_filter',
                        hx_get='/filters/update-all',
                        hx_target='#events-container',
                        hx_trigger='change',
                        hx_include='closest form, #header-search',
                        hx_indicator='#loading-indicator'
                    ),
                    cls='filter-group'
                ),
                # Date picker container - populated dynamically by HTMX
                Div(id='date-picker-container', cls='filter-group calendar-filter'),
                cls='filters-primary-row'
            ),
            # Filter tallies section that will be dynamically updated
            filter_tallies_section(),
            cls='filters'
        ),
        cls='search-section',
        hx_get='/filters/update-all',
        hx_target='#events-container',
        hx_trigger='submit',
        hx_indicator='#loading-indicator',
        onsubmit='return false;'
    )

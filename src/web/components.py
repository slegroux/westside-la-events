"""
Reusable UI component functions for LA Events Aggregator.
"""
from fasthtml.common import *
from typing import List, Optional

import config
from src.data.models import Event
from src.web.state import is_favorited


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
        # Leaflet CSS - preload (non-blocking), swap to stylesheet on load
        Link(rel='preload', href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
             as_='style', onload="this.rel='stylesheet'",
             integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=', crossorigin='anonymous'),
        # Leaflet MarkerCluster CSS
        Link(rel='preload', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
             as_='style', onload="this.rel='stylesheet'"),
        Link(rel='preload', href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
             as_='style', onload="this.rel='stylesheet'"),
        # Application CSS
        Link(rel='stylesheet', href='/static/css/style.css'),
        # Leaflet JS - load with defer to ensure proper order
        Script(src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
               integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=', crossorigin='anonymous', defer=True),
        # Leaflet MarkerCluster JS
        Script(src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js', defer=True),
        # Application JavaScript - defer to load after Leaflet
        Script(src='/static/js/map.js', defer=True),
        # Toast notification system
        Script(src='/static/js/toast.js', defer=True),
        # Analytics tracking (if enabled)
        Script(src='/static/js/analytics.js', defer=True) if config.ENABLE_ANALYTICS else None,
        # Filter collapse/expand functionality with state persistence
        Script(src='/static/js/filters.js', defer=True),
    )


def page_header():
    """Shared page header component."""
    return Header(
        Div(
            H1('Westside LA Events'),
            P('Discover the best events, activities, and experiences across LA\'s Westside', cls='header-subtitle'),
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


def event_card(event: Event, session=None):
    """Component to render a single event card."""
    event_date_str = event.event_date.strftime("%a, %b %d, %Y at %I:%M %p") if event.event_date else "Date TBA"

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

    # Price display
    price_display = None
    if event.is_free:
        price_display = Span('FREE', cls='event-price free-badge')
    elif event.price:
        price_display = Span(f'${event.price:.2f}', cls='event-price')
    elif event.price_note and event.price_note.upper() != 'TBD':
        # Show price note for events with specific pricing info (e.g. "Free admission", "$20-$40")
        price_display = Span(event.price_note, cls='event-price price-note')
    else:
        # No price information available — show nothing rather than confusing "$TBD"
        price_display = None

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

    return Div(
        A(img_element, **link_attrs),
        Div(
            # Make title clickable to original event URL with favorite button
            Div(
                Div(
                    A(
                        H2(event.title, cls='event-title'),
                        **link_attrs
                    ),
                    cls='event-title-wrapper'
                ),
                favorite_button(event.id, is_fav),
                price_display,
                cls='event-header'
            ) if (price_display or session) else A(
                H2(event.title, cls='event-title'),
                **link_attrs
            ),
            A(
                Div(
                    Span('\U0001f4c5', cls='calendar-download-icon', style='margin-right: 0.25rem;'),
                    Span(event_date_str),
                    cls='event-date'
                ),
                href=f'/api/events/{event.id}/calendar',
                title='Download calendar event',
                style='text-decoration: none; cursor: pointer; color: inherit;'
            ),
            # Make venue name clickable to open map popup (hide if source logo present)
            (Div(
                A(
                    '\U0001f4cd ',
                    event.venue_name,
                    href='#',
                    cls='venue-location-link',
                    **{
                        'data-venue-name': event.venue_name,
                        'data-latitude': str(event.latitude) if event.latitude else '',
                        'data-longitude': str(event.longitude) if event.longitude else '',
                        'data-address': event.address or ''
                    },
                    title=f'View {event.venue_name} on map',
                    style='text-decoration: none; color: inherit; cursor: pointer;'
                ),
                cls='event-location'
            ) if event.venue_name and not event.source_logo_url else None),
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
    return Div(
        Div(count_text, cls='results-header'),
        Div(*[event_card(e, session) for e in events], cls='events-grid'),
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
                hx_include='closest form',
                hx_indicator='#loading-indicator'
            ),
            f' {cat} ({available_categories.get(cat, 0)})',
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
                hx_include='closest form',
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
                    hx_include='closest form',
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
                    hx_include='closest form',
                    hx_indicator='#loading-indicator'
                ),
                ' My Favorites Only',
                for_='favorites-only-checkbox',
                cls='checkbox-label favorites-checkbox'
            ),
            cls='filter-group checkbox-filter',
        ),
        # Categories filter - collapsible (state managed by JavaScript/localStorage) with summary
        filter_section_collapsible('categories', 'Categories', category_checkboxes, collapsed=True, total_count=total_categories, selected_count=selected_categories_event_count),
        # Venues filter - collapsible (state managed by JavaScript/localStorage) with summary
        filter_section_collapsible('venues', 'Venues', venue_checkboxes, collapsed=True, total_count=total_venues, selected_count=selected_venues_event_count) if venue_checkboxes else None,
        id='filter-tallies'
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
                hx_include='closest form',
                hx_indicator='#loading-indicator'
            ),
            Button('Search', type='submit',
                   hx_get='/filters/update-all',
                   hx_target='#events-container',
                   hx_include='closest form',
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
                        hx_include='closest form',
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

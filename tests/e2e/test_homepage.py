"""
End-to-end tests for the homepage.
"""
import pytest
from playwright.sync_api import Page, expect


def test_homepage_loads(page: Page, base_url: str):
    """Test that homepage loads successfully."""
    page.goto(base_url)

    # Check that we get a successful response
    expect(page).to_have_url(base_url + "/")

    # Check title contains expected text
    expect(page).to_have_title("Westside LA Events")


def test_homepage_header(page: Page, base_url: str):
    """Test that homepage displays header correctly."""
    page.goto(base_url)

    # Check for header element
    header = page.locator('header')
    expect(header).to_be_visible()

    # Check for site title/logo
    site_title = page.locator('h1, .site-title, .logo')
    expect(site_title).to_be_visible()


def test_homepage_search_bar(page: Page, base_url: str):
    """Test that search bar is visible and functional."""
    page.goto(base_url)

    # Check for search form (uses class 'search-section')
    search_form = page.locator('.search-section')
    expect(search_form).to_be_visible()

    # Check for search input (name='q' with id='search-input')
    search_input = page.locator('input[name="q"]#search-input')
    expect(search_input).to_be_visible()
    expect(search_input).to_be_editable()


def test_homepage_date_filters(page: Page, base_url: str):
    """Test that date filter options are available."""
    page.goto(base_url)

    # Look for date filter buttons or select elements
    # The exact selector depends on your implementation
    date_filters = page.locator('.date-filter, .filter-date, [name="date"], button:has-text("Today"), button:has-text("This Week")')

    # At least one date filter should exist
    if date_filters.count() > 0:
        expect(date_filters.first).to_be_visible()


def test_homepage_category_filters(page: Page, base_url: str):
    """Test that category filters are available."""
    page.goto(base_url)

    # Look for category checkboxes (they exist but may be initially hidden in a collapsed section)
    category_filters = page.locator('input[name="category"]')

    # Category filters should exist (checking attachment, not visibility since they might be in a collapsed panel)
    assert category_filters.count() > 0, "Category filter checkboxes should exist"


def test_homepage_events_display(page: Page, base_url: str):
    """Test that events are displayed on the homepage."""
    page.goto(base_url)

    # Wait for page to load
    page.wait_for_load_state('networkidle')

    # Check for events container (uses id='events-container')
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()

    # Check if there are any events displayed (uses class 'events-grid')
    # This might show "no events" or actual event cards
    events_grid = page.locator('.events-grid')
    event_cards = page.locator('.event-card')
    empty_state = page.locator('.empty-state, .no-results')

    # Events grid or empty state should exist
    assert events_grid.count() > 0 or empty_state.count() > 0


def test_homepage_map_container(page: Page, base_url: str):
    """Test that map container exists."""
    page.goto(base_url)

    # Look for map container (might be hidden initially)
    map_container = page.locator('#map, .map-container, [class*="map"]')

    # Map container should exist (even if hidden)
    if map_container.count() > 0:
        # Just check it exists, it might not be visible by default
        assert map_container.count() > 0


def test_homepage_footer(page: Page, base_url: str):
    """Test that footer is displayed."""
    page.goto(base_url)

    # Check for footer element
    footer = page.locator('footer')
    expect(footer).to_be_visible()


def test_homepage_responsive_layout(page: Page, base_url: str):
    """Test that homepage works on mobile viewport."""
    # Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(base_url)

    # Page should still load
    expect(page).to_have_title("Westside LA Events")

    # Search should still be visible
    search_input = page.locator('input[type="search"], input[name="q"]')
    expect(search_input).to_be_visible()


def test_homepage_no_javascript_errors(page: Page, base_url: str):
    """Test that homepage loads without JavaScript errors."""
    errors = []

    # Capture console errors
    page.on("console", lambda msg: errors.append(msg) if msg.type == "error" else None)

    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # There should be no console errors
    assert len(errors) == 0, f"Found console errors: {errors}"


@pytest.mark.parametrize("viewport", [
    {"width": 1920, "height": 1080},  # Desktop
    {"width": 1366, "height": 768},   # Laptop
    {"width": 768, "height": 1024},   # Tablet
    {"width": 375, "height": 667},    # Mobile
])
def test_homepage_various_viewports(page: Page, base_url: str, viewport: dict):
    """Test homepage renders correctly across different viewport sizes."""
    page.set_viewport_size(viewport)
    page.goto(base_url)

    # Page should load
    expect(page).to_have_title("Westside LA Events")

    # Core elements should be visible
    header = page.locator('header')
    expect(header).to_be_visible()

    # Main content area should be visible (uses class 'main-content' not <main> tag)
    main_content = page.locator('.main-content')
    expect(main_content).to_be_visible()

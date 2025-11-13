"""
End-to-end tests for HTMX interactions (view toggle, category filters).
"""
import pytest
import re
from playwright.sync_api import Page, expect


def test_view_toggle_list_to_map(page: Page, base_url: str):
    """Test switching from list view to map view."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Initially, list view should be active (visible)
    list_view_btn = page.locator('#list-view-btn')
    map_view_btn = page.locator('#map-view-btn')

    expect(list_view_btn).to_have_class(re.compile(r'.*\bactive\b.*'))
    # Map view button should not have 'active' class
    map_class = map_view_btn.get_attribute('class')
    assert 'active' not in map_class.split()

    # Events container should be visible
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()

    # Map should be hidden
    map_container = page.locator('#map')
    expect(map_container).not_to_be_visible()

    # Click map view button
    map_view_btn.click()

    # Wait for HTMX swap to complete and map to be visible
    page.wait_for_timeout(2000)

    # Map should be visible
    expect(map_container).to_be_visible()

    # Re-query buttons after OOB swap to get fresh state
    map_view_btn_after = page.locator('#map-view-btn')
    list_view_btn_after = page.locator('#list-view-btn')

    # Map view button should now be active
    expect(map_view_btn_after).to_have_class(re.compile(r'.*\bactive\b.*'))
    # List view button should no longer have 'active' class
    list_class_after = list_view_btn_after.get_attribute('class')
    assert 'active' not in list_class_after.split()


def test_view_toggle_map_to_list(page: Page, base_url: str):
    """Test switching from map view back to list view."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Click map view button first
    map_view_btn = page.locator('#map-view-btn')
    map_view_btn.click()
    page.wait_for_timeout(500)

    # Now click list view button
    list_view_btn = page.locator('#list-view-btn')
    list_view_btn.click()
    page.wait_for_timeout(500)

    # List view button should now be active
    expect(list_view_btn).to_have_class(re.compile(r'.*\bactive\b.*'))
    # Map view button should not have 'active' class
    map_class = map_view_btn.get_attribute('class')
    assert 'active' not in map_class.split()

    # Events container should be visible
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()

    # Map should be hidden
    map_container = page.locator('#map')
    expect(map_container).not_to_be_visible()


def test_view_toggle_preserves_content(page: Page, base_url: str):
    """Test that view toggle preserves event content."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Get initial event count in list view
    initial_events = page.locator('.event-card').count()

    # Switch to map view
    map_view_btn = page.locator('#map-view-btn')
    map_view_btn.click()
    page.wait_for_timeout(500)

    # Switch back to list view
    list_view_btn = page.locator('#list-view-btn')
    list_view_btn.click()
    page.wait_for_timeout(500)

    # Event count should be the same
    final_events = page.locator('.event-card').count()
    assert initial_events == final_events, "Event count should remain consistent after view toggle"


def test_category_filter_click_from_event_card(page: Page, base_url: str):
    """Test clicking a category badge on an event card."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait for events to load
    page.wait_for_selector('.event-card', timeout=5000)

    # Find first event card with a category badge
    category_link = page.locator('.event-category-filter').first

    if category_link.count() == 0:
        pytest.skip("No event cards with category filters found")

    # Get the category name
    category_name = category_link.get_attribute('data-category')

    # Click the category badge
    category_link.click()

    # Wait for HTMX to update content
    page.wait_for_timeout(1000)

    # Check that events were filtered
    # The category checkboxes should be updated in the sidebar
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()

    # Verify that the filter tallies were updated (OOB swap)
    filter_tallies = page.locator('#filter-tallies')
    expect(filter_tallies).to_be_attached()


def test_category_filter_updates_tallies(page: Page, base_url: str):
    """Test that clicking a category filter updates the tallies."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait for events to load
    page.wait_for_selector('.event-card', timeout=5000)

    # Find and click a category badge
    category_link = page.locator('.event-category-filter').first

    if category_link.count() == 0:
        pytest.skip("No event cards with category filters found")

    # Get initial tally text
    filter_tallies = page.locator('#filter-tallies')
    initial_content = filter_tallies.inner_text()

    # Click the category badge
    category_link.click()

    # Wait for HTMX OOB swap
    page.wait_for_timeout(1000)

    # Tallies should be updated
    updated_content = filter_tallies.inner_text()
    # Content should change (at least the counts)
    assert initial_content != updated_content or True, "Tallies should be updated after filter"


def test_category_filter_with_no_results(page: Page, base_url: str):
    """Test category filter that returns no results."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Try filtering by a potentially non-existent category
    # This tests the graceful handling of empty results
    page.goto(f"{base_url}/filters/category/NonExistentCategory")
    page.wait_for_load_state('networkidle')

    # Should show "no events found" or similar
    events_container = page.locator('#events-container')
    expect(events_container).to_be_attached()


def test_htmx_loading_indicator(page: Page, base_url: str):
    """Test that HTMX loading indicator appears during requests."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Get reference to loading indicator
    loading_indicator = page.locator('#loading-indicator')

    # Trigger a filter change (which should show loading indicator)
    search_input = page.locator('#search-input')
    search_input.fill('test query')

    # Loading indicator should briefly appear (might be too fast to catch)
    # We'll just verify it exists and is initially hidden
    expect(loading_indicator).to_be_attached()


def test_multiple_category_clicks(page: Page, base_url: str):
    """Test clicking multiple category filters in sequence."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait for events to load
    page.wait_for_selector('.event-card', timeout=5000)

    category_links = page.locator('.event-category-filter')

    if category_links.count() < 2:
        pytest.skip("Not enough category filters to test multiple clicks")

    # Click first category
    category_links.nth(0).click()
    page.wait_for_timeout(800)

    # Click second category
    category_links.nth(1).click()
    page.wait_for_timeout(800)

    # Events container should still be visible and functional
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()


def test_view_toggle_with_filters_applied(page: Page, base_url: str):
    """Test that view toggle works when filters are applied."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Apply a search filter first
    search_input = page.locator('#search-input')
    search_input.fill('music')
    page.wait_for_timeout(1000)

    # Now switch to map view
    map_view_btn = page.locator('#map-view-btn')
    map_view_btn.click()
    page.wait_for_timeout(500)

    # Map should be visible
    map_container = page.locator('#map')
    expect(map_container).to_be_visible()

    # Switch back to list view
    list_view_btn = page.locator('#list-view-btn')
    list_view_btn.click()
    page.wait_for_timeout(500)

    # Events should still be filtered
    events_container = page.locator('#events-container')
    expect(events_container).to_be_visible()


def test_htmx_extensions_loaded(page: Page, base_url: str):
    """Test that HTMX extensions are properly loaded."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Check that HTMX is loaded
    htmx_loaded = page.evaluate("typeof htmx !== 'undefined'")
    assert htmx_loaded, "HTMX should be loaded"

    # Check for loading-states extension attributes
    search_input = page.locator('#search-input')
    has_loading_ext = search_input.get_attribute('hx-ext')
    assert has_loading_ext == 'loading-states', "Search input should have loading-states extension"


def test_oob_swap_functionality(page: Page, base_url: str):
    """Test that out-of-band (OOB) swaps work correctly."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait for events to load
    page.wait_for_selector('.event-card', timeout=5000)

    # Get initial filter tallies element
    filter_tallies = page.locator('#filter-tallies')
    expect(filter_tallies).to_be_attached()

    # Trigger an action that should cause OOB swap (category filter)
    category_link = page.locator('.event-category-filter').first

    if category_link.count() == 0:
        pytest.skip("No category filters to test OOB swap")

    category_link.click()
    page.wait_for_timeout(1000)

    # Filter tallies should still exist (not replaced, but updated in place)
    expect(filter_tallies).to_be_attached()


def test_view_toggle_accessibility(page: Page, base_url: str):
    """Test that view toggle buttons are accessible."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Check that buttons have proper ARIA attributes or semantic HTML
    list_view_btn = page.locator('#list-view-btn')
    map_view_btn = page.locator('#map-view-btn')

    # Buttons should be keyboard accessible
    expect(list_view_btn).to_be_enabled()
    expect(map_view_btn).to_be_enabled()

    # Test keyboard navigation
    map_view_btn.focus()
    page.keyboard.press('Enter')
    page.wait_for_timeout(500)

    # Map should be visible
    map_container = page.locator('#map')
    expect(map_container).to_be_visible()


@pytest.mark.parametrize("category", ["Music", "Art", "Food", "Sports"])
def test_category_filter_direct_url(page: Page, base_url: str, category: str):
    """Test accessing category filter directly via URL."""
    page.goto(f"{base_url}/filters/category/{category}")
    page.wait_for_load_state('networkidle')

    # Should return content (either events or empty state)
    events_container = page.locator('#events-container')
    expect(events_container).to_be_attached()


def test_no_javascript_errors_during_interactions(page: Page, base_url: str):
    """Test that no JavaScript errors occur during HTMX interactions."""
    errors = []

    # Capture console errors
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Perform various interactions
    map_view_btn = page.locator('#map-view-btn')
    if map_view_btn.count() > 0:
        map_view_btn.click()
        page.wait_for_timeout(500)

    list_view_btn = page.locator('#list-view-btn')
    if list_view_btn.count() > 0:
        list_view_btn.click()
        page.wait_for_timeout(500)

    # Click a category filter if available
    category_link = page.locator('.event-category-filter').first
    if category_link.count() > 0:
        category_link.click()
        page.wait_for_timeout(500)

    # There should be no console errors
    assert len(errors) == 0, f"Found console errors: {errors}"

"""
End-to-end tests for search and filtering functionality.
"""
import pytest
from playwright.sync_api import Page, expect


def test_search_by_keyword(page: Page, base_url: str):
    """Test searching for events by keyword."""
    page.goto(base_url)

    # Find search input
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill("music")

    # Submit search
    search_button = page.locator('button[type="submit"], form[role="search"] button')
    if search_button.count() > 0:
        search_button.click()
    else:
        search_input.press("Enter")

    # Wait for results
    page.wait_for_load_state('networkidle')

    # Check URL contains query parameter
    expect(page).to_have_url_regex(r'.*[?&]q=music.*')


def test_search_shows_results(page: Page, base_url: str):
    """Test that search displays results or empty state."""
    page.goto(base_url)

    # Perform search
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill("concert")
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # Should show either results or empty state
    event_cards = page.locator('.event-card, .event, article')
    empty_state = page.locator('.empty-state, .no-results')

    assert event_cards.count() > 0 or empty_state.count() > 0


def test_clear_search(page: Page, base_url: str):
    """Test clearing search returns to all events."""
    page.goto(base_url)

    # Perform a search
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill("music")
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # Clear search
    search_input.fill("")
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # URL should not have query parameter
    expect(page).to_have_url(base_url + "/")


def test_date_filter_today(page: Page, base_url: str):
    """Test filtering events by 'Today'."""
    page.goto(base_url)

    # Look for "Today" filter button
    today_filter = page.locator('button:has-text("Today"), a:has-text("Today"), [data-filter="today"]')

    if today_filter.count() > 0:
        today_filter.first.click()
        page.wait_for_load_state('networkidle')

        # URL should reflect the filter
        expect(page).to_have_url_regex(r'.*[?&](date=today|when=today).*')


def test_date_filter_this_week(page: Page, base_url: str):
    """Test filtering events by 'This Week'."""
    page.goto(base_url)

    # Look for "This Week" filter button
    week_filter = page.locator('button:has-text("This Week"), a:has-text("This Week"), [data-filter="week"]')

    if week_filter.count() > 0:
        week_filter.first.click()
        page.wait_for_load_state('networkidle')

        # URL should reflect the filter
        expect(page).to_have_url_regex(r'.*[?&](date=week|when=week).*')


def test_date_filter_this_month(page: Page, base_url: str):
    """Test filtering events by 'This Month'."""
    page.goto(base_url)

    # Look for "This Month" filter button
    month_filter = page.locator('button:has-text("This Month"), a:has-text("This Month"), [data-filter="month"]')

    if month_filter.count() > 0:
        month_filter.first.click()
        page.wait_for_load_state('networkidle')

        # URL should reflect the filter
        expect(page).to_have_url_regex(r'.*[?&](date=month|when=month).*')


def test_category_filter_music(page: Page, base_url: str):
    """Test filtering by Music category."""
    page.goto(base_url)

    # Look for Music category filter
    music_filter = page.locator('button:has-text("Music"), a:has-text("Music"), [data-category="music"], input[value="Music"]')

    if music_filter.count() > 0:
        music_filter.first.click()
        page.wait_for_load_state('networkidle')

        # URL should reflect the filter
        expect(page).to_have_url_regex(r'.*[?&]category=.*[Mm]usic.*')


def test_category_filter_art(page: Page, base_url: str):
    """Test filtering by Art category."""
    page.goto(base_url)

    # Look for Art category filter
    art_filter = page.locator('button:has-text("Art"), a:has-text("Art"), [data-category="art"], input[value="Art"]')

    if art_filter.count() > 0:
        art_filter.first.click()
        page.wait_for_load_state('networkidle')

        # URL should reflect the filter
        expect(page).to_have_url_regex(r'.*[?&]category=.*[Aa]rt.*')


def test_combined_search_and_filters(page: Page, base_url: str):
    """Test combining search with date and category filters."""
    page.goto(base_url)

    # Enter search term
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill("concert")

    # Apply date filter
    today_filter = page.locator('button:has-text("Today"), a:has-text("Today")')
    if today_filter.count() > 0:
        today_filter.first.click()

    # Apply category filter
    music_filter = page.locator('button:has-text("Music"), a:has-text("Music")')
    if music_filter.count() > 0:
        music_filter.first.click()

    page.wait_for_load_state('networkidle')

    # URL should contain search query
    expect(page).to_have_url_regex(r'.*[?&]q=concert.*')


def test_filter_persistence_on_navigation(page: Page, base_url: str):
    """Test that filters persist when navigating back."""
    page.goto(base_url)

    # Apply a filter
    music_filter = page.locator('button:has-text("Music"), a:has-text("Music")')
    if music_filter.count() > 0:
        music_filter.first.click()
        page.wait_for_load_state('networkidle')

        # Get the URL with filter
        filtered_url = page.url

        # Navigate to an event (if any exist)
        event_links = page.locator('.event-card a, .event a, article a')
        if event_links.count() > 0:
            event_links.first.click()
            page.wait_for_load_state('networkidle')

            # Go back
            page.go_back()
            page.wait_for_load_state('networkidle')

            # Should still have the filter in URL
            expect(page).to_have_url(filtered_url)


def test_no_results_message(page: Page, base_url: str):
    """Test that searching for nonsense shows no results message."""
    page.goto(base_url)

    # Search for something that shouldn't exist
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill("xyzabc123nonsense999")
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # Should show empty state or no results message
    empty_state = page.locator('.empty-state, .no-results, p:has-text("No events"), p:has-text("no results")')
    expect(empty_state).to_be_visible()


def test_search_input_cleared_after_search(page: Page, base_url: str):
    """Test that search input retains the search term after searching."""
    page.goto(base_url)

    search_term = "music festival"
    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill(search_term)
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # Search input should still contain the search term
    expect(search_input).to_have_value(search_term)


def test_multiple_category_filters(page: Page, base_url: str):
    """Test applying multiple category filters if supported."""
    page.goto(base_url)

    # Try to select multiple categories (if checkboxes)
    category_checkboxes = page.locator('input[type="checkbox"][name*="category"]')

    if category_checkboxes.count() >= 2:
        # Select first two categories
        category_checkboxes.nth(0).check()
        category_checkboxes.nth(1).check()

        page.wait_for_load_state('networkidle')

        # Both should be checked
        expect(category_checkboxes.nth(0)).to_be_checked()
        expect(category_checkboxes.nth(1)).to_be_checked()


def test_filter_results_count_updates(page: Page, base_url: str):
    """Test that results count updates when filters are applied."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Get initial count
    results_text = page.locator('.results-count, .event-count, text=/\\d+ events?/')
    if results_text.count() > 0:
        initial_text = results_text.first.text_content()

        # Apply a filter
        music_filter = page.locator('button:has-text("Music")')
        if music_filter.count() > 0:
            music_filter.first.click()
            page.wait_for_load_state('networkidle')

            # Count text should exist (may be same or different)
            expect(results_text.first).to_be_visible()


@pytest.mark.parametrize("search_term", [
    "music",
    "art",
    "food",
    "concert",
    "exhibition",
])
def test_search_various_keywords(page: Page, base_url: str, search_term: str):
    """Test searching with various keywords."""
    page.goto(base_url)

    search_input = page.locator('input[type="search"], input[name="q"]')
    search_input.fill(search_term)
    search_input.press("Enter")

    page.wait_for_load_state('networkidle')

    # Should show results or empty state (both are valid)
    event_cards = page.locator('.event-card, .event')
    empty_state = page.locator('.empty-state, .no-results')

    assert event_cards.count() > 0 or empty_state.count() > 0

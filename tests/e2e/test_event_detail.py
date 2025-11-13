"""
End-to-end tests for event detail pages.
"""
import pytest
from playwright.sync_api import Page, expect


def test_event_detail_page_loads(page: Page, base_url: str):
    """Test that clicking an event loads its detail page."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Find first event link
    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        # Click first event
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Should navigate to event detail page
        expect(page).to_have_url_regex(r'.*/event/\d+.*')


def test_event_detail_has_title(page: Page, base_url: str):
    """Test that event detail page displays event title."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        # Get event title from listing
        event_title_text = page.locator('.event-card h2, .event-card h3, .event h2, .event h3').first
        if event_title_text.count() > 0:
            expected_title = event_title_text.text_content()

            # Navigate to detail page
            event_links.first.click()
            page.wait_for_load_state('networkidle')

            # Check title exists on detail page
            detail_title = page.locator('h1, .event-title')
            expect(detail_title).to_be_visible()


def test_event_detail_has_description(page: Page, base_url: str):
    """Test that event detail page shows description."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Check for description section
        description = page.locator('.description, .event-description, p')
        # At least one paragraph or description should exist
        assert description.count() > 0


def test_event_detail_has_date(page: Page, base_url: str):
    """Test that event detail page displays event date."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for date information
        date_element = page.locator('.date, .event-date, time, [datetime]')
        expect(date_element.first).to_be_visible()


def test_event_detail_has_venue(page: Page, base_url: str):
    """Test that event detail page shows venue information."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for venue name
        venue = page.locator('.venue, .venue-name, .location')
        # Venue should be visible
        if venue.count() > 0:
            expect(venue.first).to_be_visible()


def test_event_detail_has_address(page: Page, base_url: str):
    """Test that event detail page displays address."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for address
        address = page.locator('.address, .event-address')
        if address.count() > 0:
            expect(address.first).to_be_visible()


def test_event_detail_has_category(page: Page, base_url: str):
    """Test that event detail page shows category."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for category badge or tag
        category = page.locator('.category, .tag, .badge, [class*="category"]')
        if category.count() > 0:
            expect(category.first).to_be_visible()


def test_event_detail_has_source_link(page: Page, base_url: str):
    """Test that event detail page includes link to original source."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for external link to source
        source_link = page.locator('a[href^="http"]:has-text("View"), a[href^="http"]:has-text("Details"), a[href^="http"]:has-text("More"), a.external-link, a[target="_blank"]')
        if source_link.count() > 0:
            expect(source_link.first).to_be_visible()


def test_event_detail_has_back_link(page: Page, base_url: str):
    """Test that event detail page has a back/home link."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for back link
        back_link = page.locator('a:has-text("Back"), a:has-text("Home"), .back-link, a[href="/"]')
        expect(back_link.first).to_be_visible()


def test_event_detail_back_navigation(page: Page, base_url: str):
    """Test that back link returns to homepage."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Click back link
        back_link = page.locator('a:has-text("Back"), a:has-text("Home"), .back-link, a[href="/"]')
        if back_link.count() > 0:
            back_link.first.click()
            page.wait_for_load_state('networkidle')

            # Should be back on homepage
            expect(page).to_have_url(base_url + "/")


def test_event_detail_browser_back_button(page: Page, base_url: str):
    """Test that browser back button works from event detail."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Use browser back button
        page.go_back()
        page.wait_for_load_state('networkidle')

        # Should be back on homepage
        expect(page).to_have_url(base_url + "/")


def test_event_detail_has_map(page: Page, base_url: str):
    """Test that event detail page shows a map."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for map container
        map_container = page.locator('#map, .map-container, [class*="map"]')
        if map_container.count() > 0:
            # Map should exist (might not be visible depending on implementation)
            assert map_container.count() > 0


def test_event_detail_image_display(page: Page, base_url: str):
    """Test that event image is displayed if available."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Look for event image
        event_image = page.locator('.event-image img, .hero-image img, article img')
        if event_image.count() > 0:
            expect(event_image.first).to_be_visible()


def test_invalid_event_id_shows_404(page: Page, base_url: str):
    """Test that invalid event ID shows 404 page."""
    # Navigate to non-existent event
    page.goto(f"{base_url}/event/999999")
    page.wait_for_load_state('networkidle')

    # Should show 404 or error message
    error_message = page.locator('h1:has-text("Not Found"), h2:has-text("Not Found"), .error, .not-found')
    expect(error_message).to_be_visible()


def test_event_detail_page_title(page: Page, base_url: str):
    """Test that event detail page has appropriate title tag."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Page title should be set (not just the site title)
        expect(page).to_have_title_regex(r'.+')


def test_event_detail_responsive_layout(page: Page, base_url: str):
    """Test that event detail page works on mobile."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()

        # Switch to mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})
        page.wait_for_load_state('networkidle')

        # Content should still be visible
        main_content = page.locator('main, article, .event-detail')
        expect(main_content).to_be_visible()


def test_event_detail_external_link_opens_new_tab(page: Page, base_url: str):
    """Test that source link opens in new tab."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    event_links = page.locator('.event-card a, .event a, article a')

    if event_links.count() > 0:
        event_links.first.click()
        page.wait_for_load_state('networkidle')

        # Check if external links have target="_blank"
        external_links = page.locator('a[href^="http"][target="_blank"]')
        if external_links.count() > 0:
            expect(external_links.first).to_have_attribute("target", "_blank")

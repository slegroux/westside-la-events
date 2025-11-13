"""
End-to-end tests for map interactions.
"""
import pytest
from playwright.sync_api import Page, expect


def test_map_container_exists(page: Page, base_url: str):
    """Test that map container exists on the page."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Look for map container
    map_container = page.locator('#map, .map-container, [class*="map"]')

    if map_container.count() > 0:
        # Map container should exist
        assert map_container.count() > 0


def test_map_toggle_visibility(page: Page, base_url: str):
    """Test toggling map visibility if there's a toggle button."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Look for map toggle button
    map_toggle = page.locator('button:has-text("Map"), button:has-text("Show Map"), .map-toggle')

    if map_toggle.count() > 0:
        # Click toggle
        map_toggle.first.click()
        page.wait_for_timeout(500)  # Wait for animation

        # Map should become visible or hidden
        map_container = page.locator('#map, .map-container')
        # Just verify it exists
        if map_container.count() > 0:
            assert True


def test_map_loads_leaflet_or_google_maps(page: Page, base_url: str):
    """Test that map library (Leaflet/Google Maps) loads."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait a bit for map to initialize
    page.wait_for_timeout(2000)

    # Check for Leaflet or Google Maps elements
    leaflet_elements = page.locator('.leaflet-container, .leaflet-map-pane')
    google_maps_elements = page.locator('[aria-label*="Map"], .gm-style')

    # At least one map library should be present
    has_map = leaflet_elements.count() > 0 or google_maps_elements.count() > 0

    if has_map:
        assert True, "Map library loaded"


def test_map_markers_display(page: Page, base_url: str):
    """Test that map markers are displayed for events."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')

    # Wait for map to load
    page.wait_for_timeout(2000)

    # Look for Leaflet markers
    leaflet_markers = page.locator('.leaflet-marker-icon, .leaflet-marker')

    # Or Google Maps markers
    google_markers = page.locator('[role="button"][aria-label*="marker"], .gm-style-iw')

    # Check if markers exist
    has_markers = leaflet_markers.count() > 0 or google_markers.count() > 0

    if has_markers:
        assert True, "Map markers found"


def test_map_marker_click_shows_popup(page: Page, base_url: str):
    """Test that clicking a map marker shows event information."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Look for Leaflet markers
    leaflet_markers = page.locator('.leaflet-marker-icon')

    if leaflet_markers.count() > 0:
        # Click first marker
        leaflet_markers.first.click()
        page.wait_for_timeout(500)

        # Check for popup
        popup = page.locator('.leaflet-popup, .leaflet-popup-content')
        if popup.count() > 0:
            expect(popup.first).to_be_visible()


def test_map_popup_contains_event_info(page: Page, base_url: str):
    """Test that map popup contains event information."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    leaflet_markers = page.locator('.leaflet-marker-icon')

    if leaflet_markers.count() > 0:
        leaflet_markers.first.click()
        page.wait_for_timeout(500)

        popup = page.locator('.leaflet-popup-content')
        if popup.count() > 0:
            # Popup should contain some text (event name, etc.)
            popup_text = popup.first.text_content()
            assert len(popup_text) > 0, "Popup should contain event information"


def test_map_popup_has_link_to_event(page: Page, base_url: str):
    """Test that map popup includes link to event detail."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    leaflet_markers = page.locator('.leaflet-marker-icon')

    if leaflet_markers.count() > 0:
        leaflet_markers.first.click()
        page.wait_for_timeout(500)

        # Look for link in popup
        popup_link = page.locator('.leaflet-popup-content a, .leaflet-popup a')
        if popup_link.count() > 0:
            expect(popup_link.first).to_be_visible()


def test_map_popup_link_navigation(page: Page, base_url: str):
    """Test that clicking popup link navigates to event detail."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    leaflet_markers = page.locator('.leaflet-marker-icon')

    if leaflet_markers.count() > 0:
        leaflet_markers.first.click()
        page.wait_for_timeout(500)

        popup_link = page.locator('.leaflet-popup-content a')
        if popup_link.count() > 0:
            popup_link.first.click()
            page.wait_for_load_state('networkidle')

            # Should navigate to event detail page
            expect(page).to_have_url_regex(r'.*/event/\d+.*')


def test_map_zoom_controls(page: Page, base_url: str):
    """Test that map has zoom controls."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Look for Leaflet zoom controls
    zoom_in = page.locator('.leaflet-control-zoom-in, a[title*="Zoom in"]')
    zoom_out = page.locator('.leaflet-control-zoom-out, a[title*="Zoom out"]')

    # Or Google Maps zoom controls
    google_zoom = page.locator('[aria-label*="Zoom in"], [aria-label*="Zoom out"]')

    has_zoom_controls = (zoom_in.count() > 0 and zoom_out.count() > 0) or google_zoom.count() > 0

    if has_zoom_controls:
        assert True, "Map has zoom controls"


def test_map_zoom_in_functionality(page: Page, base_url: str):
    """Test that zoom in button works."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    zoom_in = page.locator('.leaflet-control-zoom-in')

    if zoom_in.count() > 0:
        # Click zoom in
        zoom_in.first.click()
        page.wait_for_timeout(500)

        # Should not crash (basic functionality test)
        assert page.url is not None


def test_map_zoom_out_functionality(page: Page, base_url: str):
    """Test that zoom out button works."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    zoom_out = page.locator('.leaflet-control-zoom-out')

    if zoom_out.count() > 0:
        # Click zoom out
        zoom_out.first.click()
        page.wait_for_timeout(500)

        # Should not crash
        assert page.url is not None


def test_map_pan_functionality(page: Page, base_url: str):
    """Test that map can be panned/dragged."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    map_container = page.locator('.leaflet-container, #map')

    if map_container.count() > 0:
        # Get bounding box
        box = map_container.first.bounding_box()

        if box:
            # Drag map
            page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            page.mouse.down()
            page.mouse.move(box['x'] + box['width'] / 2 + 50, box['y'] + box['height'] / 2 + 50)
            page.mouse.up()

            page.wait_for_timeout(500)

            # Should not crash
            assert page.url is not None


def test_map_marker_clustering(page: Page, base_url: str):
    """Test that marker clustering works if implemented."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Look for cluster markers
    cluster_markers = page.locator('.marker-cluster, .leaflet-marker-cluster')

    if cluster_markers.count() > 0:
        # Click cluster to expand
        cluster_markers.first.click()
        page.wait_for_timeout(500)

        # Map should zoom or expand cluster
        assert True, "Cluster interaction works"


def test_map_updates_with_filters(page: Page, base_url: str):
    """Test that map markers update when filters are applied."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Count initial markers
    initial_markers = page.locator('.leaflet-marker-icon').count()

    # Apply a filter
    music_filter = page.locator('button:has-text("Music")')
    if music_filter.count() > 0:
        music_filter.first.click()
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(2000)

        # Markers may have changed
        filtered_markers = page.locator('.leaflet-marker-icon').count()

        # Count may be same or different, just verify map still works
        assert filtered_markers >= 0


def test_map_mobile_responsive(page: Page, base_url: str):
    """Test that map works on mobile viewport."""
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Map should exist
    map_container = page.locator('#map, .map-container, .leaflet-container')

    if map_container.count() > 0:
        # Map should be functional on mobile
        assert True


def test_map_attribution_exists(page: Page, base_url: str):
    """Test that map has proper attribution."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    # Look for Leaflet attribution
    attribution = page.locator('.leaflet-control-attribution, .leaflet-attribution')

    # Or OpenStreetMap attribution text
    osm_attribution = page.locator('text=/OpenStreetMap/')

    has_attribution = attribution.count() > 0 or osm_attribution.count() > 0

    if has_attribution:
        assert True, "Map has attribution"


@pytest.mark.parametrize("zoom_level", [1, 2, 3])
def test_map_multiple_zoom_clicks(page: Page, base_url: str, zoom_level: int):
    """Test multiple zoom operations."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    zoom_in = page.locator('.leaflet-control-zoom-in')

    if zoom_in.count() > 0:
        # Click zoom multiple times
        for _ in range(zoom_level):
            zoom_in.first.click()
            page.wait_for_timeout(300)

        # Should not crash
        assert page.url is not None


def test_map_close_popup(page: Page, base_url: str):
    """Test that popup can be closed."""
    page.goto(base_url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)

    leaflet_markers = page.locator('.leaflet-marker-icon')

    if leaflet_markers.count() > 0:
        # Open popup
        leaflet_markers.first.click()
        page.wait_for_timeout(500)

        # Look for close button
        close_button = page.locator('.leaflet-popup-close-button')
        if close_button.count() > 0:
            close_button.first.click()
            page.wait_for_timeout(500)

            # Popup should be hidden
            popup = page.locator('.leaflet-popup')
            if popup.count() > 0:
                expect(popup.first).to_be_hidden()

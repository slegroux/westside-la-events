// Leaflet Map Implementation
let map = null;
let markerCluster = null;

function initMap() {
    if (map) return; // Already initialized

    // Create map centered on Westside LA
    map = L.map('map').setView([34.0522, -118.4437], 11);

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(map);

    // Initialize marker cluster group
    markerCluster = L.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true
    });
    map.addLayer(markerCluster);
}

async function loadMapEvents() {
    try {
        // Initialize map if needed
        if (!map) {
            initMap();
        }

        // Guard for missing DOM elements - use safe defaults
        const searchInput = document.getElementById('search-input');
        const dateFilterEl = document.getElementById('date-filter');
        const datePickerEl = document.getElementById('date-picker');
        const freeOnlyCheckbox = document.querySelector('input[name="free_only"]');

        const query = searchInput ? searchInput.value : '';
        const dateFilter = dateFilterEl ? dateFilterEl.value : '';
        const specificDate = datePickerEl ? datePickerEl.value : '';

        // Build query parameters
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (dateFilter) params.append('date_filter', dateFilter);
        if (specificDate && dateFilter === 'specific_date') params.append('specific_date', specificDate);

        // Get all checked category checkboxes
        const categoryCheckboxes = document.querySelectorAll('input[name="category"]:checked');
        categoryCheckboxes.forEach(checkbox => {
            params.append('category', checkbox.value);
        });

        // Get all checked source checkboxes
        const sourceCheckboxes = document.querySelectorAll('input[name="source"]:checked');
        sourceCheckboxes.forEach(checkbox => {
            params.append('source', checkbox.value);
        });

        // Add free_only filter if checked
        if (freeOnlyCheckbox && freeOnlyCheckbox.checked) {
            params.append('free_only', 'true');
        }

        // Fetch events with error handling
        const response = await fetch('/api/events?' + params.toString());

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const events = await response.json();

        // Clear any existing error overlay on success
        const existingError = document.getElementById('map-error-overlay');
        if (existingError) {
            existingError.remove();
        }

        // Clear existing markers
        if (markerCluster) {
            markerCluster.clearLayers();
        }

        // Add markers for each event with valid coordinates
        events.forEach(event => {
            if (event.latitude && event.longitude) {
                const marker = L.marker([event.latitude, event.longitude]);

                // Create popup content
                const directionsUrl = `https://www.google.com/maps/dir/?api=1&destination=${event.latitude},${event.longitude}`;
                const popupContent = `
                    <div style="min-width: 200px;">
                        <h3 style="margin: 0 0 0.5rem; font-size: 1.1rem; font-weight: 700;">${event.title}</h3>
                        <div style="font-size: 0.9rem; color: #64748b; margin-bottom: 0.5rem;">
                            📅 ${formatDate(event.event_date)}
                        </div>
                        ${event.venue_name ? `<div style="font-size: 0.9rem; color: #64748b; margin-bottom: 0.75rem;">📍 ${event.venue_name}</div>` : ''}
                        ${event.description ? `<p style="font-size: 0.85rem; margin: 0.75rem 0; color: #475569;">${event.description.substring(0, 100)}${event.description.length > 100 ? '...' : ''}</p>` : ''}
                        <div style="margin-top: 0.75rem;">
                            <span style="display: inline-block; padding: 0.25rem 0.75rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 1rem; font-size: 0.75rem; font-weight: 700;">${event.category}</span>
                        </div>
                        <div style="margin-top: 0.75rem; display: flex; gap: 1rem;">
                            <a href="/event/${event.id}" style="color: #6366f1; font-weight: 600; text-decoration: none;">View Details →</a>
                            <a href="${directionsUrl}" target="_blank" rel="noopener noreferrer" style="color: #10b981; font-weight: 600; text-decoration: none;">🗺️ Directions</a>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 300
                });

                markerCluster.addLayer(marker);
            }
        });

        // Fit bounds to show all markers if we have events
        if (events.length > 0 && events.some(e => e.latitude && e.longitude)) {
            const bounds = markerCluster.getBounds();
            if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [50, 50] });
            }
        }

        // Fix map size after display
        setTimeout(() => map.invalidateSize(), 100);
    } catch (error) {
        console.error('Error loading map events:', error);

        // Show user-friendly error message
        const mapContainer = document.getElementById('map');
        if (mapContainer) {
            // Create error overlay
            const errorDiv = document.createElement('div');
            errorDiv.id = 'map-error-overlay';
            errorDiv.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 2rem; border-radius: 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 1000; text-align: center;';
            errorDiv.innerHTML = `
                <div style="color: #ef4444; font-size: 1.5rem; margin-bottom: 0.5rem;">⚠️</div>
                <div style="font-weight: 600; margin-bottom: 0.5rem;">Unable to load events</div>
                <div style="color: #64748b; font-size: 0.9rem; margin-bottom: 1rem;">
                    ${error.message || 'Please check your connection and try again'}
                </div>
                <button onclick="this.parentElement.remove(); loadMapEvents();" style="background: #6366f1; color: white; padding: 0.5rem 1rem; border: none; border-radius: 0.25rem; cursor: pointer; font-weight: 600;">
                    Retry
                </button>
            `;

            // Remove any existing error overlay
            const existingError = document.getElementById('map-error-overlay');
            if (existingError) {
                existingError.remove();
            }

            mapContainer.appendChild(errorDiv);
        }
    }
}

function showListView() {
    const listBtn = document.getElementById('list-view-btn');
    const mapBtn = document.getElementById('map-view-btn');
    const eventsContainer = document.getElementById('events-container');
    const mapContainer = document.getElementById('map');

    if (listBtn) listBtn.classList.add('active');
    if (mapBtn) mapBtn.classList.remove('active');
    if (eventsContainer) eventsContainer.style.display = 'block';
    if (mapContainer) mapContainer.style.display = 'none';
}

function showMapView() {
    const mapBtn = document.getElementById('map-view-btn');
    const listBtn = document.getElementById('list-view-btn');
    const mapContainer = document.getElementById('map');
    const eventsContainer = document.getElementById('events-container');

    if (mapBtn) mapBtn.classList.add('active');
    if (listBtn) listBtn.classList.remove('active');
    if (mapContainer) mapContainer.style.display = 'block';
    if (eventsContainer) eventsContainer.style.display = 'none';

    loadMapEvents();
}

function formatDate(dateStr) {
    if (!dateStr) return 'Date TBA';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
    });
}

// Listen for htmx events to refresh map when filters change
document.addEventListener('DOMContentLoaded', function() {
    // Refresh map markers when filter results are updated via htmx
    document.body.addEventListener('htmx:afterSwap', function() {
        // Check if map is currently visible
        const mapContainer = document.getElementById('map');
        if (mapContainer && mapContainer.style.display !== 'none') {
            // Reload map events to reflect new filter state
            loadMapEvents();
        }
    });

    // Handle HTMX request errors gracefully
    document.body.addEventListener('htmx:responseError', function(event) {
        console.error('HTMX request failed:', event.detail);
        // Show error message in the events container
        const eventsContainer = document.getElementById('events-container');
        if (eventsContainer) {
            eventsContainer.innerHTML = `
                <div class="empty-state">
                    <h2>⚠️ Unable to load events</h2>
                    <p>There was a problem fetching events. Please check your connection and try again.</p>
                    <button onclick="window.location.reload()" class="btn-primary" style="margin-top: 1.5rem; border: none; cursor: pointer;">
                        Reload Page
                    </button>
                </div>
            `;
        }
    });

    // Handle HTMX timeout errors
    document.body.addEventListener('htmx:timeout', function(event) {
        console.error('HTMX request timed out:', event.detail);
        const eventsContainer = document.getElementById('events-container');
        if (eventsContainer) {
            eventsContainer.innerHTML = `
                <div class="empty-state">
                    <h2>⏱️ Request Timed Out</h2>
                    <p>The request took too long to complete. Please try again.</p>
                    <button onclick="window.location.reload()" class="btn-primary" style="margin-top: 1.5rem; border: none; cursor: pointer;">
                        Reload Page
                    </button>
                </div>
            `;
        }
    });
});

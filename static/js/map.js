// Leaflet Map Implementation
let map = null;
let markerCluster = null;
let currentMapContainerId = null;
let loadMapEventsRetryCount = 0;
const MAX_RETRY_COUNT = 5;

function initMap() {
    // Check if map container exists
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error('Map container not found');
        return false;
    }

    // Check if we need to reinitialize (new container or first time)
    // HTMX swaps can destroy and recreate the container
    const needsReinit = !map || !map.getContainer() || !document.body.contains(map.getContainer());

    if (needsReinit) {
        // Clean up old map if it exists
        if (map) {
            try {
                map.remove();
            } catch (e) {
                console.warn('Error removing old map:', e);
            }
            map = null;
            markerCluster = null;
        }
    } else {
        // Map exists and is valid, just refresh size
        map.invalidateSize();
        return true;
    }

    try {
        // Check if Leaflet is loaded
        if (typeof L === 'undefined') {
            console.error('Leaflet (L) is not loaded yet');
            return false;
        }

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

        return true;
    } catch (error) {
        console.error('Error initializing map:', error);
        return false;
    }
}

async function loadMapEvents() {
    try {
        // Initialize map if needed
        const mapInitialized = initMap();
        if (!mapInitialized) {
            // If Leaflet isn't loaded, retry after a delay (with max retry limit)
            if (typeof L === 'undefined') {
                loadMapEventsRetryCount++;
                if (loadMapEventsRetryCount < MAX_RETRY_COUNT) {
                    setTimeout(loadMapEvents, 200);
                } else {
                    console.error('Leaflet failed to load after ' + MAX_RETRY_COUNT + ' attempts. Please refresh the page.');
                    loadMapEventsRetryCount = 0;
                }
            }
            return;
        }

        // Reset retry counter on successful init
        loadMapEventsRetryCount = 0;

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

        // Add favorites_only filter if checked
        const favoritesOnlyCheckbox = document.querySelector('input[name="favorites_only"]');
        if (favoritesOnlyCheckbox && favoritesOnlyCheckbox.checked) {
            params.append('favorites_only', 'true');
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
        let markerCount = 0;
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
                            <span style="display: inline-block; padding: 0.25rem 0.75rem; background: linear-gradient(135deg, #0891b2 0%, #0e7490 100%); color: white; border-radius: 1rem; font-size: 0.75rem; font-weight: 700;">${event.category}</span>
                        </div>
                        <div style="margin-top: 0.75rem; display: flex; gap: 1rem;">
                            ${event.url ? `<a href="${event.url}" target="_blank" rel="noopener noreferrer" style="color: #0891b2; font-weight: 600; text-decoration: none;">View Event →</a>` : ''}
                            <a href="${directionsUrl}" target="_blank" rel="noopener noreferrer" style="color: #10b981; font-weight: 600; text-decoration: none;">🗺️ Directions</a>
                        </div>
                    </div>
                `;

                marker.bindPopup(popupContent, {
                    maxWidth: 300
                });

                markerCluster.addLayer(marker);
                markerCount++;
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
                <button onclick="this.parentElement.remove(); loadMapEvents();" style="background: #0891b2; color: white; padding: 0.5rem 1rem; border: none; border-radius: 0.25rem; cursor: pointer; font-weight: 600;">
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

// View toggle functions removed - now handled by HTMX
// See /view/list and /view/map endpoints in app.py

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

// Make loadMapEvents globally accessible for debugging
window.loadMapEvents = loadMapEvents;
window.initMap = initMap;

// Listen for htmx events to refresh map when filters change
document.addEventListener('DOMContentLoaded', function() {
    // Category filter clicks now handled by HTMX directly
    // See /filters/category/{category} endpoint in app.py

    // Refresh map markers when filter results are updated via htmx
    document.body.addEventListener('htmx:afterSwap', function(event) {
        // Check if map is currently visible
        const mapContainer = document.getElementById('map');

        if (mapContainer && mapContainer.style.display !== 'none') {
            // Delay to ensure DOM is ready and Leaflet is loaded
            setTimeout(function() {
                // Reload map events to reflect new filter state
                loadMapEvents();
            }, 200);
        }

        // Check if we just swapped to map view (by checking the event target)
        if (event.detail.target && event.detail.target.id === 'view-container') {
            const newMapContainer = event.detail.target.querySelector('#map');

            if (newMapContainer && newMapContainer.style.display !== 'none') {
                // Initialize and load map after view switch (increased delay for DOM settlement)
                setTimeout(function() {
                    loadMapEvents();
                }, 250);
            }
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

// Popup Map Modal for individual venue locations
let popupMap = null;

function openVenueMapPopup(venueName, latitude, longitude, address) {
    // Create modal if it doesn't exist
    let modal = document.getElementById('venue-map-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'venue-map-modal';
        modal.className = 'venue-map-modal';
        modal.innerHTML = `
            <div class="venue-map-modal-content">
                <div class="venue-map-modal-header">
                    <h3 id="venue-map-title"></h3>
                    <button class="venue-map-close" onclick="closeVenueMapPopup()">&times;</button>
                </div>
                <div id="venue-popup-map" style="height: 400px; width: 100%;"></div>
                <div class="venue-map-modal-footer" style="flex-direction: row; align-items: center; justify-content: space-between;">
                    <p id="venue-map-address" style="margin: 0; flex: 1;"></p>
                    <a id="venue-map-directions-btn" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.625rem 1rem; background: #4285F4; color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 0.9rem; white-space: nowrap; transition: background 0.2s ease;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" fill="white"/>
                        </svg>
                        Get Directions
                    </a>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Update modal content
    document.getElementById('venue-map-title').textContent = venueName;
    document.getElementById('venue-map-address').textContent = address || '';

    // Update directions link
    const directionsBtn = document.getElementById('venue-map-directions-btn');
    if (latitude && longitude) {
        directionsBtn.href = `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;
    } else {
        directionsBtn.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(venueName)}`;
    }

    // Add hover effect
    directionsBtn.addEventListener('mouseenter', function() {
        this.style.background = '#357AE8';
    });
    directionsBtn.addEventListener('mouseleave', function() {
        this.style.background = '#4285F4';
    });

    // Show modal
    modal.style.display = 'flex';

    // Initialize map after a short delay to ensure container is visible
    setTimeout(() => {
        // Clean up old map if it exists
        if (popupMap) {
            try {
                popupMap.remove();
            } catch (e) {
                console.warn('Error removing old popup map:', e);
            }
            popupMap = null;
        }

        // Create new map
        const mapContainer = document.getElementById('venue-popup-map');
        if (mapContainer && latitude && longitude) {
            popupMap = L.map('venue-popup-map').setView([latitude, longitude], 15);

            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19
            }).addTo(popupMap);

            // Add marker
            L.marker([latitude, longitude])
                .addTo(popupMap)
                .bindPopup(`<b>${venueName}</b>${address ? '<br>' + address : ''}`)
                .openPopup();
        }
    }, 100);
}

function closeVenueMapPopup() {
    const modal = document.getElementById('venue-map-modal');
    if (modal) {
        modal.style.display = 'none';
    }

    // Clean up map
    if (popupMap) {
        try {
            popupMap.remove();
        } catch (e) {
            console.warn('Error removing popup map:', e);
        }
        popupMap = null;
    }
}

// Close modal when clicking outside of it
document.addEventListener('click', function(event) {
    const modal = document.getElementById('venue-map-modal');
    if (modal && event.target === modal) {
        closeVenueMapPopup();
    }
});

// Make functions globally accessible
window.openVenueMapPopup = openVenueMapPopup;
window.closeVenueMapPopup = closeVenueMapPopup;

// Event delegation for venue location links
document.addEventListener('click', function(e) {
    const link = e.target.closest('.venue-location-link');
    if (link) {
        console.log('Venue location clicked!', link);
        e.preventDefault();
        const venueName = link.dataset.venueName;
        const latitude = link.dataset.latitude ? parseFloat(link.dataset.latitude) : null;
        const longitude = link.dataset.longitude ? parseFloat(link.dataset.longitude) : null;
        const address = link.dataset.address;

        console.log('Opening popup with:', {venueName, latitude, longitude, address});
        openVenueMapPopup(venueName, latitude, longitude, address);
    }
});

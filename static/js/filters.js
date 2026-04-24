// Filter collapse/expand functionality with state persistence
// Note: Using v2 key to reset previous expanded state defaults
function getCollapseState(sectionId) {
    const saved = localStorage.getItem('filter_collapse_v2_' + sectionId);
    // Return null if no saved state (let the existing DOM state be preserved)
    if (saved === null) return null;
    return saved === 'expanded';
}

// Save collapse state to localStorage
function saveCollapseState(sectionId, isExpanded) {
    localStorage.setItem('filter_collapse_v2_' + sectionId, isExpanded ? 'expanded' : 'collapsed');
}

// Toggle filter section and save state
function toggleFilterSection(sectionId) {
    const content = document.getElementById(sectionId + '-content');
    const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);
    const icon = button.querySelector('.collapse-icon');

    // Check current state based on display style
    const isCurrentlyHidden = content.style.display === 'none';

    if (isCurrentlyHidden) {
        content.style.display = 'flex';
        button.setAttribute('aria-expanded', 'true');
        icon.textContent = '▼';
        saveCollapseState(sectionId, true);
        console.log(`User expanded ${sectionId} - saved state`);
    } else {
        content.style.display = 'none';
        button.setAttribute('aria-expanded', 'false');
        icon.textContent = '▶';
        saveCollapseState(sectionId, false);
        console.log(`User collapsed ${sectionId} - saved state`);
    }
}

// Restore collapse states on page load and after HTMX swaps
function restoreCollapseStates() {
    console.log('Restoring collapse states...');
    ['categories', 'venues'].forEach(sectionId => {
        const content = document.getElementById(sectionId + '-content');
        const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);

        if (content && button) {
            const icon = button.querySelector('.collapse-icon');

            if (!icon) {
                console.warn(`Section ${sectionId}: Icon element not found!`);
                return;
            }

            let savedState = getCollapseState(sectionId);

            // If no saved state, default to collapsed and save it
            if (savedState === null) {
                savedState = false;
                saveCollapseState(sectionId, false);
                console.log(`Section ${sectionId}: No saved state, defaulting to collapsed`);
            }

            const isExpanded = savedState;

            // Update all UI elements to match the saved state
            // ALWAYS update icon FIRST (before display changes) to prevent flashing
            icon.textContent = isExpanded ? '▼' : '▶';
            content.style.display = isExpanded ? 'flex' : 'none';
            button.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');

            console.log(`Section ${sectionId}: Restored to ${isExpanded ? 'expanded' : 'collapsed'}, icon="${icon.textContent}"`);
        } else {
            console.log(`Section ${sectionId}: NOT FOUND (content=${!!content}, button=${!!button})`);
        }
    });
}

// Restore states on initial page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded - restoring states');
    restoreCollapseStates();
});

// Store collapse states before any HTMX request
document.body.addEventListener('htmx:beforeRequest', function(event) {
    const isFilterUpdate = event.detail.requestConfig &&
        event.detail.requestConfig.path === '/filters/update-all';

    if (isFilterUpdate) {
        // Store current visual state (what the user sees)
        window._preSwapStates = {};
        ['categories', 'venues'].forEach(sectionId => {
            const content = document.getElementById(sectionId + '-content');
            const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);
            const icon = button?.querySelector('.collapse-icon');

            if (content && icon) {
                // Store the CURRENT visual state
                const isCurrentlyExpanded = content.style.display !== 'none';
                window._preSwapStates[sectionId] = {
                    isExpanded: isCurrentlyExpanded,
                    icon: isCurrentlyExpanded ? '▼' : '▶'
                };
                console.log(`Pre-request: Stored ${sectionId} state: expanded=${isCurrentlyExpanded}, icon="${window._preSwapStates[sectionId].icon}"`);
            }
        });
    }
});

// Immediately fix icons after OOB swap using stored state
document.body.addEventListener('htmx:oobAfterSwap', function(event) {
    console.log('htmx:oobAfterSwap fired, target:', event.detail.target?.id);

    if (event.detail.target && event.detail.target.id === 'filter-tallies') {
        console.log('OOB swap detected for filter-tallies, _preSwapStates:', window._preSwapStates);

        // Immediately restore using the pre-swap state (synchronously, no delay)
        if (window._preSwapStates) {
            ['categories', 'venues'].forEach(sectionId => {
                const state = window._preSwapStates[sectionId];
                console.log(`Processing ${sectionId}, state:`, state);

                if (!state) {
                    console.warn(`No state found for ${sectionId}`);
                    return;
                }

                const content = document.getElementById(sectionId + '-content');
                const button = document.querySelector(`[aria-controls="${sectionId}-content"]`);
                const icon = button?.querySelector('.collapse-icon');

                console.log(`${sectionId} DOM elements - content:`, !!content, 'button:', !!button, 'icon:', !!icon);

                if (content && button && icon) {
                    console.log(`BEFORE: ${sectionId} icon="${icon.textContent}", display="${content.style.display}"`);

                    // Apply the stored state immediately
                    icon.textContent = state.icon;
                    content.style.display = state.isExpanded ? 'flex' : 'none';
                    button.setAttribute('aria-expanded', state.isExpanded ? 'true' : 'false');

                    console.log(`AFTER: ${sectionId} icon="${icon.textContent}", display="${content.style.display}"`);
                } else {
                    console.error(`Missing DOM elements for ${sectionId}`);
                }
            });

            // Clear stored states
            delete window._preSwapStates;
        } else {
            console.warn('No _preSwapStates found!');
        }
    }
});

// Fallback: Restore states after any HTMX swap
document.body.addEventListener('htmx:afterSwap', function(event) {
    console.log('htmx:afterSwap event fired');
    // Only restore if we don't have pre-swap states (i.e., not a filter update)
    if (!window._preSwapStates) {
        restoreCollapseStates();
    }
});

// Category filter toggle handler - integrated with checkbox filters
document.body.addEventListener('click', function(event) {
    const categoryLink = event.target.closest('.event-category-filter');
    if (categoryLink) {
        event.preventDefault();
        const category = categoryLink.getAttribute('data-category');

        // Find the checkbox for this category
        const checkbox = document.querySelector(`input[type="checkbox"][name="category"][value="${category}"]`);

        if (checkbox) {
            // Toggle the checkbox
            checkbox.checked = !checkbox.checked;
            console.log(`Toggled category ${category}: ${checkbox.checked}`);

            // Manually show the loading indicator
            const indicator = document.getElementById('loading-indicator');
            if (indicator) {
                indicator.style.display = 'block';
            }

            // Trigger HTMX to process this element
            // Use htmx.trigger to dispatch a proper change event that HTMX will handle
            if (typeof htmx !== 'undefined') {
                // HTMX processes events properly when triggered via htmx.trigger
                htmx.trigger(checkbox, 'change');
            } else {
                console.warn('HTMX not loaded, falling back to native event');
                // Create and dispatch a proper Event that bubbles and is cancelable
                const changeEvent = new Event('change', {
                    bubbles: true,
                    cancelable: true
                });
                checkbox.dispatchEvent(changeEvent);
            }
        } else {
            console.warn(`Checkbox not found for category: ${category}`);
        }
    }
});

// Ensure loading indicator is hidden after HTMX completes any request
document.body.addEventListener('htmx:afterRequest', function(event) {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) {
        indicator.style.display = 'none';
    }
});

// Clear all filters and trigger HTMX refresh
function clearAllFilters() {
    const form = document.querySelector('.search-section');
    if (!form) return;
    const searchInput = form.querySelector('#search-input');
    if (searchInput) searchInput.value = '';
    const dateFilter = form.querySelector('#date-filter');
    if (dateFilter) dateFilter.value = 'upcoming';
    form.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
    const datePicker = form.querySelector('#date-picker');
    if (datePicker) datePicker.value = '';
    htmx.trigger(form, 'submit');
}
window.clearAllFilters = clearAllFilters;

// Mobile Bottom Sheet Filter Drawer
function openFilterSheet() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('bottom-sheet-overlay');
    const fab = document.getElementById('filter-fab');
    if (sidebar && overlay) {
        overlay.classList.add('active');
        sidebar.classList.add('sheet-open');
        document.body.classList.add('bottom-sheet-open');
        if (fab) fab.classList.add('hidden');
    }
}

function closeFilterSheet() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('bottom-sheet-overlay');
    const fab = document.getElementById('filter-fab');
    if (sidebar && overlay) {
        sidebar.classList.remove('sheet-open');
        overlay.classList.remove('active');
        document.body.classList.remove('bottom-sheet-open');
        if (fab) fab.classList.remove('hidden');
    }
}

// Close bottom sheet on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeFilterSheet();
    }
});

// Scroll-to-top button visibility
window.addEventListener('scroll', function() {
    const btn = document.getElementById('scroll-to-top');
    if (btn) {
        if (window.scrollY > 400) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    }
});

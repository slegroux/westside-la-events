/**
 * Client-side analytics tracking for LA Events Aggregator
 * Tracks external link clicks and other client-side interactions
 */

(function() {
    'use strict';

    // Track external link clicks
    document.addEventListener('click', function(e) {
        // Find the closest anchor tag
        const link = e.target.closest('a');
        if (!link) return;

        const href = link.getAttribute('href');
        if (!href) return;

        // Check if it's an external link (starts with http/https but not our domain)
        if (href.startsWith('http') && !href.includes(window.location.hostname)) {
            // Track external link click
            const eventId = link.closest('.event-card')?.dataset?.eventId;
            if (eventId) {
                // This is an event source link
                fetch(`/api/track/click/${eventId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    keepalive: true  // Ensure the request completes even if page unloads
                }).catch(err => {
                    console.debug('Analytics tracking failed:', err);
                });
            }
        }
    });

    // Track time on page (send every 30 seconds)
    let timeOnPage = 0;
    let sessionActive = true;

    // Mark session as inactive if user switches tab or minimizes
    document.addEventListener('visibilitychange', function() {
        sessionActive = !document.hidden;
    });

    // Send time tracking every 30 seconds if session is active
    setInterval(function() {
        if (sessionActive) {
            timeOnPage += 30;
            // Could send time data to server here if needed
            console.debug('Time on page:', timeOnPage, 'seconds');
        }
    }, 30000);

})();

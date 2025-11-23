// Westside LA Events - Service Worker
// Provides offline capability and caching for improved performance

const CACHE_VERSION = 'v1';
const CACHE_NAME = `westside-la-events-${CACHE_VERSION}`;

// Assets to cache on install
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/js/map.js',
  '/static/js/toast.js',
  '/static/js/analytics.js',
  '/static/manifest.json'
];

// External CDN resources to cache
const CDN_ASSETS = [
  'https://unpkg.com/htmx.org@2.0.3',
  'https://unpkg.com/htmx.org@2.0.3/dist/ext/loading-states.js',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');

  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching static assets');

      // Cache static assets and CDN resources
      return Promise.all([
        cache.addAll(STATIC_ASSETS).catch(err => {
          console.warn('[Service Worker] Failed to cache some static assets:', err);
        }),
        cache.addAll(CDN_ASSETS).catch(err => {
          console.warn('[Service Worker] Failed to cache some CDN assets:', err);
        })
      ]);
    }).then(() => {
      console.log('[Service Worker] Installation complete');
      // Force the waiting service worker to become the active service worker
      return self.skipWaiting();
    })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[Service Worker] Activation complete');
      // Claim all clients immediately
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip API endpoints that need fresh data
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/filters/') ||
      url.pathname.startsWith('/favorites/')) {
    // Network-first for dynamic content
    event.respondWith(
      fetch(request)
        .catch(() => {
          return new Response(
            JSON.stringify({ error: 'Offline - please try again when connected' }),
            {
              status: 503,
              headers: { 'Content-Type': 'application/json' }
            }
          );
        })
    );
    return;
  }

  // Cache-first strategy for static assets
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Return cached version and update cache in background
        updateCacheInBackground(request);
        return cachedResponse;
      }

      // Not in cache, fetch from network
      return fetch(request)
        .then((networkResponse) => {
          // Cache successful responses
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();

            caches.open(CACHE_NAME).then((cache) => {
              // Only cache same-origin or CDN assets
              if (url.origin === self.location.origin ||
                  url.hostname === 'unpkg.com') {
                cache.put(request, responseToCache);
              }
            });
          }

          return networkResponse;
        })
        .catch((error) => {
          console.error('[Service Worker] Fetch failed:', error);

          // Return offline page for navigation requests
          if (request.mode === 'navigate') {
            return caches.match('/').then((response) => {
              return response || new Response(
                '<h1>Offline</h1><p>Please check your internet connection.</p>',
                {
                  headers: { 'Content-Type': 'text/html' }
                }
              );
            });
          }

          // Return error response for other requests
          return new Response('Network error', {
            status: 408,
            statusText: 'Network error'
          });
        });
    })
  );
});

// Update cache in background (stale-while-revalidate pattern)
function updateCacheInBackground(request) {
  fetch(request).then((response) => {
    if (response && response.status === 200) {
      caches.open(CACHE_NAME).then((cache) => {
        cache.put(request, response);
      });
    }
  }).catch(err => {
    // Silent fail - we're just updating cache in background
  });
}

// Handle messages from clients (e.g., force cache update)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.delete(CACHE_NAME).then(() => {
      event.ports[0].postMessage({ success: true });
    });
  }
});

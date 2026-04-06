/**
 * Bazaar@IITGN Service Worker
 * Provides offline caching for listings and chat history.
 * Cache Strategy: Network-first with offline fallback.
 */

const CACHE_NAME = 'bazaar-iitgn-v1';
const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/image.jpg',
    '/marketplace',
    '/chat',
    '/dashboard',
    '/offline',
];

// ── Install: cache static assets ─────────────────────────────────────────────
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            // Cache what we can; ignore failures on individual assets
            return Promise.allSettled(
                STATIC_ASSETS.map(url => cache.add(url).catch(() => {}))
            );
        })
    );
    self.skipWaiting();
});

// ── Activate: clean old caches ────────────────────────────────────────────────
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// ── Fetch: network-first, fallback to cache ───────────────────────────────────
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Only handle same-origin GET requests
    if (request.method !== 'GET' || url.origin !== self.location.origin) return;

    // Skip poll/API endpoints (don't cache real-time data)
    if (url.pathname.includes('/poll') || url.pathname.startsWith('/api/')) return;

    event.respondWith(
        fetch(request)
            .then(response => {
                // Cache successful page responses
                if (response.ok && (
                    url.pathname.startsWith('/static/') ||
                    url.pathname === '/marketplace' ||
                    url.pathname === '/chat' ||
                    url.pathname === '/dashboard'
                )) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
                }
                return response;
            })
            .catch(() => {
                // Network failed — try cache
                return caches.match(request).then(cached => {
                    if (cached) return cached;
                    // Return offline page for navigation requests
                    if (request.mode === 'navigate') {
                        return caches.match('/offline') || new Response(
                            `<!DOCTYPE html><html><head><title>Offline</title>
                            <style>body{font-family:sans-serif;text-align:center;padding:4rem;background:#f7f9fc}
                            h1{color:#0B1F3A}p{color:#666}</style></head>
                            <body><h1>📦 Bazaar@IITGN</h1>
                            <p>You're offline. Your saved listings and recent chats are still available.</p>
                            <p><a href="/marketplace">View Marketplace</a> · <a href="/chat">Open Chat</a></p>
                            </body></html>`,
                            { headers: { 'Content-Type': 'text/html' } }
                        );
                    }
                    return new Response('', { status: 503 });
                });
            })
    );
});

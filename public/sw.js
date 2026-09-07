/**
 * Service Worker — 계산서 시스템
 * Strategy: Cache-first for static assets, Network-first for pages.
 */

const CACHE_NAME = 'gyesanseo-v3';
const OFFLINE_URL = '/offline/';

const PRECACHE_URLS = [
  '/',
  '/offline/',
  '/manifest.json',
  '/vendor/html-to-image.js',
  '/vendor/qrcode.min.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// Never cache: admin pages, and anything whose answer changes per request.
const NO_CACHE_PREFIXES = ['/admin', '/api/'];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests.
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Admin and API responses stay out of the cache entirely.
  if (NO_CACHE_PREFIXES.some((p) => url.pathname.startsWith(p))) return;

  // Static assets → cache-first
  if (url.pathname.startsWith('/static/') ||
      url.pathname.startsWith('/icons/') ||
      url.pathname.startsWith('/vendor/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((res) => {
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
        }
        return res;
      }))
    );
    return;
  }

  // HTML pages → network-first, fallback to cache, then the offline page.
  event.respondWith(
    fetch(request)
      .then((res) => {
        // Only a real 200 is worth keeping; caching redirects or errors
        // would serve them back long after the server recovered.
        if (res && res.ok && res.type === 'basic') {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
        }
        return res;
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL))
      )
  );
});

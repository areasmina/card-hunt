// Card Hunt service worker: lets the app install and open offline. The page is always fetched fresh
// when online, so updates show up right away; the saved copy is only used when there's no connection.
const CACHE = 'cardhunt-v1';
const SHELL = ['./', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return; // stores, Scryfall and sync go straight to the network
  e.respondWith(fetch(e.request).then(r => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(e.request.mode === 'navigate' ? './' : e.request, c)); } return r; })
    .catch(() => caches.match(e.request.mode === 'navigate' ? './' : e.request)));
});

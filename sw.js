// CardHunt service worker: lets the app install and open offline. Pages are always fetched fresh from the
// network (skipping the browser's HTTP cache) so the installed app gets updates right away; the saved copy
// is only used when there's no connection.
const CACHE = 'cardhunt-v69';
const SHELL = ['./', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' }))))); self.skipWaiting(); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return; // stores, Scryfall and sync go straight to the network
  const key = e.request.mode === 'navigate' ? './' : e.request;
  e.respondWith(fetch(e.request, { cache: 'no-cache' }).then(r => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(key, c)); } return r; })
    .catch(() => caches.match(key)));
});

// Service worker: makes the app installable and lets it start offline.
// The page is fetched fresh when online (falls back to the cached copy); the map file is
// served from the cache. Other areas' maps (map-data-*.bin) are cached the first time they load. Bump VERSION whenever a map file changes so phones fetch the new map.
const VERSION = "v3";
const CACHE = "run-loops-" + VERSION, FONTS = "run-loops-fonts";
const SHELL = ["./", "manifest.webmanifest", "map-data.bin", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== FONTS).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET") return;
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    e.respondWith(caches.open(FONTS).then(async (c) => (await c.match(req)) || fetch(req).then((r) => { if (r.ok || r.type === "opaque") c.put(req, r.clone()); return r; })));
    return;
  }
  if (url.origin !== location.origin) return;
  if (req.mode === "navigate" || url.pathname.endsWith("/index.html")) {
    // network first, so a new version shows up on the next launch
    e.respondWith(fetch(req).then((r) => { if (r.ok) caches.open(CACHE).then((c) => c.put("./", r.clone())); return r; })
      .catch(() => caches.match("./", { ignoreSearch: true })));
    return;
  }
  e.respondWith(caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
    return r;
  })));
});

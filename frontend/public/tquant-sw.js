const CACHE_NAME = "tquant-static-v3";
const SAFE_ASSET = /\.(?:js|css|png|svg|ico|webp|woff2?|webmanifest)$/i;
const APP_SHELL = ["/", "/offline.html", "/offline.css", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(() => undefined))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request, { cache: "no-store" }));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(navigationFallback(request));
    return;
  }
  if (!SAFE_ASSET.test(url.pathname)) return;
  event.respondWith(cacheFirst(request));
});

async function navigationFallback(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    if (response.ok) {
      cache.put("/", response.clone());
    }
    return response;
  } catch {
    const cache = await caches.open(CACHE_NAME);
    return (await cache.match(request)) || (await cache.match("/")) || (await cache.match("/offline.html"));
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

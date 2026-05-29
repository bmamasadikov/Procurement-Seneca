const CACHE_NAME = "sentask-static-v1";
const CACHEABLE_PATH_PREFIXES = [
  "/_next/static/",
  "/pwa/icon-192",
  "/pwa/icon-512",
];
const CACHEABLE_PATHS = new Set([
  "/manifest.webmanifest",
  "/favicon.ico",
]);

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isCacheable =
    CACHEABLE_PATHS.has(url.pathname) ||
    CACHEABLE_PATH_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));

  if (!isCacheable) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;

      return fetch(request).then((response) => {
        if (!response.ok) return response;

        const responseClone = response.clone();
        void caches.open(CACHE_NAME).then((cache) => {
          void cache.put(request, responseClone);
        });

        return response;
      });
    })
  );
});

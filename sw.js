/* Service Worker: оффлайн и мгновенная повторная загрузка.
   Стратегии:
   - навигация и data/*.json — сеть, при сбое кэш (данные всегда свежие);
   - остальное (app.js, style.css, постеры) — кэш, при отсутствии — сеть.
     Версионные ссылки (app.js?v=N) при апдейте приходят свежими: URL меняется. */
const CACHE = "movie-site-v1";
const POSTER_LIMIT = 400; // не раздуваем кэш постеров бесконечно

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(["./", "manifest.webmanifest"])).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function trimPosters(cacheName) {
  const c = await caches.open(cacheName);
  const keys = await c.keys();
  if (keys.length <= POSTER_LIMIT) return;
  for (const key of keys.slice(0, keys.length - POSTER_LIMIT)) await c.delete(key);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // Чужие домены (прокси картинок) не перехватываем — у них свой HTTP-кэш
  if (url.origin !== location.origin) return;

  const freshFirst = req.mode === "navigate" || url.pathname.includes("/data/");
  if (freshFirst) {
    e.respondWith(
      fetch(req)
        .then((r) => {
          if (r.ok) {
            const copy = r.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return r;
        })
        .catch(() =>
          caches
            .match(req, { ignoreSearch: true })
            .then((hit) => hit || caches.match("./", { ignoreSearch: true }))
        )
    );
    return;
  }

  // Картинки и статика: кэш первым
  e.respondWith(
    caches.match(req).then((hit) => {
      if (hit) return hit;
      return fetch(req).then((r) => {
        if (r.ok && url.pathname.includes("/posters/")) {
          const copy = r.clone();
          caches.open(CACHE).then((c) => {
            c.put(req, copy);
            trimPosters(CACHE);
          });
        }
        return r;
      });
    })
  );
});

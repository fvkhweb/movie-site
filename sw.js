/* Service Worker: офлайн и мгновенная повторная загрузка.
   Стратегии:
   - навигация и data/*.json — сеть, при сбое кэш (данные всегда свежие);
   - статика (app.js, style.css, шрифты, иконки) — stale-while-revalidate;
   - постеры — stale-while-revalidate: сразу из кэша, обновление в фоне.
   Кэш статики чистится только по постерам, служебные файлы не трогаем. */
const CACHE = "movie-site-v2";
const POSTER_LIMIT = 400;
const NAV_TIMEOUT = 5000;

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      // Кэшируем оболочку: index.html и всё, что он подключает.
      // Ошибка одного файла не должна ломать установку SW.
      try {
        const res = await fetch("./", { cache: "no-cache" });
        if (res.ok) {
          await cache.put("./", res.clone());
          const html = await res.text();
          const urls = [...html.matchAll(/(?:src|href)\s*=\s*["']([^"']+)["']/g)]
            .map((m) => m[1])
            .filter((u) => u && !u.startsWith("#") && !u.startsWith("data:") && !u.startsWith("javascript:") && !u.startsWith("mailto:") && !u.startsWith("http") && !u.startsWith("//"))
            .map((u) => new URL(u, self.location.href).href);
          // reload — чтобы не поймать старую версию из HTTP-кэша.
          await Promise.allSettled(urls.map((u) => cache.add(new Request(u, { cache: "reload" }))));
        }
      } catch {
        // Первый запуск без сети: оболочку докачаем при следующем визите.
      }
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      // На fvkhweb.github.io живут и другие проекты: чистим только свои кэши.
      await Promise.all(
        keys.filter((k) => k.startsWith("movie-site-") && k !== CACHE).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

function isPoster(url) {
  return url.pathname.includes("/posters/");
}

async function trimPosters() {
  const cache = await caches.open(CACHE);
  const keys = (await cache.keys()).filter((req) => isPoster(new URL(req.url)));
  if (keys.length <= POSTER_LIMIT) return;
  // Удаляем самые старые постеры, не считая остальную статику.
  for (const req of keys.slice(0, keys.length - POSTER_LIMIT)) {
    await cache.delete(req);
  }
}

async function put(cache, request, response) {
  try {
    await cache.put(request, response);
  } catch {
    // Квота или opaque-ответ — не роняем запрос из-за кэша.
  }
}

function timeout(ms) {
  return new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), ms));
}

async function networkFirst(request, fallbackUrl, timeoutMs = 0) {
  const cache = await caches.open(CACHE);
  try {
    const network = fetch(request);
    // Таймаут только для навигации: данные (2 МБ) на слабой сети качаются дольше.
    const response = timeoutMs > 0 ? await Promise.race([network, timeout(timeoutMs)]) : await network;
    if (response && response.ok) await put(cache, request, response.clone());
    return response;
  } catch {
    const hit = await cache.match(request, { ignoreSearch: true });
    if (hit) return hit;
    if (fallbackUrl) {
      const fallback = await cache.match(fallbackUrl, { ignoreSearch: true });
      if (fallback) return fallback;
    }
    return new Response("Нет соединения", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

async function cacheFirst(request, revalidate) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(request);
  if (hit) {
    if (revalidate) {
      // Постеры обновляем в фоне: старый отдаём сразу, новый кладём в кэш.
      fetch(request)
        .then((response) => {
          if (response && response.ok) return put(cache, request, response);
        })
        .catch(() => {});
    }
    return hit;
  }

  try {
    const response = await fetch(request);
    if (response && response.ok) {
      await put(cache, request, response.clone());
      if (isPoster(new URL(request.url))) trimPosters().catch(() => {});
    }
    return response;
  } catch {
    return new Response("", { status: 504 });
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  // Чужие домены (прокси картинок) не перехватываем — у них свой HTTP-кэш
  if (url.origin !== location.origin) return;

  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req, "./", NAV_TIMEOUT));
    return;
  }

  if (url.pathname.includes("/data/")) {
    event.respondWith(networkFirst(req));
    return;
  }

  // APK и latest.json не кэшируем: обновление должно всегда идти в сеть.
  if (url.pathname.includes("/app/")) return;

  // Статика и постеры — stale-while-revalidate: страница не ждёт сеть,
  // а свежая версия подтягивается в фоне. Это спасает и от забытого ?v=.
  event.respondWith(cacheFirst(req, true));
});

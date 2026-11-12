import os, json, time, re, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
POISKKINO_API_KEY = os.environ.get("POISKKINO_API_KEY", "")

TMDB_BASE = "https://api.themoviedb.org/3"
# Прокси-шаблон только для локальной отладки (на Actions не задаётся),
# например: https://api.allorigins.win/raw?url={url}
TMDB_PROXY_TEMPLATE = os.environ.get("TMDB_PROXY_TEMPLATE", "")

IMG_SIZE = "w500"
POSTERS_DIR = "posters"
IMG_SOURCES = [
    "https://image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
    "https://imagetmdb.com/t/p/" + IMG_SIZE + "{path}",
    "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
]
IMG_MIRROR = "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE

KP_BASE = "https://api.kinopoisk.dev/v1.4/movie"
# Пул ключей: в секрет можно вписать несколько через запятую
KP_DEV_KEYS = [k.strip() for k in os.environ.get("POISKKINO_API_KEY", "").replace(";", ",").split(",") if k.strip()]
KP_HEADERS = {"X-API-KEY": KP_DEV_KEYS[0] if KP_DEV_KEYS else ""}
# У бесплатного тарифа ~200 запросов/сутки, по 2 на фильм; запас — 90 фильмов на ключ
KP_MAX_MOVIES = int(os.environ.get("KP_MAX_MOVIES", str(90 * max(1, len(KP_DEV_KEYS)))))

# Второй источник — Kinopoisk Unofficial (kinopoiskapiunofficial.tech),
# ~500 запросов/сутки на каждый ключ. Дополняет тот, у кого лимит не выбрался,
# и даёт интересные факты и кадры из фильмов.
KPU_API_KEYS = [k.strip() for k in os.environ.get("KP_UNOFFICIAL_API_KEY", "").replace(";", ",").split(",") if k.strip()]
KPU_ROOT = "https://kinopoiskapiunofficial.tech/api"
# ~120 фильмов на ключ (поиск + детали + кадры)
UNOFFICIAL_MAX_MOVIES = int(os.environ.get("UNOFFICIAL_MAX_MOVIES", str(120 * max(1, len(KPU_API_KEYS)))))
KPU_STATE = {"idx": 0, "exhausted": set(), "premium_logged": set()}

POPULAR_PAGES = int(os.environ.get("POPULAR_PAGES", "20"))
TOP_PAGES = int(os.environ.get("TOP_PAGES", "20"))
GENRE_PAGES = int(os.environ.get("GENRE_PAGES", "6"))
API_WORKERS = int(os.environ.get("API_WORKERS", "8"))
DOWNLOAD_WORKERS = int(os.environ.get("DOWNLOAD_WORKERS", "8"))
TEST_LIMIT = int(os.environ.get("LIMIT_MOVIES", "0"))  # >0 — только для локального теста

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


def tmdb_get(path, params=None):
    p = {"api_key": TMDB_API_KEY, "language": "ru-RU", **(params or {})}
    url = f"{TMDB_BASE}{path}"
    for attempt in range(3):
        try:
            if TMDB_PROXY_TEMPLATE:
                r = session.get(TMDB_PROXY_TEMPLATE.format(url=quote(url + "?" +
                                "&".join(f"{k}={quote(str(v))}" for k, v in p.items()))), timeout=40)
            else:
                r = session.get(url, params=p, timeout=40)
            if r.status_code == 200:
                return r.json()
            print(f"  TMDB {path}: HTTP {r.status_code} (попытка {attempt + 1})")
        except Exception as e:
            print(f"  TMDB {path}: {e} (попытка {attempt + 1})")
        time.sleep(1.5 * (attempt + 1))
    return None


def collect_candidates():
    """Список фильмов: популярное + топ + лучшее по каждому жанру."""
    found = {}  # id -> запись из списка (с popularity)
    order_popular, order_top = [], []

    for page in range(1, POPULAR_PAGES + 1):
        data = tmdb_get("/movie/popular", {"page": page})
        if not data:
            break
        for m in data.get("results", []):
            m["_popularity"] = m.get("popularity", 0)
            found[m["id"]] = m
            if len(order_popular) < 60:
                order_popular.append(m["id"])
        print(f"popular: страница {page}, всего {len(found)}")

    for page in range(1, TOP_PAGES + 1):
        data = tmdb_get("/movie/top_rated", {"page": page})
        if not data:
            break
        for m in data.get("results", []):
            m["_popularity"] = m.get("popularity", 0)
            found.setdefault(m["id"], m)
            if len(order_top) < 60:
                order_top.append(m["id"])
        print(f"top_rated: страница {page}, всего {len(found)}")

    genre_list = tmdb_get("/genre/movie/list") or {}
    genres = genre_list.get("genres", [])
    by_genre = {}
    for g in genres:
        ids = []
        for page in range(1, GENRE_PAGES + 1):
            data = tmdb_get("/discover/movie", {
                "with_genres": g["id"], "sort_by": "popularity.desc",
                "vote_count.gte": 200, "include_adult": "false", "page": page,
            })
            if not data:
                break
            for m in data.get("results", []):
                m["_popularity"] = m.get("popularity", 0)
                found.setdefault(m["id"], m)
                ids.append(m["id"])
            print(f"жанр {g['name']}: страница {page}, всего {len(found)}")
        by_genre[str(g["id"])] = ids

    lists = {
        "popular": order_popular,
        "top_rated": order_top,
        "by_genre": by_genre,
    }
    return list(found.values()), genres, lists


def enrich_movie(m):
    """Детали + актёры TMDB для одного фильма."""
    details = tmdb_get(f"/movie/{m['id']}") or {}
    credits = tmdb_get(f"/movie/{m['id']}/credits") or {}

    release = details.get("release_date") or ""
    cast = []
    for c in (credits.get("cast") or [])[:8]:
        cast.append({
            "id": c.get("id") or 0,
            "name": c.get("name", ""),
            "character": c.get("character", ""),
            "photo": c.get("profile_path") or "",
        })

    return {
        "id": m["id"],
        "title": details.get("title") or m.get("title", ""),
        "original_title": details.get("original_title") or "",
        "year": release[:4],
        "rating": round(details.get("vote_average") or 0, 1),
        "popularity": round(m.get("_popularity", 0), 1),
        "runtime": details.get("runtime") or 0,
        "genres": [g["id"] for g in details.get("genres", [])],
        "countries": [c.get("name", "") for c in details.get("production_countries", [])],
        "poster_path": details.get("poster_path") or "",
        "backdrop": details.get("backdrop_path") or "",
        "description": details.get("overview") or "",
        "cast": cast,
        "similar": get_recommendations(m["id"]),
        "trailer": get_trailer(m["id"]),
    }


def get_kp_unofficial(title, year):
    """Резервный источник данных о фильме: Kinopoisk Unofficial API.
    Формат поиска v2.2: {"total": N, "items": [...]} с полем kinopoiskId."""
    if not KPU_API_KEYS:
        return None
    try:
        params = {"keyword": title}
        if year and str(year).isdigit():
            params["yearFrom"] = year
            params["yearTo"] = year

        r = kpu_get("v2.2/films", params)
        if r is None or r.status_code != 200:
            hint = {401: "неверный ключ KP_UNOFFICIAL_API_KEY",
                    402: "лимит ключа исчерпан",
                    403: "метод недоступен на тарифе"}.get(r.status_code if r else 0, "")
            print(f"  КП-Unofficial поиск '{title}': HTTP {r.status_code if r else 'нет ключей'} {hint}")
            return None

        data = r.json()
        films = data.get("films") or data.get("items") or []
        if not films:
            return None

        f = films[0]
        film_id = f.get("filmId") or f.get("kinopoiskId")
        poster = f.get("posterUrl") or f.get("posterUrlPreview") or ""
        description = f.get("description")
        rating = f.get("ratingKinopoisk") or f.get("rating")

        time.sleep(0.2)
        # Детали пробуем в двух версиях API: v2.2 отдаёт объект напрямую,
        # v2.1 оборачивает его в {"data": {...}}
        details_data = None
        for ver in ("v2.2", "v2.1"):
            d = kpu_get(f"{ver}/films/{film_id}")
            if d is None:
                break
            if d.status_code == 200:
                det = d.json()
                details_data = det.get("data") if isinstance(det.get("data"), dict) else det
                break
        if details_data:
            description = details_data.get("description") or description
            poster = details_data.get("posterUrl") or poster
            rating = details_data.get("ratingKinopoisk") or rating

        facts = []
        time.sleep(0.2)
        for ver in ("v2.2", "v2.1"):
            fr = kpu_get(f"{ver}/films/{film_id}/facts")
            if fr is None:
                break
            if fr.status_code == 200:
                items = fr.json().get("items") or []
                facts = [
                    re.sub(r"<[^>]+>", "", i.get("text") or "").strip()
                    for i in items
                    if i.get("text")
                ][:3]
                if facts:
                    break
        return {
            "poster": poster,
            "description": description,
            "kp_rating": rating,
            "facts": facts,
            "film_id": film_id,
        }
    except Exception as e:
        print(f"  КП-Unofficial ошибка для '{title}': {e}")
    return None


def kpu_get(path, params=None):
    """Запрос к Kinopoisk Unofficial с ротацией ключей.
    402/429 — лимит ключа: переключаемся на следующий.
    403 — метод недоступен на тарифе: просто пропускаем (ключ не тратим)."""
    if not KPU_API_KEYS:
        return None

    while True:
        idx = KPU_STATE["idx"]
        try:
            r = session.get(f"{KPU_ROOT}/{path}", headers={"X-API-KEY": KPU_API_KEYS[idx]},
                            params=params, timeout=15)
        except Exception as e:
            print(f"  КП-Unofficial {path}: {e}")
            return None

        if r.status_code in (402, 429):
            KPU_STATE["exhausted"].add(idx)
            rest = [i for i in range(len(KPU_API_KEYS)) if i not in KPU_STATE["exhausted"]]
            if not rest:
                print(f"  КП-Unofficial: все ключи исчерпаны")
                return r
            KPU_STATE["idx"] = rest[0]
            continue

        if r.status_code == 403 and "premium" not in KPU_STATE["premium_logged"]:
            KPU_STATE["premium_logged"].add("premium")
            print("  КП-Unofficial: метод недоступен на бесплатном тарифе (403)")
        return r


def get_kp_frame(kp_id):
    """Кадр из фильма через Kinopoisk Unofficial v2.1 (картинки на Яндекс.CDN —
    открываются из РФ без VPN и прокси). Ответ: {"frames": [{"image", "preview"}]}."""
    if not KPU_API_KEYS or not kp_id:
        return ""
    r = kpu_get(f"v2.1/films/{kp_id}/frames")
    if r is None:
        return ""
    if r.status_code == 200:
        frames = r.json().get("frames") or []
        if frames and frames[0].get("image"):
            return frames[0]["image"]
    return ""


def get_recommendations(movie_id):
    """Похожие фильмы из TMDB (id, только те, у кого есть постер)."""
    data = tmdb_get(f"/movie/{movie_id}/recommendations") or {}
    return [r["id"] for r in data.get("results", [])[:8] if r.get("poster_path")][:6]


def get_trailer(movie_id):
    """Ключ YouTube-трейлера из TMDB (сначала русский, потом английский)."""
    for lang in ("ru-RU", "en-US"):
        data = tmdb_get(f"/movie/{movie_id}/videos", {"language": lang}) or {}
        vids = [v for v in data.get("results", []) if v.get("site") == "YouTube" and v.get("key")]
        if vids:
            best = (
                [v for v in vids if v.get("official") and v.get("type") == "Trailer"]
                or [v for v in vids if v.get("type") == "Trailer"]
                or vids
            )
            return best[0]["key"]
    return ""


# Пул ключей для kinopoisk.dev с ротацией при исчерпании лимита
DEV_STATE = {"idx": 0, "exhausted": set()}


def kp_dev_get(path, params=None):
    if not KP_DEV_KEYS:
        return None
    while True:
        idx = DEV_STATE["idx"]
        try:
            r = session.get(f"{KP_BASE}{path}", headers={"X-API-KEY": KP_DEV_KEYS[idx]},
                            params=params, timeout=15)
        except Exception as e:
            print(f"  КП-dev {path}: {e}")
            return None
        if r.status_code in (402, 429, 403) and len(KP_DEV_KEYS) > 1:
            # У kinopoisk.dev 403 = лимит исчерпан; 401 = неверный ключ (не ротируем)
            rest = [i for i in range(len(KP_DEV_KEYS)) if i not in DEV_STATE["exhausted"]]
            if not rest:
                return r
            DEV_STATE["exhausted"].add(idx)
            DEV_STATE["idx"] = rest[0]
            continue
        return r


def get_kp_data(title, year):
    if not KP_DEV_KEYS:
        return None
    try:
        params = {"query": title, "limit": 1}
        if year and str(year).isdigit():
            params["year"] = year

        time.sleep(0.3)
        r = kp_dev_get("/search", params)
        if r is None or r.status_code != 200:
            print(f"  КП поиск '{title}': HTTP {r.status_code if r else 'нет ключей'}")
            return None

        docs = r.json().get("docs", [])
        if not docs:
            return None

        movie = docs[0]
        kp_id = movie["id"]
        poster = (movie.get("poster") or {}).get("url") or (movie.get("poster") or {}).get("previewUrl")
        time.sleep(0.3)
        d_resp = kp_dev_get(f"/{kp_id}")
        if d_resp is None or d_resp.status_code != 200:
            print(f"  КП детали {kp_id}: HTTP {d_resp.status_code}")
            return {
                "poster": poster,
                "description": movie.get("description"),
                "kp_rating": (movie.get("rating") or {}).get("kp"),
            }

        details = d_resp.json()
        return {
            # Постер Кинопоиска лежит на Яндекс.CDN и открывается из РФ
            "poster": (details.get("poster") or {}).get("url") or poster,
            "description": details.get("description") or movie.get("description"),
            "kp_rating": (details.get("rating") or {}).get("kp"),
            "kp_id": kp_id,
        }
    except Exception as e:
        print(f"  КП ошибка для '{title}': {e}")
    return None


def download_poster(movie_id, poster_path):
    if not poster_path:
        return ""
    os.makedirs(POSTERS_DIR, exist_ok=True)
    local_path = os.path.join(POSTERS_DIR, f"{movie_id}.jpg").replace("\\", "/")

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return local_path

    for template in IMG_SOURCES:
        url = template.format(path=poster_path)
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000 and \
                    r.headers.get("Content-Type", "").startswith("image"):
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return local_path
            print(f"  постер: {url} -> {r.status_code}")
        except Exception as e:
            print(f"  постер: {url} -> ошибка: {e}")
    return ""


def build_catalog():
    candidates, genres, lists = collect_candidates()

    movies_raw = []
    with ThreadPoolExecutor(max_workers=API_WORKERS) as ex:
        futures = [ex.submit(enrich_movie, m) for m in candidates]
        done = 0
        for f in as_completed(futures):
            movies_raw.append(f.result())
            done += 1
            if done % 100 == 0:
                print(f"детали: {done}/{len(candidates)}")

    # Кинопоиск — обогащение двух источников по убыванию популярности:
    # сначала kinopoisk.dev, затем Kinopoisk Unofficial (факты + резерв).
    movies_raw.sort(key=lambda m: m["popularity"], reverse=True)
    kp_ids = {}  # tmdb_id -> id Кинопоиска (для кадров)
    for m in movies_raw[:KP_MAX_MOVIES]:
        kp = get_kp_data(m["title"], m["year"])
        if kp:
            if kp.get("kp_id"):
                kp_ids[m["id"]] = kp["kp_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
            if kp.get("kp_rating"):
                m["kp_rating"] = round(kp["kp_rating"], 1)
            if kp.get("poster"):
                m["poster_fallback"] = kp["poster"]
        time.sleep(0.3)

    for m in movies_raw[KP_MAX_MOVIES:KP_MAX_MOVIES + UNOFFICIAL_MAX_MOVIES]:
        kp = get_kp_unofficial(m["title"], m["year"])
        if kp:
            if kp.get("film_id"):
                kp_ids[m["id"]] = kp["film_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
            if kp.get("kp_rating"):
                m["kp_rating"] = round(kp["kp_rating"], 1)
            if kp.get("poster"):
                m["poster_fallback"] = kp["poster"]
            if kp.get("facts"):
                m["facts"] = kp["facts"]
        time.sleep(0.3)

    # Кадры из фильмов (Яндекс.CDN — работают из РФ без VPN)
    for m in movies_raw:
        frame = get_kp_frame(kp_ids.get(m["id"]))
        if frame:
            m["frame"] = frame
        time.sleep(0.2)

    # Постеры (параллельно)
    def job(m):
        m["poster"] = download_poster(m["id"], m["poster_path"])
        if not m.get("poster_fallback"):
            m["poster_fallback"] = IMG_MIRROR + m["poster_path"] if m["poster_path"] else ""
        return m

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
        movies = list(ex.map(job, movies_raw))
    print(f"постеры: {sum(1 for m in movies if m['poster'])}/{len(movies)}")

    # cast.json и индекс актёров собираем ДО чистки записей
    cast_map = {str(m["id"]): m.get("cast", []) for m in movies}

    # Индекс актёров для поиска по имени и страниц актёра
    people = {}
    for m in movies:
        for c in m.get("cast", []):
            key = str(c.get("id") or c["name"])
            person = people.setdefault(key, {"id": c.get("id") or 0, "name": c["name"], "photo": c["photo"], "movies": []})
            if m["id"] not in person["movies"]:
                person["movies"].append(m["id"])
            if c["photo"] and not person["photo"]:
                person["photo"] = c["photo"]

    # Чистые файлы данных
    for m in movies:
        m.pop("cast", None)
        m.pop("poster_path", None)
        m.pop("popularity", None)
        if not m.get("kp_rating"):
            m.pop("kp_rating", None)
        if not m.get("poster_fallback"):
            m.pop("poster_fallback", None)
        if not m.get("similar"):
            m.pop("similar", None)
        if not m.get("trailer"):
            m.pop("trailer", None)
        if not m.get("facts"):
            m.pop("facts", None)
        if not m.get("backdrop"):
            m.pop("backdrop", None)
        if not m.get("frame"):
            m.pop("frame", None)

    save("movies", movies)
    save("genres", genres)
    save("lists", lists)
    save("cast", cast_map)
    save("people", list(people.values()))

    print(f"=== ИТОГО: {len(movies)} фильмов, {len(people)} актёров ===")


def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    build_catalog()

import html as html_mod
import os, json, time, re, datetime, requests
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
# У бесплатного тарифа ~200 запросов/сутки, по 2 на фильм; запас — 90 фильмов на ключ
KP_MAX_MOVIES = int(os.environ.get("KP_MAX_MOVIES", str(90 * max(1, len(KP_DEV_KEYS)))))

# Второй источник — Kinopoisk Unofficial (kinopoiskapiunofficial.tech),
# ~500 запросов/сутки на каждый ключ. Дополняет тот, у кого лимит не выбрался,
# и даёт интересные факты и кадры из фильмов.
KPU_API_KEYS = [k.strip() for k in os.environ.get("KP_UNOFFICIAL_API_KEY", "").replace(";", ",").split(",") if k.strip()]
KPU_ROOT = "https://kinopoiskapiunofficial.tech/api"
# ~120 фильмов на ключ (поиск + детали + кадры)
UNOFFICIAL_MAX_MOVIES = int(os.environ.get("UNOFFICIAL_MAX_MOVIES", str(120 * max(1, len(KPU_API_KEYS)))))
KPU_PREMIUM_LOGGED = set()

# ── Импорт каталога из Кинопоиска ──────────────────────────────
# 0 — импорт выключен. Для теста запускать workflow вручную с import_limit=1000.
KP_IMPORT_LIMIT = int(os.environ.get("KP_IMPORT_LIMIT", "0"))
KP_IMPORT_SOURCE = os.environ.get("KP_IMPORT_SOURCE", "auto").strip().lower()
KP_IMPORT_RATING_FROM = float(os.environ.get("KP_IMPORT_RATING_FROM", "6.0"))
KP_IMPORT_VOTES_FROM = int(os.environ.get("KP_IMPORT_VOTES_FROM", "200"))
KP_IMPORT_YEAR_FROM = int(os.environ.get("KP_IMPORT_YEAR_FROM", "1950"))
KP_IMPORT_YEAR_TO = int(os.environ.get("KP_IMPORT_YEAR_TO", str(datetime.date.today().year)))
# KP-ID живут в отдельном диапазоне, чтобы не пересекаться с TMDB-ID.
KP_ID_OFFSET = 1_000_000_000
KP_FRAME_MAX = int(os.environ.get("KP_FRAME_MAX", "200"))
KP_STATE_FILE = "data/kp_state.json"
KP_COOLDOWN_DAYS = {
    "not_found": int(os.environ.get("KP_COOLDOWN_NOT_FOUND_DAYS", "14")),
    "no_facts": int(os.environ.get("KP_COOLDOWN_NO_FACTS_DAYS", "14")),
    "no_frame": int(os.environ.get("KP_COOLDOWN_NO_FRAME_DAYS", "14")),
    "error": int(os.environ.get("KP_COOLDOWN_ERROR_DAYS", "1")),
}

# Соответствие жанров Кинопоиска жанрам TMDB, которые уже есть в genres.json.
KP_GENRE_MAP = {
    "боевик": 28,
    "приключения": 12,
    "мультфильм": 16,
    "комедия": 35,
    "криминал": 80,
    "документальный": 99,
    "драма": 18,
    "семейный": 10751,
    "фэнтези": 14,
    "история": 36,
    "ужасы": 27,
    "музыка": 10402,
    "детектив": 9648,
    "мелодрама": 10749,
    "фантастика": 878,
    "телевизионный фильм": 10770,
    "триллер": 53,
    "военный": 10752,
    "вестерн": 37,
    # Этих жанров нет в TMDB отдельными id — кладём в ближайший.
    "биография": 36,
    "спорт": 18,
    "аниме": 16,
    "короткометражка": 18,
}

POPULAR_PAGES = int(os.environ.get("POPULAR_PAGES", "20"))
TOP_PAGES = int(os.environ.get("TOP_PAGES", "20"))
GENRE_PAGES = int(os.environ.get("GENRE_PAGES", "6"))
TRENDS_PAGES = int(os.environ.get("TRENDS_PAGES", "1"))  # «на слуху» — тренды недели (~20 фильмов)
UP_PAGES = int(os.environ.get("UP_PAGES", "8"))      # «скоро выйдут»
API_WORKERS = int(os.environ.get("API_WORKERS", "8"))
DOWNLOAD_WORKERS = int(os.environ.get("DOWNLOAD_WORKERS", "8"))
TEST_LIMIT = int(os.environ.get("LIMIT_MOVIES", "0"))  # >0 — только для локального теста

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


def mask_key(key):
    key = key or ""
    if len(key) <= 8:
        return key[:2] + "…"
    return key[:4] + "…" + key[-4:]


class KeyPool:
    """Пул ключей с round-robin и счётчиками запросов.

    Раньше код брал первый ключ и переключался на следующий только при
    исчерпании лимита. Из-за этого второй и третий ключи могли неделями
    показывать 0 запросов. Теперь ключи идут по кругу, а исчерпанные/битые
    временно исключаются из rotation.
    """

    def __init__(self, name, keys, exhaust_codes, invalid_codes=(401,)):
        self.name = name
        self.keys = list(keys)
        self.exhaust_codes = set(exhaust_codes)
        self.invalid_codes = set(invalid_codes)
        self._next = 0
        self.exhausted = set()
        self.invalid = set()
        self.requests = [0] * len(self.keys)
        self.success = [0] * len(self.keys)
        self.errors = [0] * len(self.keys)
        self.last_response = None

    def log_start(self):
        if not self.keys:
            print(f"{self.name}: ключей нет — источник выключен")
            return
        print(f"{self.name}: ключей {len(self.keys)}")
        for i, key in enumerate(self.keys):
            print(f"  #{i + 1}: {mask_key(key)}")

    def request(self, do_request):
        if not self.keys:
            return None
        n = len(self.keys)
        for offset in range(n):
            idx = (self._next + offset) % n
            if idx in self.exhausted or idx in self.invalid:
                continue
            self.requests[idx] += 1
            try:
                r = do_request(self.keys[idx])
            except Exception as e:
                self.errors[idx] += 1
                print(f"  {self.name} #{idx + 1}: {e}")
                continue
            if r is None:
                self.errors[idx] += 1
                continue
            self.last_response = r
            if r.status_code in self.invalid_codes:
                self.invalid.add(idx)
                self.errors[idx] += 1
                print(f"  {self.name} #{idx + 1}: HTTP {r.status_code} — ключ отключён")
                continue
            if r.status_code in self.exhaust_codes:
                self.exhausted.add(idx)
                print(f"  {self.name} #{idx + 1}: HTTP {r.status_code} — лимит, переключаюсь")
                continue
            self._next = (idx + 1) % n
            self.success[idx] += 1
            return r
        # Все ключи исчерпаны/отключены — отдаём последний ответ, чтобы
        # вызывающий код мог залогировать HTTP-статус.
        return self.last_response

    def log_stats(self):
        if not self.keys:
            print(f"{self.name}: запросов нет")
            return
        parts = [
            f"#{i + 1}={self.requests[i]} запр./{self.success[i]} ок/{self.errors[i]} ош"
            for i in range(len(self.keys))
        ]
        print(f"{self.name}: " + ", ".join(parts))


KPU_POOL = KeyPool("КП-Unofficial", KPU_API_KEYS, {402, 429})
DEV_POOL = KeyPool("КП-dev", KP_DEV_KEYS, {402, 429, 403})


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


def norm_title(s):
    """Название для сравнения: нижний регистр, ё→е, без пунктуации."""
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[^0-9a-zа-я]+", " ", s)
    return " ".join(s.split())


def titles_match(a, b):
    """Названия совпадают или одно целиком входит в другое
    («Дюна» / «Дюна: Часть вторая»). Короткие строки — только точно."""
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return False
    if a == b:
        return True
    return len(a) >= 4 and len(b) >= 4 and (a in b or b in a)


def kp_candidate_ok(query_names, query_year, cand_names, cand_year):
    """Найденный на Кинопоиске фильм — тот же самый?
    Название должно совпасть хотя бы по одному варианту (русский/оригинал),
    год — с точностью до года (перезапуски и тёзки отсеиваются)."""
    if not any(titles_match(q, c) for q in query_names if q for c in cand_names if c):
        return False
    try:
        qy = int(str(query_year)[:4])
        cy = int(str(cand_year)[:4])
    except (TypeError, ValueError):
        return True  # года нет — доверяем названию
    return abs(qy - cy) <= 1


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

    # «На слуху сейчас» и «Скоро в кино» — тренды недели и анонсы TMDB.
    # Тянем их ПЕРВЫМИ, до тяжёлого обхода жанров: если API начнёт
    # лимитировать, самые видимые панели главной не останутся пустыми.
    # Тренды ≠ популярное: «popular» — всевременная известность,
    # «trending/week» — то, о чём реально говорят на этой неделе.
    now_ids, up_ids = [], []
    today = datetime.date.today().isoformat()
    for page in range(1, TRENDS_PAGES + 1):
        data = tmdb_get("/trending/movie/week", {"page": page})
        if not data:
            break
        for m in data.get("results", []):
            m["_popularity"] = m.get("popularity", 0)
            found.setdefault(m["id"], m)
            now_ids.append(m["id"])
        print(f"тренды недели: страница {page}, всего {len(found)}")

    # Анонсы: /movie/upcoming почти целиком состоит из залёжавшихся дат,
    # поэтому берём /discover с датой от сегодняшнего дня и вперёд на 90 дней.
    for page in range(1, UP_PAGES + 1):
        data = tmdb_get("/discover/movie", {
            "include_adult": "false",
            "primary_release_date.gte": today,
            "primary_release_date.lte": (datetime.date.today() + datetime.timedelta(days=90)).isoformat(),
            "sort_by": "popularity.desc",
            "page": page,
        })
        if not data:
            break
        for m in data.get("results", []):
            # На всякий случай фильтруем и тут: discover иногда подсовывает
            # фильменты с датой в прошлом
            if (m.get("release_date") or "") < today:
                continue
            m["_popularity"] = m.get("popularity", 0)
            found.setdefault(m["id"], m)
            up_ids.append(m["id"])
        print(f"скоро: страница {page}, всего {len(up_ids)}")
    # Ближайшие премьеры — первыми
    up_ids.sort(key=lambda mid: (found[mid].get("release_date") or "9999-99-99"))

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
        "now_playing": now_ids,  # тренды недели («на слуху сейчас»)
        "upcoming": up_ids,
    }

    return list(found.values()), genres, lists


def enrich_movie(m):
    """Детали + актёры TMDB для одного фильма."""
    details = tmdb_get(f"/movie/{m['id']}") or {}
    credits = tmdb_get(f"/movie/{m['id']}/credits") or {}

    release = details.get("release_date") or ""
    # Режиссёр из съёмочной группы (может быть несколько — соединяем)
    director = ", ".join(
        c.get("name", "") for c in (credits.get("crew") or []) if c.get("job") == "Director"
    )[:120]
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
        "release_date": release,
        "director": director,
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


def get_kp_unofficial(title, year, original_title=""):
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
            return {"error": True}

        data = r.json()
        films = data.get("films") or data.get("items") or []
        if not films:
            return None

        # Первый результат может быть другим фильмом (тёзка, ремейк) —
        # берём только запись, совпавшую по названию и году
        query_names = [title, original_title]
        f = next(
            (x for x in films if kp_candidate_ok(
                query_names, year,
                [x.get("nameRu"), x.get("nameEn"), x.get("nameOriginal")],
                x.get("year"),
            )),
            None,
        )
        if not f:
            print(f"  КП-Unofficial '{title}' ({year}): нет совпадения среди {len(films)} результатов")
            return None
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

        time.sleep(0.2)
        facts = get_kp_facts(film_id)
        return {
            "poster": poster,
            "description": description,
            "kp_rating": rating,
            "facts": facts,
            "film_id": film_id,
        }
    except Exception as e:
        print(f"  КП-Unofficial ошибка для '{title}': {e}")
        return {"error": True}
    return None


def kpu_get(path, params=None):
    """Запрос к Kinopoisk Unofficial с round-robin по ключам.

    402/429 — лимит ключа: исключаем его до конца прогона.
    403 — метод недоступен на тарифе: это ответ, а не проблема ключа,
    поэтому ключ не отключаем.
    """
    if not KPU_API_KEYS:
        return None

    def do_request(key):
        return session.get(
            f"{KPU_ROOT}/{path}",
            headers={"X-API-KEY": key},
            params=params,
            timeout=15,
        )

    r = KPU_POOL.request(do_request)
    if r is not None and r.status_code == 403 and "premium" not in KPU_PREMIUM_LOGGED:
        KPU_PREMIUM_LOGGED.add("premium")
        print("  КП-Unofficial: метод недоступен на бесплатном тарифе (403)")
    return r


def get_kp_facts(kp_id):
    """Факты по известному id Кинопоиска — без поиска и деталей."""
    if not KPU_API_KEYS or not kp_id:
        return []
    for ver in ("v2.2", "v2.1"):
        fr = kpu_get(f"{ver}/films/{kp_id}/facts")
        if fr is None:
            return []
        if fr.status_code == 200:
            items = fr.json().get("items") or []
            facts = [
                html_mod.unescape(re.sub(r"<[^>]+>", "", i.get("text") or "")).strip()
                for i in items
                if i.get("text")
            ][:3]
            if facts:
                return facts
    return []


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
def kp_dev_get(path, params=None):
    """Запрос к kinopoisk.dev с round-robin по ключам.

    У kinopoisk.dev 403 = лимит исчерпан, 401 = неверный ключ.
    """
    if not KP_DEV_KEYS:
        return None

    def do_request(key):
        return session.get(
            f"{KP_BASE}{path}",
            headers={"X-API-KEY": key},
            params=params,
            timeout=15,
        )

    return DEV_POOL.request(do_request)


def get_kp_data(title, year, original_title=""):
    if not KP_DEV_KEYS:
        return None
    try:
        params = {"query": title, "limit": 5}
        if year and str(year).isdigit():
            params["year"] = year

        time.sleep(0.3)
        r = kp_dev_get("/search", params)
        if r is None or r.status_code != 200:
            print(f"  КП поиск '{title}': HTTP {r.status_code if r else 'нет ключей'}")
            return {"error": True}

        docs = r.json().get("docs", [])
        if not docs:
            return None

        # Первый результат может быть другим фильмом (тёзка, ремейк, кривой
        # матч) — берём только запись, совпавшую по названию и году
        query_names = [title, original_title]
        movie = next(
            (d for d in docs if kp_candidate_ok(
                query_names, year,
                [d.get("name"), d.get("alternativeName"), d.get("enName")],
                d.get("year"),
            )),
            None,
        )
        if not movie:
            print(f"  КП '{title}' ({year}): нет совпадения среди {len(docs)} результатов")
            return None
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
                "kp_id": kp_id,
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
        return {"error": True}
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


def load_old(name):
    """Вчерашние данные из репозитория (для накопления базы)."""
    try:
        with open(f"data/{name}.json", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# В русских обзорах TMDB иногда лежит текст совсем другого фильма
# (правки пользователей). Автоматически такое не отличить: у триллеров
# и документалок про насилие лексика похожая, но текст верный.
# Поэтому — список подтверждённых вручную id + предупреждения в лог
# для новых случаев (искать в логе «проверить описание»).
BAD_DESC_IDS = {155, 1096228}  # «Тёмный рыцарь», «Маск»
SUSPECT_DESC_RE = re.compile(r"сексуальн|порн|рабын|изнасил|эротич", re.I)


def desc_suspicious(m):
    return m["id"] in BAD_DESC_IDS


def get_en_overview(movie_id):
    details = tmdb_get(f"/movie/{movie_id}", {"language": "en-US"}) or {}
    return (details.get("overview") or "").strip()


# ── Состояние Кинопоиска: cooldown повторных попыток ─────────────

def load_kp_state():
    try:
        with open(KP_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("films"), dict):
            return data
    except Exception:
        pass
    return {"version": 1, "films": {}}


def save_kp_state(state):
    os.makedirs("data", exist_ok=True)
    with open(KP_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def kp_state_key(movie, status):
    # Один фильм может ждать сразу несколько задач: поиск, факты, кадр.
    # Ключ с задачей не даёт успеху в одной задаче сбросить cooldown другой.
    return f"{movie.get('id')}:{status}"


def kp_should_skip(state, movie, status):
    entry = state.get("films", {}).get(kp_state_key(movie, status))
    if not entry:
        return False
    try:
        last = datetime.date.fromisoformat(str(entry.get("last_try"))[:10])
    except Exception:
        return False
    return (datetime.date.today() - last).days < KP_COOLDOWN_DAYS.get(status, 0)


def kp_mark(state, movie, status):
    state.setdefault("films", {})[kp_state_key(movie, status)] = {
        "last_try": datetime.date.today().isoformat(),
    }


def kp_clear(state, movie, status):
    state.setdefault("films", {}).pop(kp_state_key(movie, status), None)


def prune_kp_state(state, movies):
    valid = {str(m.get("id")) for m in movies}
    state["films"] = {
        key: value for key, value in state.get("films", {}).items()
        if key.split(":", 1)[0] in valid
    }


# ── Импорт каталога из Кинопоиска ────────────────────────────────

def clean_text(value):
    if not value:
        return ""
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", str(value))).strip()


def norm_year(value):
    try:
        year = int(str(value)[:4])
    except (TypeError, ValueError):
        return None
    if 1880 <= year <= datetime.date.today().year + 5:
        return year
    return None


def kp_genres(items):
    result = []
    for item in items or []:
        name = item.get("name") if isinstance(item, dict) else item
        gid = KP_GENRE_MAP.get(str(name or "").strip().lower())
        if gid and gid not in result:
            result.append(gid)
    return result


def kp_countries(items):
    result = []
    for item in items or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(item, dict):
            name = name or item.get("country")
        name = str(name or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def kp_release_date(premiere, year):
    if isinstance(premiere, dict):
        for key in ("world", "russia", "digital", "dvd", "bluRay"):
            value = premiere.get(key)
            if value:
                return str(value)[:10]
    return f"{year}-01-01" if year else ""


def kp_pseudo_popularity(rating, votes):
    """Псевдо-popularity для сортировки каталога.

    KP-фильмы не должны лезть в топ главной (там TMDB), поэтому значение
    держим в диапазоне примерно 0–50, ниже топовых TMDB-фильмов.
    """
    try:
        rating = float(rating or 0)
        votes = float(votes or 0)
    except (TypeError, ValueError):
        return 0.0
    if rating <= 0:
        return 0.0
    return round(rating * (1 + min(4.0, (votes / 10000.0) ** 0.5)), 1)


def index_movie(index, movie):
    year = norm_year(movie.get("year") or (movie.get("release_date") or "")[:4])
    if not year:
        return
    for title in (movie.get("title"), movie.get("original_title")):
        normalized = norm_title(title)
        if normalized:
            index.add((normalized, year))


def build_existing_index(movies):
    index = set()
    for movie in movies:
        index_movie(index, movie)
    return index


def is_duplicate(movie, index):
    year = norm_year(movie.get("year") or (movie.get("release_date") or "")[:4])
    if not year:
        return False
    for title in (movie.get("title"), movie.get("original_title")):
        normalized = norm_title(title)
        if not normalized:
            continue
        if any((normalized, y) in index for y in (year - 1, year, year + 1)):
            return True
    return False


def kp_doc_to_movie(doc):
    """Карточка kinopoisk.dev -> наша схема movies.json."""
    kp_id = doc.get("id")
    if not kp_id:
        return None
    year = norm_year(doc.get("year"))
    title = clean_text(doc.get("name")) or clean_text(doc.get("alternativeName")) or clean_text(doc.get("enName"))
    if not title:
        return None
    poster = (doc.get("poster") or {}).get("url") or ""
    preview = (doc.get("poster") or {}).get("previewUrl") or poster
    if not poster:
        return None
    rating = (doc.get("rating") or {}).get("kp")
    votes = (doc.get("votes") or {}).get("kp")
    try:
        rating = round(float(rating), 1) if rating is not None else 0
    except (TypeError, ValueError):
        rating = 0
    try:
        runtime = int(doc.get("movieLength") or 0)
    except (TypeError, ValueError):
        runtime = 0
    return {
        "id": KP_ID_OFFSET + int(kp_id),
        "source": "kp",
        "kp_id": int(kp_id),
        "title": title,
        "original_title": clean_text(doc.get("alternativeName")) or clean_text(doc.get("enName")) or "",
        "year": str(year) if year else "",
        "release_date": kp_release_date(doc.get("premiere"), year),
        "rating": rating,
        "kp_rating": rating,
        "popularity": kp_pseudo_popularity(rating, votes),
        "runtime": runtime,
        "genres": kp_genres(doc.get("genres") or []),
        "countries": kp_countries(doc.get("countries") or []),
        "description": clean_text(doc.get("description")) or clean_text(doc.get("shortDescription")),
        "poster": poster,
        "poster_fallback": preview if preview != poster else "",
    }


def kpu_item_to_movie(item):
    """Карточка Kinopoisk Unofficial -> наша схема movies.json."""
    kp_id = item.get("kinopoiskId") or item.get("filmId")
    if not kp_id:
        return None
    year = norm_year(item.get("year"))
    title = clean_text(item.get("nameRu")) or clean_text(item.get("nameOriginal")) or clean_text(item.get("nameEn"))
    if not title:
        return None
    poster = item.get("posterUrl") or item.get("posterUrlPreview") or ""
    preview = item.get("posterUrlPreview") or poster
    if not poster:
        return None
    rating = item.get("ratingKinopoisk") or item.get("rating")
    votes = item.get("ratingKinopoiskVoteCount") or item.get("ratingVoteCount")
    try:
        rating = round(float(rating), 1) if rating is not None else 0
    except (TypeError, ValueError):
        rating = 0
    release = item.get("premiereRu") or item.get("premiereWorld") or ""
    return {
        "id": KP_ID_OFFSET + int(kp_id),
        "source": "kp",
        "kp_id": int(kp_id),
        "title": title,
        "original_title": clean_text(item.get("nameOriginal")) or clean_text(item.get("nameEn")) or "",
        "year": str(year) if year else "",
        "release_date": str(release)[:10] if release else (f"{year}-01-01" if year else ""),
        "rating": rating,
        "kp_rating": rating,
        "popularity": kp_pseudo_popularity(rating, votes),
        "runtime": 0,
        "genres": kp_genres(item.get("genres") or []),
        "countries": kp_countries(item.get("countries") or []),
        "description": clean_text(item.get("description")) or clean_text(item.get("shortDescription")),
        "poster": poster,
        "poster_fallback": preview if preview != poster else "",
    }


def import_from_dev(limit, index):
    if not KP_DEV_KEYS or limit <= 0:
        return []
    rating_from = KP_IMPORT_RATING_FROM
    votes_from = KP_IMPORT_VOTES_FROM
    queries = [
        {
            "sortField": "rating.kp", "sortType": "-1",
            "rating.kp": f"{rating_from}-10", "votes.kp": f"{votes_from}-100000000",
            "year": f"{KP_IMPORT_YEAR_FROM}-{KP_IMPORT_YEAR_TO}",
        },
        {
            "sortField": "votes.kp", "sortType": "-1",
            "rating.kp": f"{rating_from}-10", "votes.kp": f"{votes_from * 5}-100000000",
            "year": f"{KP_IMPORT_YEAR_FROM}-{KP_IMPORT_YEAR_TO}",
        },
        {
            "countries.name": "Россия", "sortField": "rating.kp", "sortType": "-1",
            "rating.kp": f"{max(5.0, rating_from - 0.5)}-10",
            "votes.kp": f"{max(50, votes_from // 2)}-100000000",
            "year": f"{KP_IMPORT_YEAR_FROM}-{KP_IMPORT_YEAR_TO}",
        },
    ]
    result = []
    seen = set()
    for query in queries:
        page = 1
        while len(result) < limit:
            params = {
                "page": page,
                "limit": 250,
                "selectFields": "id,name,alternativeName,enName,year,description,"
                                "shortDescription,movieLength,rating,votes,genres,"
                                "countries,poster,premiere",
                "notNullFields": "poster.url",
                "type": "movie",
                **query,
            }
            r = kp_dev_get("/movie", params)
            if r is None or r.status_code != 200:
                print(f"  КП-dev импорт: HTTP {r.status_code if r else 'нет ответа'}")
                break
            data = r.json()
            docs = data.get("docs") or []
            if not docs:
                break
            for doc in docs:
                if len(result) >= limit:
                    break
                movie = kp_doc_to_movie(doc)
                if not movie or movie["id"] in seen:
                    continue
                seen.add(movie["id"])
                # Уже известные фильмы не считаем: иначе повторный импорт
                # упрётся в первую страницу и не добавит ничего нового.
                if is_duplicate(movie, index):
                    continue
                result.append(movie)
                index_movie(index, movie)
            pages = data.get("pages") or 0
            print(f"  КП-dev импорт: страница {page}/{pages or '?'}, всего {len(result)}")
            if pages and page >= pages:
                break
            page += 1
            time.sleep(0.2)
        if len(result) >= limit:
            break
    return result


def import_from_unofficial(limit, index):
    if not KPU_API_KEYS or limit <= 0:
        return []
    result = []
    seen = set()
    page = 1
    while len(result) < limit:
        params = {
            "order": "RATING",
            "type": "FILM",
            "ratingFrom": KP_IMPORT_RATING_FROM,
            "ratingTo": 10,
            "yearFrom": KP_IMPORT_YEAR_FROM,
            "yearTo": KP_IMPORT_YEAR_TO,
            "page": page,
        }
        r = kpu_get("v2.2/films", params)
        if r is None or r.status_code != 200:
            print(f"  КП-Unofficial импорт: HTTP {r.status_code if r else 'нет ответа'}")
            break
        data = r.json()
        items = data.get("items") or data.get("films") or []
        if not items:
            break
        for item in items:
            if len(result) >= limit:
                break
            movie = kpu_item_to_movie(item)
            if not movie or movie["id"] in seen:
                continue
            seen.add(movie["id"])
            # Unofficial не умеет фильтровать по голосам — отсекаем сами,
            # иначе в базу попадёт малоизвестный фильм с парой оценок.
            if (movie.get("rating") or 0) < KP_IMPORT_RATING_FROM:
                continue
            votes = item.get("ratingKinopoiskVoteCount") or item.get("ratingVoteCount") or 0
            try:
                votes = int(votes)
            except (TypeError, ValueError):
                votes = 0
            if votes < KP_IMPORT_VOTES_FROM:
                continue
            if is_duplicate(movie, index):
                continue
            result.append(movie)
            index_movie(index, movie)
        total_pages = data.get("totalPages") or 0
        print(f"  КП-Unofficial импорт: страница {page}/{total_pages or '?'}, всего {len(result)}")
        if total_pages and page >= total_pages:
            break
        page += 1
        time.sleep(0.2)
    return result


def import_kp_movies(existing, limit):
    if limit <= 0:
        return []
    print(f"КП-импорт: цель {limit}, источник {KP_IMPORT_SOURCE}")
    # Индекс пополняется по ходу импорта: del сохраняет приоритет, а
    # unofficial получает только те фильмы, которых ещё нет в базе.
    existing_index = build_existing_index(existing)
    imported = []
    if KP_IMPORT_SOURCE in ("auto", "dev"):
        part = import_from_dev(limit, existing_index)
        print(f"КП-импорт dev: получено {len(part)}")
        imported.extend(part)
    if len(imported) < limit and KP_IMPORT_SOURCE in ("auto", "unofficial"):
        part = import_from_unofficial(limit - len(imported), existing_index)
        print(f"КП-импорт Unofficial: получено {len(part)}")
        imported.extend(part)

    unique = {movie["id"]: movie for movie in imported}
    print(f"КП-импорт: новых {len(unique)}")
    return list(unique.values())


def build_catalog():
    DEV_POOL.log_start()
    KPU_POOL.log_start()
    candidates, genres, lists = collect_candidates()

    # Если тренды/анонсы не скачались (сбой или лимит TMDB) — оставляем
    # вчерашние списки, чтобы панели главной не превращались в пустышки
    old_lists = load_old("lists") or {}
    for key in ("now_playing", "upcoming"):
        if not lists.get(key) and old_lists.get(key):
            lists[key] = old_lists[key]
            print(f"{key}: пусто, взято из вчерашнего списка ({len(lists[key])})")

    movies_raw = []
    with ThreadPoolExecutor(max_workers=API_WORKERS) as ex:
        futures = [ex.submit(enrich_movie, m) for m in candidates]
        done = 0
        for f in as_completed(futures):
            movies_raw.append(f.result())
            done += 1
            if done % 100 == 0:
                print(f"детали: {done}/{len(candidates)}")

    # ── Накопление базы: свежие данные поверх вчерашних ──
    # Фильм, попавший в каталог хоть раз, остаётся в базе навсегда.
    # Данные TMDB перекрываются свежими, а редкие Кинопоиск-поля
    # (рейтинг, факты, кадр) сохраняются — дневные квоты тратятся
    # только на фильмы, у которых их ещё нет.
    old_movies = {m["id"]: m for m in (load_old("movies") or [])}
    old_cast = load_old("cast") or {}

    # Новые карточки из Кинопоиска. Импорт включается вручную:
    # KP_IMPORT_LIMIT=0 в обычном ежедневном прогоне.
    imported = import_kp_movies(list(old_movies.values()) + movies_raw, KP_IMPORT_LIMIT)
    if imported:
        movies_raw.extend(imported)

    kp_state = load_kp_state()
    KP_FIELDS = (
        "kp_rating", "facts", "frame", "poster", "poster_fallback",
        "kp_id", "source",
    )

    for m in movies_raw:
        o = old_movies.get(m["id"])
        if not o:
            continue
        m["release_date"] = m.get("release_date") or o.get("release_date") or ""
        # Описание Кинопоиска (если когда-то получили) лучше заводского обзора TMDB
        if o.get("description") and o.get("kp_rating"):
            m["description"] = o["description"]
        for k in KP_FIELDS:
            if o.get(k) and not m.get(k):
                m[k] = o[k]

    # Архив: фильмы из вчерашней базы, которые больше не входят в списки TMDB
    current_ids = {m["id"] for m in movies_raw}
    archived = 0
    for oid, o in old_movies.items():
        if oid not in current_ids:
            movies_raw.append(o)
            archived += 1
    print(f"архив: {archived} фильмов перенесены из вчерашней базы")

    # Кинопоиск — обогащение по убыванию популярности, только для фильмов
    # без рейтинга/фактов. Cooldown не даёт каждый день тратить квоту на
    # одни и те же ненайденные фильмы.
    movies_raw.sort(key=lambda m: m.get("popularity") or 0, reverse=True)
    kp_ids = {}  # наш id -> id Кинопоиска (для фактов и кадров)
    for m in movies_raw:
        if m.get("kp_id"):
            kp_ids[m["id"]] = m["kp_id"]

    def kp_ready(m, *statuses):
        return not any(kp_should_skip(kp_state, m, s) for s in statuses)

    dev_budget = KP_MAX_MOVIES
    for m in movies_raw:
        if dev_budget <= 0:
            break
        if m.get("kp_rating"):
            continue
        if not kp_ready(m, "not_found", "error"):
            continue
        dev_budget -= 1
        kp = get_kp_data(m.get("title"), m.get("year"), m.get("original_title"))
        if kp and kp.get("error"):
            kp_mark(kp_state, m, "error")
        elif kp:
            if kp.get("kp_id"):
                kp_ids[m["id"]] = kp["kp_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
            if kp.get("kp_rating"):
                m["kp_rating"] = round(kp["kp_rating"], 1)
            if kp.get("poster"):
                m["poster_fallback"] = kp["poster"]
            kp_clear(kp_state, m, "not_found")
            kp_clear(kp_state, m, "error")
        else:
            kp_mark(kp_state, m, "not_found")
        time.sleep(0.3)

    # Факты и резервные данные: если id Кинопоиска уже известен,
    # не тратим запрос на поиск.
    fact_budget = UNOFFICIAL_MAX_MOVIES
    for m in movies_raw:
        if fact_budget <= 0:
            break
        if m.get("facts"):
            continue
        if not kp_ready(m, "no_facts", "error"):
            continue
        fact_budget -= 1
        kp_id = kp_ids.get(m["id"])
        if kp_id:
            facts = get_kp_facts(kp_id)
            kp = {"facts": facts} if facts else None
        else:
            kp = get_kp_unofficial(m.get("title"), m.get("year"), m.get("original_title"))
        if kp and kp.get("error"):
            kp_mark(kp_state, m, "error")
        elif kp:
            if kp.get("film_id"):
                kp_ids[m["id"]] = kp["film_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
            if kp.get("kp_rating"):
                m["kp_rating"] = round(kp["kp_rating"], 1)
            if kp.get("poster") and not (m.get("poster") or "").startswith("http"):
                m["poster_fallback"] = kp["poster"]
            if kp.get("facts"):
                m["facts"] = kp["facts"]
                kp_clear(kp_state, m, "no_facts")
                kp_clear(kp_state, m, "error")
            else:
                kp_mark(kp_state, m, "no_facts")
        else:
            kp_mark(kp_state, m, "no_facts")
        time.sleep(0.3)

    # ── Чистка описаний ──
    # Чужой текст (описание другого фильма) выбрасываем и подставляем
    # английский обзор TMDB — он приходит из официальной карточки и вранья
    # не содержит. Тем же способом закрываем фильмы вообще без описания.
    replaced = 0
    for m in movies_raw:
        desc = (m.get("description") or "").strip()
        if desc and not desc_suspicious(m):
            # Кандидатов на проверку печатаем в лог: если текст чужой —
            # id добавляется в BAD_DESC_IDS
            if SUSPECT_DESC_RE.search(desc):
                print(f"  проверить описание: {m['id']} {m.get('title')} ({m.get('year')})")
            continue
        # У фильмов Кинопоиска нет карточки в TMDB — английский резерв не ищем
        if m.get("source") == "kp":
            continue
        # Сначала смотрим вчерашний резерв — чтобы не дёргать TMDB каждый день
        old = old_movies.get(m["id"]) or {}
        en = old.get("description_en") or get_en_overview(m["id"]) or ""
        if en:
            m["description_en"] = en
        if desc:
            m.pop("description", None)
            replaced += 1
            print(f"  чужое описание: {m['id']} {m.get('title')} — заменено английским")
        time.sleep(0.1)
    print(f"описания: чужих заменено {replaced}")

    # Кадры из фильмов (Яндекс.CDN — работают из РФ без VPN) —
    # только для фильмов, у которых кадра ещё нет и есть id Кинопоиска.
    frame_budget = KP_FRAME_MAX
    for m in movies_raw:
        if frame_budget <= 0:
            break
        if m.get("frame"):
            continue
        kp_id = kp_ids.get(m["id"])
        if not kp_id:
            continue
        if not kp_ready(m, "no_frame"):
            continue
        frame_budget -= 1
        frame = get_kp_frame(kp_id)
        if frame:
            m["frame"] = frame
            kp_clear(kp_state, m, "no_frame")
        else:
            kp_mark(kp_state, m, "no_frame")
        time.sleep(0.2)

    # Постеры (параллельно) — докачиваем только отсутствующие файлы.
    # Удалённые постеры Кинопоиска (Яндекс.CDN) не трогаем: качать не нужно.
    def job(m):
        poster = m.get("poster") or ""
        if poster.startswith("http://") or poster.startswith("https://"):
            if not m.get("poster_fallback"):
                m["poster_fallback"] = poster
            return m
        local_path = f"{POSTERS_DIR}/{m['id']}.jpg"
        if not os.path.exists(local_path):
            m["poster"] = download_poster(m["id"], m.get("poster_path") or "")
        else:
            m["poster"] = local_path
        if not m.get("poster_fallback"):
            path = m.get("poster_path") or ""
            m["poster_fallback"] = IMG_MIRROR + path if path else ""
        return m

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
        movies = list(ex.map(job, movies_raw))
    print(f"постеры: {sum(1 for m in movies if m['poster'])}/{len(movies)}")

    # cast.json и индекс актёров собираем ДО чистки записей
    cast_map = {str(m["id"]): m.get("cast", []) for m in movies}
    # Актёры архивных фильмов — из вчерашнего cast.json
    cast_map.update(old_cast)

    # Индекс актёров для поиска по имени и страниц актёра
    people = {}
    for mid_s, cast in cast_map.items():
        for c in cast:
            key = str(c.get("id") or c["name"])
            person = people.setdefault(key, {"id": c.get("id") or 0, "name": c["name"], "photo": c["photo"], "movies": []})
            movie_id = int(mid_s) if str(mid_s).isdigit() else mid_s
            if movie_id not in person["movies"]:
                person["movies"].append(movie_id)
            if c["photo"] and not person["photo"]:
                person["photo"] = c["photo"]

    # Чистые файлы данных
    for m in movies:
        m.pop("cast", None)
        m.pop("poster_path", None)
        # popularity и release_date оставляем: нужны для сортировки
        # «Сначала популярные» и точной сортировки по дате выхода
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
        if not m.get("director"):
            m.pop("director", None)
        if not m.get("backdrop"):
            m.pop("backdrop", None)
        if not m.get("frame"):
            m.pop("frame", None)
        if not m.get("release_date"):
            m.pop("release_date", None)
        if not m.get("description"):
            m.pop("description", None)
        if not m.get("description_en"):
            m.pop("description_en", None)

    save("movies", movies)
    save("genres", genres)
    save("lists", lists)
    save("cast", cast_map)
    save("people", list(people.values()))
    prune_kp_state(kp_state, movies)
    save_kp_state(kp_state)

    DEV_POOL.log_stats()
    KPU_POOL.log_stats()

    print(f"=== ИТОГО: {len(movies)} фильмов, {len(people)} актёров ===")


def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


if __name__ == "__main__":
    build_catalog()

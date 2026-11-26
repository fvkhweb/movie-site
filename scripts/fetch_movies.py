import html as html_mod
import os, json, time, re, datetime, random, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
POISKKINO_API_KEY = os.environ.get("POISKKINO_API_KEY", "")

TMDB_BASE = "https://api.themoviedb.org/3"
# Прокси-шаблон только для локальной отладки (на Actions не задаётся),
# например: https://api.allorigins.win/raw?url={url}
TMDB_PROXY_TEMPLATE = os.environ.get("TMDB_PROXY_TEMPLATE", "")

IMG_SIZE = "w342"
POSTERS_DIR = "posters"
IMG_SOURCES = [
    "https://image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
    "https://imagetmdb.com/t/p/" + IMG_SIZE + "{path}",
    "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
]
IMG_MIRROR = "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE
# Резерв постера в сетке — мельче основного: хватает для карточки и меньше весит
POSTER_MIRROR = "https://wsrv.nl/?url=image.tmdb.org/t/p/w342"
# Общая заглушка для фильмов без постера: читается и сайтом, и приложением
PLACEHOLDER_POSTER = "posters/placeholder.webp"

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
# Жёсткий бюджет фактических запросов на ключ: 80% дневного лимита.
# Фильмовые бюджеты выше остаются, но запросы останавливаются раньше.
KP_DEV_MAX_REQUESTS = int(os.environ.get("KP_DEV_MAX_REQUESTS", "150"))
KPU_MAX_REQUESTS = int(os.environ.get("KP_UNOFFICIAL_MAX_REQUESTS", "400"))
# Ниже порога матч не принимаем даже после загрузки деталей.
KP_MIN_MATCH_SCORE = 6
KP_HIGH_MATCH_SCORE = 8
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
# Ручной аудит уже сохранённых КП-полей: 0 — выключен.
KP_AUDIT_LIMIT = int(os.environ.get("KP_AUDIT_LIMIT", "0"))
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

    def __init__(self, name, keys, exhaust_codes, invalid_codes=(401,), max_requests=0):
        self.name = name
        self.keys = list(keys)
        self.exhaust_codes = set(exhaust_codes)
        self.invalid_codes = set(invalid_codes)
        self._next = 0
        self.exhausted = set()
        self.invalid = set()
        self.limited = set()
        self.max_requests = max_requests
        self.requests = [0] * len(self.keys)
        self.success = [0] * len(self.keys)
        self.errors = [0] * len(self.keys)
        self.last_response = None

    def available(self):
        if not self.keys:
            return False
        for i in range(len(self.keys)):
            if i in self.exhausted or i in self.invalid or i in self.limited:
                continue
            if self.max_requests and self.requests[i] >= self.max_requests:
                continue
            return True
        return False

    def log_start(self):
        if not self.keys:
            print(f"{self.name}: ключей нет — источник выключен")
            return
        budget = f", бюджет {self.max_requests} запросов/ключ" if self.max_requests else ""
        print(f"{self.name}: ключей {len(self.keys)}{budget}")
        for i, key in enumerate(self.keys):
            print(f"  #{i + 1}: {mask_key(key)}")

    def request(self, do_request):
        if not self.available():
            return None
        n = len(self.keys)
        for offset in range(n):
            idx = (self._next + offset) % n
            if idx in self.exhausted or idx in self.invalid or idx in self.limited:
                continue
            if self.max_requests and self.requests[idx] >= self.max_requests:
                self.limited.add(idx)
                print(f"  {self.name} #{idx + 1}: бюджет {self.max_requests} запросов — ключ остановлен")
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
        return None

    def log_stats(self):
        if not self.keys:
            print(f"{self.name}: запросов нет")
            return
        parts = [
            f"#{i + 1}={self.requests[i]} запр./{self.success[i]} ок/{self.errors[i]} ош"
            for i in range(len(self.keys))
        ]
        print(f"{self.name}: " + ", ".join(parts))


KPU_POOL = KeyPool("КП-Unofficial", KPU_API_KEYS, {402, 429}, max_requests=KPU_MAX_REQUESTS)
DEV_POOL = KeyPool("КП-dev", KP_DEV_KEYS, {402, 429, 403}, max_requests=KP_DEV_MAX_REQUESTS)


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


def names_match(a, b):
    """Одно имя похоже на другое: целиком, по вхождению или по фамилии."""
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return None
    if a == b or a in b or b in a:
        return True
    return a.split()[-1] == b.split()[-1]


def directors_match(a, b):
    """None — сравнить нельзя (одного режиссёра нет), иначе True/False."""
    if not a or not b:
        return None
    for x in re.split(r"[,;/]", a):
        for y in re.split(r"[,;/]", b):
            if names_match(x, y):
                return True
    return False


def kp_match_score(query_names, query_year, cand_names, cand_year,
                   query_original="", cand_original="",
                   query_imdb="", cand_imdb="",
                   query_director="", cand_director=""):
    """Похожесть кандидата Кинопоиска на наш фильм; -1 — точно другой.

    imdb_id решает всё. Оригинальные названия должны совпадать: у разных
    фильмов бывает один русский прокатный title («Одержимость»). Режиссёр
    отсекает одноимённые фильмы одного года.
    """
    if query_imdb and cand_imdb:
        return 100 if query_imdb == cand_imdb else -1
    q_orig, c_orig = norm_title(query_original), norm_title(cand_original)
    if q_orig and c_orig and q_orig != c_orig:
        return -1
    if not any(titles_match(q, c) for q in query_names if q for c in cand_names if c):
        return -1
    score = 6 if q_orig and q_orig == c_orig else 0
    score += 2
    try:
        qy = int(str(query_year)[:4])
        cy = int(str(cand_year)[:4])
    except (TypeError, ValueError):
        return score + 1
    if qy == cy:
        score += 4
    elif abs(qy - cy) == 1:
        # Соседний год — только при совпадении оригинального названия.
        # Иначе одноимённый фильм другого года даёт ложный матч.
        if not (q_orig and c_orig and q_orig == c_orig):
            return -1
        score += 1
    else:
        return -1
    if query_director and cand_director:
        if directors_match(query_director, cand_director):
            score += 6
        else:
            return -1
    return score


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

    collection = details.get("belongs_to_collection") or {}

    return {
        "id": m["id"],
        "title": details.get("title") or m.get("title", ""),
        "original_title": details.get("original_title") or "",
        "year": release[:4],
        "release_date": release,
        "director": director,
        "rating": round(details.get("vote_average") or 0, 1),
        "vote_count": details.get("vote_count") or 0,
        "series": (
            {"id": collection.get("id"), "name": collection.get("name") or ""}
            if collection.get("id") else None
        ),
        "popularity": round(m.get("_popularity", 0), 1),
        "runtime": details.get("runtime") or 0,
        "genres": [g["id"] for g in details.get("genres", [])],
        "countries": [c.get("name", "") for c in details.get("production_countries", [])],
        "poster_path": details.get("poster_path") or "",
        "backdrop": details.get("backdrop_path") or "",
        "description": details.get("overview") or "",
        "imdb_id": details.get("imdb_id") or "",
        "cast": cast,
        "similar": get_recommendations(m["id"]),
        "trailer": get_trailer(m["id"]),
    }


def get_kp_unofficial(title, year, original_title="", director="", imdb_id=""):
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
        # ранжируем по названию/году и проверяем оригинальное название
        # по деталям, прежде чем брать карточку.
        query_names = [title, original_title]
        ranked = []
        for x in films:
            score = kp_match_score(
                query_names, year,
                [x.get("nameRu"), x.get("nameEn"), x.get("nameOriginal")],
                x.get("year"),
                query_original=original_title,
                cand_original=x.get("nameOriginal") or x.get("nameEn") or "",
                query_imdb=imdb_id,
                cand_imdb=x.get("imdbId") or "",
                query_director=director,
            )
            if score >= 0:
                ranked.append((score, x))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            print(f"  КП-Unofficial '{title}' ({year}): нет совпадения среди {len(films)} результатов")
            return None

        for score, f in ranked[:3]:
            film_id = f.get("filmId") or f.get("kinopoiskId")
            poster = f.get("posterUrl") or f.get("posterUrlPreview") or ""
            description = f.get("description")
            # Только рейтинг Кинопоиска: поле rating может означать другое.
            rating = f.get("ratingKinopoisk")

            if film_id and score >= KP_HIGH_MATCH_SCORE and description and poster and rating:
                time.sleep(0.2)
                facts = get_kp_facts(film_id)
                return {
                    "poster": poster,
                    "description": description,
                    "kp_rating": rating,
                    "facts": facts,
                    "film_id": film_id,
                }

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
                score = kp_match_score(
                    query_names, year,
                    [details_data.get("nameRu"), details_data.get("nameEn"), details_data.get("nameOriginal")],
                    details_data.get("year"),
                    query_original=original_title,
                    cand_original=details_data.get("nameOriginal") or details_data.get("nameEn") or "",
                    query_imdb=imdb_id,
                    cand_imdb=details_data.get("imdbId") or "",
                    query_director=director,
                    cand_director=details_data.get("director") or "",
                )
                if score < KP_MIN_MATCH_SCORE:
                    continue
            elif score < KP_HIGH_MATCH_SCORE:
                # Детали не пришли — без проверки берём только явное совпадение
                continue

            time.sleep(0.2)
            facts = get_kp_facts(film_id)
            return {
                "poster": poster,
                "description": description,
                "kp_rating": rating,
                "facts": facts,
                "film_id": film_id,
            }
        print(f"  КП-Unofficial '{title}' ({year}): кандидаты не подтвердились")
        return None
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
        if fr.status_code != 200:
            continue
        items = fr.json().get("items") or []
        return [
            html_mod.unescape(re.sub(r"<[^>]+>", "", i.get("text") or "")).strip()
            for i in items
            if i.get("text")
        ][:3]
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


KP_CLEAR_FIELDS = ("kp_id", "kp_rating", "facts", "frame", "poster_fallback")


def clear_kp_fields(movie):
    """Убирает данные КП, если сопоставление не подтвердилось."""
    for field in KP_CLEAR_FIELDS:
        movie.pop(field, None)
    if movie.get("description_source") == "kp":
        movie.pop("description", None)
        movie.pop("description_source", None)


def get_kp_details(kp_id):
    """Детали фильма по id КП (две версии API). None — сеть/лимит."""
    if not KPU_API_KEYS or not kp_id:
        return None
    for ver in ("v2.2", "v2.1"):
        r = kpu_get(f"{ver}/films/{kp_id}")
        if r is None:
            return None
        if r.status_code == 200:
            data = r.json()
            return data.get("data") if isinstance(data.get("data"), dict) else data
    return None


def audit_kp_matches(movies, state, limit):
    """Перепроверяет сохранённые КП-поля и чистит ложные сопоставления.

    С id КП сверяем карточку по названию/году/оригиналу/IMDb. Без id —
    ищем заново с ужесточённым матчингом. Транзиентные ошибки API не
    считаем приговором: поля остаются до следующего прогона.
    """
    if limit <= 0 or not KPU_POOL.available():
        return
    candidates = [m for m in movies if any(m.get(f) for f in KP_CLEAR_FIELDS)]
    # Сначала записи с id: их проверка дешевле и надёжнее.
    candidates.sort(key=lambda m: (0 if m.get("kp_id") else 1, -(m.get("popularity") or 0)))
    checked = kept = cleared = 0
    for m in candidates:
        if checked >= limit or not KPU_POOL.available():
            break
        checked += 1
        kp_id = m.get("kp_id")
        if kp_id:
            details = get_kp_details(kp_id)
            if details is None:
                kp_mark(state, m, "error")
                continue
            score = kp_match_score(
                [m.get("title"), m.get("original_title")], m.get("year"),
                [details.get("nameRu"), details.get("nameEn"), details.get("nameOriginal")],
                details.get("year"),
                query_original=m.get("original_title") or "",
                cand_original=details.get("nameOriginal") or details.get("nameEn") or "",
                query_imdb=m.get("imdb_id") or "",
                cand_imdb=details.get("imdbId") or "",
                query_director=m.get("director") or "",
                cand_director=details.get("director") or "",
            )
            if score < KP_MIN_MATCH_SCORE:
                print(f"  КП-аудит: {m['id']} {m.get('title')} — id {kp_id} не совпал, очищаю")
                clear_kp_fields(m)
                kp_mark(state, m, "not_found")
                kp_mark(state, m, "no_facts")
                cleared += 1
            else:
                rating = details.get("ratingKinopoisk")
                if rating:
                    m["kp_rating"] = round(rating, 1)
                kept += 1
            time.sleep(0.2)
            continue

        kp = get_kp_unofficial(
            m.get("title"), m.get("year"), m.get("original_title"),
            m.get("director") or "", m.get("imdb_id") or "",
        )
        if kp and kp.get("error"):
            kp_mark(state, m, "error")
            continue
        if kp and kp.get("film_id"):
            m["kp_id"] = kp["film_id"]
            if kp.get("kp_rating"):
                m["kp_rating"] = round(kp["kp_rating"], 1)
            if kp.get("description"):
                m["description"] = kp["description"]
                m["description_source"] = "kp"
            if kp.get("poster") and not (m.get("poster") or "").startswith("http"):
                m["poster_fallback"] = kp["poster"]
            if kp.get("facts"):
                m["facts"] = kp["facts"]
            kp_clear(state, m, "not_found")
            kp_clear(state, m, "error")
            kept += 1
        else:
            print(f"  КП-аудит: {m['id']} {m.get('title')} — матч не подтвердился, очищаю")
            clear_kp_fields(m)
            kp_mark(state, m, "not_found")
            kp_mark(state, m, "no_facts")
            cleared += 1
        time.sleep(0.2)
    print(f"КП-аудит: проверено {checked}, подтверждено {kept}, очищено {cleared}")


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


def get_kp_data(title, year, original_title="", imdb_id="", director=""):
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
        # матч) — ранжируем по названию/году, а режиссёра и imdb сверяем
        # по деталям выбранного кандидата.
        query_names = [title, original_title]
        ranked = []
        for d in docs:
            score = kp_match_score(
                query_names, year,
                [d.get("name"), d.get("alternativeName"), d.get("enName")],
                d.get("year"),
                query_original=original_title,
                cand_original=d.get("alternativeName") or d.get("enName") or "",
                query_imdb=imdb_id,
                cand_imdb=(d.get("externalId") or {}).get("imdb") or "",
                query_director=director,
            )
            if score >= 0:
                ranked.append((score, d))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked:
            print(f"  КП '{title}' ({year}): нет совпадения среди {len(docs)} результатов")
            return None

        for score, movie in ranked[:3]:
            kp_id = movie["id"]
            poster = (movie.get("poster") or {}).get("url") or (movie.get("poster") or {}).get("previewUrl")
            search_rating = (movie.get("rating") or {}).get("kp")
            description = movie.get("description")
            if score >= KP_HIGH_MATCH_SCORE and search_rating and poster and description:
                return {
                    "poster": poster,
                    "description": description,
                    "kp_rating": search_rating,
                    "kp_id": kp_id,
                }
            time.sleep(0.3)
            d_resp = kp_dev_get(f"/{kp_id}")
            if d_resp is None or d_resp.status_code != 200:
                print(f"  КП детали {kp_id}: HTTP {d_resp.status_code}")
                if score < KP_HIGH_MATCH_SCORE:
                    continue
                return {
                    "poster": poster,
                    "description": movie.get("description"),
                    "kp_rating": (movie.get("rating") or {}).get("kp"),
                    "kp_id": kp_id,
                }

            details = d_resp.json()
            cand_director = ", ".join(
                p.get("name", "") for p in details.get("persons") or []
                if p.get("profession") == "режиссер"
            )
            full_score = kp_match_score(
                query_names, year,
                [details.get("name"), details.get("alternativeName"), details.get("enName")],
                details.get("year"),
                query_original=original_title,
                cand_original=details.get("alternativeName") or details.get("enName") or "",
                query_imdb=imdb_id,
                cand_imdb=(details.get("externalId") or {}).get("imdb") or "",
                query_director=director,
                cand_director=cand_director,
            )
            if full_score < KP_MIN_MATCH_SCORE:
                continue
            return {
                # Постер Кинопоиска лежит на Яндекс.CDN и открывается из РФ
                "poster": (details.get("poster") or {}).get("url") or poster,
                "description": details.get("description") or movie.get("description"),
                "kp_rating": (details.get("rating") or {}).get("kp"),
                "kp_id": kp_id,
            }
        print(f"  КП '{title}' ({year}): кандидаты не подтвердились")
        return None
    except Exception as e:
        print(f"  КП ошибка для '{title}': {e}")
        return {"error": True}
    return None


def save_webp(content, local_path):
    """JPEG из TMDB -> WebP шириной 342: в сетке разницы не видно,
    а файл в несколько раз легче исходного w500."""
    try:
        import io
        from PIL import Image

        img = Image.open(io.BytesIO(content)).convert("RGB")
        if img.width > 342:
            height = round(img.height * 342 / img.width)
            img = img.resize((342, height), Image.LANCZOS)
        img.save(local_path, "WEBP", quality=82, method=6)
        return True
    except Exception as e:
        print(f"  постер WebP: {e}")
        return False


def download_poster(movie_id, poster_path):
    if not poster_path:
        return ""
    os.makedirs(POSTERS_DIR, exist_ok=True)
    local_path = os.path.join(POSTERS_DIR, f"{movie_id}.webp").replace("\\", "/")
    legacy_path = os.path.join(POSTERS_DIR, f"{movie_id}.jpg").replace("\\", "/")

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return local_path
    # Старые JPG ещё могут лежать в базе — не качаем их заново
    if os.path.exists(legacy_path) and os.path.getsize(legacy_path) > 1000:
        return legacy_path

    for template in IMG_SOURCES:
        url = template.format(path=poster_path)
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000 and \
                    r.headers.get("Content-Type", "").startswith("image"):
                if save_webp(r.content, local_path):
                    return local_path
                # Pillow нет — сохраняем как раньше, чтобы не потерять постер
                with open(legacy_path, "wb") as f:
                    f.write(r.content)
                return legacy_path
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


def dedup_key(movie):
    """Ключ одинаковых карточек. imdb_id надёжнее всего; без него —
    оригинальное название + год + режиссёр (одноимённые фильмы одного года
    с разными режиссёрами — разные фильмы)."""
    imdb = (movie.get("imdb_id") or "").strip()
    if imdb:
        return ("imdb", imdb)
    year = norm_year(movie.get("year") or (movie.get("release_date") or "")[:4])
    title = norm_title(movie.get("original_title"))
    director = norm_title(movie.get("director"))
    if title and year and director:
        return ("td", title, year, director)
    return None


def dedup_movies(movies):
    """Убирает дубли, оставляя карточку с лучшим popularity/rating,
    и переносит в неё недостающие поля Кинопоиска."""
    groups = {}
    for movie in movies:
        key = dedup_key(movie)
        if key:
            groups.setdefault(key, []).append(movie)

    dropped = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(
            key=lambda m: (m.get("popularity") or 0, m.get("rating") or 0, bool(m.get("poster"))),
            reverse=True,
        )
        keep = group[0]
        for dup in group[1:]:
            for field, value in dup.items():
                if field in ("id", "source", "kp_id", "imdb_id", "similar"):
                    continue
                if value and not keep.get(field):
                    keep[field] = value
            dropped.add(dup["id"])
    return [m for m in movies if m["id"] not in dropped], dropped


def prune_list_ids(lists, dropped):
    for key, value in (lists or {}).items():
        if key == "by_genre" and isinstance(value, dict):
            lists[key] = {
                genre: [mid for mid in ids if mid not in dropped]
                for genre, ids in value.items()
            }
        elif isinstance(value, list):
            lists[key] = [mid for mid in value if mid not in dropped]


MIN_SIMILAR = 4
MAX_SIMILAR = 6
# TMDB отдаёт рейтинг без учёта числа голосов: у свежих релизов он держится
# на 10.0 при паре оценок и вытесняет из «Похожего» всё остальное. Поэтому
# в добор пускаем только фильмы с внятным числом голосов, считаем
# байесовскую оценку и добираем разные фильмы, а не один и тот же топ жанра.
FALLBACK_MIN_VOTES = 100
FALLBACK_MIN_RATING = 5.5
FALLBACK_POOL = 50
FALLBACK_BAYES_M = 300
FALLBACK_BAYES_C = 6.2


def fallback_score(cand, year):
    """Оценка для добора: рейтинг с поправкой на число голосов и бонус
    за близость года. None — фильм слишком плохой или без голосов."""
    votes = cand.get("vote_count") or 0
    rating = cand.get("rating") or 0
    if votes < FALLBACK_MIN_VOTES or rating < FALLBACK_MIN_RATING:
        return None
    score = (votes * rating + FALLBACK_BAYES_M * FALLBACK_BAYES_C) / (
        votes + FALLBACK_BAYES_M
    )
    gap = abs((norm_year(cand.get("year")) or 0) - year)
    return score - min(gap, 20) * 0.04


def repair_similar(movies):
    """Оставляет в «Похожее» только фильмы каталога, выкидывает части той же
    серии и, если рекомендаций меньше четырёх, добирает фильмы того же жанра
    с учётом числа голосов. Добор детерминированно перемешивается по id
    фильма: списки не повторяются, но и не меняются между прогонами."""
    ids = {m["id"]: m for m in movies}
    by_genre = {}
    for movie in movies:
        for genre in movie.get("genres") or []:
            by_genre.setdefault(genre, []).append(movie)

    for movie in movies:
        series_id = (movie.get("series") or {}).get("id")
        similar = []
        for sid in movie.get("similar") or []:
            cand = ids.get(sid)
            if not cand or sid == movie["id"] or sid in similar:
                continue
            if series_id and (cand.get("series") or {}).get("id") == series_id:
                continue
            # Старые списки могли набраться мусора от прежнего добора:
            # фильм без внятного числа голосов в «Похожее» не пускаем.
            votes = cand.get("vote_count")
            if votes is not None and votes < FALLBACK_MIN_VOTES:
                continue
            similar.append(sid)

        if len(similar) < MIN_SIMILAR:
            year = norm_year(movie.get("year")) or 0
            pool = {}
            for genre in movie.get("genres") or []:
                for cand in by_genre.get(genre, []):
                    cid = cand["id"]
                    if cid == movie["id"] or cid in similar:
                        continue
                    if series_id and (cand.get("series") or {}).get("id") == series_id:
                        continue
                    score = fallback_score(cand, year)
                    if score is not None:
                        pool[cid] = (score, cand)
            ranked = sorted(pool.values(), key=lambda item: (-item[0], item[1]["id"]))
            ranked = ranked[:FALLBACK_POOL]
            need = min(MAX_SIMILAR - len(similar), len(ranked))
            if need > 0:
                picks = random.Random(movie["id"]).sample(ranked, need)
                picks.sort(key=lambda item: (-item[0], item[1]["id"]))
                similar.extend(cand["id"] for _, cand in picks)

        if similar:
            movie["similar"] = similar[:MAX_SIMILAR]
        else:
            movie.pop("similar", None)


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
        "imdb_id": (doc.get("externalId") or {}).get("imdb") or "",
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
                                "countries,poster,premiere,externalId",
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
        "kp_id", "source", "description_source",
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

    audit_kp_matches(movies_raw, kp_state, KP_AUDIT_LIMIT)

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
        if not DEV_POOL.available():
            print("  КП-dev: бюджет запросов исчерпан, остальное отложено")
            break
        if dev_budget <= 0:
            break
        if m.get("kp_id"):
            continue
        if m.get("kp_rating"):
            continue
        if not kp_ready(m, "not_found", "error"):
            continue
        dev_budget -= 1
        kp = get_kp_data(m.get("title"), m.get("year"), m.get("original_title"),
                         m.get("imdb_id") or "", m.get("director") or "")
        if kp and kp.get("error"):
            kp_mark(kp_state, m, "error")
        elif kp:
            if kp.get("kp_id"):
                kp_ids[m["id"]] = kp["kp_id"]
                m["kp_id"] = kp["kp_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
                m["description_source"] = "kp"
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
        if not KPU_POOL.available():
            print("  КП-Unofficial: бюджет запросов исчерпан, факты отложены")
            break
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
                m["kp_id"] = kp["film_id"]
            if kp.get("description"):
                m["description"] = kp["description"]
                m["description_source"] = "kp"
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
        if not KPU_POOL.available():
            print("  КП-Unofficial: бюджет запросов исчерпан, кадры отложены")
            break
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

    # Дубли могли прийти из TMDB и Кинопоиска под разными id: оставляем
    # одну карточку и переносим в неё недостающие поля.
    movies_raw, dropped = dedup_movies(movies_raw)
    if dropped:
        prune_list_ids(lists, dropped)
        print(f"дубли: убрано {len(dropped)} карточек")

    # Постеры (параллельно) — докачиваем только отсутствующие файлы.
    # Удалённые постеры Кинопоиска (Яндекс.CDN) не трогаем: качать не нужно.
    def job(m):
        poster = m.get("poster") or ""
        if poster.startswith("http://") or poster.startswith("https://"):
            if not m.get("poster_fallback"):
                m["poster_fallback"] = poster
            return m
        local_path = f"{POSTERS_DIR}/{m['id']}.webp"
        legacy_path = f"{POSTERS_DIR}/{m['id']}.jpg"
        if os.path.exists(local_path):
            m["poster"] = local_path
        elif os.path.exists(legacy_path):
            m["poster"] = legacy_path
        else:
            downloaded = download_poster(m["id"], m.get("poster_path") or "")
            if downloaded:
                m["poster"] = downloaded
        if not m.get("poster_fallback"):
            path = m.get("poster_path") or ""
            m["poster_fallback"] = POSTER_MIRROR + path if path else ""
        if not m.get("poster"):
            m["poster"] = PLACEHOLDER_POSTER
        return m

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
        movies = list(ex.map(job, movies_raw))
    print(f"постеры: {sum(1 for m in movies if m['poster'])}/{len(movies)}")

    # «Похожее» ссылается только на фильмы каталога, иначе блок пустует
    repair_similar(movies)
    linked = sum(len(m.get("similar") or []) for m in movies)
    print(f"похожее: {linked} ссылок")

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
        if not (m.get("series") or {}).get("id") or not (
            (m.get("series") or {}).get("name") or ""
        ).strip():
            m.pop("series", None)

    save("movies", movies)
    save("genres", genres)
    # Сайт и приложение читают только эти две ленты; popular/top_rated/by_genre
    # никто не использует — не возим их в data/lists.json.
    save("lists", {key: lists.get(key, []) for key in ("now_playing", "upcoming")})
    save("cast", cast_map)
    save("people", list(people.values()))
    prune_kp_state(kp_state, movies)
    save_kp_state(kp_state)
    prune_posters(movies)

    DEV_POOL.log_stats()
    KPU_POOL.log_stats()

    print(f"=== ИТОГО: {len(movies)} фильмов, {len(people)} актёров ===")


def save(name, data):
    os.makedirs("data", exist_ok=True)
    path = f"data/{name}.json"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def prune_posters(movies):
    """Удаляет постеры, на которые больше не ссылается каталог."""
    if not os.path.isdir(POSTERS_DIR):
        return
    referenced = set()
    for movie in movies:
        path = movie.get("poster") or ""
        if path and not path.startswith(("http://", "https://")):
            referenced.add(os.path.basename(path))
    removed = 0
    freed = 0
    for name in os.listdir(POSTERS_DIR):
        if not name.lower().endswith((".jpg", ".jpeg", ".webp", ".png")):
            continue
        # Общая заглушка нужна пайплайну даже когда на неё пока никто не ссылается
        if name in referenced or name.startswith("placeholder"):
            continue
        path = os.path.join(POSTERS_DIR, name)
        try:
            size = os.path.getsize(path)
            os.remove(path)
            removed += 1
            freed += size
        except OSError as e:
            print(f"  постер не удалён: {name}: {e}")
    print(f"постеры: удалено {removed} осиротевших ({freed // 1024} КБ)")


if __name__ == "__main__":
    build_catalog()

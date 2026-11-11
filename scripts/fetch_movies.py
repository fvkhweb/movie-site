import os, json, requests, time

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
POISKKINO_API_KEY = os.environ.get("POISKKINO_API_KEY", "")

TMDB_BASE = "https://api.themoviedb.org/3"
LANG = "ru-RU"

KP_BASE = "https://api.kinopoisk.dev/v1.4/movie"
KP_HEADERS = {"X-API-KEY": POISKKINO_API_KEY}

# Локальная папка с постерами. GitHub Pages отдаёт её с того же домена,
# что и сайт, поэтому картинки грузятся без VPN из РФ.
POSTERS_DIR = "posters"
IMG_SIZE = "w500"

# Порядок источников картинки. Первый доступен с раннеров GitHub Actions,
# остальные — резерв на случай недоступности.
IMG_SOURCES = [
    "https://image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
    "https://imagetmdb.com/t/p/" + IMG_SIZE + "{path}",
    "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE + "{path}",
]

# Зеркало TMDB, доступное из РФ (резервная ссылка в данных)
IMG_MIRROR = "https://wsrv.nl/?url=image.tmdb.org/t/p/" + IMG_SIZE


def fetch_tmdb(path, params=None):
    p = {"api_key": TMDB_API_KEY, "language": LANG, **(params or {})}
    r = requests.get(f"{TMDB_BASE}{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()


def download_poster(movie_id, poster_path):
    """Скачивает постер в posters/<id>.jpg и возвращает локальный путь."""
    if not poster_path:
        return None

    os.makedirs(POSTERS_DIR, exist_ok=True)
    local_path = os.path.join(POSTERS_DIR, f"{movie_id}.jpg")

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return local_path.replace("\\", "/")

    for template in IMG_SOURCES:
        url = template.format(path=poster_path)
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            content_type = r.headers.get("Content-Type", "")
            if r.status_code == 200 and len(r.content) > 1000 and content_type.startswith("image"):
                with open(local_path, "wb") as f:
                    f.write(r.content)
                return local_path.replace("\\", "/")
            print(f"  постер: {url} -> {r.status_code} {content_type}")
        except Exception as e:
            print(f"  постер: {url} -> ошибка: {e}")

    return None


def get_kp_data(title, year):
    """Обогащение данными Кинопоиска. Любая ошибка не должна ломать сбор."""
    if not POISKKINO_API_KEY:
        return None

    try:
        params = {"query": title, "limit": 1}
        if year and str(year).isdigit():
            params["year"] = year

        time.sleep(0.3)
        r = requests.get(f"{KP_BASE}/search", headers=KP_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            print(f"  КП поиск '{title}': HTTP {r.status_code}")
            return None

        docs = r.json().get("docs", [])
        if not docs:
            return None

        movie = docs[0]
        kp_id = movie["id"]
        poster = (movie.get("poster") or {}).get("url") or (movie.get("poster") or {}).get("previewUrl")

        time.sleep(0.3)
        d_resp = requests.get(f"{KP_BASE}/{kp_id}", headers=KP_HEADERS, timeout=15)
        if d_resp.status_code != 200:
            print(f"  КП детали {kp_id}: HTTP {d_resp.status_code}")
            return {
                "poster": poster,
                "description": movie.get("description"),
                "actors": "",
                "kp_rating": (movie.get("rating") or {}).get("kp"),
            }

        details = d_resp.json()
        actors = [
            p.get("name")
            for p in details.get("persons", [])
            if "актер" in (p.get("profession") or "").lower() or p.get("enProfession") == "actor"
        ]

        return {
            # Постер Кинопоиска лежит на Яндекс.CDN и открывается из РФ
            "poster": (details.get("poster") or {}).get("url") or poster,
            "description": details.get("description") or movie.get("description"),
            "actors": ", ".join(actors[:10]) + ("..." if len(actors) > 10 else ""),
            "kp_rating": (details.get("rating") or {}).get("kp"),
        }
    except Exception as e:
        print(f"  КП ошибка для '{title}': {e}")
    return None


def process_movies(results):
    movies = []
    for m in results:
        if not m.get("poster_path"):
            continue

        title = m["title"]
        year = (m.get("release_date") or "")[:4]
        poster_path = m["poster_path"]

        print(f"Ищем: {title} ({year})")
        local_poster = download_poster(m["id"], poster_path)

        movie_data = {
            "id": m["id"],
            "title": title,
            "rating": m.get("vote_average", 0),
            "year": year,
            # Основной постер — файл в репозитории (работает без VPN)
            "poster": local_poster or (IMG_MIRROR + poster_path),
            # Резерв, если локальный файл почему-то не отдался
            "poster_fallback": IMG_MIRROR + poster_path,
            "description": m.get("overview", ""),
            "actors": "",
        }

        kp_info = get_kp_data(title, year)
        if kp_info:
            if kp_info.get("poster"):
                movie_data["poster_fallback"] = kp_info["poster"]
            if kp_info.get("description"):
                movie_data["description"] = kp_info["description"]
            if kp_info.get("actors"):
                movie_data["actors"] = kp_info["actors"]
            if kp_info.get("kp_rating"):
                movie_data["rating"] = kp_info["kp_rating"]

        movies.append(movie_data)
    return movies


def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


print("=== СБОР ПОПУЛЯРНОГО ===")
popular = []
for page in range(1, 4):  # 3 страницы (60 фильмов)
    popular += process_movies(fetch_tmdb("/movie/popular", {"page": page})["results"])
save("popular", popular)

print("=== СБОР ТОПА ===")
top = []
for page in range(1, 4):
    top += process_movies(fetch_tmdb("/movie/top_rated", {"page": page})["results"])
save("top_rated", top)

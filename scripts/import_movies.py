"""Импорт фильмов по десятилетиям — отдельный контур, не трогает ежедневный пайплайн.

Запуск:
    IMPORT_LIMIT=500 IMPORT_DECADES=1990,2000,2010,2020 python scripts/import_movies.py

По умолчанию работает в dry-run: показывает, что добавит, но не пишет movies.json.
Для записи: DRY_RUN=false.
"""

import datetime
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Скрипт лежит рядом с fetch_movies.py — переиспользуем его клиентов и справочники.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_movies as fm  # noqa: E402


def parse_decades(raw):
    result = []
    for part in re.split(r"[,;\s]+", raw or ""):
        if not part:
            continue
        try:
            start = int(part)
        except ValueError:
            continue
        start = max(1990, start - start % 10)
        if start not in result:
            result.append(start)
    return sorted(result) or [1990, 2000, 2010, 2020]


IMPORT_LIMIT = int(os.environ.get("IMPORT_LIMIT", "0"))
IMPORT_DECADES = parse_decades(os.environ.get("IMPORT_DECADES", "1990,2000,2010,2020"))
IMPORT_MIN_VOTES = int(os.environ.get("IMPORT_MIN_VOTES", "200"))
IMPORT_MAX_PAGES = int(os.environ.get("IMPORT_MAX_PAGES", "100"))
IMPORT_LOCAL_POSTER_VOTES = int(os.environ.get("IMPORT_LOCAL_POSTER_VOTES", "500"))
IMPORT_WORKERS = int(os.environ.get("IMPORT_WORKERS", "6"))
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "").strip()
OMDB_MAX_MOVIES = int(os.environ.get("OMDB_MAX_MOVIES", "500"))
TASTEDIVE_API_KEY = os.environ.get("TASTEDIVE_API_KEY", "").strip()
TASTEDIVE_MAX_MOVIES = int(os.environ.get("TASTEDIVE_MAX_MOVIES", "50"))
TASTEDIVE_TARGET_SIMILAR = int(os.environ.get("TASTEDIVE_TARGET_SIMILAR", "8"))
DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() not in ("0", "false", "no")

DATA_DIR = os.environ.get("MOVIE_DATA_DIR", "data")
MOVIES_PATH = os.path.join(DATA_DIR, "movies.json")
IMPORT_LOG_DIR = os.environ.get("IMPORT_LOG_DIR", os.path.join("docs", "imports"))


def load_movies():
    with open(MOVIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def save_movies_atomic(movies):
    save_json_atomic(MOVIES_PATH, movies)


def update_cast_people(movies):
    """Дописывает актёров новых фильмов в cast.json и people.json."""
    cast_path = os.path.join(DATA_DIR, "cast.json")
    people_path = os.path.join(DATA_DIR, "people.json")
    try:
        with open(cast_path, encoding="utf-8") as f:
            cast_map = json.load(f)
    except Exception:
        cast_map = {}
    try:
        with open(people_path, encoding="utf-8") as f:
            people = json.load(f)
    except Exception:
        people = []

    people_by_key = {str(p.get("id") or p.get("name")): p for p in people}
    for movie in movies:
        items = movie.get("cast") or []
        if not items:
            continue
        cast_map[str(movie["id"])] = items
        for c in items:
            key = str(c.get("id") or c.get("name"))
            person = people_by_key.get(key)
            if not person:
                person = {
                    "id": c.get("id") or 0,
                    "name": c.get("name", ""),
                    "photo": c.get("photo") or "",
                    "movies": [],
                }
                people.append(person)
                people_by_key[key] = person
            if movie["id"] not in person["movies"]:
                person["movies"].append(movie["id"])

    save_json_atomic(cast_path, cast_map)
    save_json_atomic(people_path, people)


def decade_ranges():
    today = datetime.date.today()
    for start in IMPORT_DECADES:
        if start > today.year:
            continue
        end = min(start + 9, today.year)
        yield start, end


def discover_page(start, end, page):
    today = datetime.date.today().isoformat()
    date_to = f"{end}-12-31"
    if end >= datetime.date.today().year:
        date_to = today
    return fm.tmdb_get("/discover/movie", {
        "include_adult": "false",
        "primary_release_date.gte": f"{start}-01-01",
        "primary_release_date.lte": date_to,
        "sort_by": "vote_count.desc",
        "vote_count.gte": IMPORT_MIN_VOTES,
        "page": page,
    })


def collect_candidates(limit):
    """Собирает кандидатов по десятилетиям, не давая одному десятилетию съесть всё."""
    target = max(limit * 2, limit + 100)
    if IMPORT_MAX_PAGES * 20 < target:
        print(f"  предупреждение: {IMPORT_MAX_PAGES} страниц × 20 < цели {target}; увеличь IMPORT_MAX_PAGES")
    index = fm.build_existing_index(load_movies())
    seen_ids = {m["id"] for m in load_movies()}
    candidates = []
    skipped = {"existing": 0, "duplicate": 0, "no_id": 0}
    done = set()

    for page in range(1, IMPORT_MAX_PAGES + 1):
        if len(candidates) >= target or len(done) == len(IMPORT_DECADES):
            break
        for start, end in decade_ranges():
            if start in done:
                continue
            data = discover_page(start, end, page)
            if not data:
                done.add(start)
                continue
            results = data.get("results") or []
            if not results:
                done.add(start)
                continue
            added = 0
            page_existing = 0
            page_duplicate = 0
            page_no_id = 0
            for item in results:
                mid = item.get("id")
                if not mid:
                    page_no_id += 1
                    continue
                if mid in seen_ids:
                    page_existing += 1
                    continue
                year = (item.get("release_date") or "")[:4]
                if fm.is_duplicate({
                    "title": item.get("title"),
                    "original_title": item.get("original_title"),
                    "year": year,
                }, index):
                    page_duplicate += 1
                    continue
                seen_ids.add(mid)
                item["_decade"] = start
                candidates.append(item)
                added += 1
                if len(candidates) >= target:
                    break
            skipped["existing"] += page_existing
            skipped["duplicate"] += page_duplicate
            skipped["no_id"] += page_no_id
            total_pages = data.get("total_pages") or 0
            if total_pages and page >= total_pages:
                done.add(start)
            print(
                f"  {start}-е: страница {page}/{total_pages or '?'}, +{added}, "
                f"всего {len(candidates)} (в каталоге {page_existing}, "
                f"дубли {page_duplicate}, без id {page_no_id})"
            )
            if len(candidates) >= target:
                break
    print(
        f"Пропущено: уже в каталоге {skipped['existing']}, "
        f"дубли по названию {skipped['duplicate']}, без id {skipped['no_id']}"
    )
    return candidates


def omdb_lookup(imdb_id):
    if not OMDB_API_KEY or not imdb_id:
        return None
    try:
        r = fm.session.get("https://www.omdbapi.com/", params={
            "apikey": OMDB_API_KEY,
            "i": imdb_id,
            "plot": "full",
            "r": "json",
        }, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("Response") != "True":
            return None
        return data
    except Exception as e:
        print(f"  OMDb {imdb_id}: {e}")
        return None


def tastedive_similar(title):
    if not TASTEDIVE_API_KEY or not title:
        return []
    try:
        r = fm.session.get("https://tastedive.com/api/similar", params={
            "q": title,
            "type": "movies",
            "info": 1,
            "limit": 10,
            "k": TASTEDIVE_API_KEY,
        }, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        similar = data.get("Similar") or data.get("similar") or {}
        results = similar.get("Results") or similar.get("results") or []
        names = []
        for item in results:
            name = (item.get("Name") or item.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return names
    except Exception as e:
        print(f"  TasteDive '{title}': {e}")
        return []


def resolve_tmdb_id(name, exclude_id, cache):
    key = name.lower()
    if key in cache:
        return cache[key]
    data = fm.tmdb_get("/search/movie", {"query": name, "include_adult": "false"}) or {}
    found = None
    for item in (data.get("results") or [])[:5]:
        if item.get("id") == exclude_id:
            continue
        if fm.titles_match(name, item.get("title")) or fm.titles_match(name, item.get("original_title")):
            found = item.get("id")
            break
    cache[key] = found
    return found


def enrich_similar_with_tastedive(movies, budget):
    """Дополняет «похожие» названиями TasteDive, не заменяя рекомендации TMDB."""
    if not TASTEDIVE_API_KEY or budget <= 0:
        return 0
    cache = {}
    used = 0
    for movie in movies:
        if used >= budget:
            break
        similar = list(movie.get("similar") or [])
        if len(similar) >= TASTEDIVE_TARGET_SIMILAR:
            continue
        title = movie.get("title") or movie.get("original_title")
        if not title:
            continue
        names = tastedive_similar(title)
        used += 1
        for name in names:
            if len(similar) >= TASTEDIVE_TARGET_SIMILAR:
                break
            mid = resolve_tmdb_id(name, movie["id"], cache)
            if mid and mid != movie["id"] and mid not in similar:
                similar.append(mid)
        movie["similar"] = similar
    return used


def enrich_candidate(item):
    mid = item["id"]
    details = fm.tmdb_get(f"/movie/{mid}") or {}
    if not details:
        return None

    title = details.get("title") or details.get("original_title") or item.get("title") or ""
    original = details.get("original_title") or item.get("original_title") or ""
    release = details.get("release_date") or item.get("release_date") or ""
    year = release[:4]
    if not title or not year:
        return None

    overview_ru = (details.get("overview") or "").strip()
    overview_en = ""
    if not overview_ru:
        overview_en = fm.get_en_overview(mid)
        if not overview_en:
            return None

    poster_path = details.get("poster_path") or item.get("poster_path") or ""
    if not poster_path:
        return None

    credits = fm.tmdb_get(f"/movie/{mid}/credits") or {}
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

    vote_count = int(details.get("vote_count") or item.get("vote_count") or 0)
    vote_average = details.get("vote_average") or item.get("vote_average") or 0
    popularity = item.get("popularity") or details.get("popularity") or 0
    imdb_id = details.get("imdb_id") or ""

    similar = fm.get_recommendations(mid)
    trailer = fm.get_trailer(mid) if vote_count >= IMPORT_LOCAL_POSTER_VOTES else ""

    remote_poster = fm.IMG_MIRROR + poster_path
    remote_fallback = fm.IMG_SOURCES[0] + poster_path

    return {
        "id": mid,
        "source": "tmdb",
        "title": title,
        "original_title": original,
        "year": year,
        "release_date": release,
        "director": director,
        "rating": round(vote_average or 0, 1),
        "rating_tmdb": round(vote_average or 0, 1),
        "imdb_rating": None,
        "rating_source": "tmdb",
        "popularity": round(popularity or 0, 1),
        "runtime": details.get("runtime") or 0,
        "genres": [g["id"] for g in details.get("genres", [])],
        "countries": [c.get("name", "") for c in details.get("production_countries", [])],
        "description": overview_ru,
        "description_en": overview_en,
        "poster": remote_poster,
        "poster_fallback": remote_fallback,
        "backdrop": details.get("backdrop_path") or "",
        "cast": cast,
        "similar": similar,
        "trailer": trailer,
        "imdb_id": imdb_id,
        "_poster_path": poster_path,
        "_local_poster": vote_count >= IMPORT_LOCAL_POSTER_VOTES,
    }


def validate_movie(movie, ids):
    errors = []
    if not movie.get("id"):
        errors.append("нет id")
    if movie.get("id") in ids:
        errors.append("дубль id")
    if not movie.get("title"):
        errors.append("нет названия")
    if not movie.get("year"):
        errors.append("нет года")
    if not (movie.get("description") or movie.get("description_en")):
        errors.append("нет описания")
    if not movie.get("poster"):
        errors.append("нет постера")
    if not isinstance(movie.get("genres"), list):
        errors.append("жанры не список")
    if not isinstance(movie.get("countries"), list):
        errors.append("страны не список")
    return errors


def apply_omdb(movies, budget):
    for movie in movies:
        if budget <= 0:
            break
        imdb_id = movie.get("imdb_id")
        if not imdb_id:
            continue
        data = omdb_lookup(imdb_id)
        budget -= 1
        if not data:
            continue
        rating = data.get("imdbRating")
        if rating and rating != "N/A":
            try:
                movie["imdb_rating"] = round(float(rating), 1)
                movie["rating"] = movie["imdb_rating"]
                movie["rating_source"] = "imdb"
            except (TypeError, ValueError):
                pass
        if not movie.get("description_en"):
            plot = fm.clean_text(data.get("Plot"))
            if plot and plot != "N/A":
                movie["description_en"] = plot
        # OMDb-постер (IMDb CDN) лучше подходит для длинного хвоста:
        # популярным фильмам постер всё равно скачается локально.
        poster = data.get("Poster")
        if poster and poster != "N/A" and not movie.get("_local_poster"):
            if not movie.get("poster_fallback"):
                movie["poster_fallback"] = movie.get("poster")
            movie["poster"] = poster
    return budget


def apply_posters(movies, download=True):
    for movie in movies:
        poster_path = movie.pop("_poster_path", "")
        local = movie.pop("_local_poster", False)
        if download and local and poster_path:
            saved = fm.download_poster(movie["id"], poster_path)
            if saved:
                movie["poster"] = saved
                if not movie.get("poster_fallback"):
                    movie["poster_fallback"] = fm.IMG_SOURCES[0] + poster_path


def write_import_log(movies, started, decades):
    folder = IMPORT_LOG_DIR
    os.makedirs(folder, exist_ok=True)
    day = started.strftime("%Y-%m-%d")
    path = os.path.join(folder, f"{day}.md")
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(f"# Импорт фильмов — {day}\n\n")
        f.write(f"## {started.strftime('%H:%M')} UTC\n\n")
        f.write(f"- Десятилетия: {', '.join(f'{d}-е' for d in decades)}\n")
        f.write(f"- Добавлено: {len(movies)}\n\n")
        f.write("| # | Фильм | Год | Рейтинг |\n|---:|---|---:|---:|\n")
        for i, movie in enumerate(movies, 1):
            title = (movie.get("title") or "").replace("|", "\\|")
            rating = movie.get("rating") or "—"
            f.write(f"| {i} | {title} | {movie.get('year') or ''} | {rating} |\n")
        f.write("\n")


def run():
    if IMPORT_LIMIT <= 0:
        print("Импорт выключен: IMPORT_LIMIT=0")
        return 0
    if not fm.TMDB_API_KEY:
        print("Нет TMDB_API_KEY")
        return 1

    started = datetime.datetime.now(datetime.timezone.utc)
    movies = load_movies()
    existing_ids = {m["id"] for m in movies}
    print(f"Импорт: цель {IMPORT_LIMIT}, десятилетия {IMPORT_DECADES}, dry-run={DRY_RUN}")

    candidates = collect_candidates(IMPORT_LIMIT)
    print(f"Кандидатов собрано: {len(candidates)}")

    selected = []
    with ThreadPoolExecutor(max_workers=IMPORT_WORKERS) as ex:
        futures = {ex.submit(enrich_candidate, item): item for item in candidates}
        for future in as_completed(futures):
            try:
                movie = future.result()
            except Exception as e:
                print(f"  ошибка карточки: {e}")
                continue
            if not movie:
                continue
            if len(selected) >= IMPORT_LIMIT:
                break
            selected.append(movie)

    omdb_left = apply_omdb(selected, OMDB_MAX_MOVIES)
    tastedive_used = enrich_similar_with_tastedive(selected, TASTEDIVE_MAX_MOVIES)

    # Финальная проверка и дедупликация по id и названию+году.
    index = fm.build_existing_index(movies)
    valid = []
    skipped = []
    for movie in selected:
        movie.pop("_decade", None)
        errors = validate_movie(movie, existing_ids)
        if errors:
            skipped.append((movie.get("title"), errors))
            continue
        if fm.is_duplicate(movie, index):
            skipped.append((movie.get("title"), ["дубль названия и года"]))
            continue
        movie["rating_source"] = movie.get("rating_source") or "tmdb"
        valid.append(movie)
        existing_ids.add(movie["id"])
        fm.index_movie(index, movie)

    planned_local = sum(1 for m in valid if m.get("_local_poster"))
    apply_posters(valid, download=not DRY_RUN)

    ru = sum(1 for m in valid if m.get("description"))
    en = sum(1 for m in valid if not m.get("description"))
    local = planned_local if DRY_RUN else sum(
        1 for m in valid if str(m.get("poster", "")).startswith("posters/")
    )
    remote = len(valid) - local
    imdb = sum(1 for m in valid if m.get("rating_source") == "imdb")

    print(f"Готово к добавлению: {len(valid)}")
    print(f"  русское описание: {ru}, английское: {en}")
    print(f"  постеры: локально {local}, по ссылке {remote}")
    print(f"  рейтинг IMDb: {imdb}, осталось OMDb-запросов: {omdb_left}")
    print(f"  TasteDive: обработано {tastedive_used} фильмов")
    if skipped:
        print(f"  пропущено: {len(skipped)}")
        for title, errors in skipped[:10]:
            print(f"    {title}: {', '.join(errors)}")

    for movie in valid[:10]:
        print(f"  + {movie['title']} ({movie['year']}) — {movie.get('rating')}")

    if DRY_RUN:
        print("Dry-run: movies.json не изменён")
        return 0
    if not valid:
        print("Нечего добавлять")
        return 0

    added_at = datetime.date.today().isoformat()
    for movie in valid:
        movie["added_at"] = added_at
    movies.extend(valid)
    cast_ok = True
    try:
        update_cast_people(valid)
        print("Актёры обновлены")
    except Exception as e:
        cast_ok = False
        print(f"  актёры: {e}")
    # cast живёт только в cast.json; в movies.json он не нужен
    if cast_ok:
        for movie in movies:
            movie.pop("cast", None)
    # Рекомендации TMDB почти всегда ведут на фильмы вне каталога:
    # оставляем только существующие id и добираем похожие из базы.
    fm.repair_similar(movies)
    save_movies_atomic(movies)
    print(f"Добавлено в movies.json: {len(valid)}, всего теперь {len(movies)}")
    try:
        write_import_log(valid, started, IMPORT_DECADES)
        print(f"Лог импорта: {IMPORT_LOG_DIR}/{started.strftime('%Y-%m-%d')}.md")
    except Exception as e:
        print(f"  лог импорта: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(run())

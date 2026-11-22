"""Проверка данных сайта перед коммитом.

Запуск из корня репозитория: python scripts/validate.py
Код возврата 1 — данные битые, публиковать нельзя.
"""

import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
POSTERS = os.path.join(ROOT, "posters")

# Защита в глубину: trailer уходит в iframe, poster_fallback — в src картинки.
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
FALLBACK_HOSTS = {
    "image.tmdb.org",
    "kinopoiskapiunofficial.tech",
    "wsrv.nl",
    "images.weserv.nl",
}
FALLBACK_HOST_SUFFIXES = (".yandex.net",)

errors = []
warnings = []


def error(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def load(name, default):
    path = os.path.join(DATA, f"{name}.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        error(f"{name}.json: {e}")
        return default


def norm_year(value):
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def check_movie(movie, ids, current_year):
    mid = movie.get("id")
    if not isinstance(mid, int):
        error(f"movies: id не число: {mid!r}")
        return
    if not isinstance(movie.get("title"), str) or not movie["title"].strip():
        error(f"{mid}: пустой title")
    if movie.get("original_title") is not None and not isinstance(movie["original_title"], str):
        error(f"{mid}: original_title не строка")

    year = movie.get("year")
    if year not in (None, ""):
        if not isinstance(year, str) or not re.fullmatch(r"\d{4}", year):
            error(f"{mid}: year={year!r} — нужен YYYY")
        else:
            y = int(year)
            if not (1880 <= y <= current_year + 5):
                error(f"{mid}: year={year} вне разумного диапазона")

    release = movie.get("release_date")
    if release not in (None, ""):
        if not isinstance(release, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release):
            error(f"{mid}: release_date={release!r} — нужен YYYY-MM-DD")
        else:
            try:
                datetime.date.fromisoformat(release)
            except ValueError:
                error(f"{mid}: release_date={release!r} — несуществующая дата")

    for field, low, high in (("rating", 0, 10), ("kp_rating", 0, 10)):
        value = movie.get(field)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            error(f"{mid}: {field}={value!r} не число")
        elif not (low <= value <= high):
            error(f"{mid}: {field}={value} вне {low}..{high}")

    popularity = movie.get("popularity")
    if popularity is not None and (not isinstance(popularity, (int, float)) or popularity < 0):
        error(f"{mid}: popularity={popularity!r}")

    genres = movie.get("genres")
    if genres is not None and (
        not isinstance(genres, list) or any(not isinstance(g, int) for g in genres)
    ):
        error(f"{mid}: genres должен быть списком id")

    countries = movie.get("countries")
    if countries is not None and (
        not isinstance(countries, list) or any(not isinstance(c, str) for c in countries)
    ):
        error(f"{mid}: countries должен быть списком строк")

    similar = movie.get("similar")
    if similar is not None:
        if not isinstance(similar, list) or any(not isinstance(s, int) for s in similar):
            error(f"{mid}: similar должен быть списком id")
        else:
            if mid in similar:
                error(f"{mid}: similar ссылается сам на себя")
            unknown = [s for s in similar if s not in ids]
            if unknown:
                error(f"{mid}: similar содержит {len(unknown)} id вне каталога")
            if len(similar) < 4:
                warn(f"{mid}: в similar только {len(similar)} фильмов")
            if len(similar) > 10:
                warn(f"{mid}: в similar {len(similar)} фильмов (многовато)")

    poster = movie.get("poster")
    if not isinstance(poster, str) or not poster:
        error(f"{mid}: пустой poster")
    elif not poster.startswith(("http://", "https://")):
        path = os.path.join(ROOT, poster)
        if not os.path.exists(path):
            error(f"{mid}: файла постера нет: {poster}")
        elif os.path.getsize(path) < 1000:
            error(f"{mid}: постер подозрительно маленький: {poster}")
        elif poster.lower().endswith(".jpg"):
            warn(f"{mid}: постер ещё JPG, а не WebP")

    fallback = movie.get("poster_fallback")
    if fallback is not None and not isinstance(fallback, str):
        error(f"{mid}: poster_fallback не строка")
    elif fallback and "no-poster" in fallback.lower():
        # Заглушка не ломает карточку: основной постер уже проверен выше.
        warn(f"{mid}: poster_fallback ведёт на заглушку ({fallback})")

    trailer = movie.get("trailer")
    if trailer is not None and not isinstance(trailer, str):
        error(f"{mid}: trailer не строка")
    elif trailer and not YOUTUBE_ID.match(trailer):
        error(f"{mid}: trailer не похож на YouTube-ID: {trailer!r}")

    if fallback:
        # Схема обязательна https: javascript:/data: в src недопустимы.
        match = re.match(r"^https://([^/?#]+)", fallback)
        if not match:
            error(f"{mid}: poster_fallback должен быть https-ссылкой ({fallback})")
        else:
            host = match.group(1).lower().split(":")[0]
            if host not in FALLBACK_HOSTS and not host.endswith(FALLBACK_HOST_SUFFIXES):
                warn(f"{mid}: poster_fallback с неизвестного домена: {host}")

    if movie.get("cast"):
        warn(f"{mid}: cast продублирован в movies.json (должен быть только в cast.json)")


def main():
    current_year = datetime.date.today().year
    movies = load("movies", [])
    genres = load("genres", [])
    lists = load("lists", {})
    cast = load("cast", {})
    people = load("people", [])
    collections = load("collections", {})

    if not isinstance(movies, list) or not movies:
        error("movies.json: пустой или не список")
        movies = []

    ids = set()
    for movie in movies:
        mid = movie.get("id")
        if isinstance(mid, int):
            if mid in ids:
                error(f"movies: повторяется id {mid}")
            ids.add(mid)

    for movie in movies:
        check_movie(movie, ids, current_year)

    if not isinstance(genres, list) or not genres:
        error("genres.json: пустой или не список")
    else:
        for genre in genres:
            if not isinstance(genre, dict) or not isinstance(genre.get("id"), int):
                error(f"genres.json: битая запись {genre!r}")
                break

    if not isinstance(lists, dict):
        error("lists.json: не объект")
    else:
        for key in ("now_playing", "upcoming"):
            value = lists.get(key)
            if not isinstance(value, list) or any(not isinstance(x, int) for x in value):
                error(f"lists.json: {key} должен быть списком id")
                continue
            unknown = [x for x in value if x not in ids]
            if unknown:
                error(f"lists.json: {key} содержит {len(unknown)} id вне каталога")

    if not isinstance(cast, dict):
        error("cast.json: не объект")
    else:
        unknown = [key for key in cast if str(key) not in {str(i) for i in ids}]
        if unknown:
            warn(f"cast.json: {len(unknown)} записей для фильмов вне каталога")

    if not isinstance(people, list):
        error("people.json: не список")
    else:
        for person in people:
            if not isinstance(person, dict) or not person.get("name"):
                error("people.json: запись без имени")
                break

    collection_items = collections.get("collections") if isinstance(collections, dict) else None
    if collection_items is not None:
        if not isinstance(collection_items, list):
            error("collections.json: collections не список")
        else:
            for collection in collection_items:
                items = collection.get("items") if isinstance(collection, dict) else None
                if not isinstance(items, list):
                    error("collections.json: у подборки нет items")
                    continue
                unknown = [x for x in items if x not in ids]
                if unknown:
                    warn(f"collections.json: «{collection.get('title')}» — {len(unknown)} id вне каталога")

    poster_files = set()
    if os.path.isdir(POSTERS):
        poster_files = {
            name for name in os.listdir(POSTERS)
            if name.lower().endswith((".jpg", ".jpeg", ".webp", ".png"))
        }
    referenced = {
        os.path.basename(m.get("poster") or "")
        for m in movies
        if m.get("poster") and not str(m["poster"]).startswith(("http://", "https://"))
    }
    orphans = poster_files - referenced - {"placeholder.jpg", "placeholder.webp"}
    if orphans:
        warn(f"posters: {len(orphans)} файлов не используются (удалит пайплайн)")

    poster_bytes = 0
    for name in poster_files:
        try:
            poster_bytes += os.path.getsize(os.path.join(POSTERS, name))
        except OSError:
            pass
    movies_size = os.path.getsize(os.path.join(DATA, "movies.json")) if os.path.exists(
        os.path.join(DATA, "movies.json")
    ) else 0

    print(f"фильмов: {len(movies)}")
    print(f"постеров: {len(poster_files)} ({poster_bytes / 1024 / 1024:.1f} МБ)")
    print(f"movies.json: {movies_size / 1024 / 1024:.1f} МБ")
    if warnings:
        print(f"\nПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):")
        for message in warnings[:50]:
            print(f"  - {message}")
        if len(warnings) > 50:
            print(f"  … ещё {len(warnings) - 50}")
    if errors:
        print(f"\nОШИБКИ ({len(errors)}):")
        for message in errors[:100]:
            print(f"  - {message}")
        if len(errors) > 100:
            print(f"  … ещё {len(errors) - 100}")
        return 1
    print("\nданные в порядке")
    return 0


if __name__ == "__main__":
    sys.exit(main())

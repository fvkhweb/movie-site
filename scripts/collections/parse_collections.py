# -*- coding: utf-8 -*-
"""Импорт киноподборок (Letterboxd и подобные) в movie-site.

Как пользоваться:
1. Сохрани страницу подборки в браузере (Ctrl+S → «веб-страница, только HTML»)
   в папку scripts/collections/sources/.
   Для подборок с несколькими страницами именуй файлы так:
       mylist-p1.html, mylist-p2.html  (одна подборка, по порядку)
   Файл без суффикса -pN — самостоятельная подборка.
2. Запусти: python scripts/collections/parse_collections.py
3. Скрипт сопоставит фильмы с data/movies.json (по оригинальному названию
   и году, без внешних API), напечатает отчёт и запишет data/collections.json.

Сайт подхватывает data/collections.json и показывает подборки в секции
«Подборки» на главной. Никаких изменений в fetch_movies.py и lists.json.
"""
import json
import os
import re
import sys
from collections import defaultdict

# Консоль Windows по умолчанию в cp1251 — переключаем на UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # корень репозитория
SOURCES_DIR = os.path.join(HERE, "sources")
OUT_PATH = os.path.join(ROOT, "data", "collections.json")
MOVIES_PATH = os.path.join(ROOT, "data", "movies.json")

# ── Извлечение фильмов из сохранённого HTML ─────────────────────────

TITLE_YEAR_RE = re.compile(r'<img[^>]*alt="([^"]+?)\s*\((\d{4})[–-]?\d{0,4}\)"', re.I)
SLUG_RE = re.compile(r'data-film-slug="([^"]+)"', re.I)
OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.I)

def extract_films(html):
    """[(title, year, slug)] в порядке появления на странице."""
    films = []
    seen = set()
    # Идём по блокам постеров: внутри блока берём alt и slug
    for m in TITLE_YEAR_RE.finditer(html):
        title, year = m.group(1).strip(), int(m.group(2))
        # slug ищем в ближайших 1200 символах до img (блок постера)
        block = html[max(0, m.start() - 1200):m.start()]
        slugs = SLUG_RE.findall(block)
        slug = slugs[-1] if slugs else ""
        key = slug or f"{title.lower()}|{year}"
        if key in seen:
            continue
        seen.add(key)
        films.append({"title": title, "year": year, "slug": slug})
    return films

def extract_list_title(html, fallback_name):
    m = OG_TITLE_RE.search(html)
    if m:
        # «Название — a list by Автор» → оставляем название
        t = re.sub(r"\s*[—-]\s*a\s+list\s+by\s+.*$", "", m.group(1), flags=re.I).strip()
        if t:
            return t
    return fallback_name

# ── Сопоставление с каталогом ───────────────────────────────────────

def normalize(s):
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()

def load_catalog():
    with open(MOVIES_PATH, encoding="utf-8") as f:
        movies = json.load(f)
    index = defaultdict(list)  # нормализованное название -> [фильм]
    for m in movies:
        for key in (normalize(m.get("original_title")), normalize(m.get("title"))):
            if key:
                index[key].append(m)
    return movies, index

def match(film, index):
    """TMDB-фильм из каталога или None. Год ±1, иначе — точное название без года."""
    norm = normalize(film["title"])
    cands = index.get(norm, [])
    if not cands:
        return None
    for delta in (0, -1, 1):
        for m in cands:
            if abs(int(m.get("year", 0)) - film["year"]) == delta:
                return m
    # год не сошёлся, но название уникально — всё равно берём
    return cands[0] if len(cands) == 1 else None

# ── Сборка подборок ─────────────────────────────────────────────────

def group_source_files():
    """{имя подборки: [файлы по порядку]}.
    mylist-p1.html, mylist-p2.html → 'mylist'; single.html → 'single'."""
    if not os.path.isdir(SOURCES_DIR):
        return {}
    groups = defaultdict(list)
    for name in sorted(os.listdir(SOURCES_DIR)):
        if not name.lower().endswith((".html", ".htm")):
            continue
        base = re.sub(r"-p\d+\.html?$", "", name.lower(), flags=re.I)
        base = re.sub(r"\.html?$", "", base, flags=re.I)
        groups[base].append(os.path.join(SOURCES_DIR, name))
    return groups

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40] or "collection"

def main():
    groups = group_source_files()
    if not groups:
        print(f"Нет HTML-файлов в {SOURCES_DIR}")
        print("Сохрани страницы подборок (Ctrl+S → «только HTML») в эту папку")
        print("и запусти скрипт снова. Пример имени: top250-p1.html")
        return 1

    movies, index = load_catalog()
    print(f"Каталог: {len(movies)} фильмов, источников: {len(groups)}\n")

    collections = []
    for base, files in groups.items():
        films, html_all = [], ""
        for path in files:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
            html_all += raw
            films.extend(extract_films(raw))
        # дедуп по (название, год) — на случай повторов между страницами
        seen, ordered = set(), []
        for film in films:
            key = (normalize(film["title"]), film["year"])
            if key not in seen:
                seen.add(key)
                ordered.append(film)

        matched, unmatched = [], []
        for film in ordered:
            m = match(film, index)
            if m:
                matched.append(m["id"])
            else:
                unmatched.append(film)

        title = extract_list_title(html_all, base)
        coll = {
            "id": slugify(base),
            "title": title,
            "source": "letterboxd",
            "total": len(ordered),
            "items": matched,
            "unmatched": unmatched,
        }
        collections.append(coll)
        pct = f"{len(matched)}/{len(ordered)}"
        print(f"▸ {title}: совпало {pct}")
        if unmatched:
            for u in unmatched[:12]:
                print(f"    ✗ {u['title']} ({u['year']})")
            if len(unmatched) > 12:
                print(f"    … и ещё {len(unmatched) - 12}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "collections": collections}, f, ensure_ascii=False, indent=1)
    print(f"\nГотово: {OUT_PATH} ({len(collections)} подборок)")
    return 0

if __name__ == "__main__":
    sys.exit(main())

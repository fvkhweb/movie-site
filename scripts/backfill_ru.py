"""Постепенная замена английских описаний на русские через Кинопоиск.

Работает отдельно от ежедневного пайплайна и меняет только поле description.
Запуск:
    RU_BACKFILL_LIMIT=60 python scripts/backfill_ru.py
"""

import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_movies as fm  # noqa: E402

DATA_DIR = os.environ.get("MOVIE_DATA_DIR", "data")
MOVIES_PATH = os.path.join(DATA_DIR, "movies.json")
STATE_PATH = os.environ.get("RU_BACKFILL_STATE", os.path.join(DATA_DIR, "ru_backfill.json"))
LIMIT = int(os.environ.get("RU_BACKFILL_LIMIT", "60"))
COOLDOWN_DAYS = int(os.environ.get("RU_BACKFILL_COOLDOWN_DAYS", "14"))


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def should_skip(state, movie):
    last = state.get("failed", {}).get(str(movie.get("id")))
    if not last:
        return False
    try:
        day = datetime.date.fromisoformat(str(last)[:10])
    except ValueError:
        return False
    return (datetime.date.today() - day).days < COOLDOWN_DAYS


def find_description(movie):
    title = movie.get("title") or ""
    year = movie.get("year") or ""
    original = movie.get("original_title") or ""
    kp = fm.get_kp_data(title, year, original)
    if kp and not kp.get("error") and kp.get("description"):
        return kp["description"]
    kp = fm.get_kp_unofficial(title, year, original)
    if kp and not kp.get("error") and kp.get("description"):
        return kp["description"]
    return ""


def run():
    if not fm.KP_DEV_KEYS and not fm.KPU_API_KEYS:
        print("Нет ключей Кинопоиска — backfill выключен")
        return 1
    if LIMIT <= 0:
        print("Backfill выключен: RU_BACKFILL_LIMIT=0")
        return 0

    movies = load_json(MOVIES_PATH, [])
    state = load_json(STATE_PATH, {"version": 1, "failed": {}})
    state.setdefault("failed", {})
    candidates = [
        m for m in movies
        if m.get("description_en") and not m.get("description") and not should_skip(state, m)
    ]
    candidates.sort(key=lambda m: m.get("popularity") or 0, reverse=True)
    print(f"Backfill: кандидатов {len(candidates)}, лимит {LIMIT}")

    done = 0
    found = 0
    for movie in candidates[:LIMIT]:
        desc = find_description(movie)
        done += 1
        if desc:
            movie["description"] = fm.clean_text(desc)
            movie["description_source"] = "kp"
            state["failed"].pop(str(movie.get("id")), None)
            found += 1
            print(f"  RU: {movie.get('title')} ({movie.get('year')})")
        else:
            state["failed"][str(movie.get("id"))] = datetime.date.today().isoformat()
        time.sleep(0.3)

    if found:
        save_json_atomic(MOVIES_PATH, movies)
    save_json_atomic(STATE_PATH, state)

    left = sum(1 for m in movies if m.get("description_en") and not m.get("description"))
    print(f"Backfill: обработано {done}, русифицировано {found}, осталось {left}")
    return 0


if __name__ == "__main__":
    sys.exit(run())

"""Чистит заведомо неподтверждённые данные Кинопоиска.

Без API: у невышедших фильмов без kp_id данные КП могли прийти из
одноимённого фильма другого года (например, 1492198). Удаляем рейтинг,
кадр, запасной постер, факты и описание, пока матч не подтверждён.

Запуск из корня репозитория: python scripts/repair_kp.py
"""

import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "movies.json")

KP_FIELDS = ("kp_rating", "facts", "frame", "poster_fallback")
SUSPICIOUS_FIELDS = ("kp_rating",)
SUSPICIOUS_CLEAR = ("kp_rating", "frame", "facts")
KNOWN_BAD_IDS = {1492198}  # «Искусственный интеллект» 2026 + A.I. 2025


def main():
    today = datetime.date.today().isoformat()
    with open(PATH, encoding="utf-8") as f:
        movies = json.load(f)

    changed = []
    for movie in movies:
        mid = movie.get("id")
        release = (movie.get("release_date") or "")[:10]
        future = bool(release) and release > today
        known_bad = mid in KNOWN_BAD_IDS
        suspicious_future = (
            future
            and not movie.get("kp_id")
            and any(movie.get(field) for field in SUSPICIOUS_FIELDS)
        )
        if not (known_bad or suspicious_future):
            continue

        removed = []
        fields = KP_FIELDS if known_bad else SUSPICIOUS_CLEAR
        for field in fields:
            if movie.pop(field, None) is not None:
                removed.append(field)
        if known_bad or movie.get("description_source") == "kp":
            if movie.pop("description", None) is not None:
                removed.append("description")
            movie.pop("description_source", None)
        if removed:
            changed.append((mid, movie.get("title"), removed))

    if changed:
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False)
        os.replace(tmp, PATH)

    for mid, title, removed in changed:
        print(f"{mid} {title}: убрано {', '.join(removed)}")
    print(f"исправлено карточек: {len(changed)}")


if __name__ == "__main__":
    main()

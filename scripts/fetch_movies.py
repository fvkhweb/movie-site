import os, json, requests

API_KEY = os.environ["TMDB_API_KEY"]
BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"
LANG = "ru-RU"

def fetch(path, params=None):
    p = {"api_key": API_KEY, "language": LANG, **(params or {})}
    r = requests.get(f"{BASE}{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()

def clean_movies(results):
    movies = []
    for m in results:
        if not m.get("poster_path"):
            continue
        movies.append({
            "id": m["id"],
            "title": m["title"],
            "overview": m.get("overview", ""),
            "rating": m.get("vote_average", 0),
            "year": (m.get("release_date") or "")[:4],
            "genres": m.get("genre_ids", []),
            "poster": IMG + m["poster_path"] if m.get("poster_path") else None,
        })
    return movies

def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

GENRES = fetch("/genre/movie/list")["genres"]
save("genres", GENRES)

popular, top = [], []
for page in range(1, 11):
    popular += clean_movies(fetch("/movie/popular", {"page": page})["results"])
    top += clean_movies(fetch("/movie/top_rated", {"page": page})["results"])

save("popular", popular)
save("top_rated", sorted(top, key=lambda x: -x["rating"]))

by_genre = {}
for g in GENRES:
    res = []
    for page in range(1, 4):
        res += clean_movies(fetch("/discover/movie", {
            "with_genres": g["id"], "sort_by": "popularity.desc", "page": page
        })["results"])
    by_genre[str(g["id"])] = res
save("by_genre", by_genre)

print(f"Готово: popular={len(popular)}, жанров={len(GENRES)}")

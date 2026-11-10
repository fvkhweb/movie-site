import os, json, requests, time

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
POISKKINO_API_KEY = os.environ["POISKKINO_API_KEY"]

TMDB_BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"
LANG = "ru-RU"

KP_BASE = "https://api.kinopoisk.dev/v1.4/movie"
KP_HEADERS = {"X-API-KEY": POISKKINO_API_KEY}

def fetch_tmdb(path, params=None):
    p = {"api_key": TMDB_API_KEY, "language": LANG, **(params or {})}
    r = requests.get(f"{TMDB_BASE}{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()

# Поиск фильма в Кинопоиске по названию и году
def get_kp_data(title, year):
    try:
        # Ищем по названию, ограничиваем 1 результатом
        params = {"query": title, "limit": 1}
        if year and str(year).isdigit():
            params["year"] = year
            
        r = requests.get(f"{KP_BASE}/search", headers=KP_HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            docs = r.json().get("docs", [])
            if docs:
                movie = docs[0]
                kp_id = movie["id"]
                poster = movie.get("poster", {}).get("url")
                
                # Запрашиваем полные детали (актёры, описание) по ID
                time.sleep(0.2) # Задержка, чтобы не превысить лимит API (5 запросов/сек)
                d_resp = requests.get(f"{KP_BASE}/{kp_id}", headers=KP_HEADERS, timeout=15)
                if d_resp.status_code == 200:
                    details = d_resp.json()
                    # Вытаскиваем актёров
                    actors = []
                    for p in details.get("persons", []):
                        if "актер" in p.get("profession", "").lower() or p.get("enProfession") == "actor":
                            actors.append(p.get("name"))
                    
                    return {
                        "poster": poster,
                        "description": details.get("description") or movie.get("description"),
                        "actors": ", ".join(actors[:10]) + ("..." if len(actors) > 10 else ""),
                        "kp_rating": details.get("rating", {}).get("kp")
                    }
    except Exception as e:
        print(f"Ошибка при запросе к Кинопоиску для '{title}': {e}")
    return None

def process_movies(results):
    movies = []
    for m in results:
        if not m.get("poster_path"):
            continue
            
        title = m["title"]
        year = (m.get("release_date") or "")[:4]
        
        # Базовые данные из TMDB
        movie_data = {
            "id": m["id"],
            "title": title,
            "rating": m.get("vote_average", 0),
            "year": year,
            "genres": m.get("genre_ids", []),
            "poster": IMG + m["poster_path"],
            "description": m.get("overview", ""),
            "actors": ""
        }
        
        # Обогащаем данными из Кинопоиска (постер, описание, актёры)
        print(f"Ищем в Кинопоиске: {title} ({year})")
        kp_info = get_kp_data(title, year)
        if kp_info:
            if kp_info.get("poster"):
                movie_data["poster"] = kp_info["poster"] # Заменяем постер на Кинопоиск
            if kp_info.get("description"):
                movie_data["description"] = kp_info["description"]
            if kp_info.get("actors"):
                movie_data["actors"] = kp_info["actors"]
            if kp_info.get("kp_rating"):
                movie_data["rating"] = kp_info["kp_rating"] # Используем рейтинг КП
                
        movies.append(movie_data)
        
    return movies

def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

# Получаем жанры TMDB
GENRES = fetch_tmdb("/genre/movie/list")["genres"]
save("genres", GENRES)

# Собираем популярные (для примера берем 3 страницы = 60 фильмов, чтобы не упереться в лимит API)
popular = []
for page in range(1, 4):
    results = fetch_tmdb("/movie/popular", {"page": page})["results"]
    popular += process_movies(results)

save("popular", popular)
print(f"Готово! Собрано {len(popular)} фильмов.")

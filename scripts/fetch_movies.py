import os, json, requests, time

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
POISKKINO_API_KEY = os.environ["POISKKINO_API_KEY"]

TMDB_BASE = "https://api.themoviedb.org/3"
IMG_MIRROR = "https://imagetmdb.com/t/p/w500" # Зеркало TMDB как fallback
LANG = "ru-RU"

KP_BASE = "https://api.kinopoisk.dev/v1.4/movie"
KP_HEADERS = {"X-API-KEY": POISKKINO_API_KEY}

def fetch_tmdb(path, params=None):
    p = {"api_key": TMDB_API_KEY, "language": LANG, **(params or {})}
    r = requests.get(f"{TMDB_BASE}{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()

def get_kp_data(title, year):
    try:
        params = {"query": title, "limit": 1}
        if year and str(year).isdigit():
            params["year"] = year
            
        time.sleep(0.3)
        r = requests.get(f"{KP_BASE}/search", headers=KP_HEADERS, params=params, timeout=15)
        
        if r.status_code == 200:
            docs = r.json().get("docs", [])
            if docs:
                movie = docs[0]
                kp_id = movie["id"]
                
                # Формируем прямую ссылку на постер Кинопоиска
                direct_poster_url = f"https://st.kp.yandex.net/images/film_iphone/iphone360_{kp_id}.jpg"
                
                # Получаем детали (актёры, описание)
                time.sleep(0.3)
                d_resp = requests.get(f"{KP_BASE}/{kp_id}", headers=KP_HEADERS, timeout=15)
                
                if d_resp.status_code == 200:
                    details = d_resp.json()
                    actors = [p.get("name") for p in details.get("persons", []) if "актер" in p.get("profession", "").lower() or p.get("enProfession") == "actor"]
                    
                    return {
                        "poster": direct_poster_url, # Используем прямую ссылку
                        "description": details.get("description") or movie.get("description"),
                        "actors": ", ".join(actors[:10]) + ("..." if len(actors) > 10 else ""),
                        "kp_rating": details.get("rating", {}).get("kp")
                    }
    except Exception as e:
        print(f"Ошибка КП для '{title}': {e}")
    return None

def process_movies(results):
    movies = []
    for m in results:
        if not m.get("poster_path"):
            continue
            
        title = m["title"]
        year = (m.get("release_date") or "")[:4]
        
        movie_data = {
            "id": m["id"],
            "title": title,
            "rating": m.get("vote_average", 0),
            "year": year,
            # Запасной постер с TMDB (через зеркало)
            "poster": IMG_MIRROR + m["poster_path"],
            "description": m.get("overview", ""),
            "actors": ""
        }
        
        print(f"Ищем: {title} ({year})")
        kp_info = get_kp_data(title, year)
        
        # Если Кинопоиск нашёл фильм и дал данные — обогащаем
        if kp_info:
            # Перезаписываем постер на прямой с Кинопоиска (самый надёжный вариант)
            if kp_info.get("poster"): 
                movie_data["poster"] = kp_info["poster"]
            if kp_info.get("description"): 
                movie_data["description"] = kp_info["description"]
            if kp_info.get("actors"): 
                movie_data["actors"] = kp_info["actors"]
            if kp_info.get("kp_rating"): 
                movie_data["rating"] = kp_info["kp_rating"]
                
        movies.append(movie_data)
    return movies

# ... (остальной код функции save и сбора popular/top_rated остаётся без изменений) ...

def save(name, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{name}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

print("=== СБОР ПОПУЛЯРНОГО ===")
popular = []
for page in range(1, 4): # 3 страницы (60 фильмов)
    popular += process_movies(fetch_tmdb("/movie/popular", {"page": page})["results"])
save("popular", popular)

print("=== СБОР ТОПА ===")
top = []
for page in range(1, 4):
    top += process_movies(fetch_tmdb("/movie/top_rated", {"page": page})["results"])
save("top_rated", top)

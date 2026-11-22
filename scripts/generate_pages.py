"""Статические страницы фильмов и sitemap.xml.

Нужны поисковикам: hash-маршрут #movie/123 не индексируется как отдельная
страница. Для каждого фильма создаётся film/<id>/index.html с title,
description, canonical, OG и JSON-LD, а также ссылка в SPA.

Запуск из корня репозитория: python scripts/generate_pages.py
"""

import html
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FILM_DIR = os.path.join(ROOT, "film")
BASE = "https://fvkhweb.github.io/movie-site"

STYLE = """
    :root{color-scheme:dark}
    *{box-sizing:border-box}
    body{margin:0;background:#090b0f;color:#dce2eb;font-family:Manrope,Arial,sans-serif;line-height:1.6}
    main{max-width:980px;margin:0 auto;padding:34px 20px 70px}
    .back{color:#8a8f9a;text-decoration:none;font-size:13px;font-weight:700}
    .back:hover{color:#7fa0ff}
    article{display:grid;grid-template-columns:220px 1fr;gap:28px;margin-top:26px}
    img{width:100%;aspect-ratio:2/3;object-fit:cover;border-radius:12px;border:1px solid #ffffff14;background:#17181c}
    h1{font-size:clamp(24px,4vw,38px);line-height:1.15;margin:0 0 6px}
    .year{color:#8a8f9a;font-weight:400}
    .meta{color:#9aa3b1;margin:0 0 12px}
    .ratings{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;font-size:13px;color:#cdd5e0}
    .ratings span{border:1px solid #384252;border-radius:6px;padding:5px 9px}
    .desc{color:#a2adbb;font-size:14px}
    .cta{display:inline-block;margin-top:22px;padding:12px 18px;border-radius:8px;background:#2f6bff;color:#fff;text-decoration:none;font-weight:800}
    .note{margin-top:26px;color:#6f7783;font-size:11px}
    @media(max-width:640px){article{grid-template-columns:120px 1fr;gap:16px}main{padding-top:20px}}
"""


def text(value):
    return html.escape(str(value or ""), quote=True)


def short(text_value, limit=160):
    value = re.sub(r"\s+", " ", str(text_value or "")).strip()
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0].rstrip(",.;:")
    return cut + "…"


def poster_url(movie):
    poster = movie.get("poster") or ""
    if poster.startswith(("http://", "https://")):
        return poster
    return f"{BASE}/{poster.lstrip('/')}"


def render(movie, genre_names):
    mid = movie["id"]
    title = movie.get("title") or "Без названия"
    year = movie.get("year") or ""
    original = movie.get("original_title") or ""
    description = movie.get("description") or movie.get("description_en") or ""
    url = f"{BASE}/film/{mid}/"
    image = poster_url(movie)
    poster = movie.get("poster") or ""
    img_src = poster if poster.startswith(("http://", "https://")) else f"../../{poster.lstrip('/')}"

    genre_list = [genre_names.get(g, "") for g in movie.get("genres") or []]
    genre_list = [g for g in genre_list if g]
    director = movie.get("director") or ""

    ratings = []
    if movie.get("rating"):
        ratings.append(f"TMDB ★ {float(movie['rating']):.1f}")
    if movie.get("kp_rating"):
        ratings.append(f"Кинопоиск ★ {float(movie['kp_rating']):.1f}")
    if movie.get("runtime"):
        ratings.append(f"{int(movie['runtime'])} мин")

    meta_parts = [original, director, ", ".join(genre_list)]
    meta_line = " · ".join(part for part in meta_parts if part)

    schema = {
        "@context": "https://schema.org",
        "@type": "Movie",
        "name": title,
        "url": url,
        "image": image,
        "description": description,
    }
    if original:
        schema["alternateName"] = original
    if year:
        schema["datePublished"] = movie.get("release_date") or year
    if genre_list:
        schema["genre"] = genre_list
    if director:
        schema["director"] = {"@type": "Person", "name": director}
    if movie.get("rating"):
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": movie["rating"],
            "bestRating": 10,
            "worstRating": 0,
        }
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")

    title_year = f"{title} ({year})" if year else title
    year_span = f' <span class="year">{text(year)}</span>' if year else ""
    meta_description = short(description) or f"Описание фильма {title}."
    ratings_html = "".join(f"<span>{text(r)}</span>" for r in ratings)
    ratings_block = f'<div class="ratings">{ratings_html}</div>' if ratings else ""
    meta_block = f'<p class="meta">{text(meta_line)}</p>' if meta_line else ""

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' https: data:; style-src 'unsafe-inline'; base-uri 'self'">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <title>{text(title_year)} — Что посмотреть?</title>
  <meta name="description" content="{text(meta_description)}">
  <link rel="canonical" href="{text(url)}">
  <meta property="og:type" content="video.movie">
  <meta property="og:title" content="{text(title_year)}">
  <meta property="og:description" content="{text(short(description))}">
  <meta property="og:image" content="{text(image)}">
  <meta property="og:url" content="{text(url)}">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{schema_json}</script>
  <style>{STYLE}</style>
</head>
<body>
  <main>
    <a class="back" href="../../">← Что посмотреть?</a>
    <article>
      <img src="{text(img_src)}" alt="{text(title)}" loading="eager">
      <div>
        <h1>{text(title)}{year_span}</h1>
        {meta_block}
        {ratings_block}
        <p class="desc">{text(description) or "Описание отсутствует."}</p>
        <a class="cta" href="../../#movie/{mid}">Открыть в каталоге</a>
        <p class="note">Данные и постеры принадлежат их правообладателям. Этот продукт использует TMDB API, но не одобрен и не сертифицирован TMDB.</p>
      </div>
    </article>
  </main>
</body>
</html>
"""


def write_atomic(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)


def main():
    with open(os.path.join(DATA, "movies.json"), encoding="utf-8") as f:
        movies = json.load(f)
    with open(os.path.join(DATA, "genres.json"), encoding="utf-8") as f:
        genres = json.load(f)
    genre_names = {g["id"]: g["name"] for g in genres if isinstance(g, dict)}

    os.makedirs(FILM_DIR, exist_ok=True)
    ids = set()
    for movie in movies:
        mid = movie.get("id")
        if not isinstance(mid, int):
            continue
        ids.add(mid)
        write_atomic(os.path.join(FILM_DIR, str(mid), "index.html"), render(movie, genre_names))

    removed = 0
    for name in os.listdir(FILM_DIR):
        path = os.path.join(FILM_DIR, name)
        if os.path.isdir(path) and name.isdigit() and int(name) not in ids:
            shutil.rmtree(path)
            removed += 1

    urls = [f"{BASE}/", f"{BASE}/privacy.html"] + [f"{BASE}/film/{mid}/" for mid in sorted(ids)]
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{url}</loc></url>\n" for url in urls)
        + "</urlset>\n"
    )
    write_atomic(os.path.join(ROOT, "sitemap.xml"), sitemap)

    print(f"страниц: {len(ids)}, удалено устаревших: {removed}, url в sitemap: {len(urls)}")


if __name__ == "__main__":
    main()

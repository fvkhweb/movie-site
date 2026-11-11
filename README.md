# 🎬 Что посмотреть?

Каталог фильмов на GitHub Pages. Работает из РФ **без VPN**: постеры хранятся
прямо в репозитории, данные собраны заранее, бэкенда нет.

**Сайт:** https://fvkhweb.github.io/movie-site/

## Возможности

- Табы: популярное, топ по рейтингу, весь каталог, избранное (в localStorage).
- Фильтры: жанр, диапазон лет, минимальный рейтинг, поиск по названию и актёрам.
- Сортировки: популярность, рейтинг TMDB/Кинопоиска, год, название, длительность.
- Карточка фильма: описание, длительность, страны, жанры, оба рейтинга,
  актёры с фото (клик по актёру — все его фильмы в каталоге).
- «Случайный фильм» из текущей подборки, бесконечная прокрутка, скелетоны загрузки.

## Как это работает

```
scripts/fetch_movies.py   # сбор данных + скачивание постеров (запускается Actions)
data/                     # movies.json, cast.json, people.json, genres.json, lists.json
posters/                  # локальные постеры — отдаются с домена сайта
app.js, index.html, style.css
```

GitHub Action [update-movies.yml](.github/workflows/update-movies.yml) каждый день
(и по кнопке) собирает свежие данные из TMDB, дополняет Кинопоиском и коммитит их.
Секреты: `TMDB_API_KEY`, `POISKKINO_API_KEY`.

## Локальный запуск

```bash
python -m http.server 8000
# http://localhost:8000
```

Для отладки скрипта сбора данных (если TMDB API недоступен из вашей сети):

```bash
pip install requests
export TMDB_API_KEY=... POISKKINO_API_KEY=...
export TMDB_PROXY_TEMPLATE="https://api.allorigins.win/raw?url={url}"  # опционально
export POPULAR_PAGES=1 TOP_PAGES=1 GENRE_PAGES=0 KP_MAX_MOVIES=5      # маленький тест
python scripts/fetch_movies.py
```

## Ограничения

- Кинопоиск API (бесплатный тариф ~200 запросов/сутки) обогащает ограниченное
  число фильмов за прогон — `KP_MAX_MOVIES`.
- Репозиторий растёт примерно на 30 КБ за постер; см. [PLAN.md](PLAN.md).

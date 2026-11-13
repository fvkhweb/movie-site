/* «Что посмотреть?» v2 — каталог с фильтрами, актёрами и избранным.
   Все данные статичные, постеры локальные (работает без VPN). */

const PAGE_SIZE = 60;
const PROXY_IMG = "https://wsrv.nl/?url=";
const PROXY_IMG_2 = "https://images.weserv.nl/?url=";
const DATA_VERSION = "8"; // bump при изменении формата данных — сбрасывает кэш файлов data/*
const PIXEL =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

const state = {
  movies: [],
  genres: [],
  lists: { popular: [], top_rated: [], now_playing: [], upcoming: [] },
  cast: null,   // { movieId: [{id, name, character, photo}] }
  people: null, // [{ id, name, photo, movies: [] }]
  collections: [], // пользовательские подборки (data/collections.json)
  genre: "",    // активный жанр (чипсы)
  favorites: JSON.parse(localStorage.getItem("favorites") || "[]"),
  limit: PAGE_SIZE,
  actor: "",    // фильтр «фильмы актёра»
  currentModal: null, // какой фильм открыт в модалке
  homeScroll: 0, // позиция прокрутки до перехода на страницу фильма
};

const el = (id) => document.getElementById(id);

/* ── Утилиты ───────────────────────────────────────── */

function escapeHtml(v) {
  return String(v ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function escapeAttr(v) {
  return escapeHtml(v);
}

function personPhotoSources(path, width) {
  // Цепочка: wsrv → images.weserv.nl → прямой TMDB. Хотя бы одно сработает.
  if (!path) return null;
  const p = `image.tmdb.org/t/p/w${width || 185}${path}`;
  return {
    src: `${PROXY_IMG}${p}`,
    fallback: `${PROXY_IMG_2}${p}|https://${p}`,
  };
}

function ratingClass(value) {
  if (value >= 7.5) return "good";
  if (value >= 6) return "mid";
  return "bad";
}

function posterSources(movie) {
  // Локальный файл всегда первый, резерв — Кинопоиск (Яндекс.CDN) или wsrv-прокси
  const local = movie.poster || `posters/${movie.id}.jpg`;
  const fallback = movie.poster_fallback || "";
  return { local, fallback };
}

function runtimeLabel(min) {
  if (!min) return "";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} ч ${m ? m + " мин" : ""}`.trim() : `${m} мин`;
}

function movieById(id) {
  return state.movies.find((m) => m.id === id);
}

/* ── Загрузка данных ───────────────────────────────── */

async function loadData() {
  const v = `?v=${DATA_VERSION}`;
  const [moviesRes, genresRes, listsRes] = await Promise.allSettled([
    fetch(`data/movies.json${v}`).then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
    fetch(`data/genres.json${v}`).then((r) => (r.ok ? r.json() : [])),
    fetch(`data/lists.json${v}`).then((r) => (r.ok ? r.json() : null)),
  ]);

  if (moviesRes.status !== "fulfilled" || !Array.isArray(moviesRes.value) || !moviesRes.value.length) {
    el("grid").innerHTML =
      "<p style='color:#aaa; grid-column: 1/-1;'>Данные ещё не загружены. " +
      "Запустите GitHub Action «Update movies» или проверьте, что data/movies.json существует.</p>";
    return;
  }

  state.movies = moviesRes.value;
  state.genres = Array.isArray(genresRes.value) ? genresRes.value : [];
  if (listsRes.value) state.lists = { ...state.lists, ...listsRes.value };

  fillControls();
  buildChips();
  render();
  renderFeature();
  renderGenres();
  renderRails();
  // Прямая ссылка на фильм: страницу можно отрисовать только после загрузки базы
  if (currentMovieId() !== null) renderMoviePage(currentMovieId());

  // Актёры и подборки грузим в фоне — не блокируют первую отрисовку
  Promise.allSettled([
    fetch(`data/cast.json${v}`).then((r) => (r.ok ? r.json() : null)),
    fetch(`data/people.json${v}`).then((r) => (r.ok ? r.json() : null)),
    fetch(`data/collections.json${v}`).then((r) => (r.ok ? r.json() : null)),
  ]).then(([cast, people, collections]) => {
    state.cast = cast.status === "fulfilled" ? cast.value : null;
    state.people = people.status === "fulfilled" ? people.value : null;
    if (collections.status === "fulfilled" && collections.value?.collections) {
      state.collections = collections.value.collections;
      renderCollections();
    }
    // Если пользователь уже что-то ищет — пересчитаем с учётом актёров,
    // а открытую модалку перерисуем с актёрами
    if (el("search").value.trim() || state.actor) render();
    if (!el("movieModal").hidden && state.currentModal) openModal(state.currentModal);
    if (document.body.dataset.view === "movie") renderMoviePage(currentMovieId());
  });
}

function fillControls() {
  const years = state.movies
    .map((m) => parseInt(m.year, 10))
    .filter((y) => y > 1900);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);

  state.genres.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g.id;
    opt.textContent = "не: " + g.name;
    el("genreExclude").appendChild(opt);
  });

  for (const sel of [el("yearFrom"), el("yearTo")]) {
    for (let y = maxYear; y >= minYear; y--) {
      const opt = document.createElement("option");
      opt.value = y;
      opt.textContent = y;
      sel.appendChild(opt);
    }
  }
}

/* ── Чипсы жанров (как в макете) ───────────────────── */

function buildChips() {
  const chips = el("chips");
  chips.innerHTML = "";
  const all = document.createElement("button");
  all.className = "chip active";
  all.dataset.genre = "";
  all.textContent = "Все фильмы";
  chips.appendChild(all);
  state.genres.forEach((g) => {
    const b = document.createElement("button");
    b.className = "chip";
    b.dataset.genre = g.id;
    b.textContent = g.name.charAt(0).toUpperCase() + g.name.slice(1);
    chips.appendChild(b);
  });
  chips.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    setGenre(chip.dataset.genre);
  });
}

function setGenre(genreId) {
  state.genre = genreId;
  document.querySelectorAll("#chips .chip").forEach((c) =>
    c.classList.toggle("active", c.dataset.genre === genreId)
  );
  // жанр живёт внутри панели «Фильтры» — подсвечиваем кнопку
  el("filterToggle").classList.toggle("has-genre", !!genreId);
  render();
}

/* ── Фильтрация ────────────────────────────────────── */

function currentList() {
  return state.movies;
}

function actorMatches(query) {
  if (!state.people) return null;
  const q = query.toLowerCase();
  const set = new Set();
  state.people.forEach((p) => {
    if (p.name && p.name.toLowerCase().includes(q)) {
      p.movies.forEach((id) => set.add(id));
    }
  });
  return set;
}

function filteredList() {
  let list = currentList();

  const q = el("search").value.trim().toLowerCase();
  const genre = state.genre;
  const genreExclude = el("genreExclude").value;
  const yFrom = el("yearFrom").value;
  const yTo = el("yearTo").value;
  const ratingMin = el("ratingMin").value;
  const sortType = el("sortSelect").value;

  let actorIds = null;
  if (state.actor) {
    actorIds = new Set(
      (state.people || []).find((p) => p.name === state.actor)?.movies || []
    );
    list = list.filter((m) => actorIds.has(m.id));
  } else if (q && state.people) {
    actorIds = actorMatches(q);
  }

  list = list.filter((m) => {
    if (state.actor) return actorIds.has(m.id);
    if (genreExclude && (m.genres || []).includes(Number(genreExclude))) return false;
    if (genre && !(m.genres || []).includes(Number(genre))) return false;
    if (yFrom && parseInt(m.year, 10) < Number(yFrom)) return false;
    if (yTo && parseInt(m.year, 10) > Number(yTo)) return false;
    if (ratingMin && (m.rating || 0) < Number(ratingMin)) return false;
    if (q) {
      const inTitle = m.title && m.title.toLowerCase().includes(q);
      const inActor = actorIds ? actorIds.has(m.id) : false;
      if (!inTitle && !inActor) return false;
    }
    return true;
  });

  const byId = (a, b, dir) => dir * String(a ?? "").localeCompare(String(b ?? ""), "ru");
  const num = (v) => Number(v) || 0;
  // Сортировка по новизне учитывает не только год, но и месяц и день выхода
  // (release_date вида "2026-03-14"). Если точной даты нет, берём год как "1 января".
  const releaseTS = (m) => {
    const d = m.release_date || (m.year ? `${m.year}-01-01` : "");
    const t = Date.parse(d);
    return isNaN(t) ? 0 : t;
  };
  if (sortType === "rating_desc") list.sort((a, b) => num(b.rating) - num(a.rating));
  else if (sortType === "kp_rating_desc") list.sort((a, b) => num(b.kp_rating) - num(a.kp_rating));
  else if (sortType === "year_desc") list.sort((a, b) => releaseTS(b) - releaseTS(a) || num(b.year) - num(a.year));
  else if (sortType === "year_asc") list.sort((a, b) => releaseTS(a) - releaseTS(b) || num(a.year) - num(b.year));
  else if (sortType === "title_asc") list.sort((a, b) => byId(a.title, b.title, 1));
  else if (sortType === "runtime_desc") list.sort((a, b) => num(b.runtime) - num(a.runtime));
  else list.sort((a, b) => num(b.popularity) - num(a.popularity));

  return list;
}

/* ── Отрисовка ─────────────────────────────────────── */

const GENRE_EN = {
  28: "ACTION", 12: "ADVENTURE", 16: "ANIMATION", 35: "COMEDY", 80: "CRIME",
  99: "DOCUMENTARY", 18: "DRAMA", 10751: "FAMILY", 14: "FANTASY", 36: "HISTORY",
  27: "HORROR", 10402: "MUSIC", 9648: "MYSTERY", 10749: "ROMANCE", 878: "SCI-FI",
  10770: "TV MOVIE", 53: "THRILLER", 10752: "WAR", 37: "WESTERN",
};

function filmsWord(n) {
  const d = n % 10, h = n % 100;
  if (d === 1 && h !== 11) return "ФИЛЬМ";
  if (d >= 2 && d <= 4 && (h < 12 || h > 14)) return "ФИЛЬМА";
  return "ФИЛЬМОВ";
}

function cardHtml(m) {
  const { local, fallback } = posterSources(m);
  const isFav = state.favorites.includes(m.id);
  const rating = m.rating ? Number(m.rating).toFixed(1) : "";
  const genreName = (state.genres.find((g) => g.id === (m.genres || [])[0]) || {}).name || "";

  return `
  <article class="movie" data-id="${m.id}">
    <div class="poster">
      <img alt="${escapeAttr(m.title || "")}" loading="lazy"
           src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>
      ${rating ? `<span class="poster-rating">★ ${rating}</span>` : ""}
      <button class="heart ${isFav ? "saved" : ""}" data-id="${m.id}" aria-label="В избранное">${isFav ? "♥" : "♡"}</button>
    </div>
    <div class="movie-title">${escapeHtml(m.title || "Без названия")}</div>
    <div class="movie-sub">${escapeHtml(m.year || "")}${genreName ? " &nbsp;·&nbsp; " + escapeHtml(genreName.toUpperCase()) : ""}</div>
  </article>`;
}

function render() {
  const grid = el("grid");
  if (!grid) return;

  state.limit = PAGE_SIZE;
  const list = filteredList();

  el("emptyState").hidden = list.length > 0;
  updateResultsCount(list.length);
  updateCatalogTitle();
  grid.innerHTML = list.slice(0, state.limit).map(cardHtml).join("");
  el("sentinel").hidden = list.length <= state.limit;

  renderSaved();
  renderFeature();
  updateFavBadge();
}

/* ── Прыжок к секции ─────────────────────────────────
   Мгновенный скролл с коррекцией по кадрам: длинная страница,
   лента догружает карточки и высота блоков меняется — smooth
   scroll обрывается на полпути. Мгновенный прыжок надёжнее. */
function jumpTo(target) {
  if (!target) return;
  const headerH = document.querySelector("header")?.offsetHeight || 64;
  // Секциям у низа страницы не хватает «страницы под ними», чтобы встать
  // к шапке — временно наращиваем высоту, пока пользователь не уйдёт выше
  const want = target.getBoundingClientRect().top + window.scrollY - headerH - 8;
  const max = document.documentElement.scrollHeight - window.innerHeight;
  if (want > max) {
    const spacer = document.createElement("div");
    spacer.style.height = `${want - max}px`;
    document.body.appendChild(spacer);
    const release = () => {
      if (window.scrollY < want - 200) {
        spacer.remove();
        window.removeEventListener("scroll", release);
      }
    };
    window.addEventListener("scroll", release, { passive: true });
  }
  const align = () => {
    const y = target.getBoundingClientRect().top + window.scrollY - headerH - 8;
    window.scrollTo({ top: Math.max(0, y), behavior: "instant" });
  };
  align();
  // Картинки и лента меняют высоту страницы ещё секунду-другую после
  // прыжка — корректируем позицию, пока она не стабилизируется
  let stable = 0;
  let frames = 0;
  const tick = () => {
    const delta = target.getBoundingClientRect().top - headerH - 8;
    if (Math.abs(delta) <= 2) {
      stable++;
    } else {
      stable = 0;
      align();
    }
    if (stable < 10 && frames++ < 180) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* ── Фич-блок «Выбор редакции» ─────────────────────── */

function renderFeature() {
  const feature = el("feature");
  if (!feature || !state.movies.length) return;
  // Если у популярных фильмов есть кадры с Кинопоиска (Яндекс.CDN) —
  // показываем фильм с кадром: он ландшафтный и красиво заполняет блок
  const withFrame = state.movies.filter((m) => m.frame && m.description && m.rating);
  const pool = withFrame.length
    ? withFrame
    : state.movies.filter((m) => m.description && m.rating);
  if (!pool.length) return;
  const m = pool.sort((a, b) => (b.popularity || 0) - (a.popularity || 0))[0];

  const { local, fallback } = posterSources(m);
  const artSrc = m.frame || local;
  const artFallback = m.frame ? local : fallback;
  const isFav = state.favorites.includes(m.id);
  const genreName = (state.genres.find((g) => g.id === (m.genres || [])[0]) || {}).name || "";
  const tag = [genreName.toUpperCase(), (m.countries || [])[0]?.toUpperCase()].filter(Boolean).join(" / ");

  feature.innerHTML = `
    <div class="feature-art">
      <img alt="${escapeAttr(m.title || "")}" src="${escapeAttr(artSrc)}" ${artFallback ? `data-fallback="${escapeAttr(artFallback)}"` : ""}>
      <div class="feature-index">FEATURED FILM — 001</div>
    </div>
    <div class="feature-copy">
      <div class="tag">${escapeHtml(tag || "ВЫБОР РЕДАКЦИИ")}</div>
      <h2>${escapeHtml(m.title || "")}</h2>
      <div class="meta">
        ${m.year ? `<span>${escapeHtml(m.year)}</span>` : ""}
        ${m.runtime ? `<span>${runtimeLabel(m.runtime).toUpperCase()}</span>` : ""}
        <span class="rating">★ ${Number(m.rating).toFixed(1)}</span>
      </div>
      <p>${escapeHtml(m.description)}</p>
      <div class="feature-actions">
        <button class="primary" data-open="${m.id}">О фильме <span>↗</span></button>
        <button class="secondary" data-heart="${m.id}">${isFav ? "♥ В избранном" : "＋ В избранное"}</button>
      </div>
    </div>`;
  feature.hidden = false;
}

/* ── Карточки жанров ───────────────────────────────── */

function renderGenres() {
  const strip = el("genreStrip");
  if (!strip || !state.movies.length) return;
  const counts = {};
  state.movies.forEach((m) => (m.genres || []).forEach((g) => { counts[g] = (counts[g] || 0) + 1; }));
  const top = state.genres
    .map((g) => ({ ...g, count: counts[g.id] || 0 }))
    .filter((g) => g.count > 4)
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  strip.innerHTML = top
    .map(
      (g) => `
    <div class="genre-card" data-genre="${g.id}">
      <b>${escapeHtml(g.name.charAt(0).toUpperCase() + g.name.slice(1))}</b>
      <span>${GENRE_EN[g.id] || "GENRE"} / ${g.count} ${filmsWord(g.count)} ↗</span>
    </div>`
    )
    .join("");

  strip.addEventListener("click", (e) => {
    const card = e.target.closest(".genre-card");
    if (!card) return;
    setGenre(card.dataset.genre);
    jumpTo(el("catalog"));
  });
}

/* ── Подборки (data/collections.json) ──────────────── */

// Какие подборки раскрыты полностью (по id) — по умолчанию показываем
// первые COLL_PREVIEW карточек, остальное по кнопке «Показать все»
const COLL_PREVIEW = 10;
const collOpen = new Set();

function renderCollections() {
  const wrap = el("collectionsList");
  const section = el("collections");
  if (!wrap || !state.collections.length) return;

  wrap.innerHTML = state.collections
    .map((c) => {
      const list = c.items.map(movieById).filter(Boolean);
      if (!list.length) return "";
      const open = collOpen.has(c.id);
      const shown = open ? list : list.slice(0, COLL_PREVIEW);
      const cards = shown
        .map(
          (m, i) => `
      <div class="coll-card" data-id="${m.id}" title="${escapeAttr(m.title || "")}">
        <span class="coll-rank">${String(i + 1).padStart(3, "0")}</span>
        <img alt="${escapeAttr(m.title || "")}" loading="lazy" src="${escapeAttr(m.poster || `posters/${m.id}.jpg`)}">
      </div>`
        )
        .join("");
      const hidden = list.length - shown.length;
      const toggle = list.length > COLL_PREVIEW
        ? `<button class="coll-all" data-collall="${escapeAttr(c.id)}">${
            open ? "Свернуть" : `Показать все · ${list.length}`
          } <span>${open ? "↖" : "↘"}</span></button>`
        : "";
      const meta = `${c.total} ${filmsWord(c.total)} · В КАТАЛОГЕ ${list.length}/${c.total}`;
      return `
    <div class="collection">
      <div class="section-head"><div class="section-title">${escapeHtml((c.title || "").toUpperCase())}</div><div class="section-meta">${escapeHtml(meta)}</div></div>
      <div class="coll-row">${cards}</div>
      ${toggle}
    </div>`;
    })
    .join("");

  if (wrap.innerHTML) section.hidden = false;
  bindImageFallbacks(wrap);
}

/* ── Ленты «На слуху сейчас» и «Скоро в кино» ──────── */

function fmtDateRu(iso) {
  const t = Date.parse(iso || "");
  if (isNaN(t)) return "";
  return new Date(t).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

function railCardHtml(m, opts = {}) {
  const sub = opts.date && m.release_date
    ? `В КИНО ${fmtDateRu(m.release_date).toUpperCase()}`
    : m.rating
      ? `★ ${Number(m.rating).toFixed(1)}`
      : escapeHtml(m.year || "");
  return `
  <div class="rail-card" data-id="${m.id}" title="${escapeAttr(m.title || "")}">
    <div class="poster">
      <img alt="${escapeAttr(m.title || "")}" loading="lazy"
           src="${escapeAttr(m.poster || `posters/${m.id}.jpg`)}" ${m.poster_fallback ? `data-fallback="${escapeAttr(m.poster_fallback)}"` : ""}>
    </div>
    <div class="movie-title">${escapeHtml(m.title || "Без названия")}</div>
    <div class="movie-sub">${sub}</div>
  </div>`;
}

function renderRails() {
  const now = (state.lists.now_playing || []).map(movieById).filter(Boolean);
  const up = (state.lists.upcoming || []).map(movieById).filter(Boolean);

  const nowRow = el("nowRow");
  if (nowRow) {
    nowRow.innerHTML = now.map((m) => railCardHtml(m)).join("");
    el("nowPlaying").hidden = !now.length;
    el("nowEmpty").hidden = !!now.length;
  }
  const upRow = el("upRow");
  if (upRow) {
    upRow.innerHTML = up.map((m) => railCardHtml(m, { date: true })).join("");
    el("upcoming").hidden = !up.length;
    el("upEmpty").hidden = !!up.length;
  }
}

/* ── «Твой список» ─────────────────────────────────── */

function renderSaved() {
  const grid = el("savedGrid");
  if (!grid) return;
  const list = state.favorites.map(movieById).filter(Boolean);
  grid.innerHTML = list.map(cardHtml).join("");
  el("savedEmpty").hidden = list.length > 0;
}

function renderMore() {
  const list = filteredList();
  if (state.limit >= list.length) {
    el("sentinel").hidden = true;
    return;
  }
  const grid = el("grid");
  const prev = state.limit;
  state.limit += PAGE_SIZE;
  // Добавляем только новые карточки — полная перерисовка прерывала бы
  // плавный скролл по якорям и сбрасывала бы загрузку картинок
  const frag = document.createElement("div");
  frag.innerHTML = list.slice(prev, state.limit).map(cardHtml).join("");
  while (frag.firstChild) grid.appendChild(frag.firstChild);
  el("sentinel").hidden = list.length <= state.limit;
}

function updateResultsCount(count) {
  let text = `${count} ${filmsWord(count)}`;
  if (state.actor) text += ` · АКТЁР: «${escapeHtml(state.actor)}» <button class="iconbtn small" id="clearActor" title="Убрать фильтр">✕</button>`;
  el("resultCount").innerHTML = text;
  const clearActor = el("clearActor");
  if (clearActor) clearActor.onclick = () => { state.actor = ""; render(); };
}

function updateCatalogTitle() {
  const q = el("search").value.trim();
  const title = q || state.actor
    ? "РЕЗУЛЬТАТЫ ПОИСКА"
    : state.genre
      ? (state.genres.find((g) => String(g.id) === state.genre) || {}).name?.toUpperCase() || "КАТАЛОГ"
      : "ПОПУЛЯРНОЕ СЕЙЧАС";
  el("catalogTitle").textContent = title;
}

function updateFavBadge() {
  const badge = el("favCount");
  if (!badge) return;
  badge.textContent = `${state.favorites.length} В ИЗБРАННОМ`;
}

/* ── Избранное ─────────────────────────────────────── */

function toggleFavorite(id) {
  const i = state.favorites.indexOf(id);
  if (i === -1) state.favorites.push(id);
  else state.favorites.splice(i, 1);
  localStorage.setItem("favorites", JSON.stringify(state.favorites));
  updateFavBadge();
  // Обновим сердечки везде
  document.querySelectorAll(`.heart[data-id="${id}"]`).forEach((b) => {
    const active = state.favorites.includes(id);
    b.classList.toggle("saved", active);
    b.textContent = active ? "♥" : "♡";
  });
  document.querySelectorAll(`.fav-btn[data-id="${id}"]`).forEach((b) => {
    const active = state.favorites.includes(id);
    b.classList.toggle("active", active);
    b.textContent = active ? "♥ В избранном" : "＋ В избранное";
  });
  document.querySelectorAll(`#feature [data-heart]`).forEach((b) => {
    b.textContent = state.favorites.includes(id) ? "♥ В избранном" : "＋ В избранное";
  });
  renderSaved();
  renderFeature();
}

/* ── Модалка ───────────────────────────────────────── */

function openModal(id) {
  const m = movieById(id);
  if (!m) return;
  state.currentModal = id;

  const { local, fallback } = posterSources(m);
  const isFav = state.favorites.includes(m.id);
  const genreChips = (m.genres || [])
    .map((gid) => (state.genres.find((g) => g.id === gid) || {}).name)
    .filter(Boolean)
    .map((name) => `<span class="chip">${escapeHtml(name)}</span>`)
    .join("");

  const ratings = [
    m.rating ? `<span class="rating-pill"><span class="label">TMDB</span>⭐ ${Number(m.rating).toFixed(1)}</span>` : "",
    m.kp_rating ? `<span class="rating-pill"><span class="label">Кинопоиск</span>⭐ ${Number(m.kp_rating).toFixed(1)}</span>` : "",
    m.runtime ? `<span class="rating-pill"><span class="label">Время</span>${runtimeLabel(m.runtime)}</span>` : "",
  ].filter(Boolean).join("");

  const cast = (state.cast && state.cast[String(m.id)]) || [];
  const castHtml = cast.length
    ? `<div class="cast-section"><h3>В главных ролях</h3><div class="cast-row">${cast
        .map(
          (c) => `
      <div class="cast-card" data-actor="${escapeAttr(c.name)}" title="Фильмы актёра">
        ${
          c.photo
            ? (() => {
                const ps = personPhotoSources(c.photo);
                return `<img alt="${escapeAttr(c.name)}" loading="lazy" src="${escapeAttr(ps.src)}" data-fallback="${escapeAttr(ps.fallback)}">`;
              })()
            : `<div class="cast-photo-empty">🎭</div>`
        }
        <div class="cast-name">${escapeHtml(c.name)}</div>
        ${c.character ? `<div class="cast-role">${escapeHtml(c.character)}</div>` : ""}
      </div>`
        )
        .join("")}</div></div>`
    : "";

  const facts = (m.facts || []).slice(0, 3);
  const factsHtml = facts.length
    ? `<div class="facts-section"><h3>💡 Интересные факты</h3><ul>${facts
        .map((f) => `<li>${escapeHtml(f)}</li>`)
        .join("")}</ul></div>`
    : "";

  const similar = (m.similar || []).map(movieById).filter(Boolean).slice(0, 6);
  const similarHtml = similar.length
    ? `<div class="similar-section"><h3>🎯 Похожее</h3><div class="similar-row">${similar
        .map(
          (s) => `
      <div class="similar-card" data-id="${s.id}">
        <img alt="${escapeAttr(s.title || "")}" loading="lazy" src="${escapeAttr(s.poster || `posters/${s.id}.jpg`)}">
        <span>${escapeHtml(s.title || "")}</span>
      </div>`
        )
        .join("")}</div></div>`
    : "";

  el("modalBody").innerHTML = `
    <div class="modal-banner no-image">
      ${
        local || fallback
          ? `<img class="hero-poster" alt="${escapeAttr(m.title || "")}" src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>`
          : `<div class="poster-empty" style="width:200px;">Нет постера</div>`
      }
      <div class="movie-info">
        <h2>${escapeHtml(m.title || "Без названия")}${m.year ? ` (${escapeHtml(m.year)})` : ""}</h2>
        <p class="movie-sub">${escapeHtml([m.original_title, (m.countries || []).join(", ")].filter(Boolean).join(" • "))}</p>
        <div class="ratings">${ratings}</div>
        <div class="chips">${genreChips}</div>
        <div class="movie-actions">
          <button class="fav-btn ${isFav ? "active" : ""}" data-id="${m.id}" title="В избранное">${isFav ? "♥ В избранном" : "＋ В избранное"}</button>
          ${m.trailer ? `<button class="primary trailer-btn" data-trailer="${escapeAttr(m.trailer)}">▶ Трейлер</button>` : ""}
        </div>
      </div>
    </div>
    <div class="movie-body">
      <p class="overview">${escapeHtml(m.description || "Описание отсутствует.")}</p>
    </div>
    ${factsHtml}
    ${castHtml}
    ${similarHtml}`;

  // Кадр на фоне баннера: сначала кадр Кинопоиска (Яндекс.CDN — работает
  // из РФ без VPN), затем TMDB-кадр через прокси. Если всё мимо — градиент.
  const banner = el("modalBody").querySelector(".modal-banner");
  const apply = (url) => {
    if (banner && banner.isConnected) {
      banner.style.backgroundImage = `url('${url}')`;
      banner.classList.remove("no-image");
    }
  };
  const probe = (url, onFail) => {
    const im = new Image();
    im.onload = () => apply(url);
    im.onerror = () => onFail && onFail();
    im.src = url;
  };
  const tryTmdbBackdrop = () => {
    if (!m.backdrop) return;
    const path = `image.tmdb.org/t/p/w780${m.backdrop}`;
    probe(`${PROXY_IMG}${path}`, () => probe(`${PROXY_IMG_2}${path}`, () => probe(`https://${path}`)));
  };
  if (m.frame) {
    probe(m.frame, tryTmdbBackdrop);
  } else {
    tryTmdbBackdrop();
  }

  el("movieModal").hidden = false;
  document.body.style.overflow = "hidden";
}

function closeModal() {
  el("movieModal").hidden = true;
  document.body.style.overflow = "";
}

/* ── Страница фильма (отдельный «экран» по адресу #movie/{id}) ── */

function currentMovieId() {
  const mm = location.hash.match(/^#movie\/(\d+)$/);
  return mm ? Number(mm[1]) : null;
}

function openMovie(id) {
  // Фильм из базы открывается отдельной страницей; адрес меняется,
  // поэтому кнопка «назад» в браузере возвращает к каталогу
  if (movieById(id)) location.hash = `movie/${id}`;
}

function probeImage(url, onOk, onFail) {
  const im = new Image();
  im.onload = () => onOk(url);
  im.onerror = () => onFail && onFail();
  im.src = url;
}

function setMovieHeroBackdrop(m) {
  const art = el("moviePage").querySelector(".hero-art");
  if (!art) return;
  const apply = (url) => {
    if (art.isConnected) {
      art.src = url;
      art.hidden = false;
    }
  };
  const chain = [];
  // Кадр Кинопоиска (Яндекс.CDN — из РФ без VPN), затем TMDB-кадр через прокси
  if (m.frame) chain.push(m.frame);
  if (m.backdrop) {
    const p = `image.tmdb.org/t/p/w1280${m.backdrop}`;
    chain.push(`${PROXY_IMG}${p}`, `${PROXY_IMG_2}${p}`, `https://${p}`);
  }
  const next = () => {
    const url = chain.shift();
    if (url) probeImage(url, apply, next);
  };
  next();
}

function moviePageHtml(m) {
  const { local, fallback } = posterSources(m);
  const isFav = state.favorites.includes(m.id);
  const genreChips = (m.genres || [])
    .map((gid) => (state.genres.find((g) => g.id === gid) || {}).name)
    .filter(Boolean)
    .map((name) => `<span class="chip">${escapeHtml(name)}</span>`)
    .join("");

  const ratings = [
    m.rating ? `<span class="rating-pill"><span class="label">TMDB</span>⭐ ${Number(m.rating).toFixed(1)}</span>` : "",
    m.kp_rating ? `<span class="rating-pill"><span class="label">Кинопоиск</span>⭐ ${Number(m.kp_rating).toFixed(1)}</span>` : "",
    m.runtime ? `<span class="rating-pill"><span class="label">Время</span>${runtimeLabel(m.runtime)}</span>` : "",
  ].filter(Boolean).join("");

  const cast = (state.cast && state.cast[String(m.id)]) || [];
  const castHtml = cast.length
    ? `<div class="cast-section"><h3>В главных ролях</h3><div class="cast-row">${cast
        .map(
          (c) => `
      <div class="cast-card" data-actor="${escapeAttr(c.name)}" title="Фильмы актёра">
        ${
          c.photo
            ? (() => {
                const ps = personPhotoSources(c.photo);
                return `<img alt="${escapeAttr(c.name)}" loading="lazy" src="${escapeAttr(ps.src)}" data-fallback="${escapeAttr(ps.fallback)}">`;
              })()
            : `<div class="cast-photo-empty">🎭</div>`
        }
        <div class="cast-name">${escapeHtml(c.name)}</div>
        ${c.character ? `<div class="cast-role">${escapeHtml(c.character)}</div>` : ""}
      </div>`
        )
        .join("")}</div></div>`
    : "";

  const facts = (m.facts || []).slice(0, 5);
  const factsHtml = facts.length
    ? `<div class="facts-section"><h3>💡 Интересные факты</h3><ul>${facts
        .map((f) => `<li>${escapeHtml(f)}</li>`)
        .join("")}</ul></div>`
    : "";

  const similar = (m.similar || []).map(movieById).filter(Boolean).slice(0, 10);
  const similarHtml = similar.length
    ? `<div class="similar-section"><h3>🎯 Похожее</h3><div class="similar-row">${similar
        .map(
          (s) => `
      <div class="similar-card" data-id="${s.id}">
        <img alt="${escapeAttr(s.title || "")}" loading="lazy" src="${escapeAttr(s.poster || `posters/${s.id}.jpg`)}">
        <span>${escapeHtml(s.title || "")}</span>
      </div>`
        )
        .join("")}</div></div>`
    : "";

  const premiere = m.release_date
    ? `ПРЕМЬЕРА ${escapeHtml(fmtDateRu(m.release_date).toUpperCase())}`
    : m.year
      ? escapeHtml(m.year)
      : "ФИЛЬМ";

  return `
  <div class="movie-hero">
    <img class="hero-art" alt="" hidden>
    <div class="hero-shade"></div>
    <button class="movie-back" id="movieBack" title="Назад">← Каталог</button>
    <div class="wrap hero-inner">
      ${
        local || fallback
          ? `<img class="hero-thumb" alt="${escapeAttr(m.title || "")}" src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>`
          : `<div class="hero-thumb poster-empty">Нет постера</div>`
      }
      <div class="hero-text">
        <div class="tag">${premiere}</div>
        <h1>${escapeHtml(m.title || "Без названия")}</h1>
        <p class="movie-sub">${escapeHtml([m.original_title, (m.countries || []).join(", ")].filter(Boolean).join(" • "))}</p>
        <div class="ratings">${ratings}</div>
        <div class="chips">${genreChips}</div>
        <div class="movie-actions">
          <button class="fav-btn ${isFav ? "active" : ""}" data-id="${m.id}" title="В избранное">${isFav ? "♥ В избранном" : "＋ В избранное"}</button>
          ${m.trailer ? `<button class="primary trailer-btn" data-trailer="${escapeAttr(m.trailer)}">▶ Трейлер</button>` : ""}
        </div>
      </div>
    </div>
  </div>
  <div class="wrap movie-page-body">
    <div class="overview-block"><p class="overview">${escapeHtml(m.description || "Описание отсутствует.")}</p></div>
    ${factsHtml}
    ${castHtml}
    ${similarHtml}
  </div>`;
}

function renderMoviePage(id) {
  const m = movieById(id);
  if (!m) {
    if (state.movies.length) location.hash = ""; // фильма нет в базе
    return; // данные ещё не догрузились — роутер вызовется снова после загрузки
  }
  const page = el("moviePage");
  const same = document.body.dataset.view === "movie" && page.dataset.movieId === String(id);
  document.body.dataset.view = "movie";
  state.currentModal = id;
  page.innerHTML = moviePageHtml(m);
  page.dataset.movieId = String(id);
  page.hidden = false;
  document.querySelector("main").style.display = "none";
  document.title = `${m.title || "Фильм"} — Что посмотреть?`;
  if (!same) {
    setMovieHeroBackdrop(m);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
}

function exitMoviePage() {
  document.body.dataset.view = "";
  el("moviePage").hidden = true;
  el("moviePage").innerHTML = "";
  document.querySelector("main").style.display = "";
  document.title = "Что посмотреть?";
}

function updateNavActive() {
  const h = (location.hash || "#home").replace("#", "");
  const section = h.startsWith("movie/") ? "" : h || "home";
  document.querySelectorAll(".navlinks a, .tabbar a").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("href") === `#${section}`);
  });
}

function goBackFromMovie() {
  if (history.length > 1) {
    history.back();
    // Если назад идти некуда (страницу открыли по прямой ссылке) — уходим сами
    setTimeout(() => {
      if (currentMovieId() !== null) location.hash = "";
    }, 400);
  } else {
    location.hash = "";
  }
}

/* Роутер: #movie/{id} — страница фильма, #секция — прыжок по главной */
function route() {
  const id = currentMovieId();
  const wasMovie = document.body.dataset.view === "movie";
  if (id !== null) {
    if (!wasMovie) state.homeScroll = window.scrollY;
    renderMoviePage(id);
    return;
  }
  if (wasMovie) exitMoviePage();
  updateNavActive();
  if (wasMovie) render(); // применить фильтры, изменённые внутри страницы фильма
  const hash = location.hash;
  if (hash && hash !== "#home") {
    const target = document.querySelector(hash);
    if (target) {
      jumpTo(target);
      return;
    }
  }
  if (wasMovie && state.homeScroll) {
    window.scrollTo({ top: state.homeScroll, behavior: "instant" });
  } else {
    window.scrollTo({ top: 0, behavior: "instant" });
  }
}

/* Клик внутри страницы фильма (и модалки-запаски): избранное, трейлер,
   актёр, похожий фильм, кнопка «Назад» */
function bindMovieBodyActions(root) {
  root.addEventListener("click", (e) => {
    const back = e.target.closest("#movieBack");
    if (back) {
      goBackFromMovie();
      return;
    }
    const fav = e.target.closest(".fav-btn");
    if (fav) {
      toggleFavorite(Number(fav.dataset.id));
      return;
    }
    const trailer = e.target.closest(".trailer-btn");
    if (trailer) {
      const art = root.querySelector(".hero-art") || root.querySelector(".hero-poster");
      if (art) {
        const wrap = document.createElement("div");
        wrap.className = "trailer-wrap";
        wrap.innerHTML =
          `<iframe src="https://www.youtube.com/embed/${escapeAttr(trailer.dataset.trailer)}?autoplay=1" ` +
          `allow="autoplay; encrypted-media" allowfullscreen title="Трейлер"></iframe>`;
        art.replaceWith(wrap);
        trailer.remove();
      }
      return;
    }
    const actor = e.target.closest(".cast-card");
    if (actor) {
      state.actor = actor.dataset.actor;
      el("search").value = "";
      el("clearSearch").hidden = true;
      if (root === el("moviePage")) {
        location.hash = "#catalog"; // роутер вернёт на главную и применит фильтр
      } else {
        closeModal();
        jumpTo(el("catalog"));
        render();
      }
      return;
    }
    const similarCard = e.target.closest(".similar-card");
    if (similarCard) {
      if (root === el("moviePage")) location.hash = `movie/${similarCard.dataset.id}`;
      else openMovie(Number(similarCard.dataset.id));
    }
  });
}

function openRandom() {
  const list = filteredList();
  if (!list.length) return;
  openMovie(list[Math.floor(Math.random() * list.length)].id);
}

/* ── Запасные ссылки для картинок ──────────────────── */

function bindImageFallbacks(root) {
  root.addEventListener(
    "error",
    (e) => {
      const img = e.target;
      if (img.tagName !== "IMG") return;
      // data-fallback может содержать цепочку ссылок через |
      const chain = (img.dataset.fallback || "").split("|").filter(Boolean);
      if (chain.length) {
        if (chain.length > 1) img.dataset.fallback = chain.slice(1).join("|");
        else delete img.dataset.fallback;
        img.src = chain[0];
      } else {
        img.src = PIXEL;
        img.style.opacity = "0";
      }
    },
    true
  );
}

/* ── События ───────────────────────────────────────── */

function bindEvents() {
  bindImageFallbacks(el("grid"));
  bindImageFallbacks(el("savedGrid"));
  bindImageFallbacks(el("feature"));
  bindImageFallbacks(el("modalBody"));
  bindImageFallbacks(el("moviePage"));
  bindImageFallbacks(el("nowRow"));
  bindImageFallbacks(el("upRow"));

  for (const id of ["search", "genreExclude", "yearFrom", "yearTo", "ratingMin", "sortSelect"]) {
    const node = el(id);
    node.addEventListener(node.tagName === "INPUT" ? "input" : "change", render);
  }

  el("search").addEventListener("input", () => {
    el("clearSearch").hidden = !el("search").value;
  });
  el("clearSearch").addEventListener("click", () => {
    el("search").value = "";
    el("clearSearch").hidden = true;
    state.actor = "";
    render();
  });

  el("randomBtn").addEventListener("click", openRandom);

  el("filterToggle").addEventListener("click", () => {
    const panel = el("filterPanel");
    panel.hidden = !panel.hidden;
    el("filterToggle").querySelector("span").textContent = panel.hidden ? "⌄" : "⌃";
  });

  el("resetBtn").addEventListener("click", () => {
    el("search").value = "";
    el("clearSearch").hidden = true;
    el("genreExclude").value = "";
    el("yearFrom").value = "";
    el("yearTo").value = "";
    el("ratingMin").value = "";
    el("sortSelect").value = "default";
    state.actor = "";
    setGenre("");
    render();
  });

  el("topSearch").addEventListener("click", () => {
    el("search").focus();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // Меню: переходы по хешу обрабатывает роутер (route на hashchange)
  // Клик по карточке / сердечку / фич-блоку (делегирование на документе,
  // работает и для каталога, и для «Твоего списка»)
  document.addEventListener("click", (e) => {
    const heart = e.target.closest(".heart");
    if (heart) {
      e.stopPropagation();
      toggleFavorite(Number(heart.dataset.id));
      return;
    }
    const featOpen = e.target.closest("#feature [data-open]");
    if (featOpen) {
      openMovie(Number(featOpen.dataset.open));
      return;
    }
    const featHeart = e.target.closest("#feature [data-heart]");
    if (featHeart) {
      toggleFavorite(Number(featHeart.dataset.heart));
      return;
    }
    const collCard = e.target.closest(".coll-card");
    if (collCard) {
      openMovie(Number(collCard.dataset.id));
      return;
    }
    const railCard = e.target.closest(".rail-card");
    if (railCard) {
      openMovie(Number(railCard.dataset.id));
      return;
    }
    const collAll = e.target.closest("[data-collall]");
    if (collAll) {
      const id = collAll.dataset.collall;
      collOpen.has(id) ? collOpen.delete(id) : collOpen.add(id);
      const wasOpen = collOpen.has(id);
      renderCollections();
      // после перерисовки держим нажатую кнопку на месте
      const btn = document.querySelector(`[data-collall="${id}"]`);
      if (btn) btn.scrollIntoView({ behavior: "instant", block: "center" });
      if (wasOpen) {
        const sec = document.getElementById("collections");
        sec.scrollIntoView({ behavior: "instant", block: "start" });
      }
      return;
    }
    const movie = e.target.closest(".movie");
    if (movie) openMovie(Number(movie.dataset.id));
  });

  bindMovieBodyActions(el("modalBody"));
  bindMovieBodyActions(el("moviePage"));

  el("modalClose").addEventListener("click", closeModal);
  el("movieModal").addEventListener("click", (e) => {
    if (e.target.classList.contains("modal-backdrop")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !el("movieModal").hidden) closeModal();
  });

  // Бесконечная прокрутка
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) renderMore();
  }, { rootMargin: "600px" });
  observer.observe(el("sentinel"));
}

/* ── Старт ─────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  // Скелетоны на время загрузки данных
  el("grid").innerHTML = Array.from({ length: 12 }, () => '<div class="skeleton"></div>').join("");
  bindEvents();
  window.addEventListener("hashchange", route);
  route();
  loadData();
});

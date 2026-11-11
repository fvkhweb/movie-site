/* «Что посмотреть?» v2 — каталог с фильтрами, актёрами и избранным.
   Все данные статичные, постеры локальные (работает без VPN). */

const PAGE_SIZE = 60;
const PROXY_IMG = "https://wsrv.nl/?url=";
const PIXEL =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

const state = {
  movies: [],
  genres: [],
  lists: { popular: [], top_rated: [] },
  cast: null,   // { movieId: [{id, name, character, photo}] }
  people: null, // [{ id, name, photo, movies: [] }]
  view: "popular",
  favorites: JSON.parse(localStorage.getItem("favorites") || "[]"),
  limit: PAGE_SIZE,
  actor: "",    // фильтр «фильмы актёра»
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

function personPhoto(path, width) {
  if (!path) return "";
  return `${PROXY_IMG}image.tmdb.org/t/p/w${width || 185}${path}`;
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
  const [moviesRes, genresRes, listsRes] = await Promise.allSettled([
    fetch("data/movies.json").then((r) => (r.ok ? r.json() : Promise.reject(r.status))),
    fetch("data/genres.json").then((r) => (r.ok ? r.json() : [])),
    fetch("data/lists.json").then((r) => (r.ok ? r.json() : null)),
  ]);

  if (moviesRes.status !== "fulfilled" || !Array.isArray(moviesRes.value) || !moviesRes.value.length) {
    el("grid").innerHTML =
      "<p style='color:#aaa; grid-column: 1/-1;'>Данные ещё не загружены. " +
      "Запустите GitHub Action «Update movies» или проверьте, что data/movies.json существует.</p>";
    return;
  }

  state.movies = moviesRes.value;
  state.genres = Array.isArray(genresRes.value) ? genresRes.value : [];
  if (listsRes.value) state.lists = listsRes.value;

  el("catalogInfo").textContent = `Каталог: ${state.movies.length} фильмов`;

  fillControls();
  render();

  // Актёры грузим в фоне — поиск по актёрам заработает после загрузки
  Promise.allSettled([
    fetch("data/cast.json").then((r) => (r.ok ? r.json() : null)),
    fetch("data/people.json").then((r) => (r.ok ? r.json() : null)),
  ]).then(([cast, people]) => {
    state.cast = cast.status === "fulfilled" ? cast.value : null;
    state.people = people.status === "fulfilled" ? people.value : null;
    // Если пользователь уже что-то ищет — пересчитаем с учётом актёров
    if (el("search").value.trim() || state.actor) render();
  });
}

function fillControls() {
  const years = state.movies
    .map((m) => parseInt(m.year, 10))
    .filter((y) => y > 1900);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);

  const genreSelect = el("genreSelect");
  state.genres.forEach((g) => {
    const opt = document.createElement("option");
    opt.value = g.id;
    opt.textContent = g.name;
    genreSelect.appendChild(opt);
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

/* ── Фильтрация ────────────────────────────────────── */

function currentList() {
  if (state.view === "favorites") {
    return state.favorites.map(movieById).filter(Boolean);
  }
  if (state.view === "top_rated") {
    return (state.lists.top_rated || []).map(movieById).filter(Boolean);
  }
  if (state.view === "popular") {
    return (state.lists.popular || []).map(movieById).filter(Boolean);
  }
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
  const genre = el("genreSelect").value;
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
  if (sortType === "rating_desc") list.sort((a, b) => num(b.rating) - num(a.rating));
  else if (sortType === "kp_rating_desc") list.sort((a, b) => num(b.kp_rating) - num(a.kp_rating));
  else if (sortType === "year_desc") list.sort((a, b) => num(b.year) - num(a.year));
  else if (sortType === "year_asc") list.sort((a, b) => num(a.year) - num(b.year));
  else if (sortType === "title_asc") list.sort((a, b) => byId(a.title, b.title, 1));
  else if (sortType === "runtime_desc") list.sort((a, b) => num(b.runtime) - num(a.runtime));
  else if (state.view === "all") list.sort((a, b) => num(b.popularity) - num(a.popularity));

  return list;
}

/* ── Отрисовка ─────────────────────────────────────── */

function cardHtml(m) {
  const { local, fallback } = posterSources(m);
  const isFav = state.favorites.includes(m.id);
  const rating = m.rating ? Number(m.rating).toFixed(1) : "";
  const genresText = (m.genres || [])
    .map((id) => (state.genres.find((g) => g.id === id) || {}).name)
    .filter(Boolean)
    .slice(0, 2)
    .join(" • ");

  return `
  <div class="card" data-id="${m.id}">
    <img alt="${escapeAttr(m.title || "")}" loading="lazy"
         src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>
    <div class="shade"></div>
    ${rating ? `<span class="rating-badge ${ratingClass(m.rating)}">⭐ ${rating}</span>` : ""}
    <button class="fav-btn ${isFav ? "active" : ""}" data-id="${m.id}" title="В избранное">${isFav ? "❤" : "🤍"}</button>
    <div class="meta">
      <b>${escapeHtml(m.title || "Без названия")}</b>
      <span>${escapeHtml([m.year || "", genresText].filter(Boolean).join(" • "))}</span>
    </div>
  </div>`;
}

function render() {
  const grid = el("grid");
  if (!grid) return;

  state.limit = PAGE_SIZE;
  const list = filteredList();

  el("emptyState").hidden = list.length > 0;
  updateResultsCount(list.length);

  grid.innerHTML = list.slice(0, state.limit).map(cardHtml).join("");
  el("sentinel").hidden = list.length <= state.limit;
  updateFavBadge();
}

function renderMore() {
  const list = filteredList();
  if (state.limit >= list.length) {
    el("sentinel").hidden = true;
    return;
  }
  state.limit += PAGE_SIZE;
  const grid = el("grid");
  const html = list.slice(0, state.limit).map(cardHtml).join("");
  // Перерисовываем целиком — просто и надёжно при таких объёмах
  grid.innerHTML = html;
  el("sentinel").hidden = list.length <= state.limit;
}

function updateResultsCount(count) {
  const parts = [];
  parts.push(`Найдено: ${count}`);
  if (state.actor) parts.push(`актёр: «${escapeHtml(state.actor)}» <button class="icon-btn" id="clearActor" title="Убрать фильтр">✕</button>`);
  el("resultsCount").innerHTML = parts.join(" • ");
  const clearActor = el("clearActor");
  if (clearActor) clearActor.onclick = () => { state.actor = ""; render(); };
}

function updateFavBadge() {
  const badge = el("favCount");
  if (!badge) return;
  badge.hidden = state.favorites.length === 0;
  badge.textContent = state.favorites.length;
}

/* ── Избранное ─────────────────────────────────────── */

function toggleFavorite(id, btn) {
  const i = state.favorites.indexOf(id);
  if (i === -1) state.favorites.push(id);
  else state.favorites.splice(i, 1);
  localStorage.setItem("favorites", JSON.stringify(state.favorites));
  updateFavBadge();
  // Обновим сердечки везде
  document.querySelectorAll(`.fav-btn[data-id="${id}"]`).forEach((b) => {
    const active = state.favorites.includes(id);
    b.classList.toggle("active", active);
    b.textContent = active ? "❤" : "🤍";
  });
  if (state.view === "favorites") render();
}

/* ── Модалка ───────────────────────────────────────── */

function openModal(id) {
  const m = movieById(id);
  if (!m) return;

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
            ? `<img alt="${escapeAttr(c.name)}" loading="lazy" src="${escapeAttr(personPhoto(c.photo))}">`
            : `<div class="cast-photo-empty">🎭</div>`
        }
        <div class="cast-name">${escapeHtml(c.name)}</div>
        ${c.character ? `<div class="cast-role">${escapeHtml(c.character)}</div>` : ""}
      </div>`
        )
        .join("")}</div></div>`
    : "";

  el("modalBody").innerHTML = `
    <div class="movie-hero">
      ${
        local || fallback
          ? `<img alt="${escapeAttr(m.title || "")}" src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>`
          : `<div class="poster-empty" style="width:200px;">Нет постера</div>`
      }
      <div class="movie-info">
        <h2>${escapeHtml(m.title || "Без названия")}${m.year ? ` (${escapeHtml(m.year)})` : ""}</h2>
        <p class="movie-sub">${escapeHtml([m.original_title, (m.countries || []).join(", ")].filter(Boolean).join(" • "))}</p>
        <div class="ratings">${ratings}</div>
        <div class="chips">${genreChips}</div>
        <p class="overview">${escapeHtml(m.description || "Описание отсутствует.")}</p>
        <button class="fav-btn ${isFav ? "active" : ""}" data-id="${m.id}" style="position:static; margin-top:12px;" title="В избранное">${isFav ? "❤" : "🤍"}</button>
      </div>
    </div>
    ${castHtml}`;

  el("movieModal").hidden = false;
  document.body.style.overflow = "hidden";
}

function closeModal() {
  el("movieModal").hidden = true;
  document.body.style.overflow = "";
}

function openRandom() {
  const list = filteredList();
  if (!list.length) return;
  openModal(list[Math.floor(Math.random() * list.length)].id);
}

/* ── Запасные ссылки для картинок ──────────────────── */

function bindImageFallbacks(root) {
  root.addEventListener(
    "error",
    (e) => {
      const img = e.target;
      if (img.tagName !== "IMG") return;
      const fb = img.dataset.fallback;
      if (fb) {
        delete img.dataset.fallback;
        img.src = fb;
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
  bindImageFallbacks(el("modalBody"));

  el("tabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    state.view = tab.dataset.view;
    render();
  });

  for (const id of ["search", "genreSelect", "yearFrom", "yearTo", "ratingMin", "sortSelect"]) {
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

  el("resetBtn").addEventListener("click", () => {
    el("search").value = "";
    el("clearSearch").hidden = true;
    el("genreSelect").value = "";
    el("yearFrom").value = "";
    el("yearTo").value = "";
    el("ratingMin").value = "";
    el("sortSelect").value = "default";
    state.actor = "";
    render();
  });

  // Клик по карточке / сердечку / актёру (делегирование)
  el("grid").addEventListener("click", (e) => {
    const fav = e.target.closest(".fav-btn");
    if (fav) {
      e.stopPropagation();
      toggleFavorite(Number(fav.dataset.id), fav);
      return;
    }
    const card = e.target.closest(".card");
    if (card) openModal(Number(card.dataset.id));
  });

  el("modalBody").addEventListener("click", (e) => {
    const fav = e.target.closest(".fav-btn");
    if (fav) {
      toggleFavorite(Number(fav.dataset.id), fav);
      return;
    }
    const actor = e.target.closest(".cast-card");
    if (actor) {
      state.actor = actor.dataset.actor;
      el("search").value = "";
      el("clearSearch").hidden = true;
      switchToAll();
      closeModal();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

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

function switchToAll() {
  state.view = "all";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "all"));
  render();
}

/* ── Старт ─────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", () => {
  // Скелетоны на время загрузки данных
  el("grid").innerHTML = Array.from({ length: 12 }, () => '<div class="skeleton"></div>').join("");
  bindEvents();
  loadData();
});

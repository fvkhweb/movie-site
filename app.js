/* «Что посмотреть?» v2 — каталог с фильтрами, актёрами и избранным.
   Все данные статичные, постеры локальные (работает без VPN). */

// На мобильных батч меньше: сотни постеров разом душат слабые сети
const PAGE_SIZE = window.matchMedia("(max-width: 650px)").matches ? 30 : 60;
const PROXY_IMG = "https://wsrv.nl/?url=";
const PROXY_IMG_2 = "https://images.weserv.nl/?url=";
const DATA_VERSION = "11"; // bump при изменении формата данных — сбрасывает кэш файлов data/*
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
  countries: [], // страны из данных: [{ name, label, count }]
  countryInclude: new Set(), // показывать только эти страны
  countryExclude: new Set(), // исключить эти страны
  countryQuery: "", // поиск по списку стран
  favorites: JSON.parse(localStorage.getItem("favorites") || "[]"),
  limit: PAGE_SIZE,
  actor: "",    // фильтр «фильмы актёра»
  currentModal: null, // какой фильм открыт в модалке
  homeScroll: 0, // позиция прокрутки до перехода на страницу фильма
};

const el = (id) => document.getElementById(id);

/* ── Даты релиза ───────────────────────────────────── */

// Фильм, до премьеры которого не больше недели, ещё показываем в каталоге
// с плашкой «Скоро в кино». Премьеры дальше недели живут только
// в блоке «Скоро в кино», чтобы не забивать «Новинки».
const SOON_DAYS = 7;
const DAY_MS = 86400000;

function todayISO() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Сколько дней осталось до премьеры: >0 — ещё не вышел, null — даты нет
function daysUntilRelease(m) {
  const raw = (m && m.release_date) || "";
  if (!raw) return null;
  const t = Date.parse(raw.slice(0, 10));
  if (isNaN(t)) return null;
  return Math.round((t - Date.parse(todayISO())) / DAY_MS);
}

function isUnreleased(m) {
  const d = daysUntilRelease(m);
  return d !== null && d > 0;
}

function isSoonRelease(m) {
  const d = daysUntilRelease(m);
  return d !== null && d > 0 && d <= SOON_DAYS;
}

function isFarUpcoming(m) {
  const d = daysUntilRelease(m);
  return d !== null && d > SOON_DAYS;
}

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
  // Цепочка прокси: wsrv → images.weserv.nl → imagetmdb → statically.io → прямой TMDB.
  // Все — бесплатных CDN-зеркал TMDB: если одно лежит, подхватывает следующее.
  if (!path) return null;
  const w = width || 185;
  const p = `image.tmdb.org/t/p/w${w}${path}`;
  return {
    src: `${PROXY_IMG}${p}`,
    fallback: `${PROXY_IMG_2}${p}|https://imagetmdb.com/t/p/w${w}${path}|https://cdn.statically.io/img/${p}|https://${p}`,
  };
}

function ratingClass(value) {
  if (value >= 7.5) return "good";
  if (value >= 6) return "mid";
  return "bad";
}

function movieDescription(m) {
  // Русский обзор — основной; если его нет (или он оказался чужим и был
  // выброшен ботом), показываем английский оригинал с TMDB
  return m.description || m.description_en || "";
}

function posterSources(movie) {
  // Локальный файл всегда первый, резерв — Кинопоиск (Яндекс.CDN) или wsrv-прокси
  const local = movie.poster || `posters/${movie.id}.jpg`;
  const fallback = movie.poster_fallback || "";
  return { local, fallback };
}

function kpFrameSources(url) {
  // Кадр Кинопоиска бывает в размере /orig (~4 МБ!) и /960x540 (~80 КБ).
  // Просим маленький, оригинал держим запасным.
  if (!url) return null;
  const small = url.replace(/\/orig$/, "/960x540");
  return { small, orig: url };
}

function runtimeLabel(min) {
  if (!min) return "";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h} ч ${m ? m + " мин" : ""}`.trim() : `${m} мин`;
}

/* ── Появление карточек при прокрутке (аккуратные анимации) ── */

const revealIO = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) {
      e.target.classList.add("visible");
      revealIO.unobserve(e.target);
    }
  });
}, { rootMargin: "40px" });

function reveal(root) {
  (root || document).querySelectorAll(".anim:not(.visible)").forEach((n, i) => {
    n.style.transitionDelay = `${(i % 10) * 25}ms`;
    revealIO.observe(n);
  });
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
  if (document.body.dataset.view === "rails") renderRailsPage();

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
      if (document.body.dataset.view === "collections") renderCollectionsPage();
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
  // Годы в фильтре — только по текущий: анонсы 2027+ не должны
  // предлагаться в выпадающих списках
  const maxYear = Math.min(Math.max(...years), new Date().getFullYear());

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

  buildCountryFilter();
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
  // жанр и страны живут внутри панели «Фильтры» — подсвечиваем кнопку
  updateFilterHighlight();
  render();
}

/* ── Фильтр по странам: широкий выпадающий список ──── */

function buildCountryFilter() {
  const counts = new Map();
  state.movies.forEach((m) => {
    (m.countries || []).forEach((c) => counts.set(c, (counts.get(c) || 0) + 1));
  });
  state.countries = [...counts.entries()]
    .map(([name, count]) => ({ name, label: countryLabel(name), count }))
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  renderCountryChips();
}

function renderCountryChips() {
  const box = el("countryChips");
  if (!box) return;
  const q = state.countryQuery.trim().toLowerCase();
  const list = state.countries.filter(
    (c) => !q || c.label.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)
  );
  box.innerHTML = list.length
    ? list
        .map((c) => {
          const inc = state.countryInclude.has(c.name);
          const exc = state.countryExclude.has(c.name);
          const cls = inc ? " include" : exc ? " exclude" : "";
          const title = inc
            ? "Включена — клик, чтобы исключить"
            : exc
              ? "Исключена — клик, чтобы снять"
              : "Клик — включить, ещё раз — исключить";
          return `<button type="button" class="country-option${cls}" data-country="${escapeAttr(c.name)}" title="${title}"><span class="cname">${escapeHtml(c.label)}</span><span class="mark" aria-hidden="true"></span></button>`;
        })
        .join("")
    : `<div class="country-nothing">Ничего не найдено</div>`;
  updateCountryBadge();
}

function updateCountryBadge() {
  const total = state.countryInclude.size + state.countryExclude.size;
  const badge = el("countryBadge");
  if (badge) {
    badge.hidden = !total;
    badge.textContent = total;
  }
  const summary = el("countrySummary");
  if (summary) {
    const parts = [];
    if (state.countryInclude.size) parts.push(`показывать: ${state.countryInclude.size}`);
    if (state.countryExclude.size) parts.push(`исключить: ${state.countryExclude.size}`);
    summary.textContent = parts.length ? parts.join(" · ") : "Страны не выбраны";
  }
}

function countryOptionEl(name) {
  return [...document.querySelectorAll(".country-option")].find(
    (b) => b.dataset.country === name
  );
}

// Красим один пункт на месте, чтобы список не терял прокрутку при клике
function paintCountryOption(btn, name) {
  if (!btn) return;
  const inc = state.countryInclude.has(name);
  const exc = state.countryExclude.has(name);
  btn.classList.toggle("include", inc);
  btn.classList.toggle("exclude", exc);
  btn.title = inc
    ? "Включена — клик, чтобы исключить"
    : exc
      ? "Исключена — клик, чтобы снять"
      : "Клик — включить, ещё раз — исключить";
}

// Тройное состояние: выкл → включить → исключить → выкл
function cycleCountry(name) {
  if (state.countryInclude.has(name)) {
    state.countryInclude.delete(name);
    state.countryExclude.add(name);
  } else if (state.countryExclude.has(name)) {
    state.countryExclude.delete(name);
  } else {
    state.countryInclude.add(name);
  }
  paintCountryOption(countryOptionEl(name), name);
  updateCountryBadge();
  updateFilterHighlight();
  render();
}

function clearCountries() {
  state.countryInclude.clear();
  state.countryExclude.clear();
  state.countryQuery = "";
  el("countrySearch").value = "";
  renderCountryChips();
  updateFilterHighlight();
  render();
}

function openCountryPopover() {
  const pop = el("countryPopover");
  const btn = el("countryToggle");
  if (!pop || !btn) return;
  const r = btn.getBoundingClientRect();
  const top = Math.round(Math.min(r.bottom + 8, window.innerHeight - 160));
  pop.style.top = `${top}px`;
  // Ниже кнопки на мобильном попап иначе уедет за нижний край экрана
  pop.style.maxHeight = `${Math.max(220, Math.min(window.innerHeight * 0.72, window.innerHeight - top - 16, 560))}px`;
  pop.hidden = false;
  btn.setAttribute("aria-expanded", "true");
  window.addEventListener("scroll", onCountryScroll, { passive: true });
  window.addEventListener("resize", closeCountryPopover, { passive: true });
  el("countrySearch").focus();
}

function closeCountryPopover() {
  const pop = el("countryPopover");
  if (!pop || pop.hidden) return;
  pop.hidden = true;
  el("countryToggle").setAttribute("aria-expanded", "false");
  window.removeEventListener("scroll", onCountryScroll);
  window.removeEventListener("resize", closeCountryPopover);
}

function onCountryScroll() {
  closeCountryPopover();
}

function updateFilterHighlight() {
  el("filterToggle").classList.toggle("has-genre", !!state.genre);
  el("countryToggle").classList.toggle(
    "has-country",
    state.countryInclude.size > 0 || state.countryExclude.size > 0
  );
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
    // Дальние премьеры не мешают каталогу: они живут в блоке «Скоро в кино».
    // Исключение — явный поиск по названию: человек ищет конкретный фильм.
    if (!q && isFarUpcoming(m)) return false;
    const countries = m.countries || [];
    if (state.countryExclude.size && countries.some((c) => state.countryExclude.has(c))) return false;
    if (state.countryInclude.size && !countries.some((c) => state.countryInclude.has(c))) return false;
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

// Русские названия стран TMDB (в данных они на английском).
// Незнакомые страны показываем как есть — база обновляется автоматически.
const COUNTRY_RU = {
  "United States of America": "США",
  "United Kingdom": "Великобритания",
  "France": "Франция",
  "Japan": "Япония",
  "Germany": "Германия",
  "Canada": "Канада",
  "Italy": "Италия",
  "Spain": "Испания",
  "India": "Индия",
  "China": "Китай",
  "South Korea": "Южная Корея",
  "Mexico": "Мексика",
  "Australia": "Австралия",
  "Hong Kong": "Гонконг",
  "Belgium": "Бельгия",
  "Ireland": "Ирландия",
  "Brazil": "Бразилия",
  "Sweden": "Швеция",
  "Switzerland": "Швейцария",
  "Denmark": "Дания",
  "New Zealand": "Новая Зеландия",
  "Finland": "Финляндия",
  "Poland": "Польша",
  "Netherlands": "Нидерланды",
  "Thailand": "Таиланд",
  "Norway": "Норвегия",
  "Romania": "Румыния",
  "Indonesia": "Индонезия",
  "Czech Republic": "Чехия",
  "United Arab Emirates": "ОАЭ",
  "Austria": "Австрия",
  "Luxembourg": "Люксембург",
  "Taiwan": "Тайвань",
  "Philippines": "Филиппины",
  "South Africa": "ЮАР",
  "Turkey": "Турция",
  "Russia": "Россия",
  "Cyprus": "Кипр",
  "Greece": "Греция",
  "Morocco": "Марокко",
  "Ukraine": "Украина",
  "Saudi Arabia": "Саудовская Аравия",
  "Hungary": "Венгрия",
  "Soviet Union": "СССР",
  "Colombia": "Колумбия",
  "Israel": "Израиль",
  "Singapore": "Сингапур",
  "Yugoslavia": "Югославия",
  "Croatia": "Хорватия",
  "Serbia": "Сербия",
  "Bulgaria": "Болгария",
  "Egypt": "Египет",
  "Portugal": "Португалия",
  "Iceland": "Исландия",
  "Netherlands Antilles": "Антильские острова",
  "Latvia": "Латвия",
  "Palestinian Territory": "Палестина",
  "Argentina": "Аргентина",
  "Chile": "Чили",
  "Qatar": "Катар",
  "Vietnam": "Вьетнам",
  "Lebanon": "Ливан",
  "Tunisia": "Тунис",
  "Malawi": "Малави",
  "Bahamas": "Багамы",
  "Belarus": "Беларусь",
  "Ecuador": "Эквадор",
  "Iran": "Иран",
  "Macedonia": "Македония",
  "Ethiopia": "Эфиопия",
  "Ghana": "Гана",
  "Jordan": "Иордания",
  "Namibia": "Намибия",
  "Puerto Rico": "Пуэрто-Рико",
  "Nigeria": "Нигерия",
  "Cuba": "Куба",
  "Congo": "Конго",
  "Syrian Arab Republic": "Сирия",
  "Gabon": "Габон",
  "Rwanda": "Руанда",
  "Chad": "Чад",
  "Cote D'Ivoire": "Кот-д’Ивуар",
  "Estonia": "Эстония",
  "Montenegro": "Черногория",
  "Slovenia": "Словения",
  "Czechoslovakia": "Чехословакия",
  "West Germany": "ФРГ",
  "East Germany": "ГДР",
  "Georgia": "Грузия",
  "Armenia": "Армения",
  "Kazakhstan": "Казахстан",
  "Uzbekistan": "Узбекистан",
  "Moldova": "Молдова",
  "Lithuania": "Литва",
  "Azerbaijan": "Азербайджан",
};

function countryLabel(name) {
  return COUNTRY_RU[name] || name;
}

function filmsWord(n) {
  const d = n % 10, h = n % 100;
  if (d === 1 && h !== 11) return "ФИЛЬМ";
  if (d >= 2 && d <= 4 && (h < 12 || h > 14)) return "ФИЛЬМА";
  return "ФИЛЬМОВ";
}

function cardHtml(m, opts = {}) {
  const { local, fallback } = posterSources(m);
  const isFav = state.favorites.includes(m.id);
  const rating = m.rating ? Number(m.rating).toFixed(1) : "";
  const genreName = (state.genres.find((g) => g.id === (m.genres || [])[0]) || {}).name || "";
  const soon = isSoonRelease(m);
  const sub = (opts.date || soon) && m.release_date
    ? `В КИНО ${fmtDateRu(m.release_date).toUpperCase()}`
    : [m.year || "", genreName ? genreName.toUpperCase() : ""].filter(Boolean).map(escapeHtml).join(" &nbsp;·&nbsp; ");

  return `
  <article class="movie anim" data-id="${m.id}">
    <div class="poster">
      <img alt="${escapeAttr(m.title || "")}" loading="lazy" decoding="async"
           src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>
      ${rating ? `<span class="poster-rating">★ ${rating}</span>` : ""}
      ${soon && !opts.date ? `<span class="poster-soon">СКОРО В КИНО</span>` : ""}
      <button class="heart ${isFav ? "saved" : ""}" data-id="${m.id}" aria-label="В избранное">${isFav ? "♥" : "♡"}</button>
    </div>
    <div class="movie-title">${escapeHtml(m.title || "Без названия")}</div>
    <div class="movie-sub">${sub}</div>
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
  reveal(grid);

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
  // Кинопоиск добавляем только в каталог: главная — по рейтингам TMDB.
  const films = state.movies.filter((m) => m.source !== "kp");
  // Если у популярных фильмов есть кадры с Кинопоиска (Яндекс.CDN) —
  // показываем фильм с кадром: он ландшафтный и красиво заполняет блок
  const withFrame = films.filter((m) => m.frame && movieDescription(m) && m.rating);
  const pool = withFrame.length
    ? withFrame
    : films.filter((m) => movieDescription(m) && m.rating);
  if (!pool.length) return;
  const m = pool.sort((a, b) => (b.popularity || 0) - (a.popularity || 0))[0];

  const { local, fallback } = posterSources(m);
  const kp = kpFrameSources(m.frame);
  const artSrc = (kp && kp.small) || local;
  const artFallback = kp ? [kp.orig, local].filter(Boolean).join("|") : fallback;
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
      <p>${escapeHtml(movieDescription(m))}</p>
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
    <div class="genre-card anim" data-genre="${g.id}">
      <b>${escapeHtml(g.name.charAt(0).toUpperCase() + g.name.slice(1))}</b>
      <span>${GENRE_EN[g.id] || "GENRE"} / ${g.count} ${filmsWord(g.count)} ↗</span>
    </div>`
    )
    .join("");
  reveal(strip);

  strip.addEventListener("click", (e) => {
    const card = e.target.closest(".genre-card");
    if (!card) return;
    setGenre(card.dataset.genre);
    jumpTo(el("catalog"));
  });
}

/* ── Подборки (отдельная страница #collections) ────── */

function renderCollectionsPage() {
  const wrap = el("collectionsList");
  if (!wrap) return;
  if (!state.collections.length) {
    wrap.innerHTML = '<div class="empty">Подборки появятся после следующего обновления базы.</div>';
    return;
  }
  wrap.innerHTML = state.collections
    .map((c) => {
      const list = c.items.map(movieById).filter(Boolean);
      if (!list.length) return "";
      const meta = `${c.total} ${filmsWord(c.total)} · В КАТАЛОГЕ ${list.length}/${c.total}`;
      const cards = list
        .map(
          (m, i) => `
      <div class="coll-card anim" data-id="${m.id}" title="${escapeAttr(m.title || "")}">
        <span class="coll-rank">${String(i + 1).padStart(3, "0")}</span>
        <img alt="${escapeAttr(m.title || "")}" loading="lazy" decoding="async" src="${escapeAttr(m.poster || `posters/${m.id}.jpg`)}">
      </div>`
        )
        .join("");
      return `
    <div class="collection">
      <div class="section-head"><div class="section-title">${escapeHtml((c.title || "").toUpperCase())}</div><div class="section-meta">${escapeHtml(meta)}</div></div>
      <div class="coll-row">${cards}</div>
    </div>`;
    })
    .join("");
  reveal(wrap);
}

function showCollectionsPage() {
  document.body.dataset.view = "collections";
  const page = el("collectionsPage");
  page.innerHTML =
    `<div class="wrap coll-page-head">
      <button class="movie-back" id="collBack" title="Назад">← Назад</button>
      <div class="section-head"><div class="section-title">ПОДБОРКИ</div><div class="section-meta">COLLECTIONS</div></div>
    </div>
    <div class="wrap" id="collectionsList"></div>`;
  page.hidden = false;
  document.title = "Подборки — Что посмотреть?";
  renderCollectionsPage();
  updateNavActive();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function hideCollectionsPage() {
  document.body.dataset.view = "";
  const page = el("collectionsPage");
  page.hidden = true;
  page.innerHTML = "";
  document.title = "Что посмотреть?";
}

/* ── Страницы «На слуху сейчас» (#trending) и «Скоро в кино» (#soon) ── */

const RAIL_TITLES = {
  trending: { title: "НА СЛУХУ СЕЙЧАС", meta: "TRENDING NOW", page: "На слуху сейчас" },
  soon: { title: "СКОРО В КИНО", meta: "COMING SOON", page: "Скоро в кино" },
};

function renderRailsPage() {
  if (document.body.dataset.view !== "rails") return;
  const grid = el("railsGrid");
  if (!grid) return;
  const mode = state.railsMode;
  const info = RAIL_TITLES[mode];
  const today = todayISO();
  let list;
  if (mode === "soon") {
    const raw = (state.lists.upcoming || []).map(movieById).filter(Boolean);
    list = [
      ...raw
        .filter((m) => m.release_date && m.release_date.slice(0, 10) >= today)
        .sort((a, b) => a.release_date.localeCompare(b.release_date)),
      ...raw.filter((m) => !m.release_date),
    ];
  } else {
    list = (state.lists.now_playing || []).map(movieById).filter(Boolean);
  }
  const meta = el("railsMeta");
  if (meta) meta.textContent = `${info.meta} · ${list.length} ${filmsWord(list.length)}`;
  if (!list.length) {
    grid.innerHTML = '<div class="empty">Список подтянется при следующем обновлении базы.</div>';
    return;
  }
  grid.innerHTML = list.map((m) => cardHtml(m, { date: mode === "soon" })).join("");
  bindImageFallbacks(grid);
  reveal(grid);
}

function showRailsPage(mode) {
  state.railsMode = mode;
  document.body.dataset.view = "rails";
  const info = RAIL_TITLES[mode];
  const page = el("railsPage");
  page.innerHTML = `<div class="wrap coll-page-head">
      <button class="movie-back" id="railsBack" title="Назад">← Назад</button>
      <div class="section-head"><div class="section-title">${info.title}</div><div class="section-meta" id="railsMeta">${info.meta}</div></div>
    </div>
    <div class="wrap"><div class="grid" id="railsGrid"></div></div>`;
  page.hidden = false;
  document.title = `${info.page} — Что посмотреть?`;
  bindImageFallbacks(el("railsGrid")); // свежий контейнер — свежий обработчик
  renderRailsPage();
  updateNavActive();
  window.scrollTo({ top: 0, behavior: "instant" });
}

function hideRailsPage() {
  state.railsMode = null;
  document.body.dataset.view = "";
  const page = el("railsPage");
  page.hidden = true;
  page.innerHTML = "";
  document.title = "Что посмотреть?";
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
  <div class="rail-card anim" data-id="${m.id}" title="${escapeAttr(m.title || "")}">
    <div class="poster">
      <img alt="${escapeAttr(m.title || "")}" loading="lazy" decoding="async"
           src="${escapeAttr(m.poster || `posters/${m.id}.jpg`)}" ${m.poster_fallback ? `data-fallback="${escapeAttr(m.poster_fallback)}"` : ""}>
    </div>
    <div class="movie-title">${escapeHtml(m.title || "Без названия")}</div>
    <div class="movie-sub">${sub}</div>
  </div>`;
}

function renderRails() {
  const today = todayISO();
  const now = (state.lists.now_playing || []).map(movieById).filter(Boolean);
  // «Скоро в кино» — только невышедшие, ближайшие первыми;
  // страховка от залежавшихся дат в данных. Анонсы без точной даты
  // (например, просто «2027») — в конце списка.
  const upRaw = (state.lists.upcoming || []).map(movieById).filter(Boolean);
  const up = [
    ...upRaw
      .filter((m) => m.release_date && m.release_date.slice(0, 10) >= today)
      .sort((a, b) => a.release_date.localeCompare(b.release_date)),
    ...upRaw.filter((m) => !m.release_date),
  ];

  const nowRow = el("nowRow");
  if (nowRow) {
    nowRow.innerHTML = now.map((m) => railCardHtml(m)).join("");
    el("nowPlaying").hidden = !now.length;
    el("nowEmpty").hidden = !!now.length;
    reveal(nowRow);
  }
  const upRow = el("upRow");
  if (upRow) {
    upRow.innerHTML = up.map((m) => railCardHtml(m, { date: true })).join("");
    el("upcoming").hidden = !up.length;
    el("upEmpty").hidden = !!up.length;
    reveal(upRow);
  }
}

/* ── «Твой список» ─────────────────────────────────── */

function renderSaved() {
  const grid = el("savedGrid");
  if (!grid) return;
  const list = state.favorites.map(movieById).filter(Boolean);
  grid.innerHTML = list.map(cardHtml).join("");
  reveal(grid);
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
  reveal(grid);
}

function updateResultsCount(count) {
  let text = `${count} ${filmsWord(count)}`;
  if (state.actor) text += ` · АКТЁР: «${escapeHtml(state.actor)}» <button class="iconbtn small" id="clearActor" title="Убрать фильтр">✕</button>`;
  el("resultCount").innerHTML = text;
  const clearActor = el("clearActor");
  if (clearActor) clearActor.onclick = () => { state.actor = ""; render(); };
}

// Подписи сортировки для заголовка каталога
const SORT_TITLES = {
  default: "ПОПУЛЯРНОЕ СЕЙЧАС",
  rating_desc: "ЛУЧШИЕ ПО РЕЙТИНГУ",
  kp_rating_desc: "ЛУЧШИЕ ПО КИНОПОИСКУ",
  year_desc: "НОВИНКИ",
  year_asc: "КЛАССИКА СНАЧАЛА",
  title_asc: "ПО АЛФАВИТУ",
  runtime_desc: "САМЫЕ ДЛИННЫЕ",
};

function updateCatalogTitle() {
  const q = el("search").value.trim();
  const title = q || state.actor
    ? "РЕЗУЛЬТАТЫ ПОИСКА"
    : state.genre
      ? (state.genres.find((g) => String(g.id) === state.genre) || {}).name?.toUpperCase() || "КАТАЛОГ"
      : SORT_TITLES[el("sortSelect").value] || SORT_TITLES.default;
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
  const premiere = isUnreleased(m)
    ? `ПРЕМЬЕРА ${escapeHtml(fmtDateRu(m.release_date).toUpperCase())}`
    : "";

  const ratings = [
    m.rating ? `<span class="rating-pill"><span class="label">TMDB</span>⭐ ${Number(m.rating).toFixed(1)}</span>` : "",
    m.kp_rating ? `<span class="rating-pill"><span class="label">Кинопоиск</span>⭐ ${Number(m.kp_rating).toFixed(1)}</span>` : "",
    m.runtime ? `<span class="rating-pill"><span class="label">Время</span>${runtimeLabel(m.runtime)}</span>` : "",
  ].filter(Boolean).join("");

  const cast = (state.cast && state.cast[String(m.id)]) || m.cast || [];
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
        ${premiere ? `<div class="tag">${premiere}</div>` : ""}
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
      <p class="overview">${escapeHtml(movieDescription(m) || "Описание отсутствует.")}</p>
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

function probeImage(url, onOk, onFail, timeoutMs = 8000) {
  // Зависшее соединение не вызывает ни onload, ни onerror —
  // поэтому по таймауту считаем пробу неудачной и идём дальше по цепочке
  const im = new Image();
  let done = false;
  const finish = (fn, arg) => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    fn && fn(arg);
  };
  const timer = setTimeout(() => finish(onFail), timeoutMs);
  im.onload = () => finish(onOk, url);
  im.onerror = () => finish(onFail);
  im.src = url;
}

function setMovieHeroBackdrop(m) {
  const hero = el("moviePage").querySelector(".movie-hero");
  if (!hero) return;
  const apply = (url) => {
    state.heroApplied = { id: m.id, url };
    // страница могла перерисоваться, пока кадр грузился — берём свежий элемент
    const artNow = el("moviePage").querySelector(".hero-art");
    if (artNow) {
      artNow.src = url;
      artNow.hidden = false;
    }
  };
  const chain = [];
  // Кадр Кинопоиска (Яндекс.CDN — из РФ без VPN), сначала маленький вариант,
  // затем оригинал, затем TMDB-кадр через прокси
  const kp = kpFrameSources(m.frame);
  if (kp) chain.push(kp.small, kp.orig);
  if (m.backdrop) {
    const p = `image.tmdb.org/t/p/w1280${m.backdrop}`;
    chain.push(`${PROXY_IMG}${p}`, `${PROXY_IMG_2}${p}`, `https://imagetmdb.com/t/p/w1280${m.backdrop}`, `https://cdn.statically.io/img/${p}`, `https://${p}`);
  }
  if (!chain.length) {
    // Кадра нет совсем — убираем пустой баннер, контент начинается сразу
    hero.remove();
    el("moviePage").querySelector(".movie-head")?.classList.add("no-hero");
    return;
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
  // Кадр, уже загруженный для этого фильма, вставляем сразу —
  // чтобы перерисовка страницы (после догрузки актёров) его не потеряла
  const heroApplied = state.heroApplied?.id === m.id ? state.heroApplied.url : null;
  const genreChips = (m.genres || [])
    .map((gid) => (state.genres.find((g) => g.id === gid) || {}).name)
    .filter(Boolean)
    .map((name) => `<span class="chip">${escapeHtml(name)}</span>`)
    .concat(
      (m.countries || []).map((c) => `<span class="chip chip-country">${escapeHtml(c)}</span>`)
    )
    .join("");

  const ratings = [
    m.rating
      ? `<span class="rating-pill ${ratingClass(m.rating)}"><span class="label">TMDB</span><span class="val">★ ${Number(m.rating).toFixed(1)}</span></span>`
      : "",
    m.kp_rating
      ? `<span class="rating-pill ${ratingClass(m.kp_rating)}"><span class="label">Кинопоиск</span><span class="val">★ ${Number(m.kp_rating).toFixed(1)}</span></span>`
      : "",
    m.runtime ? `<span class="rating-pill"><span class="label">Время</span><span class="val">${runtimeLabel(m.runtime)}</span></span>` : "",
  ].filter(Boolean).join("");

  const cast = (state.cast && state.cast[String(m.id)]) || m.cast || [];
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

  // Плашка премьеры — только у ещё не вышедших фильмов;
  // у вышедших дата ни к чему (она есть в описании и фактах)
  const premiere = isUnreleased(m)
    ? `ПРЕМЬЕРА ${escapeHtml(fmtDateRu(m.release_date).toUpperCase())}`
    : "";

  return `
  <div class="movie-hero">
    <img class="hero-art" alt="" ${heroApplied ? `src="${escapeAttr(heroApplied)}"` : "hidden"}>
    <div class="hero-shade"></div>
    <button class="movie-back" id="movieBack" title="Назад">← Каталог</button>
  </div>
  <div class="movie-head">
    ${
      local || fallback
        ? `<img class="hero-thumb" alt="${escapeAttr(m.title || "")}" src="${escapeAttr(local)}" ${fallback ? `data-fallback="${escapeAttr(fallback)}"` : ""}>`
        : `<div class="hero-thumb poster-empty">Нет постера</div>`
    }
    <div class="hero-text">
      ${premiere ? `<div class="tag">${premiere}</div>` : ""}
      <h1>${escapeHtml(m.title || "Без названия")}${m.year ? ` <span class="title-year">${escapeHtml(m.year)}</span>` : ""}</h1>
      ${m.director ? `<p class="movie-byline">Режиссёр: <b>${escapeHtml(m.director)}</b></p>` : ""}
      <p class="movie-sub">${escapeHtml(m.original_title || "")}</p>
      <div class="ratings">${ratings}</div>
      <div class="chips">${genreChips}</div>
      <div class="movie-actions">
        <button class="fav-btn ${isFav ? "active" : ""}" data-id="${m.id}" title="В избранное">${isFav ? "♥ В избранном" : "＋ В избранное"}</button>
        ${m.trailer ? `<button class="primary trailer-btn" data-trailer="${escapeAttr(m.trailer)}">▶ Трейлер</button>` : ""}
      </div>
    </div>
  </div>
  <div class="wrap movie-page-body">
    <div class="overview-block"><p class="overview">${escapeHtml(movieDescription(m) || "Описание отсутствует.")}</p></div>
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
  document.title = "Что посмотреть?";
}

function updateNavActive() {
  const h = (location.hash || "#home").replace("#", "");
  const section = h.startsWith("movie/") ? "" : h || "home";
  document.querySelectorAll(".navlinks a, .tabbar a").forEach((a) => {
    a.classList.toggle("active", a.getAttribute("href") === `#${section}`);
  });
}

/* Роутер: #movie/{id} — страница фильма, #collections — страница подборок,
   #секция — прыжок по главной */
function route() {
  const id = currentMovieId();
  const wasMovie = document.body.dataset.view === "movie";
  const wasColl = document.body.dataset.view === "collections";
  const wasRails = document.body.dataset.view === "rails";
  const wasAny = wasMovie || wasColl || wasRails;
  if (id !== null) {
    if (!wasAny) state.homeScroll = window.scrollY;
    if (wasColl) hideCollectionsPage();
    if (wasRails) hideRailsPage();
    renderMoviePage(id);
    return;
  }
  if (location.hash === "#collections") {
    if (!wasAny) state.homeScroll = window.scrollY;
    if (wasMovie) exitMoviePage();
    if (wasRails) hideRailsPage();
    if (!wasColl) showCollectionsPage();
    return;
  }
  if (location.hash === "#trending" || location.hash === "#soon") {
    const mode = location.hash === "#trending" ? "trending" : "soon";
    if (!wasAny) state.homeScroll = window.scrollY;
    if (wasMovie) exitMoviePage();
    if (wasColl) hideCollectionsPage();
    if (!wasRails || state.railsMode !== mode) showRailsPage(mode);
    return;
  }
  // возврат на главную
  if (wasMovie) exitMoviePage();
  if (wasColl) hideCollectionsPage();
  if (wasRails) hideRailsPage();
  if (wasAny) {
    updateNavActive();
    render();
  } else {
    updateNavActive();
  }
  const hash = location.hash;
  if (hash && hash !== "#home") {
    const target = document.querySelector(hash);
    if (target) {
      jumpTo(target);
      return;
    }
  }
  if (wasAny && state.homeScroll) {
    window.scrollTo({ top: state.homeScroll, behavior: "instant" });
  } else {
    window.scrollTo({ top: 0, behavior: "instant" });
  }
}

/* Кнопка «Назад» на отдельных страницах */
function goBack() {
  const from = document.body.dataset.view;
  if (history.length > 1) {
    history.back();
    // Если назад идти некуда (страницу открыли по прямой ссылке) — уходим сами
    setTimeout(() => {
      if (document.body.dataset.view === from) location.hash = "";
    }, 400);
  } else {
    location.hash = "";
  }
}

/* Клик внутри страницы фильма (и модалки-запаски): избранное, трейлер,
   актёр, похожий фильм. Кнопки «Назад» обрабатываются на документе. */
function bindMovieBodyActions(root) {
  root.addEventListener("click", (e) => {
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

  el("countrySearch").addEventListener("input", () => {
    state.countryQuery = el("countrySearch").value;
    renderCountryChips();
  });
  el("countryChips").addEventListener("click", (e) => {
    const option = e.target.closest(".country-option");
    if (option) cycleCountry(option.dataset.country);
  });
  el("countryToggle").addEventListener("click", () => {
    if (el("countryPopover").hidden) openCountryPopover();
    else closeCountryPopover();
  });
  el("countryClear").addEventListener("click", clearCountries);
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#countryDropdown")) closeCountryPopover();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeCountryPopover();
  });

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
    clearCountries();
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
    const back = e.target.closest("#movieBack, #collBack, #railsBack");
    if (back) {
      goBack();
      return;
    }
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

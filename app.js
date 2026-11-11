let movies = [];
let dataCache = { popular: [], top_rated: [] };
let currentTab = 'popular';

async function load() {
  // allSettled не дает сайту упасть, если одного файла нет
  const results = await Promise.allSettled([
    fetch("data/popular.json").then(r => r.ok ? r.json() : []),
    fetch("data/top_rated.json").then(r => r.ok ? r.json() : [])
  ]);

  dataCache.popular = results[0].status === 'fulfilled' ? results[0].value : [];
  dataCache.top_rated = results[1].status === 'fulfilled' ? results[1].value : [];

  switchTab(currentTab);
}

function switchTab(tab) {
  currentTab = tab;
  const popBtn = document.getElementById('tab-popular');
  const topBtn = document.getElementById('tab-top');
  if (popBtn) popBtn.classList.toggle('active', tab === 'popular');
  if (topBtn) topBtn.classList.toggle('active', tab === 'top_rated');

  movies = dataCache[tab] || [];
  render();
}

// Список ссылок на постер: локальный файл, затем резерв.
// Локальные картинки отдаются с того же домена, что и сайт,
// поэтому работают без VPN из РФ.
function posterSources(movie) {
  const sources = [];
  const poster = movie.poster || "";
  const local = `posters/${movie.id}.jpg`;

  if (!poster) {
    sources.push(local);
  } else if (/^https?:\/\//i.test(poster)) {
    if (poster.includes("image.tmdb.org")) {
      sources.push(local, poster.replace("image.tmdb.org", "imagetmdb.com"));
    } else {
      sources.push(poster);
    }
  } else {
    sources.push(poster);
  }

  if (movie.poster_fallback && !sources.includes(movie.poster_fallback)) {
    sources.push(movie.poster_fallback);
  }

  return sources;
}

// Навешиваем переключение на резервную ссылку, а если всё упало — прячем картинку
function setupPosters(root) {
  root.querySelectorAll("img[data-srcs]").forEach(img => {
    let srcs = [];
    try {
      srcs = JSON.parse(img.dataset.srcs);
    } catch (e) {
      srcs = [];
    }
    if (!srcs.length) {
      img.style.display = "none";
      return;
    }

    let index = 0;
    img.addEventListener("error", () => {
      index++;
      if (index < srcs.length) {
        img.src = srcs[index];
      } else {
        img.style.display = "none";
      }
    });
    img.src = srcs[0];
  });
}

function emptyPoster(style) {
  return `<div class="poster-empty" style="${style}">Нет постера</div>`;
}

function render() {
  const qInput = document.getElementById("search");
  const sortInput = document.getElementById("sortSelect");
  const q = qInput ? qInput.value.toLowerCase() : "";
  const sortType = sortInput ? sortInput.value : "default";

  let list = Array.isArray(movies) ? movies.filter(m => (!q || (m.title && m.title.toLowerCase().includes(q)))) : [];

  if (sortType === 'rating_desc') {
    list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  } else if (sortType === 'year_desc') {
    list.sort((a, b) => (b.year || '').localeCompare(a.year || ''));
  } else if (sortType === 'title_asc') {
    list.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
  }

  const grid = document.getElementById("grid");
  if (!grid) return;

  if (list.length === 0) {
    grid.innerHTML = "<p style='color:#aaa;'>Фильмы не найдены или данные ещё не загружены. Проверьте логи GitHub Actions.</p>";
    return;
  }

  grid.innerHTML = list.map(m => {
    const sources = posterSources(m);
    const imgHtml = sources.length
      ? `<img alt="${escapeHtml(m.title || '')}" loading="lazy" data-srcs='${escapeAttr(JSON.stringify(sources))}'>`
      : emptyPoster("height: 270px; border-radius: 10px 10px 0 0;");

    return `
    <div class="card" onclick="openModal(${m.id})">
      ${imgHtml}
      <div class="info">
        <b>${escapeHtml(m.title || 'Без названия')}</b> <span>⭐ ${m.rating ? Number(m.rating).toFixed(1) : '—'} (${m.year || '—'})</span>
      </div>
    </div>`;
  }).join("");

  setupPosters(grid);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Для JSON внутри атрибута: кавычки одинарные, поэтому экранируем только их и амперсанд
function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function openModal(id) {
  const movie = movies.find(m => m.id === id);
  if (!movie) return;

  const modal = document.getElementById("movieModal");
  const modalBody = document.getElementById("modalBody");
  if (!modal || !modalBody) return;

  const sources = posterSources(movie);
  const imgHtml = sources.length
    ? `<img style="width: 200px; border-radius: 8px; object-fit: cover;" data-srcs='${escapeAttr(JSON.stringify(sources))}'>`
    : emptyPoster("width: 200px; height: 300px; border-radius: 8px;");

  modalBody.innerHTML = `
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
      ${imgHtml}
      <div style="flex: 1; min-width: 250px;">
        <h2 style="margin-top: 0;">${escapeHtml(movie.title)} (${movie.year || '—'})</h2>
        <p><strong>Рейтинг:</strong> ⭐ ${movie.rating ? Number(movie.rating).toFixed(1) : 'Нет'}</p>
        <p><strong>Актеры:</strong> ${escapeHtml(movie.actors || 'Информация отсутствует')}</p>
        <p><strong>Описание:</strong> ${escapeHtml(movie.description || 'Описание отсутствует')}</p>
      </div>
    </div>
  `;

  setupPosters(modalBody);
  modal.style.display = "block";
}

document.addEventListener("DOMContentLoaded", () => {
  const closeBtn = document.querySelector(".close-button");
  if (closeBtn) closeBtn.onclick = () => document.getElementById("movieModal").style.display = "none";

  window.onclick = (event) => {
    const modal = document.getElementById("movieModal");
    if (event.target == modal) modal.style.display = "none";
  };

  const searchInput = document.getElementById("search");
  if (searchInput) searchInput.addEventListener("input", render);

  const sortSelect = document.getElementById("sortSelect");
  if (sortSelect) sortSelect.addEventListener("change", render);

  load();
});

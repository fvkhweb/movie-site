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
    let safePoster = m.poster ? m.poster.replace("image.tmdb.org", "imagetmdb.com") : "";
    
    // Простой onerror: если картинка не загрузится, она просто скроется, а верстка не поедет
    let imgHtml = safePoster 
      ? `<img src="${safePoster}" alt="${m.title || ''}" loading="lazy" onerror="this.style.display='none'">` 
      : `<div style="height: 270px; display: flex; align-items: center; justify-content: center; background: #2a2a2a; color: #666; border-radius: 10px 10px 0 0;">Нет постера</div>`;

    return `
    <div class="card" onclick="openModal(${m.id})">
      ${imgHtml}
      <div class="info">
        <b>${m.title || 'Без названия'}</b> <span>⭐ ${m.rating ? Number(m.rating).toFixed(1) : '—'} (${m.year || '—'})</span>
      </div>
    </div>`;
  }).join("");
}

function openModal(id) {
  const movie = movies.find(m => m.id === id);
  if (!movie) return;

  const modal = document.getElementById("movieModal");
  const modalBody = document.getElementById("modalBody");
  if (!modal || !modalBody) return;

  let safePoster = movie.poster ? movie.poster.replace("image.tmdb.org", "imagetmdb.com") : "";
  let imgHtml = safePoster 
      ? `<img src="${safePoster}" style="width: 200px; border-radius: 8px; object-fit: cover;" onerror="this.style.display='none'">` 
      : `<div style="width: 200px; height: 300px; display: flex; align-items: center; justify-content: center; background: #2a2a2a; color: #666; border-radius: 8px;">Нет постера</div>`;

  modalBody.innerHTML = `
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
      ${imgHtml}
      <div style="flex: 1; min-width: 250px;">
        <h2 style="margin-top: 0;">${movie.title} (${movie.year || '—'})</h2>
        <p><strong>Рейтинг:</strong> ⭐ ${movie.rating ? Number(movie.rating).toFixed(1) : 'Нет'}</p>
        <p><strong>Актеры:</strong> ${movie.actors || 'Информация отсутствует'}</p>
        <p><strong>Описание:</strong> ${movie.description || 'Описание отсутствует'}</p>
      </div>
    </div>
  `;
  
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

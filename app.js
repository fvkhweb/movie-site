let movies = []; // Текущий список для отображения
let dataCache = { popular: [], top_rated: [] }; // Кэш данных
let currentTab = 'popular';

async function load() {
  // Загружаем оба файла
  const [pop, top] = await Promise.all([
    fetch("data/popular.json").then(r => r.json()),
    fetch("data/top_rated.json").then(r => r.json())
  ]);
  
  dataCache.popular = pop;
  dataCache.top_rated = top;
  
  switchTab(currentTab);
}

function switchTab(tab) {
  currentTab = tab;
  
  // Обновляем визуальное состояние кнопок
  document.getElementById('tab-popular').classList.toggle('active', tab === 'popular');
  document.getElementById('tab-top').classList.toggle('active', tab === 'top_rated');
  
  // Берем данные из кэша
  movies = dataCache[tab];
  render();
}

function render() {
  const q = document.getElementById("search").value.toLowerCase();
  const sortType = document.getElementById("sortSelect").value;
  
  // 1. Фильтрация
  let list = movies.filter(m => (!q || m.title.toLowerCase().includes(q)));
  
  // 2. Сортировка
  if (sortType === 'rating_desc') {
    list.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  } else if (sortType === 'year_desc') {
    list.sort((a, b) => (b.year || '').localeCompare(a.year || ''));
  } else if (sortType === 'title_asc') {
    list.sort((a, b) => a.title.localeCompare(b.title));
  }
  
    // 3. Рендер с заглушкой для битых постеров
  document.getElementById("grid").innerHTML = list.map(m => {
    // Замена заблокированного домена на зеркало прямо на лету
    let safePoster = m.poster ? m.poster.replace("image.tmdb.org", "imagetmdb.com") : "";
    
    return `
    <div class="card" onclick="openModal(${m.id})">
      <img src="${safePoster}" alt="${m.title}" loading="lazy" 
           onerror="this.style.display='none'; this.parentElement.classList.add('no-image'); this.parentElement.insertAdjacentHTML('afterbegin', '<div class=\\'no-poster\\'>Нет постера</div>');">
      <div class="info">
        <b>${m.title}</b> <span>⭐ ${m.rating ? m.rating.toFixed(1) : '—'} (${m.year})</span>
      </div>
    </div>`;
  }).join("");
// Модалка
function openModal(id) {
  // Ищем фильм в текущем списке
  const movie = movies.find(m => m.id === id);
  if (!movie) return;

  const modal = document.getElementById("movieModal");
  const modalBody = document.getElementById("modalBody");

  modalBody.innerHTML = `
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
      <img src="${movie.poster}" style="width: 200px; border-radius: 8px; object-fit: cover;" onerror="this.style.display='none'">
      <div style="flex: 1; min-width: 250px;">
        <h2 style="margin-top: 0;">${movie.title} (${movie.year})</h2>
        <p><strong>Рейтинг:</strong> ⭐ ${movie.rating ? movie.rating.toFixed(1) : 'Нет'}</p>
        <p><strong>Актеры:</strong> ${movie.actors || 'Информация отсутствует'}</p>
        <p><strong>Описание:</strong> ${movie.description || 'Описание отсутствует'}</p>
      </div>
    </div>
  `;
  
  modal.style.display = "block";
}

document.querySelector(".close-button").onclick = () => {
  document.getElementById("movieModal").style.display = "none";
};
window.onclick = (event) => {
  const modal = document.getElementById("movieModal");
  if (event.target == modal) modal.style.display = "none";
};

document.getElementById("search").addEventListener("input", render);
document.getElementById("sortSelect").addEventListener("change", render);
load();

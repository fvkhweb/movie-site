let movies = [];

async function load() {
  // Жанры можно оставить, если хотите фильтровать, но пока сфокусируемся на фильмах
  movies = await (await fetch("data/popular.json")).json();
  render();
}

function render() {
  const q = document.getElementById("search").value.toLowerCase();
  const list = movies.filter(m => (!q || m.title.toLowerCase().includes(q)));
  
  document.getElementById("grid").innerHTML = list.slice(0, 60).map(m => `
    <div class="card" onclick="openModal(${m.id})">
      <img src="${m.poster}" alt="${m.title}" loading="lazy">
      <div class="info">
        <b>${m.title}</b> <span>⭐ ${m.rating ? m.rating.toFixed(1) : '—'} (${m.year})</span>
      </div>
    </div>`).join("");
}

// Функция открытия модального окна
function openModal(id) {
  const movie = movies.find(m => m.id === id);
  if (!movie) return;

  const modal = document.getElementById("movieModal");
  const modalBody = document.getElementById("modalBody");

  modalBody.innerHTML = `
    <div style="display: flex; gap: 20px; flex-wrap: wrap;">
      <img src="${movie.poster}" style="width: 200px; border-radius: 8px; object-fit: cover;">
      <div style="flex: 1; min-width: 250px;">
        <h2 style="margin-top: 0;">${movie.title} (${movie.year})</h2>
        <p><strong>Рейтинг:</strong> ⭐ ${movie.rating ? movie.rating.toFixed(1) : 'Нет'}</p>
        <p><strong>Актёры:</strong> ${movie.actors || 'Информация отсутствует'}</p>
        <p><strong>Описание:</strong> ${movie.description || 'Описание отсутствует'}</p>
      </div>
    </div>
  `;
  
  modal.style.display = "block";
}

// Закрытие модального окна
document.querySelector(".close-button").onclick = () => {
  document.getElementById("movieModal").style.display = "none";
};
window.onclick = (event) => {
  const modal = document.getElementById("movieModal");
  if (event.target == modal) modal.style.display = "none";
};

document.getElementById("search").addEventListener("input", render);
load();

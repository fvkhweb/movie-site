let movies = [], genres = [];

async function load() {
  genres = await (await fetch("data/genres.json")).json();
  movies = await (await fetch("data/popular.json")).json();

  const sel = document.getElementById("genreFilter");
  genres.forEach(g => {
    const o = document.createElement("option");
    o.value = g.id;
    o.textContent = g.name;
    sel.appendChild(o);
  });
  render();
}

function render() {
  const q = document.getElementById("search").value.toLowerCase();
  const gid = document.getElementById("genreFilter").value;
  const list = movies.filter(m =>
    (!gid || m.genres.includes(+gid)) &&
    (!q || m.title.toLowerCase().includes(q))
  );
  document.getElementById("grid").innerHTML = list.slice(0, 60).map(m => `
    <div class="card">
      <img src="https://imagetmdb.com/t/p/w500${m.poster.replace('https://image.tmdb.org/t/p/w500', '')}" alt="" loading="lazy">
      <div class="info">
        <b>${m.title}</b> <span>⭐ ${m.rating.toFixed(1)} (${m.year})</span>
        <p>${m.overview.slice(0, 120)}…</p>
      </div>
    </div>`).join("");
}

document.getElementById("search").addEventListener("input", render);
document.getElementById("genreFilter").addEventListener("change", render);
load();

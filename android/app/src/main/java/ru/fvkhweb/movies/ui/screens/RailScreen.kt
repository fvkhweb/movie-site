package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.SecondaryButton
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.formatDateRu
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.White

/** Полный список «На слуху» или «Скоро в кино» — та же сетка, что в каталоге. */
@Composable
fun RailScreen(
    viewModel: MainViewModel,
    type: String,
    onBack: () -> Unit,
    onOpenMovie: (Long) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val upcoming = type == "upcoming"
    val title = if (upcoming) "СКОРО В КИНО" else "НА СЛУХУ СЕЙЧАС"
    val meta = if (upcoming) "COMING SOON" else "TRENDING NOW"

    val movies = remember(state.lists, state.moviesById, upcoming) {
        val ids = if (upcoming) state.lists.upcoming else state.lists.nowPlaying
        val raw = ids.mapNotNull { state.moviesById[it] }
        if (upcoming) {
            val today = java.time.LocalDate.now().toString()
            raw.filter { !it.releaseDate.isNullOrBlank() && it.releaseDate.take(10) >= today }
                .sortedBy { it.releaseDate } + raw.filter { it.releaseDate.isNullOrBlank() }
        } else {
            raw
        }
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(gridColumns()),
        modifier = Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding()
            .navigationBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 30.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(Modifier.padding(top = 6.dp, bottom = 4.dp)) {
                SecondaryButton("← Назад", onBack)
                Text(title, style = AppText.h2, color = White, modifier = Modifier.padding(top = 16.dp))
                Text(
                    "$meta / ${movies.size} ${filmsWord(movies.size)}",
                    style = AppText.meta,
                    color = Muted,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }

        if (movies.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                EmptyState("Список подтянется при следующем обновлении базы.")
            }
        }

        itemsIndexed(movies, key = { _, movie -> movie.id }) { index, movie ->
            MovieCard(
                movie = movie,
                genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                isFavorite = movie.id in favorites,
                onClick = { onOpenMovie(movie.id) },
                onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                subtitle = if (upcoming && !movie.releaseDate.isNullOrBlank()) {
                    "В КИНО " + formatDateRu(movie.releaseDate).uppercase()
                } else {
                    null
                },
                revealIndex = index % 10,
            )
        }
    }
}

package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.SyncStatus
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.White

@Composable
fun FavoritesScreen(
    viewModel: MainViewModel,
    onOpenMovie: (Long) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()

    val ids = remember(favorites) { favorites.toList() }
    val movies = remember(ids, state.moviesById) { ids.mapNotNull { state.moviesById[it] } }

    LazyVerticalGrid(
        columns = GridCells.Fixed(gridColumns()),
        modifier = Modifier.fillMaxSize().background(Bg).statusBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 28.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .staggerReveal(index = 0, duration = 360),
            ) {
                Text("ТВОЙ СПИСОК", style = AppText.h2, color = White)
                Text(
                    "BOOKMARKS / ${movies.size} ${filmsWord(movies.size)}",
                    style = AppText.meta,
                    color = Muted,
                    modifier = Modifier.padding(top = 4.dp),
                )
                SyncStatus(
                    refreshing = state.refreshing,
                    offline = state.offline,
                    modifier = Modifier.padding(top = 12.dp),
                )
            }
        }

        if (movies.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                EmptyState("Нажми на сердечко у фильма, чтобы сохранить его здесь.")
            }
        }

        itemsIndexed(movies, key = { _, movie -> movie.id }) { index, movie: Movie ->
            MovieCard(
                movie = movie,
                genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                isFavorite = true,
                onClick = { onOpenMovie(movie.id) },
                onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                revealIndex = index % 10,
            )
        }
    }
}

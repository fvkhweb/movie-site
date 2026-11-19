package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.CircleButton
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.SyncStatus
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.White

@Composable
fun CollectionDetailScreen(
    viewModel: MainViewModel,
    collectionId: String,
    onBack: () -> Unit,
    onOpenMovie: (Long) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val collection = remember(state.collections, collectionId) {
        state.collections.firstOrNull { it.id == collectionId }
    }
    val movies: List<Movie> = remember(collection, state.moviesById) {
        collection?.items?.mapNotNull { state.moviesById[it] }.orEmpty()
    }

    if (collection == null) {
        if (state.loading) {
            LoadingState()
            return
        }
        Column(
            Modifier
                .fillMaxSize()
                .background(Bg)
                .statusBarsPadding()
                .padding(12.dp),
        ) {
            CircleButton("←", onBack)
            EmptyState("Подборка не найдена. Возможно, она обновится позже.")
        }
        return
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(gridColumns()),
        modifier = Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 30.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .staggerReveal(index = 0, duration = 260),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircleButton("←", onBack)
                    Spacer(Modifier.width(12.dp))
                    Text(
                        "ПОДБОРКА",
                        style = AppText.meta.copy(letterSpacing = 1.4.sp),
                        color = Blue2,
                    )
                    Spacer(Modifier.weight(1f))
                    Text(
                        "${movies.size} ${filmsWord(movies.size)}",
                        style = AppText.meta,
                        color = Muted,
                    )
                }
                Text(
                    collection.title,
                    style = AppText.h1.copy(fontSize = 21.sp),
                    color = White,
                    modifier = Modifier.padding(top = 16.dp),
                )
                Text(
                    buildString {
                        append("${collection.total} ${filmsWord(collection.total)}")
                        append(" · В КАТАЛОГЕ ${movies.size}")
                        collection.source?.takeIf { it.isNotBlank() }?.let { append(" · ${it.uppercase()}") }
                    },
                    style = AppText.meta,
                    color = Muted,
                    modifier = Modifier.padding(top = 6.dp),
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
                EmptyState("В этой подборке пока нет фильмов из каталога.")
            }
        }

        itemsIndexed(movies, key = { _, movie -> movie.id }) { index, movie ->
            MovieCard(
                movie = movie,
                genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                isFavorite = movie.id in favorites,
                onClick = { onOpenMovie(movie.id) },
                onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                revealIndex = index % 8,
            )
        }
    }
}

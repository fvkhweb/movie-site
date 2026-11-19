package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.RemoteImage
import ru.fvkhweb.movies.ui.components.SyncStatus
import ru.fvkhweb.movies.ui.components.clickScale
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.White

@Composable
fun CollectionsScreen(
    viewModel: MainViewModel,
    onOpenMovie: (Long) -> Unit,
    onOpenCollection: (String) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()

    if (!state.hasData) {
        LoadingState()
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Bg).statusBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 28.dp),
    ) {
        item {
            Column(Modifier.staggerReveal(index = 0, duration = 360)) {
                Text("ПОДБОРКИ", style = AppText.h2, color = White)
                Text(
                    "COLLECTIONS / ${state.collections.size}",
                    style = AppText.mono,
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

        if (state.collections.isEmpty()) {
            item { EmptyState("Подборки появятся после следующего обновления базы.") }
        }

        items(state.collections, key = { it.id }) { collection ->
            val movies: List<Movie> = collection.items.mapNotNull { state.moviesById[it] }
            if (movies.isNotEmpty()) {
                Column(
                    Modifier
                        .padding(top = 26.dp, bottom = 12.dp)
                        .staggerReveal(index = 1, duration = 260),
                ) {
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickScale(scaleDown = 0.985f) { onOpenCollection(collection.id) },
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                text = collection.title.uppercase(),
                                style = AppText.section,
                                color = White,
                            )
                            Text(
                                text = "${collection.total} ${filmsWord(collection.total)} · В КАТАЛОГЕ ${movies.size}/${collection.total}",
                                style = AppText.meta,
                                color = Muted,
                                modifier = Modifier.padding(top = 6.dp),
                            )
                        }
                        Text(
                            text = "ВСЕ  →",
                            style = AppText.meta.copy(letterSpacing = 1.sp),
                            color = Blue2,
                        )
                    }
                }
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    itemsIndexed(movies, key = { _, movie -> movie.id }) { index, movie ->
                        CollectionPoster(
                            movie = movie,
                            rank = index + 1,
                            revealIndex = index % 10,
                            onClick = { onOpenMovie(movie.id) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CollectionPoster(movie: Movie, rank: Int, revealIndex: Int, onClick: () -> Unit) {
    Box(
        Modifier
            .width(96.dp)
            .staggerReveal(index = revealIndex, offsetY = 14),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(2f / 3f)
                .clip(RoundedCornerShape(8.dp))
                .clickScale(scaleDown = 0.94f, onClick = onClick),
        ) {
            RemoteImage(
                urls = Media.posterUrls(movie),
                contentDescription = movie.title,
                modifier = Modifier.fillMaxSize(),
            )
            Text(
                text = rank.toString().padStart(3, '0'),
                style = AppText.mono.copy(fontSize = 9.sp),
                color = Color.White.copy(alpha = 0.9f),
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(5.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(Color(0x99090B0F))
                    .padding(horizontal = 4.dp, vertical = 2.dp),
            )
        }
    }
}

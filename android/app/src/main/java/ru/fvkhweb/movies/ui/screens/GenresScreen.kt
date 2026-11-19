package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.model.Genre
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.SyncStatus
import ru.fvkhweb.movies.ui.components.clickScale
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.White

private val genreEn = mapOf(
    28 to "ACTION", 12 to "ADVENTURE", 16 to "ANIMATION", 35 to "COMEDY", 80 to "CRIME",
    99 to "DOCUMENTARY", 18 to "DRAMA", 10751 to "FAMILY", 14 to "FANTASY", 36 to "HISTORY",
    27 to "HORROR", 10402 to "MUSIC", 9648 to "MYSTERY", 10749 to "ROMANCE", 878 to "SCI-FI",
    10770 to "TV MOVIE", 53 to "THRILLER", 10752 to "WAR", 37 to "WESTERN",
)

private data class GenreStat(val genre: Genre, val count: Int)

@Composable
fun GenresScreen(
    viewModel: MainViewModel,
    onOpenCatalog: () -> Unit,
) {
    val state by viewModel.catalog.collectAsState()

    if (!state.hasData) {
        LoadingState()
        return
    }

    val items = remember(state.movies, state.genres) {
        val counts = HashMap<Int, Int>()
        state.movies.forEach { movie -> movie.genres.forEach { counts[it] = (counts[it] ?: 0) + 1 } }
        state.genres
            .map { GenreStat(it, counts[it.id] ?: 0) }
            .filter { it.count > 0 }
            .sortedByDescending { it.count }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding(),
    ) {
        Column(
            Modifier
                .padding(horizontal = 16.dp)
                .padding(top = 14.dp)
                .staggerReveal(index = 0, duration = 360),
        ) {
            Text("ЖАНРЫ", style = AppText.h2, color = White)
            Text(
                "GENRE INDEX / ${items.size}",
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

        LazyVerticalGrid(
            columns = GridCells.Fixed(if (gridColumns() == 2) 2 else 4),
            contentPadding = PaddingValues(16.dp),
            horizontalArrangement = Arrangement.spacedBy(9.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp),
            modifier = Modifier.fillMaxSize(),
        ) {
            itemsIndexed(items, key = { _, item -> item.genre.id }) { index, item ->
                GenreTile(item, revealIndex = index % 10) {
                    viewModel.setGenre(item.genre.id)
                    onOpenCatalog()
                }
            }
        }
    }
}

@Composable
private fun GenreTile(item: GenreStat, revealIndex: Int, onClick: () -> Unit) {
    val shape = RoundedCornerShape(10.dp)
    Box(
        Modifier
            .fillMaxWidth()
            .height(86.dp)
            .staggerReveal(index = revealIndex)
            .clip(shape)
            .background(Panel)
            .border(1.dp, Line, shape)
            .clickScale(scaleDown = 0.95f, onClick = onClick)
            .padding(12.dp),
    ) {
        Column(Modifier.align(Alignment.CenterStart)) {
            val name = item.genre.name.replaceFirstChar { it.uppercase() }
            Text(
                name,
                style = AppText.h2.copy(fontSize = if (name.length > 13) 12.5.sp else 15.sp),
                color = White,
                maxLines = 2,
            )
            Text(
                "${genreEn[item.genre.id] ?: "GENRE"} / ${item.count} ${filmsWord(item.count)}\u00A0↗",
                style = AppText.meta.copy(fontSize = 8.5.sp),
                color = Blue2,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
    }
}

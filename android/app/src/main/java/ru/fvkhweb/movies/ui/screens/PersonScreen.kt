package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
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
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.CircleButton
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.RemoteImage
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.White

@Composable
fun PersonScreen(
    viewModel: MainViewModel,
    personName: String,
    onBack: () -> Unit,
    onOpenMovie: (Long) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val person = remember(state.people, personName) { state.personByName(personName) }

    if (person == null && state.loading) {
        LoadingState()
        return
    }

    val movies: List<Movie> = remember(person, state.moviesById) {
        person?.movies?.mapNotNull { state.moviesById[it] }.orEmpty()
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(gridColumns()),
        modifier = Modifier.fillMaxSize().background(Bg).statusBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 28.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .staggerReveal(index = 0, duration = 380),
            ) {
                CircleButton("←", onBack)
                if (person == null) {
                    EmptyState("Актёр не найден в базе.")
                } else {
                    Row(
                        Modifier.fillMaxWidth().padding(top = 18.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(14.dp),
                    ) {
                        Box(
                            Modifier
                                .size(84.dp)
                                .clip(CircleShape)
                                .background(Panel)
                                .border(1.dp, Line, CircleShape),
                        ) {
                            RemoteImage(
                                urls = Media.personPhoto(person.photo),
                                contentDescription = person.name,
                                modifier = Modifier.fillMaxSize(),
                            )
                        }
                        Column {
                            Text(person.name, style = AppText.h1.copy(fontSize = 21.sp), color = White)
                            Text(
                                "${movies.size} ${filmsWord(movies.size)} В КАТАЛОГЕ",
                                style = AppText.meta,
                                color = Muted,
                                modifier = Modifier.padding(top = 6.dp),
                            )
                        }
                    }
                }
            }
        }

        itemsIndexed(movies, key = { _, movie -> movie.id }) { index, movie ->
            MovieCard(
                movie = movie,
                genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                isFavorite = movie.id in favorites,
                onClick = { onOpenMovie(movie.id) },
                onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                revealIndex = index % 10,
            )
        }
    }
}

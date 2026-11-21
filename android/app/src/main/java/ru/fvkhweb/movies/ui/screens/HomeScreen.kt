package ru.fvkhweb.movies.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.model.Genre
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.ErrorState
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.PrimaryButton
import ru.fvkhweb.movies.ui.components.RailCard
import ru.fvkhweb.movies.ui.components.RatingBadge
import ru.fvkhweb.movies.ui.components.RemoteImage
import ru.fvkhweb.movies.ui.components.SecondaryButton
import ru.fvkhweb.movies.ui.components.SectionHead
import ru.fvkhweb.movies.ui.components.SyncStatus
import ru.fvkhweb.movies.ui.components.clickScale
import ru.fvkhweb.movies.ui.components.gridColumns
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.filmsWord
import ru.fvkhweb.movies.ui.formatDateRu
import ru.fvkhweb.movies.ui.runtimeLabel
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.Soft
import ru.fvkhweb.movies.ui.theme.White

private val genreEn = mapOf(
    28 to "ACTION", 12 to "ADVENTURE", 16 to "ANIMATION", 35 to "COMEDY", 80 to "CRIME",
    99 to "DOCUMENTARY", 18 to "DRAMA", 10751 to "FAMILY", 14 to "FANTASY", 36 to "HISTORY",
    27 to "HORROR", 10402 to "MUSIC", 9648 to "MYSTERY", 10749 to "ROMANCE", 878 to "SCI-FI",
    10770 to "TV MOVIE", 53 to "THRILLER", 10752 to "WAR", 37 to "WESTERN",
)

private data class GenreCount(val genre: Genre, val count: Int)

@Composable
fun HomeScreen(
    viewModel: MainViewModel,
    onOpenMovie: (Long) -> Unit,
    onOpenCatalog: () -> Unit,
    onOpenGenre: (Int) -> Unit,
    onOpenRail: (String) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()

    if (!state.hasData) {
        when {
            state.error != null -> ErrorState(state.error!!, viewModel::refresh)
            else -> LoadingState()
        }
        return
    }

    val movies = state.movies
    // Кинопоиск добавляется только в каталог: на главной — фильмы TMDB.
    val homeMovies = remember(movies) { movies.filter { it.source != "kp" } }
    val popular = remember(homeMovies) {
        homeMovies.sortedWith(compareByDescending<Movie> { it.popularity ?: 0.0 }).take(18)
    }
    val featured = remember(homeMovies) { pickFeatured(homeMovies) }

    val genreCounts = remember(movies, state.genres) {
        val counts = HashMap<Int, Int>()
        movies.forEach { movie -> movie.genres.forEach { counts[it] = (counts[it] ?: 0) + 1 } }
        state.genres
            .map { GenreCount(it, counts[it.id] ?: 0) }
            .filter { it.count > 4 }
            .sortedByDescending { it.count }
            .take(8)
    }

    val nowPlaying = remember(state.lists.nowPlaying, state.moviesById) {
        state.lists.nowPlaying.mapNotNull { state.moviesById[it] }
    }
    val upcoming = remember(state.lists.upcoming, state.moviesById) {
        val raw = state.lists.upcoming.mapNotNull { state.moviesById[it] }
        val today = java.time.LocalDate.now().toString()
        raw.filter { !it.releaseDate.isNullOrBlank() && it.releaseDate.take(10) >= today }
            .sortedBy { it.releaseDate } + raw.filter { it.releaseDate.isNullOrBlank() }
    }

    LazyVerticalGrid(
        columns = GridCells.Fixed(gridColumns()),
        modifier = Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding(),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 30.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            HomeHeader(refreshing = state.refreshing, offline = state.offline)
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            SearchTeaser(onOpenCatalog)
        }

        if (featured != null) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                FeatureCard(
                    movie = featured,
                    genreName = state.genreName(featured.genres.firstOrNull() ?: 0),
                    isFavorite = featured.id in favorites,
                    onOpen = { onOpenMovie(featured.id) },
                    onToggleFavorite = { viewModel.toggleFavorite(featured.id) },
                )
            }
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            SectionHead(
                title = "ПОПУЛЯРНОЕ СЕЙЧАС",
                meta = "${movies.size} ${filmsWord(movies.size)}",
                metaStyle = AppText.bodyBold,
            )
        }

        itemsIndexed(popular, key = { _, movie -> movie.id }) { index, movie ->
            MovieCard(
                movie = movie,
                genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                isFavorite = movie.id in favorites,
                onClick = { onOpenMovie(movie.id) },
                onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                revealIndex = index % 8,
            )
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            Box(Modifier.padding(top = 4.dp)) {
                SecondaryButton("Смотреть весь каталог  →", onOpenCatalog)
            }
        }

        if (nowPlaying.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                SectionHead(
                    title = "НА СЛУХУ СЕЙЧАС",
                    meta = "TRENDING NOW · ВСЕ →",
                    onClick = { onOpenRail("trending") },
                )
            }
            item(span = { GridItemSpan(maxLineSpan) }) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    itemsIndexed(nowPlaying, key = { _, movie -> movie.id }) { index, movie ->
                        RailCard(
                            movie = movie,
                            onClick = { onOpenMovie(movie.id) },
                            revealIndex = index % 8,
                        )
                    }
                }
            }
        }

        if (upcoming.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                SectionHead(
                    title = "СКОРО В КИНО",
                    meta = "COMING SOON · ВСЕ →",
                    onClick = { onOpenRail("upcoming") },
                )
            }
            item(span = { GridItemSpan(maxLineSpan) }) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    itemsIndexed(upcoming, key = { _, movie -> movie.id }) { index, movie ->
                        RailCard(
                            movie = movie,
                            onClick = { onOpenMovie(movie.id) },
                            subtitle = "В КИНО " + formatDateRu(movie.releaseDate).uppercase(),
                            revealIndex = index % 8,
                        )
                    }
                }
            }
        }

        if (genreCounts.isNotEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                SectionHead("ВЫБИРАЙ ПО НАСТРОЕНИЮ", "GENRE INDEX")
            }
            item(span = { GridItemSpan(maxLineSpan) }) {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                    itemsIndexed(genreCounts, key = { _, item -> item.genre.id }) { index, item ->
                        GenreCard(item, revealIndex = index % 8, onClick = { onOpenGenre(item.genre.id) })
                    }
                }
            }
        }

    }
}

@Composable
private fun HomeHeader(refreshing: Boolean, offline: Boolean) {
    Column(
        Modifier
            .fillMaxWidth()
            .staggerReveal(index = 0, duration = 320),
    ) {
        Row(
            Modifier.fillMaxWidth().padding(top = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("ЧТО ПОСМОТРЕТЬ", style = AppText.brand, color = White)
            Text("?", style = AppText.brand, color = Blue)
        }

        SyncStatus(refreshing = refreshing, offline = offline, modifier = Modifier.padding(top = 14.dp))

        Text(
            "FILM INDEX / ВАШ КИНОНАВИГАТОР",
            style = AppText.eyebrow,
            color = Blue2,
            modifier = Modifier.padding(top = 28.dp),
        )
        Text(
            buildAnnotatedString {
                append("ИЩИ СВОЁ\n")
                withStyle(SpanStyle(color = Blue)) { append("СЛЕДУЮЩЕЕ") }
                append(" КИНО.")
            },
            style = AppText.display,
            color = White,
            modifier = Modifier.padding(top = 10.dp),
        )
        Text(
            "Не бесконечный выбор. Только фильмы, которые стоит добавить в список.",
            style = AppText.bodySmall,
            color = Muted,
            modifier = Modifier.padding(top = 12.dp),
        )
    }
}

@Composable
private fun SearchTeaser(onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(top = 20.dp)
            .height(48.dp)
            .clip(RoundedCornerShape(9.dp))
            .background(Color(0xFF10141B))
            .border(1.dp, Line, RoundedCornerShape(9.dp))
            .clickScale(scaleDown = 0.98f, onClick = onClick)
            .padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.Search, contentDescription = null, tint = Muted, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(10.dp))
        Text("Название фильма или актёр…", style = AppText.body, color = Color(0xFF667080))
    }
}

@Composable
private fun FeatureCard(
    movie: Movie,
    genreName: String,
    isFavorite: Boolean,
    onOpen: () -> Unit,
    onToggleFavorite: () -> Unit,
) {
    val shape = RoundedCornerShape(14.dp)
    val country = movie.countries.firstOrNull()
    val tag = listOfNotNull(
        genreName.uppercase().takeIf { it.isNotBlank() },
        country?.uppercase(),
    ).joinToString(" / ")

    Column(
        Modifier
            .fillMaxWidth()
            .staggerReveal(index = 1, duration = 520)
            .clip(shape)
            .background(Panel)
            .border(1.dp, Line, shape)
            .clickScale(scaleDown = 0.985f, onClick = onOpen),
    ) {
        Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f)) {
            RemoteImage(
                urls = Media.heroUrls(movie),
                contentDescription = movie.title,
                modifier = Modifier.fillMaxSize(),
            )
            Box(
                Modifier
                    .matchParentSize()
                    .background(
                        Brush.verticalGradient(
                            0f to Color.Transparent,
                            0.55f to Bg.copy(alpha = 0.35f),
                            1f to Bg.copy(alpha = 0.92f),
                        ),
                    ),
            )
            Text(
                "FEATURED FILM — 001",
                style = AppText.mono,
                color = Color.White.copy(alpha = 0.6f),
                modifier = Modifier.align(Alignment.TopStart).padding(12.dp),
            )
            Column(Modifier.align(Alignment.BottomStart).padding(14.dp)) {
                Text(tag.ifBlank { "ВЫБОР РЕДАКЦИИ" }, style = AppText.monoWide, color = Blue2)
                Text(
                    movie.title.ifBlank { "Без названия" },
                    style = AppText.h1.copy(fontSize = 21.sp),
                    color = White,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Row(
                    Modifier.padding(top = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    movie.year?.takeIf { it.isNotBlank() }?.let {
                        Text(it, style = AppText.monoMedium, color = Soft)
                    }
                    movie.runtime?.takeIf { it > 0 }?.let {
                        Text(runtimeLabel(it).uppercase(), style = AppText.monoMedium, color = Soft)
                    }
                    movie.rating?.takeIf { it > 0 }?.let { RatingBadge(it) }
                }
            }
        }

        Column(Modifier.padding(14.dp)) {
            Text(
                movie.descriptionText.ifBlank { "Описание появится позже." },
                style = AppText.bodySmall,
                color = Soft,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis,
            )
            Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                PrimaryButton("О фильме", onOpen, suffix = "↗")
                SecondaryButton(
                    if (isFavorite) "♥\uFE0E В избранном" else "＋ В избранное",
                    onToggleFavorite,
                    active = isFavorite,
                )
            }
        }
    }
}

@Composable
private fun GenreCard(item: GenreCount, revealIndex: Int, onClick: () -> Unit) {
    val shape = RoundedCornerShape(10.dp)
    Column(
        Modifier
            .width(138.dp)
            .staggerReveal(index = revealIndex)
            .clip(shape)
            .background(Panel)
            .border(1.dp, Line, shape)
            .clickScale(scaleDown = 0.95f, onClick = onClick)
            .padding(12.dp),
    ) {
        Text(
            item.genre.name.replaceFirstChar { it.uppercase() },
            style = AppText.h2.copy(fontSize = 15.sp),
            color = White,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            "${genreEn[item.genre.id] ?: "GENRE"} / ${item.count} ${filmsWord(item.count)}\u00A0↗",
            style = AppText.meta.copy(fontSize = 8.5.sp),
            color = Muted,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 12.dp),
        )
    }
}

private fun pickFeatured(movies: List<Movie>): Movie? {
    val withFrame = movies.filter {
        !it.frame.isNullOrBlank() && it.descriptionText.isNotBlank() && (it.rating ?: 0.0) > 0
    }
    val pool = withFrame.ifEmpty {
        movies.filter { it.descriptionText.isNotBlank() && (it.rating ?: 0.0) > 0 }
    }
    return pool.maxByOrNull { it.popularity ?: 0.0 }
}

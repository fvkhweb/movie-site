package ru.fvkhweb.movies.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.model.CastMember
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.components.CircleButton
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.LoadingState
import ru.fvkhweb.movies.ui.components.PrimaryButton
import ru.fvkhweb.movies.ui.components.RailCard
import ru.fvkhweb.movies.ui.components.RemoteImage
import ru.fvkhweb.movies.ui.components.SecondaryButton
import ru.fvkhweb.movies.ui.components.SectionHead
import ru.fvkhweb.movies.ui.components.staggerReveal
import ru.fvkhweb.movies.ui.formatDateRu
import ru.fvkhweb.movies.ui.isUnreleased
import ru.fvkhweb.movies.ui.runtimeLabel
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bad
import ru.fvkhweb.movies.ui.theme.BadLine
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Good
import ru.fvkhweb.movies.ui.theme.GoodLine
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Mid
import ru.fvkhweb.movies.ui.theme.MidLine
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.Soft
import ru.fvkhweb.movies.ui.theme.White
import java.util.Locale

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MovieDetailScreen(
    viewModel: MainViewModel,
    movieId: Long,
    onBack: () -> Unit,
    onOpenMovie: (Long) -> Unit,
    onOpenPerson: (String) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val favorites by viewModel.favorites.collectAsState()
    val movie = state.moviesById[movieId]
    val context = LocalContext.current

    if (movie == null) {
        if (state.loading) {
            LoadingState()
        } else {
            Column(Modifier.fillMaxSize().statusBarsPadding().padding(12.dp)) {
                CircleButton("←", onBack)
                EmptyState("Фильм не найден в каталоге.")
            }
        }
        return
    }

    val isFavorite = movie.id in favorites
    val cast = state.castOf(movie.id).ifEmpty { movie.cast }
    val similar = remember(movie.similar, state.moviesById) {
        movie.similar.mapNotNull { state.moviesById[it] }.take(10)
    }

    val share: () -> Unit = {
        val text = buildString {
            append(movie.title)
            movie.year?.takeIf { it.isNotBlank() }?.let { append(" ($it)") }
            append("\n").append(Media.BASE)
        }
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        runCatching { context.startActivity(Intent.createChooser(send, "Поделиться")) }
        Unit
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().background(Bg).navigationBarsPadding(),
        contentPadding = PaddingValues(bottom = 30.dp),
    ) {
        item {
            Box(Modifier.fillMaxWidth().height(232.dp)) {
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
                                0f to Bg.copy(alpha = 0.15f),
                                0.55f to Bg.copy(alpha = 0.35f),
                                1f to Bg,
                            ),
                        ),
                )
                Row(
                    Modifier
                        .fillMaxWidth()
                        .statusBarsPadding()
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    CircleButton("←", onBack)
                    CircleButton("↗", share)
                }
            }
        }

        item {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .staggerReveal(index = 1, duration = 480),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    Modifier
                        .width(100.dp)
                        .aspectRatio(2f / 3f)
                        .clip(RoundedCornerShape(10.dp))
                        .background(Panel)
                        .border(1.dp, Line, RoundedCornerShape(10.dp)),
                ) {
                    RemoteImage(
                        urls = Media.posterUrls(movie),
                        contentDescription = movie.title,
                        modifier = Modifier.fillMaxSize(),
                    )
                }

                Column(Modifier.weight(1f)) {
                    if (isUnreleased(movie.releaseDate)) {
                        Text(
                            "ПРЕМЬЕРА " + formatDateRu(movie.releaseDate).uppercase(),
                            style = AppText.eyebrow.copy(fontSize = 9.sp),
                            color = Blue2,
                        )
                    }
                    Text(
                        movie.title.ifBlank { "Без названия" },
                        style = AppText.h1.copy(fontSize = 20.sp, lineHeight = 24.sp),
                        color = White,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                    movie.year?.takeIf { it.isNotBlank() }?.let {
                        Text(it, style = AppText.monoMedium, color = Muted, modifier = Modifier.padding(top = 4.dp))
                    }
                    movie.originalTitle?.takeIf { it.isNotBlank() }?.let {
                        Text(
                            it,
                            style = AppText.bodySmall,
                            color = Muted,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.padding(top = 2.dp),
                        )
                    }
                    movie.director?.takeIf { it.isNotBlank() }?.let {
                        Row(Modifier.padding(top = 6.dp)) {
                            Text("Режиссёр: ", style = AppText.bodySmall, color = Muted)
                            Text(it, style = AppText.bodySmall, color = White)
                        }
                    }
                }
            }
        }

        item {
            FlowRow(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
                verticalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                movie.rating?.takeIf { it > 0 }?.let {
                    RatingPill("TMDB", "★ " + String.format(Locale.US, "%.1f", it), tone = it)
                }
                movie.kpRating?.takeIf { it > 0 }?.let {
                    RatingPill("Кинопоиск", "★ " + String.format(Locale.US, "%.1f", it), tone = it)
                }
                movie.runtime?.takeIf { it > 0 }?.let {
                    RatingPill("Время", runtimeLabel(it), tone = null)
                }
            }
        }

        item {
            FlowRow(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(7.dp),
                verticalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                movie.genres.mapNotNull { state.genresById[it]?.name }.forEach { genre ->
                    InfoChip(genre.replaceFirstChar { it.uppercase() })
                }
                movie.countries.forEach { country -> InfoChip(country, subtle = true) }
            }
        }

        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SecondaryButton(
                    if (isFavorite) "♥\uFE0E В избранном" else "＋ В избранное",
                    onClick = { viewModel.toggleFavorite(movie.id) },
                    active = isFavorite,
                )
                movie.trailer?.takeIf { it.isNotBlank() }?.let { trailer ->
                    PrimaryButton("▶ Трейлер", onClick = {
                        val intent = Intent(
                            Intent.ACTION_VIEW,
                            Uri.parse("https://www.youtube.com/watch?v=$trailer"),
                        )
                        runCatching { context.startActivity(intent) }
                    })
                }
            }
        }

        item {
            Text(
                movie.descriptionText.ifBlank { "Описание отсутствует." },
                style = AppText.body,
                color = Soft,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }

        if (movie.facts.isNotEmpty()) {
            item {
                Column(Modifier.padding(horizontal = 16.dp)) {
                    SectionHead("💡 ИНТЕРЕСНЫЕ ФАКТЫ", "FACTS")
                    movie.facts.take(6).forEach { fact ->
                        Row(Modifier.padding(bottom = 8.dp)) {
                            Text("— ", style = AppText.bodySmall, color = Blue2)
                            Text(fact, style = AppText.bodySmall, color = Soft)
                        }
                    }
                }
            }
        }

        if (cast.isNotEmpty()) {
            item {
                SectionHead(
                    "В ГЛАВНЫХ РОЛЯХ",
                    "CAST",
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(cast, key = { it.name }) { member ->
                        CastCard(member) { onOpenPerson(member.name) }
                    }
                }
            }
        }

        if (similar.isNotEmpty()) {
            item {
                SectionHead(
                    "🎯 ПОХОЖЕЕ",
                    "SIMILAR",
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
            }
            item {
                LazyRow(
                    contentPadding = PaddingValues(horizontal = 16.dp),
                    horizontalArrangement = Arrangement.spacedBy(9.dp),
                ) {
                    items(similar, key = { it.id }) { item ->
                        RailCard(movie = item, onClick = { onOpenMovie(item.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun CastCard(member: CastMember, onClick: () -> Unit) {
    Column(
        Modifier
            .width(82.dp)
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier
                .size(66.dp)
                .clip(CircleShape)
                .background(Panel)
                .border(1.dp, Line, CircleShape)
                .then(Modifier),
        ) {
            RemoteImage(
                urls = Media.personPhoto(member.photo),
                contentDescription = member.name,
                modifier = Modifier.fillMaxSize().clip(CircleShape),
            )
        }
        Text(
            member.name,
            style = AppText.chip,
            color = White,
            maxLines = 2,
            minLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
        member.character?.takeIf { it.isNotBlank() }?.let {
            Text(
                it,
                style = AppText.meta.copy(fontSize = 8.5.sp),
                color = Muted,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun InfoChip(text: String, subtle: Boolean = false) {
    Box(
        Modifier
            .clip(RoundedCornerShape(100.dp))
            .background(if (subtle) Color.Transparent else Panel)
            .border(1.dp, if (subtle) Line.copy(alpha = 0.7f) else Line, RoundedCornerShape(100.dp))
            .padding(horizontal = 11.dp, vertical = 6.dp),
    ) {
        Text(
            text,
            style = AppText.chip,
            color = if (subtle) Muted else Color(0xFFC6CCD5),
        )
    }
}

@Composable
private fun RatingPill(label: String, value: String, tone: Double?) {
    val (content, stroke) = when {
        tone == null -> Muted to Line
        tone >= 7.5 -> Good to GoodLine
        tone >= 6.0 -> Mid to MidLine
        else -> Bad to BadLine
    }
    Row(
        Modifier
            .clip(RoundedCornerShape(8.dp))
            .border(1.dp, stroke, RoundedCornerShape(8.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(label, style = AppText.meta.copy(fontSize = 8.sp), color = Muted)
        Text(value, style = AppText.monoMedium, color = content)
    }
}

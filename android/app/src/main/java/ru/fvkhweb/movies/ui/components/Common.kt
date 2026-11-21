package ru.fvkhweb.movies.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import java.util.Locale
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.formatDateRu
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bad
import ru.fvkhweb.movies.ui.theme.Blue
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.Panel2
import ru.fvkhweb.movies.ui.theme.White

@Composable
fun RemoteImage(
    urls: List<String>,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    alignment: Alignment = Alignment.Center,
) {
    var index by remember(urls) { mutableIntStateOf(0) }
    Box(modifier.background(Panel2)) {
        if (urls.isNotEmpty()) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(urls[index.coerceIn(0, urls.lastIndex)])
                    .crossfade(160)
                    .build(),
                contentDescription = contentDescription,
                contentScale = contentScale,
                alignment = alignment,
                modifier = Modifier.fillMaxSize(),
                onError = {
                    if (index < urls.lastIndex) index += 1
                },
            )
        }
    }
}

/** Число колонок как на сайте: телефон — 2, планшет — 4, широкий экран — 5. */
@Composable
fun gridColumns(): Int {
    val width = LocalConfiguration.current.screenWidthDp
    return when {
        width < 600 -> 2
        width < 900 -> 4
        else -> 5
    }
}

@Composable
fun SectionHead(
    title: String,
    meta: String = "",
    modifier: Modifier = Modifier,
    metaStyle: TextStyle = AppText.meta,
    onClick: (() -> Unit)? = null,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .staggerReveal(index = 0, duration = 220, offsetY = 10)
            .padding(top = 26.dp, bottom = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Bottom,
    ) {
        Text(title, style = AppText.section, color = White)
        if (meta.isNotBlank()) {
            Text(meta, style = metaStyle, color = Muted)
        }
    }
}

/** Заметная плашка о том, что каталог сейчас обновляется или открыт из кэша. */
@Composable
fun SyncStatus(
    refreshing: Boolean,
    offline: Boolean,
    modifier: Modifier = Modifier,
) {
    AnimatedVisibility(
        visible = refreshing || offline,
        enter = fadeIn(animationSpec = tween(160)) + expandVertically(animationSpec = tween(180)),
        exit = fadeOut(animationSpec = tween(120)) + shrinkVertically(animationSpec = tween(140)),
        modifier = modifier,
    ) {
        val shape = RoundedCornerShape(8.dp)
        val accent = if (offline) Bad else Blue2
        Row(
            Modifier
                .fillMaxWidth()
                .clip(shape)
                .background(accent.copy(alpha = 0.09f))
                .border(1.dp, accent.copy(alpha = 0.3f), shape)
                .padding(horizontal = 10.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (refreshing) {
                CircularProgressIndicator(
                    color = Blue2,
                    strokeWidth = 1.5.dp,
                    modifier = Modifier.size(12.dp),
                )
            } else {
                Box(
                    Modifier
                        .size(6.dp)
                        .clip(CircleShape)
                        .background(Muted),
                )
            }
            Spacer(Modifier.width(8.dp))
            Text(
                text = if (offline) "ОФЛАЙН · ДАННЫЕ ИЗ КЭША" else "ОБНОВЛЕНИЕ КАТАЛОГА…",
                style = AppText.tag.copy(fontSize = 9.5.sp),
                color = accent,
            )
            Spacer(Modifier.weight(1f))
            if (refreshing) {
                Text(
                    "ПОДОЖДИТЕ",
                    style = AppText.meta.copy(fontSize = 8.sp),
                    color = Muted,
                )
            }
        }
    }
}

@Composable
fun RatingBadge(value: Double, modifier: Modifier = Modifier) {
    Box(
        modifier
            .clip(RoundedCornerShape(4.dp))
            .background(Color(0xCC090B0F))
            .border(1.dp, Color.White.copy(alpha = 0.14f), RoundedCornerShape(4.dp))
            .padding(horizontal = 5.dp, vertical = 3.dp),
    ) {
        Text(
            "★ " + String.format(Locale.US, "%.1f", value),
            style = AppText.mono.copy(fontSize = 9.5.sp),
            color = Color(0xFFDCE5FF),
        )
    }
}

@Composable
fun HeartButton(
    isFavorite: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Int = 28,
) {
    val pop = remember { Animatable(1f) }
    LaunchedEffect(isFavorite) {
        pop.animateTo(1.32f, spring(dampingRatio = 0.38f, stiffness = Spring.StiffnessMedium))
        pop.animateTo(1f, spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium))
    }
    val background by animateColorAsState(
        targetValue = if (isFavorite) Blue.copy(alpha = 0.24f) else Color(0xB8090B0F),
        animationSpec = tween(220),
        label = "heart-bg",
    )
    val borderColor by animateColorAsState(
        targetValue = if (isFavorite) Blue.copy(alpha = 0.6f) else Color.White.copy(alpha = 0.12f),
        animationSpec = tween(220),
        label = "heart-border",
    )
    Box(
        modifier
            .size(size.dp)
            .graphicsLayer {
                scaleX = pop.value
                scaleY = pop.value
            }
            .clip(CircleShape)
            .background(background)
            .border(1.dp, borderColor, CircleShape)
            .clickScale(scaleDown = 0.86f, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = if (isFavorite) Icons.Filled.Favorite else Icons.Filled.FavoriteBorder,
            contentDescription = if (isFavorite) "В избранном" else "В избранное",
            tint = if (isFavorite) Blue2 else White,
            modifier = Modifier.size((size * 0.52f).dp),
        )
    }
}

/** Плашка «Скоро в кино» на постере. */
@Composable
fun SoonBadge(modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .background(
                Brush.verticalGradient(
                    0f to Color.Transparent,
                    1f to Color(0xF5090B0F),
                ),
            )
            .padding(top = 12.dp)
            .padding(horizontal = 8.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.fillMaxWidth().height(1.dp).background(Color(0x997FA0FF)))
            Text(
                "СКОРО В КИНО",
                style = AppText.posterSoon,
                color = Color(0xFFE3EBFF),
                maxLines = 1,
                modifier = Modifier.padding(top = 7.dp),
            )
        }
    }
}

@Composable
fun MovieCard(
    movie: Movie,
    genreName: String,
    isFavorite: Boolean,
    onClick: () -> Unit,
    onToggleFavorite: () -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    revealIndex: Int = 0,
) {
    val soon = Movie.isSoonRelease(movie.releaseDate)
    Column(
        modifier = modifier
            .staggerReveal(index = revealIndex)
            .clickScale(scaleDown = 0.97f, onClick = onClick),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(2f / 3f)
                .clip(RoundedCornerShape(9.dp))
                .background(Panel)
                .border(1.dp, Color.White.copy(alpha = 0.05f), RoundedCornerShape(9.dp)),
        ) {
            RemoteImage(
                urls = Media.posterUrls(movie),
                contentDescription = movie.title,
                modifier = Modifier.fillMaxSize(),
            )
            Box(
                Modifier
                    .matchParentSize()
                    .background(
                        Brush.verticalGradient(
                            0.5f to Color.Transparent,
                            1f to Color.Black.copy(alpha = 0.35f),
                        ),
                    ),
            )
            movie.rating?.takeIf { it > 0 }?.let {
                RatingBadge(it, Modifier.align(Alignment.TopStart).padding(6.dp))
            }
            HeartButton(
                isFavorite = isFavorite,
                onClick = onToggleFavorite,
                modifier = Modifier.align(Alignment.TopEnd).padding(6.dp),
                size = 27,
            )
            if (soon && subtitle == null) {
                SoonBadge(Modifier.align(Alignment.BottomCenter))
            }
        }
        Text(
            text = movie.title.ifBlank { "Без названия" },
            style = AppText.cardTitle,
            color = White,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 7.dp),
        )
        val sub = subtitle ?: if (soon && !movie.releaseDate.isNullOrBlank()) {
            "В КИНО " + formatDateRu(movie.releaseDate).uppercase()
        } else {
            listOfNotNull(
                movie.year?.takeIf { it.isNotBlank() },
                genreName.uppercase().takeIf { it.isNotBlank() },
            ).joinToString("\u00A0·\u00A0")
        }
        if (sub.isNotBlank()) {
            Text(
                text = sub,
                style = AppText.meta,
                color = Muted,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
    }
}

@Composable
fun RailCard(
    movie: Movie,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    subtitle: String? = null,
    revealIndex: Int = 0,
) {
    Column(
        modifier = modifier
            .width(140.dp)
            .staggerReveal(index = revealIndex)
            .clickScale(scaleDown = 0.96f, onClick = onClick),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(2f / 3f)
                .clip(RoundedCornerShape(9.dp))
                .background(Panel)
                .border(1.dp, Color.White.copy(alpha = 0.05f), RoundedCornerShape(9.dp)),
        ) {
            RemoteImage(
                urls = Media.posterUrls(movie),
                contentDescription = movie.title,
                modifier = Modifier.fillMaxSize(),
            )
            Box(
                Modifier
                    .matchParentSize()
                    .background(
                        Brush.verticalGradient(
                            0.5f to Color.Transparent,
                            1f to Color.Black.copy(alpha = 0.35f),
                        ),
                    ),
            )
            if (Movie.isSoonRelease(movie.releaseDate) && subtitle == null) {
                SoonBadge(Modifier.align(Alignment.BottomCenter))
            }
        }
        Text(
            text = movie.title.ifBlank { "Без названия" },
            style = AppText.cardTitle,
            color = White,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 7.dp),
        )
        val sub = subtitle ?: when {
            (movie.rating ?: 0.0) > 0 -> "★ " + String.format(Locale.US, "%.1f", movie.rating)
            else -> movie.year.orEmpty()
        }
        if (sub.isNotBlank()) {
            Text(
                text = sub,
                style = AppText.meta,
                color = Muted,
                maxLines = 1,
                modifier = Modifier.padding(top = 3.dp),
            )
        }
    }
}

@Composable
fun Chip(
    text: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val shape = RoundedCornerShape(100.dp)
    val background by animateColorAsState(
        targetValue = if (selected) Blue.copy(alpha = 0.18f) else Color.Transparent,
        animationSpec = tween(180),
        label = "chip-bg",
    )
    val stroke by animateColorAsState(
        targetValue = if (selected) Blue else Line,
        animationSpec = tween(180),
        label = "chip-stroke",
    )
    val contentColor by animateColorAsState(
        targetValue = if (selected) Color(0xFFDBE6FF) else Color(0xFF9CA6B5),
        animationSpec = tween(180),
        label = "chip-text",
    )
    val scale by animateFloatAsState(
        targetValue = if (selected) 1.04f else 1f,
        animationSpec = spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium),
        label = "chip-scale",
    )
    Box(
        modifier
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .clip(shape)
            .background(background)
            .border(1.dp, stroke, shape)
            .clickScale(scaleDown = 0.93f, onClick = onClick)
            .padding(horizontal = 13.dp, vertical = 8.dp),
    ) {
        Text(
            text,
            style = AppText.chip,
            color = contentColor,
        )
    }
}

@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    suffix: String? = null,
) {
    Row(
        modifier
            .height(40.dp)
            .clip(RoundedCornerShape(9.dp))
            .background(Blue)
            .clickScale(scaleDown = 0.95f, onClick = onClick)
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, style = AppText.button, color = Color.White)
        if (suffix != null) {
            Spacer(Modifier.width(6.dp))
            Text(suffix, style = AppText.button, color = Color.White)
        }
    }
}

@Composable
fun SecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = false,
) {
    val background by animateColorAsState(
        targetValue = if (active) Blue.copy(alpha = 0.16f) else Color.Transparent,
        animationSpec = tween(180),
        label = "secondary-bg",
    )
    val stroke by animateColorAsState(
        targetValue = if (active) Blue else Line,
        animationSpec = tween(180),
        label = "secondary-stroke",
    )
    val contentColor by animateColorAsState(
        targetValue = if (active) Color(0xFFDBE6FF) else Color(0xFFC6CCD5),
        animationSpec = tween(180),
        label = "secondary-text",
    )
    Row(
        modifier
            .height(40.dp)
            .clip(RoundedCornerShape(9.dp))
            .background(background)
            .border(1.dp, stroke, RoundedCornerShape(9.dp))
            .clickScale(scaleDown = 0.95f, onClick = onClick)
            .padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text,
            style = AppText.button,
            color = contentColor,
        )
    }
}

@Composable
fun CircleButton(
    glyph: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Int = 38,
) {
    Box(
        modifier
            .size(size.dp)
            .clip(CircleShape)
            .background(Color(0xCC090B0F))
            .border(1.dp, Line, CircleShape)
            .clickScale(scaleDown = 0.9f, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(glyph, color = White, style = AppText.body.copy(fontSize = (size * 0.42f).sp))
    }
}

@Composable
fun EmptyState(text: String, modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .padding(vertical = 40.dp, horizontal = 16.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = AppText.bodySmall, color = Muted)
    }
}

@Composable
fun LoadingState(text: String = "Обновление каталога…", modifier: Modifier = Modifier) {
    val pulse = rememberInfiniteTransition(label = "loading-pulse")
    val scale by pulse.animateFloat(
        initialValue = 0.92f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "loading-scale",
    )
    val textAlpha by pulse.animateFloat(
        initialValue = 0.45f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 900),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "loading-text-alpha",
    )
    Column(
        modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(
            color = Blue,
            strokeWidth = 2.dp,
            modifier = Modifier
                .size(30.dp)
                .graphicsLayer {
                    scaleX = scale
                    scaleY = scale
                },
        )
        Spacer(Modifier.height(16.dp))
        Text(text, style = AppText.bodySmall, color = Muted.copy(alpha = textAlpha))
    }
}

@Composable
fun ErrorState(message: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(message, style = AppText.body, color = Color(0xFFC6CCD5))
        Spacer(Modifier.height(16.dp))
        PrimaryButton("Повторить", onRetry)
    }
}

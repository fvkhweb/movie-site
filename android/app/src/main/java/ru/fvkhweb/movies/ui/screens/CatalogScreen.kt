package ru.fvkhweb.movies.ui.screens

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.data.model.Genre
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.ui.CountryOption
import ru.fvkhweb.movies.ui.FilterState
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.SortType
import ru.fvkhweb.movies.ui.buildCountryOptions
import ru.fvkhweb.movies.ui.components.Chip
import ru.fvkhweb.movies.ui.components.EmptyState
import ru.fvkhweb.movies.ui.components.MovieCard
import ru.fvkhweb.movies.ui.components.PrimaryButton
import ru.fvkhweb.movies.ui.components.SecondaryButton
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CatalogScreen(
    viewModel: MainViewModel,
    onOpenMovie: (Long) -> Unit,
) {
    val state by viewModel.catalog.collectAsState()
    val filters by viewModel.filters.collectAsState()
    val filtered by viewModel.filtered.collectAsState()
    val favorites by viewModel.favorites.collectAsState()

    var showSort by remember { mutableStateOf(false) }
    var showFilters by remember { mutableStateOf(false) }
    var showCountries by remember { mutableStateOf(false) }
    var countryQuery by remember { mutableStateOf("") }

    val countryOptions = remember(state.movies) {
        val counts = HashMap<String, Int>()
        state.movies.forEach { movie ->
            movie.countries.forEach { name -> counts[name] = (counts[name] ?: 0) + 1 }
        }
        buildCountryOptions(counts)
    }

    var limit by remember(filters) { mutableIntStateOf(30) }
    val visible = remember(filtered, limit) { filtered.take(limit) }
    val gridState = rememberLazyGridState()

    LaunchedEffect(gridState, filtered.size, limit) {
        snapshotFlow { gridState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0 }
            .collect { last ->
                if (visible.size < filtered.size && last >= visible.size - 6) {
                    limit = (limit + 30).coerceAtMost(filtered.size)
                }
            }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Bg)
            .statusBarsPadding(),
    ) {
        Column(Modifier.padding(horizontal = 16.dp).staggerReveal(index = 0, duration = 220)) {
            Row(
                Modifier.fillMaxWidth().padding(top = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text("КАТАЛОГ", style = AppText.h2, color = White)
                    Text(
                        "CATALOG / ${filtered.size} ${filmsWord(filtered.size)}",
                        style = AppText.meta,
                        color = Muted,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                Spacer(Modifier.weight(1f))
                SecondaryButton("↻", viewModel::refresh)
            }

            SyncStatus(
                refreshing = state.refreshing,
                offline = state.offline,
                modifier = Modifier.padding(top = 10.dp),
            )

            SearchField(
                value = filters.query,
                onValueChange = viewModel::setQuery,
                modifier = Modifier.padding(top = 14.dp),
            )

            Row(
                Modifier.fillMaxWidth().padding(top = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SecondaryButton(
                    text = filters.sort.label,
                    onClick = { showSort = true },
                    modifier = Modifier.weight(1f),
                )
                SecondaryButton(
                    text = if (filters.activeFilters > 0) "Фильтры · ${filters.activeFilters}" else "Фильтры",
                    onClick = { showFilters = true },
                    modifier = Modifier.weight(1f),
                    active = filters.activeFilters > 0,
                )
                SecondaryButton(
                    text = "🎲",
                    onClick = { viewModel.randomMovie()?.let { onOpenMovie(it.id) } },
                    modifier = Modifier.width(48.dp),
                )
            }

            Row(
                Modifier.fillMaxWidth().padding(top = 8.dp),
            ) {
                SecondaryButton(
                    text = if (filters.countryCount > 0) "Страны · ${filters.countryCount}" else "Страны",
                    onClick = { showCountries = true },
                    modifier = Modifier.weight(1f),
                    active = filters.countryCount > 0,
                )
            }

            if (filters.genre != null || filters.actor != null) {
                Row(
                    Modifier.fillMaxWidth().padding(top = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    filters.genre?.let { id ->
                        Chip(
                            text = state.genreName(id) + "  ✕",
                            selected = true,
                            onClick = { viewModel.setGenre(null) },
                        )
                    }
                    filters.actor?.let { name ->
                        Chip(
                            text = name + "  ✕",
                            selected = true,
                            onClick = { viewModel.setActor(null) },
                        )
                    }
                }
            }
        }

        LazyVerticalGrid(
            columns = GridCells.Fixed(gridColumns()),
            state = gridState,
            modifier = Modifier.fillMaxWidth().weight(1f),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 26.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            if (filtered.isEmpty()) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    EmptyState(
                        if (state.loading) "Загружаем каталог…"
                        else "Ничего не найдено. Попробуй изменить запрос или фильтр.",
                    )
                }
            }

            itemsIndexed(visible, key = { _, movie -> movie.id }) { index, movie: Movie ->
                MovieCard(
                    movie = movie,
                    genreName = state.genreName(movie.genres.firstOrNull() ?: 0),
                    isFavorite = movie.id in favorites,
                    onClick = { onOpenMovie(movie.id) },
                    onToggleFavorite = { viewModel.toggleFavorite(movie.id) },
                    revealIndex = index % 10,
                )
            }

            if (visible.size < filtered.size) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Box(
                        Modifier.fillMaxWidth().padding(top = 6.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        SecondaryButton("Показать ещё", {
                            limit = (limit + 30).coerceAtMost(filtered.size)
                        })
                    }
                }
            }
        }
    }

    if (showSort) {
        ModalBottomSheet(
            onDismissRequest = { showSort = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Panel,
        ) {
            Column(Modifier.fillMaxWidth().padding(bottom = 24.dp).navigationBarsPadding()) {
                Text(
                    "СОРТИРОВКА",
                    style = AppText.h2.copy(fontSize = 15.sp),
                    color = White,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                )
                SortType.entries.forEach { type ->
                    Row(
                        Modifier
                            .fillMaxWidth()
                            .clickable {
                                viewModel.setSort(type)
                                showSort = false
                            }
                            .padding(horizontal = 20.dp, vertical = 13.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            type.label,
                            style = AppText.body,
                            color = if (type == filters.sort) White else Muted,
                            modifier = Modifier.weight(1f),
                        )
                        if (type == filters.sort) {
                            Text("✓", style = AppText.body, color = Blue2)
                        }
                    }
                }
            }
        }
    }

    if (showFilters) {
        ModalBottomSheet(
            onDismissRequest = { showFilters = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Panel,
        ) {
            FilterPanel(
                genres = state.genres,
                filters = filters,
                onGenre = viewModel::setGenre,
                onExcludeGenre = viewModel::setExcludeGenre,
                onRating = viewModel::setRatingMin,
                onYears = viewModel::setYears,
                onReset = viewModel::resetFilters,
                onDone = { showFilters = false },
                yearRange = remember(state.movies) {
                    val years = state.movies.mapNotNull { it.year?.toIntOrNull() }
                    if (years.isEmpty()) 1900..2030 else years.min()..years.max()
                },
            )
        }
    }

    if (showCountries) {
        ModalBottomSheet(
            onDismissRequest = { showCountries = false },
            sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
            containerColor = Panel,
        ) {
            CountryPanel(
                options = countryOptions,
                query = countryQuery,
                onQueryChange = { countryQuery = it },
                include = filters.countryInclude,
                exclude = filters.countryExclude,
                onCycle = viewModel::cycleCountry,
                onClear = viewModel::clearCountries,
                onDone = { showCountries = false },
            )
        }
    }
}

@Composable
private fun CountryPanel(
    options: List<CountryOption>,
    query: String,
    onQueryChange: (String) -> Unit,
    include: Set<String>,
    exclude: Set<String>,
    onCycle: (String) -> Unit,
    onClear: () -> Unit,
    onDone: () -> Unit,
) {
    val lower = query.trim().lowercase()
    val list = remember(options, lower) {
        if (lower.isEmpty()) options
        else options.filter {
            it.label.lowercase().contains(lower) || it.name.lowercase().contains(lower)
        }
    }
    val total = include.size + exclude.size
    val summary = buildList {
        if (include.isNotEmpty()) add("показывать: ${include.size}")
        if (exclude.isNotEmpty()) add("исключить: ${exclude.size}")
    }.joinToString(" · ").ifEmpty { "Страны не выбраны" }

    Column(
        Modifier
            .fillMaxWidth()
            .navigationBarsPadding()
            .padding(bottom = 18.dp),
    ) {
        Column(Modifier.padding(horizontal = 20.dp)) {
            Text("СТРАНЫ", style = AppText.h2.copy(fontSize = 15.sp), color = White)
            Text(
                summary,
                style = AppText.countryFoot,
                color = if (total > 0) White else Muted,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        SearchField(
            value = query,
            onValueChange = onQueryChange,
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 10.dp),
            placeholder = "Найти страну…",
        )

        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier.fillMaxWidth().heightIn(max = 330.dp),
            contentPadding = PaddingValues(horizontal = 20.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            if (list.isEmpty()) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    Box(
                        Modifier.fillMaxWidth().padding(vertical = 26.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("Ничего не найдено", style = AppText.countryFoot, color = Muted)
                    }
                }
            }
            items(list, key = { it.name }) { option ->
                CountryOptionRow(
                    option = option,
                    mode = when {
                        option.name in include -> 1
                        option.name in exclude -> 2
                        else -> 0
                    },
                    onClick = { onCycle(option.name) },
                )
            }
        }

        Row(
            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SecondaryButton("Сбросить страны", onClear, Modifier.weight(1f))
            PrimaryButton("Готово", onDone, Modifier.weight(1f))
        }
        Text(
            "Клик — включить · ещё раз — исключить · третий — снять",
            style = AppText.countryFoot,
            color = Color(0xFF667080),
            modifier = Modifier.padding(horizontal = 20.dp),
        )
    }
}

@Composable
private fun CountryOptionRow(
    option: CountryOption,
    mode: Int,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(7.dp)
    val included = mode == 1
    val excluded = mode == 2
    val background by animateColorAsState(
        targetValue = when {
            included -> Color(0x293268FF)
            excluded -> Color(0x148D3B3B)
            else -> Color.Transparent
        },
        animationSpec = tween(160),
        label = "country-bg",
    )
    val stroke by animateColorAsState(
        targetValue = when {
            included -> Color(0x663268FF)
            excluded -> Color(0x558D3B3B)
            else -> Color.Transparent
        },
        animationSpec = tween(160),
        label = "country-stroke",
    )
    Row(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(background)
            .border(1.dp, stroke, shape)
            .clickScale(scaleDown = 0.97f, onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            option.label,
            style = AppText.countryOption,
            color = when {
                included -> White
                excluded -> Color(0xFFFF9D9D)
                else -> Color(0xFFC6CCD5)
            },
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            textDecoration = if (excluded) TextDecoration.LineThrough else null,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = when {
                included -> "+"
                excluded -> "−"
                else -> ""
            },
            style = AppText.countryOption.copy(fontWeight = FontWeight.W700),
            color = when {
                included -> Color(0xFF7FA0FF)
                excluded -> Color(0xFFFF9D9D)
                else -> Color(0xFF5B6675)
            },
        )
    }
}

@Composable
private fun SearchField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    placeholder: String = "Название фильма или актёр…",
) {
    val shape = RoundedCornerShape(9.dp)
    var focused by remember { mutableStateOf(false) }
    val stroke by animateColorAsState(
        targetValue = if (focused) Blue2.copy(alpha = 0.8f) else Line,
        animationSpec = tween(180),
        label = "search-stroke",
    )
    BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = true,
        textStyle = AppText.body.copy(color = White),
        cursorBrush = SolidColor(Blue2),
        modifier = modifier
            .fillMaxWidth()
            .height(48.dp)
            .onFocusChanged { focused = it.isFocused },
        decorationBox = { inner ->
            Row(
                Modifier
                    .fillMaxSize()
                    .clip(shape)
                    .background(Color(0xFF10141B))
                    .border(1.dp, stroke, shape)
                    .padding(horizontal = 14.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Filled.Search, contentDescription = null, tint = Muted, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(10.dp))
                Box(Modifier.weight(1f)) {
                    if (value.isEmpty()) {
                        Text(placeholder, style = AppText.body, color = Color(0xFF667080))
                    }
                    inner()
                }
                if (value.isNotEmpty()) {
                    Text(
                        "✕",
                        style = AppText.body,
                        color = Muted,
                        modifier = Modifier
                            .clickScale(scaleDown = 0.85f) { onValueChange("") }
                            .padding(6.dp),
                    )
                }
            }
        },
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun FilterPanel(
    genres: List<Genre>,
    filters: FilterState,
    onGenre: (Int?) -> Unit,
    onExcludeGenre: (Int?) -> Unit,
    onRating: (Int?) -> Unit,
    onYears: (Int?, Int?) -> Unit,
    onReset: () -> Unit,
    onDone: () -> Unit,
    yearRange: IntRange,
) {
    val yearsDesc = remember(yearRange) { yearRange.reversed().toList() }

    Column(
        Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            .navigationBarsPadding()
            .padding(bottom = 24.dp),
    ) {
        Text("ФИЛЬТРЫ", style = AppText.h2.copy(fontSize = 15.sp), color = White)

        Text("ЖАНР", style = AppText.monoWide, color = Muted, modifier = Modifier.padding(top = 18.dp, bottom = 8.dp))
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(7.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Chip("Все фильмы", filters.genre == null, onClick = { onGenre(null) })
            genres.forEach { genre ->
                Chip(
                    text = genre.name.replaceFirstChar { it.uppercase() },
                    selected = filters.genre == genre.id,
                    onClick = { onGenre(if (filters.genre == genre.id) null else genre.id) },
                )
            }
        }

        Text("РЕЙТИНГ", style = AppText.monoWide, color = Muted, modifier = Modifier.padding(top = 18.dp, bottom = 8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            Chip("Любой", filters.ratingMin == null, onClick = { onRating(null) })
            listOf(9, 8, 7, 6, 5).forEach { value ->
                Chip("★ $value+", filters.ratingMin == value, onClick = {
                    onRating(if (filters.ratingMin == value) null else value)
                })
            }
        }

        Row(
            Modifier.fillMaxWidth().padding(top = 18.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SelectField(
                label = "Год от",
                value = filters.yearFrom?.toString() ?: "Любой",
                options = yearsDesc.map { (it as Int?) to it.toString() },
                onSelect = { onYears(it, filters.yearTo) },
                modifier = Modifier.weight(1f),
            )
            SelectField(
                label = "Год до",
                value = filters.yearTo?.toString() ?: "Любой",
                options = yearsDesc.map { (it as Int?) to it.toString() },
                onSelect = { onYears(filters.yearFrom, it) },
                modifier = Modifier.weight(1f),
            )
        }

        Box(Modifier.fillMaxWidth().padding(top = 10.dp)) {
            SelectField(
                label = "Исключить жанр",
                value = filters.excludeGenre?.let { id ->
                    genres.firstOrNull { it.id == id }?.name?.replaceFirstChar { it.uppercase() }
                } ?: "Не исключать",
                options = listOf<Pair<Int?, String>>(null to "Не исключать") +
                    genres.map { (it.id as Int?) to it.name.replaceFirstChar { c -> c.uppercase() } },
                onSelect = onExcludeGenre,
                modifier = Modifier.fillMaxWidth(),
            )
        }

        Row(
            Modifier.fillMaxWidth().padding(top = 20.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            SecondaryButton("Сбросить", onReset, Modifier.weight(1f))
            PrimaryButton("Готово", onDone, Modifier.weight(1f))
        }
    }
}

@Composable
private fun <T> SelectField(
    label: String,
    value: String,
    options: List<Pair<T?, String>>,
    onSelect: (T?) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val shape = RoundedCornerShape(9.dp)

    Box(modifier) {
        Row(
            Modifier
                .fillMaxWidth()
                .height(46.dp)
                .clip(shape)
                .background(Color(0xFF10141B))
                .border(1.dp, Line, shape)
                .clickable { expanded = true }
                .padding(horizontal = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(label, style = AppText.meta.copy(fontSize = 8.5.sp), color = Muted)
                Text(
                    value,
                    style = AppText.bodySmall,
                    color = Color(0xFFC6CCD5),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text("⌄", style = AppText.body, color = Muted)
        }
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.widthIn(min = 180.dp, max = 280.dp),
        ) {
            options.forEach { (option, text) ->
                DropdownMenuItem(
                    text = { Text(text, style = AppText.bodySmall, color = White) },
                    onClick = {
                        onSelect(option)
                        expanded = false
                    },
                )
            }
        }
    }
}

package ru.fvkhweb.movies.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import java.text.Collator
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.fvkhweb.movies.AppContainer
import ru.fvkhweb.movies.data.CatalogRepository
import ru.fvkhweb.movies.data.CatalogState
import ru.fvkhweb.movies.data.FavoritesStore
import ru.fvkhweb.movies.data.model.Movie

enum class SortType(val label: String) {
    POPULARITY("Сначала популярные"),
    RATING("По рейтингу"),
    KP_RATING("Рейтинг Кинопоиска"),
    YEAR_DESC("Сначала новые"),
    YEAR_ASC("Сначала старые"),
    TITLE("По названию"),
    RUNTIME("По длительности"),
}

data class FilterState(
    val query: String = "",
    val genre: Int? = null,
    val excludeGenre: Int? = null,
    val yearFrom: Int? = null,
    val yearTo: Int? = null,
    val ratingMin: Int? = null,
    val sort: SortType = SortType.POPULARITY,
    val actor: String? = null,
    val countryInclude: Set<String> = emptySet(),
    val countryExclude: Set<String> = emptySet(),
) {
    val activeFilters: Int
        get() = listOfNotNull(genre, excludeGenre, yearFrom, yearTo, ratingMin).size

    val countryCount: Int
        get() = countryInclude.size + countryExclude.size
}

class MainViewModel(
    private val repository: CatalogRepository,
    private val favoritesStore: FavoritesStore,
) : ViewModel() {

    val catalog: StateFlow<CatalogState> = repository.state

    val favorites: StateFlow<Set<Long>> = favoritesStore.ids.stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        emptySet(),
    )

    private val _filters = MutableStateFlow(FilterState())
    val filters: StateFlow<FilterState> = _filters.asStateFlow()

    val filtered: StateFlow<List<Movie>> =
        combine(repository.state, _filters) { state, filters -> applyFilters(state, filters) }
            .flowOn(Dispatchers.Default)
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        viewModelScope.launch { repository.start() }
    }

    fun refresh() {
        viewModelScope.launch { repository.refresh() }
    }

    fun toggleFavorite(id: Long) {
        viewModelScope.launch { favoritesStore.toggle(id) }
    }

    fun setQuery(value: String) {
        _filters.update { it.copy(query = value, actor = null) }
    }

    fun setGenre(id: Int?) {
        _filters.update { it.copy(genre = id, actor = null) }
    }

    fun setExcludeGenre(id: Int?) {
        _filters.update { it.copy(excludeGenre = id) }
    }

    fun setYears(from: Int?, to: Int?) {
        _filters.update { it.copy(yearFrom = from, yearTo = to) }
    }

    fun setRatingMin(value: Int?) {
        _filters.update { it.copy(ratingMin = value) }
    }

    fun setSort(value: SortType) {
        _filters.update { it.copy(sort = value) }
    }

    fun setActor(name: String?) {
        _filters.update { it.copy(actor = name, query = "") }
    }

    fun cycleCountry(country: String) {
        _filters.update { current ->
            val include = current.countryInclude.toMutableSet()
            val exclude = current.countryExclude.toMutableSet()
            when {
                country in include -> { include.remove(country); exclude.add(country) }
                country in exclude -> { exclude.remove(country) }
                else -> include.add(country)
            }
            current.copy(countryInclude = include, countryExclude = exclude)
        }
    }

    fun clearCountries() {
        _filters.update { it.copy(countryInclude = emptySet(), countryExclude = emptySet()) }
    }

    fun resetFilters() {
        _filters.update { FilterState(query = it.query, sort = it.sort) }
    }

    fun randomMovie(): Movie? = applyFilters(repository.state.value, _filters.value).randomOrNull()

    companion object {
        fun factory(container: AppContainer): ViewModelProvider.Factory = viewModelFactory {
            initializer { MainViewModel(container.repository, container.favorites) }
        }

        private val ruCollator: Collator = Collator.getInstance(Locale("ru", "RU"))

        fun applyFilters(state: CatalogState, filters: FilterState): List<Movie> {
            if (state.movies.isEmpty()) return emptyList()

            val query = filters.query.trim()
            val lower = query.lowercase(Locale.getDefault())

            var actorIds: Set<Long>? = null
            if (!filters.actor.isNullOrBlank()) {
                actorIds = state.personByName(filters.actor)?.movies?.toSet() ?: emptySet()
            } else if (query.isNotEmpty() && state.people.isNotEmpty()) {
                actorIds = state.people.asSequence()
                    .filter { it.name.contains(lower, ignoreCase = true) }
                    .flatMap { it.movies.asSequence() }
                    .toSet()
            }

            val isActorFilter = !filters.actor.isNullOrBlank()

            val result = state.movies.filter { movie ->
                if (isActorFilter && actorIds?.contains(movie.id) != true) return@filter false

                // Дальние премьеры не мешают каталогу: они живут в блоке «Скоро в кино».
                // Исключение — явный поиск по названию: человек ищет конкретный фильм.
                if (query.isEmpty() && Movie.isFarUpcoming(movie.releaseDate)) return@filter false

                if (filters.excludeGenre != null && movie.genres.contains(filters.excludeGenre)) return@filter false
                if (filters.genre != null && !movie.genres.contains(filters.genre)) return@filter false

                val year = movie.year?.toIntOrNull()
                if (filters.yearFrom != null && (year == null || year < filters.yearFrom)) return@filter false
                if (filters.yearTo != null && (year == null || year > filters.yearTo)) return@filter false
                if (filters.ratingMin != null && (movie.rating ?: 0.0) < filters.ratingMin) return@filter false

                if (query.isNotEmpty()) {
                    val inTitle = movie.title.contains(lower, ignoreCase = true) ||
                        movie.originalTitle?.contains(lower, ignoreCase = true) == true
                    val inActor = actorIds?.contains(movie.id) == true
                    if (!inTitle && !inActor) return@filter false
                }

                // Country filter
                if (filters.countryInclude.isNotEmpty()) {
                    val movieCountries = movie.countries ?: emptyList()
                    if (movieCountries.none { it in filters.countryInclude }) return@filter false
                }
                if (filters.countryExclude.isNotEmpty()) {
                    val movieCountries = movie.countries ?: emptyList()
                    if (movieCountries.any { it in filters.countryExclude }) return@filter false
                }

                true
            }

            return when (filters.sort) {
                SortType.POPULARITY -> result.sortedWith(compareByDescending { it.popularity ?: 0.0 })
                SortType.RATING -> result.sortedWith(compareByDescending { it.rating ?: 0.0 })
                SortType.KP_RATING -> result.sortedWith(compareByDescending { it.kpRating ?: 0.0 })
                SortType.YEAR_DESC -> result.sortedWith(
                    compareByDescending<Movie> { it.releaseKey }.thenByDescending { it.year.orEmpty() },
                )
                SortType.YEAR_ASC -> result.sortedWith(
                    compareBy<Movie> { it.releaseKey }.thenBy { it.year.orEmpty() },
                )
                SortType.TITLE -> result.sortedWith { a, b -> ruCollator.compare(a.title, b.title) }
                SortType.RUNTIME -> result.sortedWith(compareByDescending { it.runtime ?: 0 })
            }
        }
    }
}

package ru.fvkhweb.movies.data

import ru.fvkhweb.movies.data.model.CastMember
import ru.fvkhweb.movies.data.model.Genre
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.data.model.MovieCollection
import ru.fvkhweb.movies.data.model.MovieLists
import ru.fvkhweb.movies.data.model.Person

data class CatalogState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val offline: Boolean = false,
    val error: String? = null,
    val movies: List<Movie> = emptyList(),
    val genres: List<Genre> = emptyList(),
    val lists: MovieLists = MovieLists(),
    val cast: Map<String, List<CastMember>> = emptyMap(),
    val people: List<Person> = emptyList(),
    val collections: List<MovieCollection> = emptyList(),
    val updatedAt: Long = 0L,
) {
    // Индексы строятся один раз на объект, а не на каждый copy()
    val moviesById: Map<Long, Movie> by lazy { movies.associateBy { it.id } }
    val genresById: Map<Int, Genre> by lazy { genres.associateBy { it.id } }
    private val peopleByName: Map<String, Person> by lazy {
        people.associateBy { it.name.lowercase() }
    }

    fun genreName(id: Int): String = genresById[id]?.name?.replaceFirstChar { it.uppercase() } ?: ""

    fun castOf(movieId: Long): List<CastMember> = cast[movieId.toString()].orEmpty()

    fun personByName(name: String): Person? = peopleByName[name.lowercase()]

    val hasData: Boolean get() = movies.isNotEmpty()
}

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
    val moviesById: Map<Long, Movie> = movies.associateBy { it.id }
    val genresById: Map<Int, Genre> = genres.associateBy { it.id }

    fun genreName(id: Int): String = genresById[id]?.name?.replaceFirstChar { it.uppercase() } ?: ""

    fun castOf(movieId: Long): List<CastMember> = cast[movieId.toString()].orEmpty()

    fun personByName(name: String): Person? =
        people.firstOrNull { it.name.equals(name, ignoreCase = true) }

    val hasData: Boolean get() = movies.isNotEmpty()
}

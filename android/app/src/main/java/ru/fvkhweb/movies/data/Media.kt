package ru.fvkhweb.movies.data

import ru.fvkhweb.movies.data.model.Movie

/**
 * Адреса картинок. Постеры лежат на домене сайта, кадры и фото актёров —
 * в TMDB, который из РФ может быть недоступен, поэтому идём через зеркала.
 */
object Media {
    const val BASE = "https://fvkhweb.github.io/movie-site/"

    private const val PROXY_1 = "https://wsrv.nl/?url="
    private const val PROXY_2 = "https://images.weserv.nl/?url="

    private fun absolute(path: String?): String? = when {
        path.isNullOrBlank() -> null
        path.startsWith("http://") || path.startsWith("https://") -> path
        else -> BASE + path.removePrefix("/")
    }

    fun posterUrls(movie: Movie): List<String> = buildList {
        absolute(movie.poster)?.let(::add)
        movie.posterFallback?.takeIf { it.isNotBlank() }?.let(::add)
    }

    fun heroUrls(movie: Movie): List<String> = buildList {
        movie.frame?.takeIf { it.isNotBlank() }?.let { frame ->
            add(frame.replace(Regex("/orig$"), "/960x540"))
            add(frame)
        }
        movie.backdrop?.takeIf { it.isNotBlank() }?.let { addAll(tmdb(it, "w1280")) }
        addAll(posterUrls(movie))
    }

    fun personPhoto(path: String?): List<String> {
        if (path.isNullOrBlank()) return emptyList()
        return tmdb(path, "w185")
    }

    private fun tmdb(path: String, size: String): List<String> {
        val hostPath = "image.tmdb.org/t/p/$size$path"
        return listOf(
            PROXY_1 + hostPath,
            PROXY_2 + hostPath,
            "https://imagetmdb.com/t/p/$size$path",
            "https://cdn.statically.io/img/$hostPath",
            "https://$hostPath",
        )
    }
}

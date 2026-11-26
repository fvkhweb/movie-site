package ru.fvkhweb.movies.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class Movie(
    val id: Long,
    val title: String = "",
    @SerialName("original_title") val originalTitle: String? = null,
    val year: String? = null,
    @SerialName("release_date") val releaseDate: String? = null,
    val director: String? = null,
    val rating: Double? = null,
    val popularity: Double? = null,
    val runtime: Int? = null,
    val genres: List<Int> = emptyList(),
    val countries: List<String> = emptyList(),
    val backdrop: String? = null,
    val description: String? = null,
    @SerialName("description_en") val descriptionEn: String? = null,
    val similar: List<Long> = emptyList(),
    val series: MovieSeries? = null,
    val trailer: String? = null,
    @SerialName("kp_rating") val kpRating: Double? = null,
    val frame: String? = null,
    val poster: String? = null,
    @SerialName("poster_fallback") val posterFallback: String? = null,
    val facts: List<String> = emptyList(),
    val cast: List<CastMember> = emptyList(),
    // "kp" — карточка из Кинопоиска: живёт только в каталоге,
    // на главную (рейтинги TMDB) не попадает.
    val source: String? = null,
) {
    val descriptionText: String
        get() = description?.takeIf { it.isNotBlank() } ?: descriptionEn.orEmpty()

    val releaseKey: String
        get() = releaseDate?.take(10) ?: year?.let { "$it-01-01" } ?: ""

    companion object {
        private const val SOON_DAYS = 7
        private const val DAY_MS = 86400000L

        fun daysUntilRelease(releaseDate: String?): Int? {
            releaseDate?.takeIf { it.isNotBlank() }?.take(10)?.let { dateStr ->
                try {
                    val parts = dateStr.split("-")
                    if (parts.size == 3) {
                        val year = parts[0].toInt()
                        val month = parts[1].toInt()
                        val day = parts[2].toInt()
                        val releaseMs = java.time.LocalDate.of(year, month, day).atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
                        val todayMs = java.time.LocalDate.now(java.time.ZoneOffset.UTC).atStartOfDay(java.time.ZoneOffset.UTC).toInstant().toEpochMilli()
                        return ((releaseMs - todayMs) / DAY_MS).toInt()
                    }
                } catch (e: Exception) {
                    // ignore
                }
            }
            return null
        }

        fun isUnreleased(releaseDate: String?): Boolean {
            val days = daysUntilRelease(releaseDate)
            return days != null && days > 0
        }

        fun isSoonRelease(releaseDate: String?): Boolean {
            val days = daysUntilRelease(releaseDate)
            return days != null && days > 0 && days <= SOON_DAYS
        }

        fun isFarUpcoming(releaseDate: String?): Boolean {
            val days = daysUntilRelease(releaseDate)
            return days != null && days > SOON_DAYS
        }
    }
}

@Serializable
data class MovieSeries(
    val id: Int = 0,
    val name: String = "",
)

@Serializable
data class Genre(
    val id: Int,
    val name: String = "",
)

@Serializable
data class MovieLists(
    val popular: List<Long> = emptyList(),
    @SerialName("top_rated") val topRated: List<Long> = emptyList(),
    @SerialName("by_genre") val byGenre: Map<String, List<Long>> = emptyMap(),
    @SerialName("now_playing") val nowPlaying: List<Long> = emptyList(),
    val upcoming: List<Long> = emptyList(),
)

@Serializable
data class CastMember(
    val id: Long? = null,
    val name: String = "",
    val character: String? = null,
    val photo: String? = null,
)

@Serializable
data class Person(
    val id: Long? = null,
    val name: String = "",
    val photo: String? = null,
    val movies: List<Long> = emptyList(),
)

@Serializable
data class CollectionsFile(
    val version: Int = 1,
    val collections: List<MovieCollection> = emptyList(),
)

@Serializable
data class MovieCollection(
    val id: String = "",
    val title: String = "",
    val source: String? = null,
    val total: Int = 0,
    val items: List<Long> = emptyList(),
)

package ru.fvkhweb.movies.ui

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private val ruDayMonth = DateTimeFormatter.ofPattern("d MMMM", Locale("ru", "RU"))

fun runtimeLabel(minutes: Int?): String {
    if (minutes == null || minutes <= 0) return ""
    val hours = minutes / 60
    val rest = minutes % 60
    return if (hours > 0) {
        if (rest > 0) "$hours ч $rest мин" else "$hours ч"
    } else "$rest мин"
}

fun formatDateRu(iso: String?): String {
    if (iso.isNullOrBlank()) return ""
    return runCatching { LocalDate.parse(iso.take(10)).format(ruDayMonth) }.getOrDefault("")
}

fun filmsWord(count: Int): String {
    val d = count % 10
    val h = count % 100
    return when {
        d == 1 && h != 11 -> "ФИЛЬМ"
        d in 2..4 && (h < 12 || h > 14) -> "ФИЛЬМА"
        else -> "ФИЛЬМОВ"
    }
}

fun todayIso(): String = LocalDate.now().toString()

fun isUnreleased(releaseDate: String?): Boolean {
    if (releaseDate.isNullOrBlank()) return false
    return releaseDate.take(10) > todayIso()
}

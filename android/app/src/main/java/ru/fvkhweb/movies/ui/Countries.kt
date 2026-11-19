package ru.fvkhweb.movies.ui

import java.util.Locale

/**
 * Русские названия стран TMDB — в данных они на английском.
 * Незнакомые страны показываем как есть: база обновляется автоматически.
 */
private val COUNTRY_RU = mapOf(
    "United States of America" to "США",
    "United Kingdom" to "Великобритания",
    "France" to "Франция",
    "Japan" to "Япония",
    "Germany" to "Германия",
    "Canada" to "Канада",
    "Italy" to "Италия",
    "Spain" to "Испания",
    "India" to "Индия",
    "China" to "Китай",
    "South Korea" to "Южная Корея",
    "Mexico" to "Мексика",
    "Australia" to "Австралия",
    "Hong Kong" to "Гонконг",
    "Belgium" to "Бельгия",
    "Ireland" to "Ирландия",
    "Brazil" to "Бразилия",
    "Sweden" to "Швеция",
    "Switzerland" to "Швейцария",
    "Denmark" to "Дания",
    "New Zealand" to "Новая Зеландия",
    "Finland" to "Финляндия",
    "Poland" to "Польша",
    "Netherlands" to "Нидерланды",
    "Thailand" to "Таиланд",
    "Norway" to "Норвегия",
    "Romania" to "Румыния",
    "Indonesia" to "Индонезия",
    "Czech Republic" to "Чехия",
    "United Arab Emirates" to "ОАЭ",
    "Austria" to "Австрия",
    "Luxembourg" to "Люксембург",
    "Taiwan" to "Тайвань",
    "Philippines" to "Филиппины",
    "South Africa" to "ЮАР",
    "Turkey" to "Турция",
    "Russia" to "Россия",
    "Cyprus" to "Кипр",
    "Greece" to "Греция",
    "Morocco" to "Марокко",
    "Ukraine" to "Украина",
    "Saudi Arabia" to "Саудовская Аравия",
    "Hungary" to "Венгрия",
    "Soviet Union" to "СССР",
    "Colombia" to "Колумбия",
    "Israel" to "Израиль",
    "Singapore" to "Сингапур",
    "Yugoslavia" to "Югославия",
    "Croatia" to "Хорватия",
    "Serbia" to "Сербия",
    "Bulgaria" to "Болгария",
    "Egypt" to "Египет",
    "Portugal" to "Португалия",
    "Iceland" to "Исландия",
    "Netherlands Antilles" to "Антильские острова",
    "Latvia" to "Латвия",
    "Palestinian Territory" to "Палестина",
    "Argentina" to "Аргентина",
    "Chile" to "Чили",
    "Qatar" to "Катар",
    "Vietnam" to "Вьетнам",
    "Lebanon" to "Ливан",
    "Tunisia" to "Тунис",
    "Malawi" to "Малави",
    "Bahamas" to "Багамы",
    "Belarus" to "Беларусь",
    "Ecuador" to "Эквадор",
    "Iran" to "Иран",
    "Macedonia" to "Македония",
    "Ethiopia" to "Эфиопия",
    "Ghana" to "Гана",
    "Jordan" to "Иордания",
    "Namibia" to "Намибия",
    "Puerto Rico" to "Пуэрто-Рико",
    "Nigeria" to "Нигерия",
    "Cuba" to "Куба",
    "Congo" to "Конго",
    "Syrian Arab Republic" to "Сирия",
    "Gabon" to "Габон",
    "Rwanda" to "Руанда",
    "Chad" to "Чад",
    "Cote D'Ivoire" to "Кот-д’Ивуар",
    "Estonia" to "Эстония",
    "Montenegro" to "Черногория",
    "Slovenia" to "Словения",
    "Czechoslovakia" to "Чехословакия",
    "West Germany" to "ФРГ",
    "East Germany" to "ГДР",
    "Georgia" to "Грузия",
    "Armenia" to "Армения",
    "Kazakhstan" to "Казахстан",
    "Uzbekistan" to "Узбекистан",
    "Moldova" to "Молдова",
    "Lithuania" to "Литва",
    "Azerbaijan" to "Азербайджан",
)

fun countryLabel(name: String): String = COUNTRY_RU[name] ?: name

data class CountryOption(
    val name: String,
    val label: String,
    val count: Int,
)

private val countryCollator: java.text.Collator = java.text.Collator.getInstance(Locale("ru", "RU")).apply {
    strength = java.text.Collator.PRIMARY
}

/** Страны из данных: с числом фильмов, по алфавиту русских названий. */
fun buildCountryOptions(counts: Map<String, Int>): List<CountryOption> =
    counts.entries
        .map { (name, count) -> CountryOption(name = name, label = countryLabel(name), count = count) }
        .sortedWith { a, b -> countryCollator.compare(a.label, b.label) }

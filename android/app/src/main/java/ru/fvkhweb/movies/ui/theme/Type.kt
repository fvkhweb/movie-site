@file:OptIn(ExperimentalTextApi::class)

package ru.fvkhweb.movies.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import ru.fvkhweb.movies.R

private fun variableFont(id: Int, weight: FontWeight) = Font(
    resId = id,
    weight = weight,
    variationSettings = FontVariation.Settings(FontVariation.weight(weight.weight)),
)

val Unbounded = FontFamily(
    variableFont(R.font.unbounded, FontWeight.W500),
    variableFont(R.font.unbounded, FontWeight.W600),
    variableFont(R.font.unbounded, FontWeight.W700),
    variableFont(R.font.unbounded, FontWeight.W800),
)

val Manrope = FontFamily(
    variableFont(R.font.manrope, FontWeight.W400),
    variableFont(R.font.manrope, FontWeight.W500),
    variableFont(R.font.manrope, FontWeight.W600),
    variableFont(R.font.manrope, FontWeight.W700),
    variableFont(R.font.manrope, FontWeight.W800),
)

val DMMono = FontFamily(
    Font(R.font.dm_mono_regular, FontWeight.W400),
    Font(R.font.dm_mono_medium, FontWeight.W500),
)

val Montserrat = FontFamily(
    Font(R.font.montserrat_regular, FontWeight.W400),
    Font(R.font.montserrat_medium, FontWeight.W500),
    Font(R.font.montserrat_semibold, FontWeight.W600),
    Font(R.font.montserrat_bold, FontWeight.W700),
)

/** Типографика приложения — Montserrat во всех стилях. */
object AppText {
    val brand = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W800,
        fontSize = 15.sp,
        letterSpacing = (-0.4).sp,
    )
    val display = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W800,
        fontSize = 30.sp,
        lineHeight = 36.sp,
        letterSpacing = (-1.2).sp,
    )
    val h1 = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W700,
        fontSize = 23.sp,
        lineHeight = 29.sp,
        letterSpacing = (-0.7).sp,
    )
    val h2 = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W700,
        fontSize = 17.sp,
        lineHeight = 22.sp,
        letterSpacing = (-0.2).sp,
    )
    val section = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W700,
        fontSize = 14.sp,
        lineHeight = 19.sp,
        letterSpacing = 0.1.sp,
    )
    val cardTitle = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W600,
        fontSize = 12.5.sp,
        lineHeight = 16.sp,
        letterSpacing = (-0.1).sp,
    )
    val body = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W400,
        fontSize = 14.sp,
        lineHeight = 21.sp,
    )
    val bodySmall = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W400,
        fontSize = 12.5.sp,
        lineHeight = 19.sp,
    )
    val bodyBold = TextStyle(fontFamily = Montserrat, fontWeight = FontWeight.W700, fontSize = 13.sp)
    val button = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W600,
        fontSize = 13.sp,
        letterSpacing = 0.1.sp,
    )
    val mono = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W500,
        fontSize = 9.5.sp,
        letterSpacing = 1.sp,
    )
    val monoWide = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W600,
        fontSize = 10.sp,
        letterSpacing = 1.6.sp,
    )
    val monoMedium = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W500,
        fontSize = 11.sp,
        letterSpacing = 0.3.sp,
    )
    val chip = TextStyle(fontFamily = Montserrat, fontWeight = FontWeight.W500, fontSize = 11.5.sp)
    val eyebrow = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W600,
        fontSize = 11.sp,
        letterSpacing = 2.sp,
    )
    val meta = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W500,
        fontSize = 11.sp,
        letterSpacing = 0.4.sp,
    )
    val tag = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W600,
        fontSize = 10.sp,
        letterSpacing = 1.4.sp,
    )
    val posterSoon = TextStyle(
        fontFamily = Montserrat,
        fontWeight = FontWeight.W700,
        fontSize = 10.sp,
        letterSpacing = 0.9.sp,
    )
    val countryBadge = TextStyle(fontFamily = Montserrat, fontWeight = FontWeight.W600, fontSize = 10.sp)
    val countryOption = TextStyle(fontFamily = Montserrat, fontWeight = FontWeight.W400, fontSize = 12.sp)
    val countryFoot = TextStyle(fontFamily = Montserrat, fontWeight = FontWeight.W400, fontSize = 11.sp)
}

val AppTypography = Typography(
    displayLarge = AppText.display,
    displayMedium = AppText.display,
    displaySmall = AppText.h1,
    headlineLarge = AppText.h1,
    headlineMedium = AppText.h2,
    headlineSmall = AppText.h2,
    titleLarge = AppText.section,
    titleMedium = AppText.cardTitle,
    titleSmall = AppText.cardTitle,
    bodyLarge = AppText.body,
    bodyMedium = AppText.bodySmall,
    bodySmall = AppText.bodySmall,
    labelLarge = AppText.button,
    labelMedium = AppText.meta,
    labelSmall = AppText.mono,
)

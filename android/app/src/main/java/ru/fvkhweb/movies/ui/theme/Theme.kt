package ru.fvkhweb.movies.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val DarkScheme = darkColorScheme(
    primary = Blue,
    onPrimary = Color.White,
    primaryContainer = Panel2,
    onPrimaryContainer = White,
    secondary = Blue2,
    onSecondary = Color.White,
    background = Bg,
    onBackground = White,
    surface = Panel,
    onSurface = White,
    surfaceVariant = Panel2,
    onSurfaceVariant = Muted,
    outline = Line,
    outlineVariant = Line,
    error = Bad,
    onError = Bg,
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(9.dp),
    medium = RoundedCornerShape(12.dp),
    large = RoundedCornerShape(14.dp),
    extraLarge = RoundedCornerShape(20.dp),
)

@Composable
fun MovieSiteTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkScheme,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}

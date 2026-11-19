package ru.fvkhweb.movies.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay

/** Общие параметры движения: короткие, мягкие, без резких скачков. */
object Motion {
    const val FadeIn = 160
    const val FadeOut = 90
    const val Reveal = 230
    const val Step = 16

    val SoftSpring = spring<Float>(
        dampingRatio = 0.78f,
        stiffness = Spring.StiffnessMediumLow,
    )

    val BouncySpring = spring<Float>(
        dampingRatio = 0.5f,
        stiffness = Spring.StiffnessMedium,
    )
}

/**
 * Нажатие с пружинным уменьшением. Заменяет обычный clickable.
 */
@Composable
fun Modifier.clickScale(
    scaleDown: Float = 0.96f,
    onClick: () -> Unit,
): Modifier {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) scaleDown else 1f,
        animationSpec = spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium),
        label = "press-scale",
    )
    return this
        .graphicsLayer {
            scaleX = scale
            scaleY = scale
        }
        .clickable(
            interactionSource = interaction,
            indication = LocalIndication.current,
            onClick = onClick,
        )
}

/**
 * Появление элемента с лёгким подъёмом и задержкой по индексу — даёт «каскад» списка.
 */
@Composable
fun Modifier.staggerReveal(
    index: Int = 0,
    step: Int = Motion.Step,
    duration: Int = Motion.Reveal,
    offsetY: Int = 12,
): Modifier {
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        delay(index.coerceIn(0, 6) * step.toLong())
        visible = true
    }
    val progress by animateFloatAsState(
        targetValue = if (visible) 1f else 0f,
        animationSpec = tween(durationMillis = duration, easing = FastOutSlowInEasing),
        label = "stagger-reveal",
    )
    return this.graphicsLayer {
        alpha = progress
        translationY = (1f - progress) * offsetY.dp.toPx()
    }
}

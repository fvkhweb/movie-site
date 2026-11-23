@file:Suppress("DEPRECATION")

package ru.fvkhweb.movies.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.fvkhweb.movies.AppContainer
import ru.fvkhweb.movies.BuildConfig
import ru.fvkhweb.movies.ui.components.PrimaryButton
import ru.fvkhweb.movies.ui.components.SecondaryButton
import ru.fvkhweb.movies.ui.components.clickScale
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bad
import ru.fvkhweb.movies.ui.theme.Blue
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Mid
import ru.fvkhweb.movies.ui.theme.Muted
import ru.fvkhweb.movies.ui.theme.Panel
import ru.fvkhweb.movies.ui.theme.Soft
import ru.fvkhweb.movies.ui.theme.White

/**
 * Автообновление: тихая проверка версии при запуске, диалог «вышла обнова»
 * и компактная плашка, если диалог отложили.
 */
@Composable
fun UpdateHost(container: AppContainer, modifier: Modifier = Modifier) {
    if (!BuildConfig.AUTOUPDATE_ENABLED) return
    val updater = container.updater ?: return
    val viewModel: UpdateViewModel = viewModel(factory = UpdateViewModel.factory(updater))
    val state by viewModel.state.collectAsState()
    val lifecycleOwner = LocalLifecycleOwner.current

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.onResume()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Box(modifier) {
        AnimatedVisibility(
            visible = state.showChip,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .navigationBarsPadding()
                .padding(bottom = 92.dp),
            enter = fadeIn() + slideInVertically { it / 2 },
            exit = fadeOut() + slideOutVertically { it / 2 },
        ) {
            UpdateChip(
                version = state.manifest?.versionName.orEmpty(),
                onClick = viewModel::open,
            )
        }
    }

    if (state.visible && state.manifest != null) {
        UpdateDialog(
            state = state,
            installedVersion = BuildConfig.VERSION_NAME,
            onInstall = viewModel::install,
            onDismiss = viewModel::dismiss,
        )
    }
}

@Composable
private fun UpdateChip(version: String, onClick: () -> Unit) {
    val shape = RoundedCornerShape(100.dp)
    Row(
        Modifier
            .clip(shape)
            .background(Brush.horizontalGradient(listOf(Blue, Color(0xFF5B7BFF))))
            .clickScale(scaleDown = 0.95f, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("ОБНОВА $version", style = AppText.tag, color = Color.White)
        Spacer(Modifier.width(8.dp))
        Text("УСТАНОВИТЬ ↗", style = AppText.tag, color = Color.White.copy(alpha = 0.85f))
    }
}

@Composable
private fun UpdateDialog(
    state: UpdateUiState,
    installedVersion: String,
    onInstall: () -> Unit,
    onDismiss: () -> Unit,
) {
    val manifest = state.manifest ?: return
    val shape = RoundedCornerShape(18.dp)

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .widthIn(max = 420.dp)
                .padding(horizontal = 18.dp)
                .clip(shape)
                .background(Panel)
                .border(1.dp, Line, shape)
                .padding(20.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("ОБНОВЛЕНИЕ", style = AppText.eyebrow, color = Blue2)
                Spacer(Modifier.weight(1f))
                Text("v${manifest.versionName}", style = AppText.mono, color = Muted)
            }

            Text(
                "ВЫШЛА ОБНОВА",
                style = AppText.h1,
                color = White,
                modifier = Modifier.padding(top = 10.dp),
            )
            Text(
                "Установлена $installedVersion · новая ${manifest.versionName}",
                style = AppText.meta,
                color = Muted,
                modifier = Modifier.padding(top = 6.dp),
            )

            if (manifest.notes.isNotEmpty()) {
                Column(Modifier.padding(top = 16.dp)) {
                    manifest.notes.forEach { note ->
                        Row(Modifier.padding(bottom = 6.dp)) {
                            Text("•", style = AppText.bodySmall, color = Blue2)
                            Spacer(Modifier.width(8.dp))
                            Text(note, style = AppText.bodySmall, color = Soft)
                        }
                    }
                }
            }

            if (state.downloading) {
                Column(Modifier.padding(top = 18.dp)) {
                    LinearProgressIndicator(
                        progress = { state.progress / 100f },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(4.dp)
                            .clip(RoundedCornerShape(100.dp)),
                        color = Blue,
                        trackColor = Line,
                    )
                    Text(
                        "Скачиваем… ${state.progress}%",
                        style = AppText.meta,
                        color = Muted,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            } else if (state.needsPermission) {
                Text(
                    "Разреши установку из этого приложения — Android спросит один раз.",
                    style = AppText.bodySmall,
                    color = Mid,
                    modifier = Modifier.padding(top = 16.dp),
                )
            } else if (state.error != null) {
                Text(
                    state.error,
                    style = AppText.bodySmall,
                    color = Bad,
                    modifier = Modifier.padding(top = 16.dp),
                )
            }

            Row(
                Modifier.padding(top = 20.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                SecondaryButton(
                    text = "Позже",
                    onClick = onDismiss,
                    modifier = Modifier.weight(1f),
                )
                PrimaryButton(
                    text = when {
                        state.downloading -> "Качаем…"
                        state.needsPermission -> "Настройки"
                        state.ready -> "Установить"
                        else -> "Обновить"
                    },
                    onClick = onInstall,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

package ru.fvkhweb.movies.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import java.io.File
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ru.fvkhweb.movies.BuildConfig
import ru.fvkhweb.movies.data.update.AppUpdater
import ru.fvkhweb.movies.data.update.UpdateManifest

data class UpdateUiState(
    val manifest: UpdateManifest? = null,
    val visible: Boolean = false,
    val checking: Boolean = false,
    val downloading: Boolean = false,
    val progress: Int = 0,
    val ready: Boolean = false,
    val needsPermission: Boolean = false,
    val error: String? = null,
) {
    val hasUpdate: Boolean get() = manifest != null
    val showChip: Boolean get() = manifest != null && !visible
}

class UpdateViewModel(private val updater: AppUpdater) : ViewModel() {

    private val _state = MutableStateFlow(UpdateUiState())
    val state: StateFlow<UpdateUiState> = _state.asStateFlow()

    private var pendingApk: File? = null

    init {
        checkIfDue()
    }

    /** Тихая проверка при запуске: не чаще раза в 6 часов. */
    fun checkIfDue() {
        if (BuildConfig.DEBUG) return
        if (System.currentTimeMillis() - updater.lastCheckAt() < AppUpdater.CHECK_INTERVAL_MS) return
        check()
    }

    fun check() {
        val current = _state.value
        if (current.checking || current.downloading) return
        viewModelScope.launch {
            _state.update { it.copy(checking = true) }
            val manifest = updater.check()
            updater.markChecked()
            _state.update {
                it.copy(
                    checking = false,
                    manifest = manifest ?: it.manifest,
                    visible = manifest != null || it.visible,
                    ready = false,
                )
            }
        }
    }

    fun open() {
        if (_state.value.manifest == null) {
            check()
            return
        }
        _state.update { it.copy(visible = true) }
    }

    fun dismiss() {
        _state.update { it.copy(visible = false) }
    }

    fun install() {
        val manifest = _state.value.manifest ?: return
        if (_state.value.downloading) return

        val cached = updater.cachedApk(manifest)?.takeIf { updater.verify(manifest, it) }
        if (cached != null) {
            _state.update { it.copy(ready = true) }
            launchInstaller(cached)
            return
        }

        viewModelScope.launch {
            _state.update {
                it.copy(downloading = true, progress = 0, error = null, needsPermission = false)
            }
            try {
                val file = updater.download(manifest) { percent ->
                    _state.update { it.copy(progress = percent) }
                }
                if (!updater.verify(manifest, file)) {
                    file.delete()
                    _state.update {
                        it.copy(downloading = false, error = "Обновление не прошло проверку подписи")
                    }
                } else {
                    _state.update { it.copy(downloading = false, ready = true, progress = 100) }
                    updater.cleanup(file)
                    launchInstaller(file)
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        downloading = false,
                        error = e.message ?: "Не удалось скачать обновление",
                    )
                }
            }
        }
    }

    private fun launchInstaller(file: File) {
        if (!updater.canInstallPackages()) {
            pendingApk = file
            _state.update { it.copy(needsPermission = true, error = null) }
            updater.openInstallPermission()
            return
        }
        pendingApk = null
        _state.update { it.copy(needsPermission = false) }
        runCatching { updater.install(file) }
            .onFailure {
                _state.update { it.copy(error = "Не удалось открыть установщик") }
            }
    }

    /** Возврат в приложение после экрана разрешений. */
    fun onResume() {
        val file = pendingApk ?: return
        if (updater.canInstallPackages()) launchInstaller(file)
    }

    companion object {
        fun factory(updater: AppUpdater): ViewModelProvider.Factory = viewModelFactory {
            initializer { UpdateViewModel(updater) }
        }
    }
}

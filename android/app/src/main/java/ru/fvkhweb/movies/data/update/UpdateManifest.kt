package ru.fvkhweb.movies.data.update

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Манифест обновления: app/latest.json на GitHub Pages.
 * versionCode сравнивается с BuildConfig.VERSION_CODE.
 */
@Serializable
data class UpdateManifest(
    val versionCode: Int = 0,
    val versionName: String = "",
    val apkUrl: String = "",
    val sha256: String = "",
    val size: Long = 0L,
    val notes: List<String> = emptyList(),
    @SerialName("publishedAt") val publishedAt: String? = null,
)

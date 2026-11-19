package ru.fvkhweb.movies.data.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import ru.fvkhweb.movies.BuildConfig

/**
 * Автообновление: манифест версии и APK лежат на GitHub Pages.
 * Проверяем versionCode, качаем файл, сверяем SHA-256 и подпись,
 * после чего отдаём его системному установщику.
 */
class AppUpdater(
    private val context: Context,
    private val client: OkHttpClient,
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        coerceInputValues = true
        explicitNulls = false
    }
    private val dir = File(context.cacheDir, "updates").apply { mkdirs() }
    private val prefs = context.getSharedPreferences("updater", Context.MODE_PRIVATE)

    fun lastCheckAt(): Long = prefs.getLong(KEY_LAST_CHECK, 0L)

    fun markChecked() {
        prefs.edit().putLong(KEY_LAST_CHECK, System.currentTimeMillis()).apply()
    }

    /** Возвращает манифест, только если на сервере версия новее установленной. */
    suspend fun check(): UpdateManifest? = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$MANIFEST_URL?t=${System.currentTimeMillis()}")
            .header("Cache-Control", "no-cache")
            .header("Pragma", "no-cache")
            .build()
        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext null
                val text = response.body?.string().orEmpty()
                if (text.isBlank()) return@withContext null
                val manifest = json.decodeFromString(UpdateManifest.serializer(), text)
                manifest.takeIf {
                    it.versionCode > BuildConfig.VERSION_CODE && it.apkUrl.isNotBlank()
                }
            }
        } catch (e: Exception) {
            null
        }
    }

    fun cachedApk(manifest: UpdateManifest): File? =
        File(dir, apkName(manifest)).takeIf { it.exists() && it.length() > 0 }

    suspend fun download(
        manifest: UpdateManifest,
        onProgress: (Int) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val target = File(dir, apkName(manifest))
        if (target.exists()) target.delete()

        val request = Request.Builder()
            .url(manifest.apkUrl)
            .header("Cache-Control", "no-cache")
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("Сервер вернул ${response.code}")
            val body = response.body ?: error("Пустой ответ сервера")
            val total = body.contentLength().takeIf { it > 0 } ?: manifest.size
            val digest = MessageDigest.getInstance("SHA-256")

            body.byteStream().use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var readTotal = 0L
                    var lastPercent = -1
                    while (true) {
                        val read = input.read(buffer)
                        if (read <= 0) break
                        output.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                        readTotal += read
                        if (total > 0) {
                            val percent = ((readTotal * 100) / total).toInt().coerceIn(0, 100)
                            if (percent != lastPercent) {
                                lastPercent = percent
                                onProgress(percent)
                            }
                        }
                    }
                }
            }

            val hash = digest.digest().joinToString("") { "%02x".format(it) }
            if (manifest.sha256.isNotBlank() && !hash.equals(manifest.sha256, ignoreCase = true)) {
                target.delete()
                error("Файл повреждён: контрольная сумма не совпала")
            }
        }
        onProgress(100)
        target
    }

    /** Пакет, версия и подпись скачанного APK должны совпадать с установленным приложением. */
    fun verify(manifest: UpdateManifest, file: File): Boolean {
        if (!file.exists()) return false
        val archive = archiveInfo(file) ?: return false
        if (archive.packageName != context.packageName) return false
        val archiveCode = if (Build.VERSION.SDK_INT >= 28) {
            archive.longVersionCode
        } else {
            @Suppress("DEPRECATION")
            archive.versionCode.toLong()
        }
        if (archiveCode != manifest.versionCode.toLong()) return false

        val archiveSigner = signerSha256(archive) ?: return false
        val installedSigner = installedSignerSha256() ?: return false
        return archiveSigner == installedSigner
    }

    fun canInstallPackages(): Boolean =
        context.packageManager.canRequestPackageInstalls()

    fun openInstallPermission() {
        runCatching {
            context.startActivity(
                Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${context.packageName}"),
                ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        }
    }

    fun install(file: File) {
        val uri = FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    /** Удаляем старые APK, чтобы кэш не рос. */
    fun cleanup(keep: File?) {
        dir.listFiles()?.forEach { file ->
            if (file.absolutePath != keep?.absolutePath) runCatching { file.delete() }
        }
    }

    private fun apkName(manifest: UpdateManifest) = "whattowatch-${manifest.versionCode}.apk"

    @Suppress("DEPRECATION")
    private fun archiveInfo(file: File): PackageInfo? =
        if (Build.VERSION.SDK_INT >= 28) {
            context.packageManager.getPackageArchiveInfo(
                file.absolutePath,
                PackageManager.GET_SIGNING_CERTIFICATES,
            )
        } else {
            context.packageManager.getPackageArchiveInfo(
                file.absolutePath,
                PackageManager.GET_SIGNATURES,
            )
        }

    private fun installedSignerSha256(): String? {
        val info = if (Build.VERSION.SDK_INT >= 28) {
            context.packageManager.getPackageInfo(
                context.packageName,
                PackageManager.GET_SIGNING_CERTIFICATES,
            )
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(
                context.packageName,
                PackageManager.GET_SIGNATURES,
            )
        }
        return signerSha256(info)
    }

    @Suppress("DEPRECATION")
    private fun signerSha256(info: PackageInfo): String? {
        val bytes = if (Build.VERSION.SDK_INT >= 28) {
            info.signingInfo?.apkContentsSigners?.firstOrNull()?.toByteArray()
        } else {
            info.signatures?.firstOrNull()?.toByteArray()
        } ?: return null
        return MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
    }

    companion object {
        const val MANIFEST_URL = "https://fvkhweb.github.io/movie-site/app/latest.json"
        private const val KEY_LAST_CHECK = "last_check_at"
        const val CHECK_INTERVAL_MS = 6L * 60 * 60 * 1000
    }
}

package ru.fvkhweb.movies

import android.app.Application
import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.Cache
import okhttp3.OkHttpClient
import ru.fvkhweb.movies.data.CatalogApi
import ru.fvkhweb.movies.data.CatalogRefreshWorker
import ru.fvkhweb.movies.data.CatalogRepository
import ru.fvkhweb.movies.data.FavoritesStore
import ru.fvkhweb.movies.data.Media
import ru.fvkhweb.movies.data.update.AppUpdater

class AppContainer(context: Context) {
    private val client = OkHttpClient.Builder()
        .cache(Cache(File(context.cacheDir, "http"), 64L * 1024 * 1024))
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .build()

    val api = CatalogApi(client, Media.BASE)
    val repository = CatalogRepository(context, api)
    val favorites = FavoritesStore(context)

    /** Скачивание APK — отдельный клиент без HTTP-кэша. В сборке RuStore его нет. */
    val updater: AppUpdater? = if (BuildConfig.AUTOUPDATE_ENABLED) {
        AppUpdater(
            context,
            OkHttpClient.Builder()
                .connectTimeout(20, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .callTimeout(10, TimeUnit.MINUTES)
                .build(),
        )
    } else {
        null
    }
}

class MoviesApplication : Application(), ImageLoaderFactory {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        scheduleCatalogRefresh()
    }

    private fun scheduleCatalogRefresh() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val request = PeriodicWorkRequestBuilder<CatalogRefreshWorker>(12, TimeUnit.HOURS)
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "catalog-refresh",
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    override fun newImageLoader(): ImageLoader = ImageLoader.Builder(this)
        .crossfade(180)
        .respectCacheHeaders(true)
        .memoryCache {
            MemoryCache.Builder(this)
                .maxSizePercent(0.25)
                .build()
        }
        .diskCache {
            DiskCache.Builder()
                .directory(cacheDir.resolve("images"))
                .maxSizeBytes(200L * 1024 * 1024)
                .build()
        }
        .build()
}

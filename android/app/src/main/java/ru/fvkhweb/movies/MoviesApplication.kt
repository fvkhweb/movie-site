package ru.fvkhweb.movies

import android.app.Application
import android.content.Context
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import java.io.File
import java.util.concurrent.TimeUnit
import okhttp3.Cache
import okhttp3.OkHttpClient
import ru.fvkhweb.movies.data.CatalogApi
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

    /** Скачивание APK — отдельный клиент без HTTP-кэша. */
    val updater = AppUpdater(
        context,
        OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .callTimeout(10, TimeUnit.MINUTES)
            .build(),
    )
}

class MoviesApplication : Application(), ImageLoaderFactory {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }

    override fun newImageLoader(): ImageLoader = ImageLoader.Builder(this)
        .crossfade(180)
        .respectCacheHeaders(false)
        .memoryCache {
            MemoryCache.Builder(this)
                .maxSizePercent(0.25)
                .build()
        }
        .diskCache {
            DiskCache.Builder()
                .directory(cacheDir.resolve("images"))
                .maxSizeBytes(400L * 1024 * 1024)
                .build()
        }
        .build()
}

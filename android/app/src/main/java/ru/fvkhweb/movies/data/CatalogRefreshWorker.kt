package ru.fvkhweb.movies.data

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import ru.fvkhweb.movies.MoviesApplication

/** Периодически подтягивает каталог, пока приложение не открыто. */
class CatalogRefreshWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as? MoviesApplication ?: return Result.success()
        app.container.repository.refresh()
        return if (app.container.repository.state.value.offline) Result.retry() else Result.success()
    }
}

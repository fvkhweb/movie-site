package ru.fvkhweb.movies.data

import android.content.Context
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import ru.fvkhweb.movies.data.model.CastMember
import ru.fvkhweb.movies.data.model.CollectionsFile
import ru.fvkhweb.movies.data.model.Genre
import ru.fvkhweb.movies.data.model.Movie
import ru.fvkhweb.movies.data.model.MovieLists
import ru.fvkhweb.movies.data.model.Person

/**
 * Каталог: сначала мгновенно отдаём локальный снимок данных, затем тихо
 * обновляем его с GitHub Pages. Сеть недоступна — приложение работает на кэше.
 */
class CatalogRepository(
    context: Context,
    private val api: CatalogApi,
) {
    private val dir = File(context.filesDir, "catalog").apply { mkdirs() }
    private val mutex = Mutex()
    private var started = false

    private val _state = MutableStateFlow(CatalogState())
    val state: StateFlow<CatalogState> = _state.asStateFlow()

    suspend fun start() {
        if (started) return
        started = true

        readSnapshot()?.let { snapshot ->
            _state.value = snapshot.copy(loading = false, refreshing = true)
        }
        refresh()
    }

    suspend fun refresh() {
        mutex.withLock {
            _state.update { it.copy(refreshing = true) }

            try {
                // decode выполняется до записи: битый ответ с кодом 200
                // не затрёт хороший локальный снимок
                val movies = fetchDecoded("data/movies.json", "movies.json") {
                    api.decode<List<Movie>>(it)
                }
                val genres = fetchDecoded("data/genres.json", "genres.json") {
                    api.decode<List<Genre>>(it)
                }
                val lists = fetchDecoded("data/lists.json", "lists.json") {
                    api.decode<MovieLists>(it)
                }

                if (movies.isEmpty()) error("Каталог пуст")

                _state.update {
                    it.copy(
                        loading = false,
                        refreshing = true,
                        error = null,
                        movies = movies,
                        genres = genres,
                        lists = lists,
                        updatedAt = System.currentTimeMillis(),
                        offline = false,
                    )
                }
            } catch (e: Exception) {
                _state.update {
                    it.copy(
                        loading = false,
                        refreshing = false,
                        offline = true,
                        error = if (it.movies.isEmpty()) humanError(e) else null,
                    )
                }
                return@withLock
            }

            loadExtras()
            _state.update { it.copy(refreshing = false) }
        }
    }

    private suspend fun loadExtras() {
        // Актёры и подборки тяжёлые и не нужны для первого экрана — грузим следом
        runCatching {
            val cast = fetchDecoded("data/cast.json", "cast.json") {
                api.decode<Map<String, List<CastMember>>>(it)
            }
            _state.update { it.copy(cast = cast) }
        }
        runCatching {
            val people = fetchDecoded("data/people.json", "people.json") {
                api.decode<List<Person>>(it)
            }
            _state.update { it.copy(people = people) }
        }
        runCatching {
            val file = fetchDecoded("data/collections.json", "collections.json") {
                api.decode<CollectionsFile>(it)
            }
            _state.update { it.copy(collections = file.collections) }
        }
    }

    /**
     * Условный запрос: при 304 декодируем локальный снимок, при 200 —
     * сначала декодируем и только потом атомарно пишем файл.
     */
    private suspend fun <T> fetchDecoded(
        path: String,
        fileName: String,
        conditional: Boolean = true,
        decode: (String) -> T,
    ): T {
        val meta = if (conditional) readMeta(fileName) else null
        val response = api.fetch(path, meta?.first, meta?.second)

        if (response.notModified) {
            val cached = withContext(Dispatchers.IO) {
                File(dir, fileName).takeIf { it.exists() }?.readText()
            }
            if (cached != null) {
                try {
                    return decode(cached)
                } catch (_: Exception) {
                    // Битый снимок: сбрасываем валидаторы и качаем заново
                }
            }
            if (!conditional) error("Сервер вернул 304 без локального снимка")
            deleteMeta(fileName)
            withContext(Dispatchers.IO) { File(dir, fileName).delete() }
            return fetchDecoded(path, fileName, conditional = false, decode = decode)
        }

        val text = response.text ?: error("Пустой ответ сервера")
        val value = decode(text)
        writeAtomic(fileName, text)
        writeMeta(fileName, response.etag, response.lastModified)
        return value
    }

    private suspend fun writeAtomic(fileName: String, text: String) = withContext(Dispatchers.IO) {
        val tmp = File(dir, "$fileName.tmp")
        tmp.writeText(text)
        val dst = File(dir, fileName)
        try {
            java.nio.file.Files.move(
                tmp.toPath(),
                dst.toPath(),
                java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                java.nio.file.StandardCopyOption.ATOMIC_MOVE,
            )
        } catch (_: Exception) {
            tmp.copyTo(dst, overwrite = true)
            tmp.delete()
        }
    }

    private suspend fun readMeta(fileName: String): Pair<String?, String?>? =
        withContext(Dispatchers.IO) {
            val file = File(dir, "$fileName.meta")
            if (!file.exists()) return@withContext null
            val lines = runCatching { file.readLines() }.getOrDefault(emptyList())
            val etag = lines.getOrNull(0)?.takeIf { it.isNotBlank() }
            val lastModified = lines.getOrNull(1)?.takeIf { it.isNotBlank() }
            if (etag == null && lastModified == null) null else etag to lastModified
        }

    private suspend fun writeMeta(fileName: String, etag: String?, lastModified: String?) =
        withContext(Dispatchers.IO) {
            val file = File(dir, "$fileName.meta")
            if (etag.isNullOrBlank() && lastModified.isNullOrBlank()) {
                file.delete()
            } else {
                file.writeText("${etag.orEmpty()}\n${lastModified.orEmpty()}")
            }
        }

    private suspend fun deleteMeta(fileName: String) = withContext(Dispatchers.IO) {
        File(dir, "$fileName.meta").delete()
    }
    private suspend fun readSnapshot(): CatalogState? = withContext(Dispatchers.IO) {
        val moviesFile = File(dir, "movies.json")
        if (!moviesFile.exists()) return@withContext null

        runCatching {
            val movies = api.decode<List<Movie>>(moviesFile.readText())
            val genres = File(dir, "genres.json").takeIf { it.exists() }
                ?.let { api.decode<List<Genre>>(it.readText()) }
                .orEmpty()
            val lists = File(dir, "lists.json").takeIf { it.exists() }
                ?.let { api.decode<MovieLists>(it.readText()) }
                ?: MovieLists()
            val cast = File(dir, "cast.json").takeIf { it.exists() }
                ?.let { api.decode<Map<String, List<CastMember>>>(it.readText()) }
                .orEmpty()
            val people = File(dir, "people.json").takeIf { it.exists() }
                ?.let { api.decode<List<Person>>(it.readText()) }
                .orEmpty()
            val collections = File(dir, "collections.json").takeIf { it.exists() }
                ?.let { api.decode<CollectionsFile>(it.readText()).collections }
                .orEmpty()

            if (movies.isEmpty()) null
            else CatalogState(
                loading = false,
                movies = movies,
                genres = genres,
                lists = lists,
                cast = cast,
                people = people,
                collections = collections,
                updatedAt = moviesFile.lastModified(),
            )
        }.getOrNull()
    }

    private fun humanError(e: Exception): String {
        val raw = e.message.orEmpty()
        return when {
            raw.contains("Unable to resolve host", true) ||
                raw.contains("timed out", true) ||
                raw.contains("timeout", true) -> "Нет соединения с интернетом. Проверьте сеть и повторите."
            else -> "Не удалось загрузить каталог. Попробуйте ещё раз."
        }
    }
}

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
                val moviesText = fetchAndStore("data/movies.json", "movies.json")
                val genresText = fetchAndStore("data/genres.json", "genres.json")
                val listsText = fetchAndStore("data/lists.json", "lists.json")

                val movies = api.decode<List<Movie>>(moviesText)
                val genres = api.decode<List<Genre>>(genresText)
                val lists = api.decode<MovieLists>(listsText)

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
            val text = fetchAndStore("data/cast.json", "cast.json")
            val cast = api.decode<Map<String, List<CastMember>>>(text)
            _state.update { it.copy(cast = cast) }
        }
        runCatching {
            val text = fetchAndStore("data/people.json", "people.json")
            val people = api.decode<List<Person>>(text)
            _state.update { it.copy(people = people) }
        }
        runCatching {
            val text = fetchAndStore("data/collections.json", "collections.json")
            val file = api.decode<CollectionsFile>(text)
            _state.update { it.copy(collections = file.collections) }
        }
    }

    private suspend fun fetchAndStore(path: String, fileName: String): String {
        val text = api.fetchText(path)
        withContext(Dispatchers.IO) {
            val tmp = File(dir, "$fileName.tmp")
            tmp.writeText(text)
            if (!tmp.renameTo(File(dir, fileName))) {
                tmp.copyTo(File(dir, fileName), overwrite = true)
                tmp.delete()
            }
        }
        return text
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

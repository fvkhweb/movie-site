package ru.fvkhweb.movies.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

class CatalogApi(
    private val client: OkHttpClient,
    private val baseUrl: String,
) {
    val json: Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
        isLenient = true
    }

    /** text == null — сервер ответил 304, данные не изменились. */
    data class Response(
        val text: String?,
        val etag: String?,
        val lastModified: String?,
    ) {
        val notModified: Boolean get() = text == null
    }

    suspend fun fetch(
        path: String,
        etag: String? = null,
        lastModified: String? = null,
    ): Response = withContext(Dispatchers.IO) {
        val builder = Request.Builder()
            .url(baseUrl + path)
            .header("Accept", "application/json")
        if (!etag.isNullOrBlank()) builder.header("If-None-Match", etag)
        if (!lastModified.isNullOrBlank()) builder.header("If-Modified-Since", lastModified)

        client.newCall(builder.build()).execute().use { response ->
            when {
                response.code == 304 -> Response(
                    text = null,
                    etag = etag ?: response.header("ETag"),
                    lastModified = lastModified ?: response.header("Last-Modified"),
                )
                !response.isSuccessful -> error("Сервер вернул ${response.code}")
                else -> Response(
                    text = response.body?.string() ?: error("Пустой ответ сервера"),
                    etag = response.header("ETag"),
                    lastModified = response.header("Last-Modified"),
                )
            }
        }
    }

    inline fun <reified T> decode(text: String): T = json.decodeFromString(text)
}

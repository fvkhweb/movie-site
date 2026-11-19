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

    suspend fun fetchText(path: String): String = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(baseUrl + path)
            .header("Accept", "application/json")
            .build()

        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                error("Сервер вернул ${response.code}")
            }
            response.body?.string() ?: error("Пустой ответ сервера")
        }
    }

    inline fun <reified T> decode(text: String): T = json.decodeFromString(text)
}

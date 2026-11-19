package ru.fvkhweb.movies.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.io.IOException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map

private val Context.favoritesDataStore by preferencesDataStore(name = "favorites")

class FavoritesStore(private val context: Context) {

    private val key = stringSetPreferencesKey("movie_ids")

    val ids: Flow<Set<Long>> = context.favoritesDataStore.data
        .catch { error ->
            if (error is IOException) emit(emptyPreferences()) else throw error
        }
        .map { prefs -> prefs[key].orEmpty().mapNotNull(String::toLongOrNull).toSet() }

    suspend fun toggle(id: Long) {
        context.favoritesDataStore.edit { prefs ->
            val current = prefs[key].orEmpty()
            val value = id.toString()
            prefs[key] = if (value in current) current - value else current + value
        }
    }

    suspend fun clear() {
        context.favoritesDataStore.edit { it.remove(key) }
    }
}

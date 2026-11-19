package ru.fvkhweb.movies

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import ru.fvkhweb.movies.ui.UpdateHost
import ru.fvkhweb.movies.ui.navigation.MoviesApp
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.MovieSiteTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)

        val container = (application as MoviesApplication).container

        setContent {
            MovieSiteTheme {
                Surface(Modifier.fillMaxSize(), color = Bg) {
                    Box(Modifier.fillMaxSize()) {
                        MoviesApp(container)
                        UpdateHost(container, Modifier.fillMaxSize())
                    }
                }
            }
        }
    }
}

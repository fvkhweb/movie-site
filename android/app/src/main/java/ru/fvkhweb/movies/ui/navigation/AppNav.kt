package ru.fvkhweb.movies.ui.navigation

import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ru.fvkhweb.movies.AppContainer
import ru.fvkhweb.movies.ui.MainViewModel
import ru.fvkhweb.movies.ui.screens.CatalogScreen
import ru.fvkhweb.movies.ui.screens.CollectionDetailScreen
import ru.fvkhweb.movies.ui.screens.CollectionsScreen
import ru.fvkhweb.movies.ui.screens.FavoritesScreen
import ru.fvkhweb.movies.ui.screens.GenresScreen
import ru.fvkhweb.movies.ui.screens.HomeScreen
import ru.fvkhweb.movies.ui.screens.MovieDetailScreen
import ru.fvkhweb.movies.ui.screens.PersonScreen
import ru.fvkhweb.movies.ui.theme.AppText
import ru.fvkhweb.movies.ui.theme.Bg
import ru.fvkhweb.movies.ui.theme.Blue
import ru.fvkhweb.movies.ui.theme.Blue2
import ru.fvkhweb.movies.ui.theme.Line
import ru.fvkhweb.movies.ui.theme.Panel

object Routes {
    const val HOME = "home"
    const val CATALOG = "catalog"
    const val GENRES = "genres"
    const val COLLECTIONS = "collections"
    const val FAVORITES = "favorites"
    const val MOVIE = "movie/{movieId}"
    const val PERSON = "person/{name}"
    const val COLLECTION = "collection/{collectionId}"

    fun movie(id: Long) = "movie/$id"
    fun person(name: String) = "person/${Uri.encode(name)}"
    fun collection(id: String) = "collection/${Uri.encode(id)}"
}

private data class TabSpec(val route: String, val icon: ImageVector, val label: String)

private val tabs = listOf(
    TabSpec(Routes.HOME, Icons.Filled.Home, "Главная"),
    TabSpec(Routes.CATALOG, Icons.Filled.Search, "Каталог"),
    TabSpec(Routes.GENRES, Icons.Filled.Star, "Жанры"),
    TabSpec(Routes.COLLECTIONS, Icons.Filled.List, "Подборки"),
    TabSpec(Routes.FAVORITES, Icons.Filled.Favorite, "Избранное"),
)

private val tabRoutes = tabs.map { it.route }.toSet()
private val tabInactive = Color(0xFF8B95A6)
private val dockShape = RoundedCornerShape(22.dp)
private val pillShape = RoundedCornerShape(17.dp)

@Composable
fun MoviesApp(container: AppContainer) {
    val viewModel: MainViewModel = viewModel(factory = MainViewModel.factory(container))
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = Bg,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = {
            AnimatedVisibility(
                visible = currentRoute == null || currentRoute in tabRoutes,
                enter = fadeIn(animationSpec = tween(180)) +
                    slideInVertically(animationSpec = spring(dampingRatio = 0.8f, stiffness = Spring.StiffnessMediumLow)) { it },
                exit = fadeOut(animationSpec = tween(120)) +
                    slideOutVertically(animationSpec = tween(180)) { it },
            ) {
                AppTabBar(currentRoute) { route ->
                    if (route != currentRoute) navController.navigateTab(route)
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Routes.HOME,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .background(Bg),
            enterTransition = {
                fadeIn(animationSpec = tween(150)) +
                    slideInVertically(animationSpec = tween(180)) { it / 40 }
            },
            exitTransition = {
                if (targetState.destination.route in tabRoutes) {
                    ExitTransition.None
                } else {
                    fadeOut(animationSpec = tween(100))
                }
            },
            popEnterTransition = {
                fadeIn(animationSpec = tween(150)) +
                    slideInHorizontally(animationSpec = tween(180)) { -it / 30 }
            },
            popExitTransition = {
                fadeOut(animationSpec = tween(100))
            },
        ) {
            composable(Routes.HOME) {
                HomeScreen(
                    viewModel = viewModel,
                    onOpenMovie = { navController.navigate(Routes.movie(it)) },
                    onOpenCatalog = { navController.navigateTab(Routes.CATALOG) },
                    onOpenGenre = { genreId ->
                        viewModel.setGenre(genreId)
                        navController.navigateTab(Routes.CATALOG)
                    },
                )
            }
            composable(Routes.CATALOG) {
                CatalogScreen(viewModel) { navController.navigate(Routes.movie(it)) }
            }
            composable(Routes.GENRES) {
                GenresScreen(viewModel) { navController.navigateTab(Routes.CATALOG) }
            }
            composable(Routes.COLLECTIONS) {
                CollectionsScreen(
                    viewModel = viewModel,
                    onOpenMovie = { navController.navigate(Routes.movie(it)) },
                    onOpenCollection = { navController.navigate(Routes.collection(it)) },
                )
            }
            composable(Routes.FAVORITES) {
                FavoritesScreen(viewModel) { navController.navigate(Routes.movie(it)) }
            }
            composable(
                route = Routes.COLLECTION,
                arguments = listOf(navArgument("collectionId") { type = NavType.StringType }),
                enterTransition = {
                    slideInHorizontally(animationSpec = tween(240)) { it } + fadeIn(tween(160))
                },
                popExitTransition = {
                    slideOutHorizontally(animationSpec = tween(220)) { it } + fadeOut(tween(160))
                },
            ) { entry ->
                CollectionDetailScreen(
                    viewModel = viewModel,
                    collectionId = entry.arguments?.getString("collectionId").orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenMovie = { navController.navigate(Routes.movie(it)) },
                )
            }
            composable(
                route = Routes.MOVIE,
                arguments = listOf(navArgument("movieId") { type = NavType.LongType }),
                enterTransition = {
                    slideInHorizontally(animationSpec = tween(320)) { it } + fadeIn(tween(220))
                },
                popExitTransition = {
                    slideOutHorizontally(animationSpec = tween(300)) { it } + fadeOut(tween(220))
                },
            ) { entry ->
                MovieDetailScreen(
                    viewModel = viewModel,
                    movieId = entry.arguments?.getLong("movieId") ?: 0L,
                    onBack = { navController.popBackStack() },
                    onOpenMovie = { navController.navigate(Routes.movie(it)) },
                    onOpenPerson = { navController.navigate(Routes.person(it)) },
                )
            }
            composable(
                route = Routes.PERSON,
                arguments = listOf(navArgument("name") { type = NavType.StringType }),
                enterTransition = {
                    slideInHorizontally(animationSpec = tween(320)) { it } + fadeIn(tween(220))
                },
                popExitTransition = {
                    slideOutHorizontally(animationSpec = tween(300)) { it } + fadeOut(tween(220))
                },
            ) { entry ->
                PersonScreen(
                    viewModel = viewModel,
                    personName = entry.arguments?.getString("name").orEmpty(),
                    onBack = { navController.popBackStack() },
                    onOpenMovie = { navController.navigate(Routes.movie(it)) },
                )
            }
        }
    }
}

private fun NavHostController.navigateTab(route: String) {
    navigate(route) {
        popUpTo(graph.findStartDestination().id) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

@Composable
private fun AppTabBar(currentRoute: String?, onSelect: (String) -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Bg)
            .navigationBarsPadding(),
    ) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(14.dp)
                .background(
                    Brush.verticalGradient(
                        0f to Bg.copy(alpha = 0f),
                        1f to Bg,
                    ),
                ),
        )
        Box(
            Modifier
                .fillMaxWidth()
                .padding(start = 12.dp, end = 12.dp, top = 2.dp, bottom = 8.dp),
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .height(66.dp)
                    .clip(dockShape)
                    .background(Panel.copy(alpha = 0.96f))
                    .border(1.dp, Line.copy(alpha = 0.9f), dockShape)
                    .padding(6.dp),
            ) {
                BoxWithConstraints(Modifier.fillMaxSize()) {
                    val itemWidth = maxWidth / tabs.size
                    val activeIndex = tabs.indexOfFirst { it.route == currentRoute }.coerceAtLeast(0)
                    val indicatorX by animateDpAsState(
                        targetValue = itemWidth * activeIndex,
                        animationSpec = spring(dampingRatio = 0.72f, stiffness = Spring.StiffnessMediumLow),
                        label = "tab-indicator",
                    )
                    Box(
                        Modifier
                            .offset(x = indicatorX)
                            .width(itemWidth)
                            .fillMaxHeight()
                            .clip(pillShape)
                            .background(
                                Brush.verticalGradient(
                                    0f to Blue.copy(alpha = 0.30f),
                                    1f to Blue.copy(alpha = 0.08f),
                                ),
                            )
                            .border(BorderStroke(1.dp, Blue.copy(alpha = 0.42f)), pillShape),
                    )
                    Row(Modifier.fillMaxSize()) {
                        tabs.forEach { tab ->
                            TabItem(
                                tab = tab,
                                active = tab.route == currentRoute,
                                onClick = { onSelect(tab.route) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RowScope.TabItem(tab: TabSpec, active: Boolean, onClick: () -> Unit) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val iconScale by animateFloatAsState(
        targetValue = when {
            pressed -> 0.86f
            active -> 1f
            else -> 0.9f
        },
        animationSpec = spring(dampingRatio = 0.55f, stiffness = Spring.StiffnessMedium),
        label = "tab-icon-scale",
    )
    val iconTint by animateColorAsState(
        targetValue = if (active) Blue2 else tabInactive,
        animationSpec = tween(180),
        label = "tab-icon-tint",
    )
    val labelColor by animateColorAsState(
        targetValue = if (active) Color(0xFFE6ECFF) else tabInactive,
        animationSpec = tween(180),
        label = "tab-label-color",
    )
    val labelAlpha by animateFloatAsState(
        targetValue = if (active) 1f else 0.8f,
        animationSpec = tween(180),
        label = "tab-label-alpha",
    )

    Column(
        Modifier
            .weight(1f)
            .fillMaxHeight()
            .clip(pillShape)
            .clickable(
                interactionSource = interaction,
                indication = null,
                onClick = onClick,
            ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(
            imageVector = tab.icon,
            contentDescription = tab.label,
            tint = iconTint,
            modifier = Modifier
                .size(22.dp)
                .graphicsLayer {
                    scaleX = iconScale
                    scaleY = iconScale
                },
        )
        Spacer(Modifier.height(3.dp))
        Text(
            tab.label.uppercase(),
            style = AppText.meta.copy(fontSize = 8.5.sp, letterSpacing = 0.5.sp),
            color = labelColor.copy(alpha = labelAlpha),
            maxLines = 1,
        )
    }
}

package com.doodletheater.tv.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.story.StoryPlayer

sealed interface Screen {
    data object Home : Screen
    data object AddStar : Screen
    data object DanceParty : Screen
    data object Lab : Screen
    data class Story(val theme: Theme) : Screen
}

/** One activity, a handful of screens; Back always returns home. */
@Composable
fun App(start: Screen = Screen.Home) {
    val context = LocalContext.current
    val api = remember { ServerApi(context.applicationContext) }
    var screen by remember { mutableStateOf(start) }
    BackHandler(enabled = screen != Screen.Home) { screen = Screen.Home }

    when (val s = screen) {
        Screen.Home -> Home(
            api,
            onAddStar = { screen = Screen.AddStar },
            onStory = { screen = Screen.Story(it) },
            onDanceParty = { screen = Screen.DanceParty },
        )
        Screen.AddStar -> AddStar(api)
        Screen.DanceParty -> DanceParty(api)
        Screen.Lab -> PuppetLab()
        is Screen.Story -> StoryPlayer(api, s.theme, onHome = { screen = Screen.Home })
    }
}

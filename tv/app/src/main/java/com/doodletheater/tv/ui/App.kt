package com.doodletheater.tv.ui

import androidx.activity.compose.BackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.story.StoryPlayer
import kotlinx.coroutines.delay

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

    // Bedtime follows the clock (19:00-06:00) unless someone flips the chip on Home.
    // A manual choice holds until the clock itself crosses the boundary, then the schedule takes over again.
    var scheduled by remember { mutableStateOf(isBedtimeHour()) }
    var manual by rememberSaveable { mutableStateOf<Boolean?>(null) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            val now = isBedtimeHour()
            if (now != scheduled) { scheduled = now; manual = null }
        }
    }
    val bedtime = manual ?: scheduled

    // A parent's "stories tonight" limit; every story that starts (including Watch again) counts.
    val tonight = remember { Tonight(context.applicationContext) }
    var limit by remember { mutableStateOf(tonight.limit) }
    var left by remember { mutableStateOf(tonight.left) }
    fun storyStarted() { tonight.markWatched(); left = tonight.left }

    BedtimeOverlay(on = bedtime) {
        when (val s = screen) {
            Screen.Home -> Home(
                api,
                onAddStar = { screen = Screen.AddStar },
                onStory = { screen = Screen.Story(it) },
                onDanceParty = { screen = Screen.DanceParty },
                bedtime = bedtime,
                onToggleBedtime = { manual = !bedtime },
                storyLimit = limit,
                storiesLeft = left,
                onCycleLimit = {
                    val choices = Tonight.CHOICES
                    limit = choices[(choices.indexOf(limit) + 1) % choices.size]
                    tonight.limit = limit; left = tonight.left
                },
            )
            Screen.AddStar -> AddStar(api)
            Screen.DanceParty -> DanceParty(api)
            Screen.Lab -> PuppetLab()
            is Screen.Story -> StoryPlayer(
                api, s.theme, onHome = { screen = Screen.Home },
                allowWatchAgain = { left != 0 },
                bedtime = bedtime,
                onStoryStart = ::storyStarted,
            )
        }
    }
}

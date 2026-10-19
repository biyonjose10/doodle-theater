package com.doodletheater.tv.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.rig.RigStore
import com.doodletheater.tv.stage.Actor
import com.doodletheater.tv.stage.Stage

/**
 * Developer screen: three bundled puppets, D-pad driven.
 * ◀ ▶ choose a puppet · ▲ ▼ choose a move · OK play it · ⏩ walk across.
 */
@Composable
fun PuppetLab() {
    val context = LocalContext.current
    val motions = remember { RigStore.motions(context) }
    val names = remember { motions.keys.toList() }
    val actors = remember {
        listOf("rigs/char1" to 0.2f, "rigs/char3" to 0.5f, "rigs/garlic" to 0.8f).map { (dir, x) ->
            Actor(RigStore.fromAssets(context, dir), motions).apply { this.x = x }
        }
    }
    var selected by remember { mutableIntStateOf(1) }
    var move by remember { mutableIntStateOf(names.indexOf("dance")) }
    val clock = remember { DoubleArray(1) }   // last frame time: written while drawing, read on key press
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }

    Box(
        Modifier
            .fillMaxSize()
            .focusRequester(focus)
            .focusable()
            .onKeyEvent { e ->
                if (e.type != KeyEventType.KeyDown) return@onKeyEvent false
                val a = actors[selected]
                val now = clock[0]
                when (e.key) {
                    Key.DirectionLeft -> selected = (selected + actors.size - 1) % actors.size
                    Key.DirectionRight -> selected = (selected + 1) % actors.size
                    Key.DirectionUp -> move = (move + names.size - 1) % names.size
                    Key.DirectionDown -> move = (move + 1) % names.size
                    Key.DirectionCenter, Key.Enter, Key.NumPadEnter -> a.play(names[move], now)
                    Key.MediaFastForward, Key.MediaPlayPause -> a.walkTo(if (a.x < 0.5f) 0.8f else 0.2f, now)
                    else -> return@onKeyEvent false
                }
                true
            },
    ) {
        Stage(actors, showFps = true, spotlight = actors[selected], onFrame = { clock[0] = it })
        Text(
            "◀ ▶ puppet    ▲ ▼ move: ${names[move]}    OK play    ⏯ walk across",
            color = Color.White, fontSize = 11.sp,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 14.dp)
                .background(Color(0x99000000), RoundedCornerShape(12.dp))
                .padding(horizontal = 12.dp, vertical = 5.dp),
        )
    }
}

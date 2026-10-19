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
import androidx.compose.runtime.mutableStateListOf
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.rig.RigStore
import com.doodletheater.tv.stage.Actor
import com.doodletheater.tv.stage.Stage

private val PARTY_MOVES = listOf("jump", "dance", "spin", "cheer", "wave", "run")

/**
 * Every star on stage at once, no AI needed. ◀ ▶ picks a star, OK makes them do the next
 * trick, ⏯ starts everyone dancing. Works offline, so there is always something to play.
 */
@Composable
fun DanceParty(api: ServerApi) {
    val context = LocalContext.current
    val motions = remember { RigStore.motions(context) }
    val actors = remember { mutableStateListOf<Actor>() }
    val clock = remember { DoubleArray(1) }
    val paint = remember { labelPaint(context, 36f) }
    var selected by remember { mutableIntStateOf(0) }
    var trick by remember { mutableIntStateOf(0) }
    val focus = remember { FocusRequester() }

    LaunchedEffect(Unit) {
        val cast = runCatching { api.cast() }.getOrDefault(emptyList()).takeLast(5)
        val loaded = if (cast.isNotEmpty()) {
            cast.mapNotNull { m -> runCatching { api.rig(m) }.getOrNull() }
        } else {
            listOf("rigs/char1", "rigs/char3", "rigs/garlic").map { RigStore.fromAssets(context, it) }
        }
        loaded.forEachIndexed { i, rig ->
            actors.add(Actor(rig, motions).apply {
                label = rig.name
                x = (i + 1f) / (loaded.size + 1f)
                heightFraction = if (loaded.size > 3) 0.36f else 0.44f
                feetY = 0.88f
            })
        }
        focus.requestFocus()
    }

    Box(
        Modifier.fillMaxSize().focusRequester(focus).focusable().onKeyEvent { e ->
            if (e.type != KeyEventType.KeyDown || actors.isEmpty()) return@onKeyEvent false
            val now = clock[0]
            when (e.key) {
                Key.DirectionLeft -> selected = (selected + actors.size - 1) % actors.size
                Key.DirectionRight -> selected = (selected + 1) % actors.size
                Key.DirectionCenter, Key.Enter -> {
                    actors[selected].play(PARTY_MOVES[trick % PARTY_MOVES.size], now); trick++
                }
                Key.MediaPlayPause, Key.MediaPlay -> actors.forEach { it.play("dance", now) }
                else -> return@onKeyEvent false
            }
            true
        },
    ) {
        Stage(actors, spotlight = actors.getOrNull(selected), labelPaint = paint, onFrame = { clock[0] = it })
        Text(
            "Dance party!   ◀ ▶ pick a star   OK do a trick   ⏯ everybody dance",
            fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Color.White,
            modifier = Modifier.align(Alignment.TopCenter).padding(top = 16.dp)
                .background(Color(0x99000000), RoundedCornerShape(12.dp)).padding(horizontal = 13.dp, vertical = 4.dp),
        )
    }
}

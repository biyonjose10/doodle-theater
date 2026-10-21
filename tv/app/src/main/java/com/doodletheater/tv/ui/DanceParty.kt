package com.doodletheater.tv.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.rig.RigStore
import com.doodletheater.tv.stage.Actor
import com.doodletheater.tv.stage.Stage
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

private val PARTY_MOVES = listOf("jump", "dance", "spin", "cheer", "wave", "run")
private const val FEET = 0.88f
private const val LABEL_PX = 36f

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
    val paint = remember { labelPaint(context, LABEL_PX) }
    var selected by remember { mutableIntStateOf(0) }
    var trick by remember { mutableIntStateOf(0) }
    var moves by remember { mutableIntStateOf(0) }       // bumps on every trick, so the tag can say "Now dancing"
    var dancing by remember { mutableStateOf(false) }
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
                feetY = FEET
            })
        }
        focus.requestFocus()
    }
    LaunchedEffect(moves) {
        if (moves == 0) return@LaunchedEffect
        dancing = true
        delay(2600)
        dancing = false
    }

    Box(
        Modifier.fillMaxSize().focusRequester(focus).focusable().onKeyEvent { e ->
            if (e.type != KeyEventType.KeyDown || actors.isEmpty()) return@onKeyEvent false
            val now = clock[0]
            when (e.key) {
                Key.DirectionLeft -> { selected = (selected + actors.size - 1) % actors.size; dancing = false }
                Key.DirectionRight -> { selected = (selected + 1) % actors.size; dancing = false }
                Key.DirectionCenter, Key.Enter -> {
                    actors[selected].play(PARTY_MOVES[trick % PARTY_MOVES.size], now); trick++; moves++
                }
                Key.MediaPlayPause, Key.MediaPlay -> { actors.forEach { it.play("dance", now) }; moves++ }
                else -> return@onKeyEvent false
            }
            true
        },
    ) {
        val star = actors.getOrNull(selected)
        val spotX by animateFloatAsState(star?.x ?: 0.5f, tween(450), label = "spot")
        Canvas(Modifier.fillMaxSize()) {
            paperStage()
            if (star != null) spotlight(spotX, FEET, poolScale = star.heightFraction / 0.5f * 0.95f, coneAlpha = 0.8f)
        }
        Stage(actors, transparent = true, labelPaint = paint, onFrame = { clock[0] = it })
        if (star != null) {
            StarTag(
                x = spotX,
                // Same maths as Actor.labelBox: the tag sits just above the paper name tag.
                labelTopFraction = star.feetY - star.heightFraction,
                labelPx = LABEL_PX,
            ) {
                if (dancing) TagPill("♪ Now dancing", color = Ink.accent, size = 11)
                else TagPill("★ Selected", size = 11)
            }
        }
        Row(
            Modifier.align(Alignment.TopCenter).padding(top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Dance party!", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 20.sp, color = Ink.ink)
            Spacer(Modifier.width(14.dp))
            KeyHint("◀ ▶", "pick a star")
            Spacer(Modifier.width(8.dp))
            KeyHint("OK", "do a trick")
            Spacer(Modifier.width(8.dp))
            KeyHint("⏯", "everybody dance")
        }
    }
}

/**
 * Places [content] centred at stage fraction [x], with its bottom just above the puppet's name
 * tag (whose top is labelTop * height - 1.5 * labelPx, mirroring Actor.labelBox).
 */
@Composable
private fun StarTag(x: Float, labelTopFraction: Float, labelPx: Float, content: @Composable () -> Unit) {
    Layout(content, Modifier.fillMaxSize()) { measurables, constraints ->
        val p = measurables.first().measure(constraints.copy(minWidth = 0, minHeight = 0))
        layout(constraints.maxWidth, constraints.maxHeight) {
            val nameTop = labelTopFraction * constraints.maxHeight - labelPx * 1.5f
            val gap = 4.dp.toPx()
            p.place(
                (x * constraints.maxWidth - p.width / 2f).roundToInt(),
                (nameTop - gap - p.height).roundToInt(),
            )
        }
    }
}

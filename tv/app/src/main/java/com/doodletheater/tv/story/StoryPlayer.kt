package com.doodletheater.tv.story

import android.media.session.MediaSession
import android.media.session.PlaybackState
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.Crossfade
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.net.CastMember
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.rig.RigStore
import com.doodletheater.tv.stage.Actor
import com.doodletheater.tv.stage.Stage
import com.doodletheater.tv.ui.Baloo
import com.doodletheater.tv.ui.Ink
import com.doodletheater.tv.ui.Theme
import com.doodletheater.tv.ui.TvCard
import com.doodletheater.tv.ui.labelPaint
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import org.json.JSONObject

private sealed interface Phase {
    data class Loading(val message: String) : Phase
    data object Title : Phase
    data object Playing : Phase
    data class Choosing(val choice: Choice) : Phase
    data object Ended : Phase
    data class Failed(val message: String) : Phase
}

private val LOOPING = setOf("walk", "run", "dance", "wave", "cheer", "scared", "idle")

/**
 * Plays an episode: backdrops, puppets, narration with read-along captions, word-timed
 * stage directions, and a choice the child makes with the remote.
 * ◀ ▶ picks a star and OK makes them jump at any moment; ⏯ / "Alexa, pause" pauses.
 */
@Composable
fun StoryPlayer(api: ServerApi, theme: Theme, onHome: () -> Unit) {
    val context = LocalContext.current
    val motions = remember { RigStore.motions(context) }
    val narrator = remember { Narrator(context) }
    val paint = remember { labelPaint(context, 38f) }
    val clock = remember { DoubleArray(1) }
    val actors = remember { mutableStateListOf<Actor>() }
    val byId = remember { mutableMapOf<String, Actor>() }
    val backdrops = remember { mutableMapOf<String, ImageBitmap>() }
    var phase by remember { mutableStateOf<Phase>(Phase.Loading("Writing tonight's story…")) }
    var episode by remember { mutableStateOf<Episode?>(null) }
    var backdrop by remember { mutableStateOf<String?>(null) }
    var caption by remember { mutableStateOf<Beat?>(null) }
    var speaker by remember { mutableStateOf<String?>(null) }
    var highlight by remember { mutableStateOf(-1 to -1) }
    var paused by remember { mutableStateOf(false) }
    var selected by remember { mutableIntStateOf(0) }
    var run by remember { mutableIntStateOf(0) }          // bump to replay
    val picked = remember { arrayOfNulls<CompletableDeferred<String>>(1) }
    val keys = remember { FocusRequester() }
    val firstOption = remember { FocusRequester() }

    // Media session: Fire TV routes "Alexa, pause/resume" and the remote's ⏯ here.
    DisposableEffect(Unit) {
        val session = MediaSession(context, "DoodleTheater")
        fun state(playing: Boolean) = session.setPlaybackState(PlaybackState.Builder()
            .setActions(PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or PlaybackState.ACTION_PLAY_PAUSE)
            .setState(if (playing) PlaybackState.STATE_PLAYING else PlaybackState.STATE_PAUSED, 0, 1f).build())
        session.setCallback(object : MediaSession.Callback() {
            override fun onPlay() { paused = false; narrator.resume(); state(true) }
            override fun onPause() { paused = true; narrator.pause(); state(false) }
            override fun onStop() { paused = true; narrator.stop(); state(false) }
        })
        state(true)
        session.isActive = true
        onDispose { session.release(); narrator.shutdown() }
    }

    fun slotX(i: Int, n: Int) = if (n == 1) 0.5f else 0.2f + i * (0.6f / (n - 1))

    fun perform(a: Action, now: Double) {
        val actor = byId[a.who] ?: return
        val i = actors.indexOf(actor)
        val home = slotX(i, actors.size)
        when {
            a.act == "enter" -> if (actor.offstage) actor.walkTo(home, now, arrive = "wave")
            a.act == "exit" -> actor.walkTo(if (actor.x < 0.5f) -0.25f else 1.25f, now)
            actor.offstage -> actor.walkTo(home, now, arrive = a.act)
            a.act == "walk" || a.act == "run" -> {
                val to = (home + if (actor.x <= home) 0.08f else -0.08f).coerceIn(0.12f, 0.88f)
                actor.walkTo(to, now, run = a.act == "run")
            }
            a.act in LOOPING -> actor.playFor(a.act, now, 2.4)
            else -> actor.play(a.act, now)
        }
    }

    suspend fun waitWhilePaused() = snapshotFlow { paused }.first { !it }

    suspend fun beat(b: Beat, ep: Episode) {
        caption = b; highlight = -1 to -1
        speaker = ep.cast.firstOrNull { it.id == b.speaker }?.name
        b.actions.filter { it.atWord == null }.forEach { perform(it, clock[0]) }
        val pending = b.actions.filter { it.atWord != null }.toMutableList()
        val pitch = ep.cast.firstOrNull { it.id == b.speaker }?.pitch ?: 1.0f
        var words = 0
        val t0 = System.nanoTime()
        do {
            waitWhilePaused()
            val onWord: (Int, Int) -> Unit = word@{ s, e ->
                if (s < 0 || e <= s || e > b.text.length) return@word   // engines occasionally report junk ranges
                words++
                highlight = s to e
                val w = b.text.substring(s, e).lowercase().trim { !it.isLetter() && it != '\'' }
                val hit = pending.firstOrNull { it.atWord!!.lowercase() == w }
                if (hit != null) { pending.remove(hit); perform(hit, clock[0]) }
            }
            if (b.audio != null) narrator.play(api.url(b.audio), b.marks, onWord)
            else narrator.speak(b.text, pitch, if (b.speaker == "narrator") 0.92f else 1.0f, onWord)
        } while (paused)
        android.util.Log.d("DoodleStory", "beat ${(System.nanoTime() - t0) / 1_000_000} ms, $words word events, " +
            "${pending.size} late actions: ${b.text.take(40)}")
        pending.forEach { perform(it, clock[0]) }
        highlight = -1 to -1
        delay(450)
    }

    LaunchedEffect(run) {
        val ep = episode ?: runCatching {
            Episode.parse(api.json("/api/story", "POST", JSONObject().put("theme", theme.id)).toString())
        }.getOrElse { phase = Phase.Failed("Couldn't write a story: ${it.message}"); return@LaunchedEffect }
        if (episode == null) {
            phase = Phase.Loading("Calling the stars to the stage…")
            ep.cast.forEachIndexed { i, s ->
                val rig = runCatching { api.rig(CastMember(s.id, s.name, "")) }.getOrNull() ?: return@forEachIndexed
                val a = Actor(rig, motions).apply {
                    label = s.name; heightFraction = if (ep.cast.size > 2) 0.34f else 0.4f; feetY = 0.86f
                    x = if (i % 2 == 0) -0.2f else 1.2f
                }
                actors.add(a); byId[s.id] = a
            }
            for (sc in ep.scenes.values) {
                if (sc.backdrop !in backdrops) runCatching { api.image("/static/backdrops/${sc.backdrop}.jpg") }
                    .onSuccess { backdrops[sc.backdrop] = it }
            }
            narrator.init()
            episode = ep
        } else {
            actors.forEachIndexed { i, a -> a.x = if (i % 2 == 0) -0.2f else 1.2f; a.play("idle", clock[0]) }
        }
        phase = Phase.Title
        backdrop = ep.scenes.getValue("start").backdrop
        narrator.speak(ep.title, 1.0f, 0.9f) { _, _ -> }
        delay(400)
        phase = Phase.Playing
        keys.requestFocus()
        var scene: Scene? = ep.scenes.getValue("start")
        while (scene != null) {
            backdrop = scene.backdrop
            for (b in scene.beats) beat(b, ep)
            val choice = scene.choice
            scene = if (choice != null) {
                caption = null
                phase = Phase.Choosing(choice)
                val wait = CompletableDeferred<String>().also { picked[0] = it }
                narrator.speak("${choice.prompt} ${choice.options[0].label}, or ${choice.options[1].label}?", 1.0f, 0.92f) { _, _ -> }
                val next = wait.await()
                phase = Phase.Playing
                keys.requestFocus()
                ep.scenes[next]
            } else null
        }
        caption = null
        actors.forEach { it.playFor("cheer", clock[0], 3.0) }
        phase = Phase.Ended
        narrator.speak("The end!", 1.1f, 0.9f) { _, _ -> }
    }

    LaunchedEffect(phase) {
        if (phase is Phase.Choosing || phase == Phase.Ended) runCatching { delay(100); firstOption.requestFocus() }
    }

    Box(
        Modifier.fillMaxSize().background(Ink.paper).focusRequester(keys).focusable()
            .onPreviewKeyEvent { e ->
                if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                if (e.key == Key.MediaPlayPause || e.key == Key.MediaPause || e.key == Key.MediaPlay) {
                    paused = !paused; if (paused) narrator.pause() else narrator.resume(); return@onPreviewKeyEvent true
                }
                if (phase != Phase.Playing || actors.isEmpty()) return@onPreviewKeyEvent false
                when (e.key) {
                    Key.DirectionLeft -> selected = (selected + actors.size - 1) % actors.size
                    Key.DirectionRight -> selected = (selected + 1) % actors.size
                    Key.DirectionCenter, Key.Enter -> actors[selected].play("jump", clock[0])
                    else -> return@onPreviewKeyEvent false
                }
                true
            },
    ) {
        Crossfade(backdrop, label = "backdrop") { name ->
            backdrops[name]?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
        }
        Stage(actors, transparent = true, spotlight = if (phase == Phase.Playing) actors.getOrNull(selected) else null,
            labelPaint = paint, onFrame = { clock[0] = it })

        caption?.let { b ->
            Column(
                Modifier.align(Alignment.TopCenter).padding(top = 16.dp).widthIn(max = 780.dp)
                    .background(Color(0xEEFFFBF0), RoundedCornerShape(18.dp)).padding(horizontal = 22.dp, vertical = 10.dp),
            ) {
                speaker?.let {
                    Text(it, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 13.sp, color = Ink.accent)
                }
                val (s, e) = highlight
                Text(
                    buildAnnotatedString {
                        if (s in 0 until e && e <= b.text.length) {
                            append(b.text.substring(0, s))
                            withStyle(SpanStyle(background = Color(0xFFFFD84D), color = Ink.ink)) { append(b.text.substring(s, e)) }
                            append(b.text.substring(e))
                        } else append(b.text)
                    },
                    fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 21.sp, color = Ink.ink, lineHeight = 28.sp,
                )
            }
        }

        when (val p = phase) {
            is Phase.Loading -> Banner(p.message, "Dance while you wait!")
            is Phase.Failed -> Banner(p.message, "Press Back to go home")
            Phase.Title -> episode?.let { Banner(it.title, theme.title) }
            is Phase.Choosing -> ChoiceCards(p.choice, firstOption) { picked[0]?.complete(it) }
            Phase.Ended -> EndCards(firstOption, onAgain = { run++ }, onHome = onHome)
            Phase.Playing -> {}
        }
        AnimatedVisibility(paused, enter = fadeIn(), exit = fadeOut(), modifier = Modifier.align(Alignment.Center)) {
            Text("⏸  Paused", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 34.sp, color = Color.White,
                modifier = Modifier.background(Color(0xAA000000), RoundedCornerShape(20.dp)).padding(horizontal = 30.dp, vertical = 10.dp))
        }
    }
}

@Composable
private fun Banner(title: String, subtitle: String) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            Modifier.background(Color(0xEEFFFBF0), RoundedCornerShape(26.dp)).padding(horizontal = 40.dp, vertical = 22.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(title, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 34.sp, color = Ink.ink, textAlign = TextAlign.Center)
            Text(subtitle, fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 16.sp, color = Ink.soft)
        }
    }
}

@Composable
private fun ChoiceCards(choice: Choice, first: FocusRequester, onPick: (String) -> Unit) {
    Column(Modifier.fillMaxSize().padding(bottom = 36.dp), verticalArrangement = Arrangement.Bottom,
        horizontalAlignment = Alignment.CenterHorizontally) {
        Text(choice.prompt, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 26.sp, color = Color.White,
            modifier = Modifier.background(Color(0xAA2B2B3A), RoundedCornerShape(16.dp)).padding(horizontal = 20.dp, vertical = 4.dp))
        Spacer(Modifier.height(14.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
            choice.options.forEachIndexed { i, o ->
                TvCard(onClick = { onPick(o.next) }, tint = if (i == 0) Ink.accent else Ink.blue, width = 230, height = 90,
                    modifier = if (i == 0) Modifier.focusRequester(first) else Modifier) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text((if (i == 0) "◀  " else "") + o.label + (if (i == 1) "  ▶" else ""), fontFamily = Baloo,
                            fontWeight = FontWeight.ExtraBold, fontSize = 20.sp, color = Color.White, textAlign = TextAlign.Center)
                    }
                }
            }
        }
    }
}

@Composable
private fun EndCards(first: FocusRequester, onAgain: () -> Unit, onHome: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(top = 40.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text("The End", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 56.sp, color = Ink.ink,
            modifier = Modifier.background(Color(0xEEFFFBF0), RoundedCornerShape(26.dp)).padding(horizontal = 40.dp))
        Spacer(Modifier.height(16.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            TvCard(onClick = onAgain, tint = Ink.accent, width = 170, height = 64, modifier = Modifier.focusRequester(first)) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Watch again", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = Color.White)
                }
            }
            TvCard(onClick = onHome, tint = Ink.blue, width = 170, height = 64) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Home", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = Color.White)
                }
            }
        }
    }
}

package com.doodletheater.tv.story

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.ui.Baloo
import com.doodletheater.tv.ui.Ink
import com.doodletheater.tv.ui.TvCard

/** How dark the stage gets at the end of a bedtime story (alpha of the night overlay). */
const val NIGHT_ALPHA = 0.7f

/** "Pip", "Pip and Max", "Pip, Max and Luna". */
fun joinNames(names: List<String>): String = when (names.size) {
    0 -> ""
    1 -> names[0]
    else -> names.dropLast(1).joinToString(", ") + " and " + names.last()
}

/**
 * The stage going to sleep: a dark-blue wash at [darkness] (0 → [NIGHT_ALPHA]), a moon,
 * and a few slowly twinkling stars that fade in with it. Slow sine-ish fades only, no flashing.
 */
@Composable
fun NightSky(darkness: Float) {
    if (darkness <= 0f) return
    val sky = (darkness / NIGHT_ALPHA).coerceIn(0f, 1f)
    Box(Modifier.fillMaxSize().background(Ink.night.copy(alpha = darkness)))
    val twinkle = rememberInfiniteTransition(label = "twinkle")
    // (x, y as fractions of the stage, period ms, start offset ms, size sp): high in the sky, clear of the puppets.
    val stars = listOf(
        floatArrayOf(0.12f, 0.10f, 3200f, 0f, 22f),
        floatArrayOf(0.27f, 0.22f, 4100f, 900f, 16f),
        floatArrayOf(0.44f, 0.08f, 3600f, 1700f, 18f),
        floatArrayOf(0.62f, 0.18f, 4400f, 400f, 14f),
        floatArrayOf(0.90f, 0.30f, 3800f, 2300f, 18f),
        floatArrayOf(0.06f, 0.34f, 4600f, 1300f, 14f),
    )
    BoxWithConstraints(Modifier.fillMaxSize().alpha(sky)) {
        // Right of the Goodnight card (max 720 dp of a 960 dp screen), so it stays visible.
        Text("🌙", fontSize = 50.sp, lineHeight = 56.sp,
            modifier = Modifier.offset(x = maxWidth * 0.89f, y = maxHeight * 0.05f))
        stars.forEach { (x, y, period, start, size) ->
            val a by twinkle.animateFloat(
                initialValue = 0.25f, targetValue = 0.95f, label = "star",
                animationSpec = infiniteRepeatable(tween(period.toInt(), easing = FastOutSlowInEasing),
                    RepeatMode.Reverse, StartOffset(start.toInt())),
            )
            Text("✨", fontSize = size.sp, lineHeight = (size + 4).sp,
                modifier = Modifier.offset(x = maxWidth * x, y = maxHeight * y).alpha(a))
        }
    }
}

/**
 * The card after the wind-down: "Goodnight!", the stars by name, then 🔁 Watch again / 🏠 Home.
 * [allowWatchAgain] = false (a parent's "stories tonight" limit) hides Watch again, focuses Home,
 * and says that was the last story.
 */
@Composable
fun GoodnightCard(
    names: List<String>,
    first: FocusRequester,
    onAgain: () -> Unit,
    onHome: () -> Unit,
    allowWatchAgain: Boolean = true,
) {
    // Short enough to stay above the puppets' name tags; wide enough that four names fit on one line.
    Box(Modifier.fillMaxSize().padding(top = 18.dp), contentAlignment = Alignment.TopCenter) {
        Column(
            Modifier.widthIn(min = 420.dp, max = 720.dp)
                .border(2.dp, Ink.line, RoundedCornerShape(24.dp))
                .background(Ink.paper, RoundedCornerShape(24.dp))
                .padding(horizontal = 32.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Goodnight!", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 48.sp,
                lineHeight = 54.sp, color = Ink.ink)
            if (names.isNotEmpty()) {
                Text("Sleep tight, ${joinNames(names)} ✨", fontFamily = Baloo, fontWeight = FontWeight.Bold,
                    fontSize = 20.sp, lineHeight = 26.sp, color = Ink.soft, textAlign = TextAlign.Center)
            }
            if (!allowWatchAgain) {
                Spacer(Modifier.height(4.dp))
                Text("That's all the stories for tonight.", fontFamily = Baloo, fontWeight = FontWeight.Bold,
                    fontSize = 18.sp, lineHeight = 24.sp, color = Ink.accent, textAlign = TextAlign.Center)
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                if (allowWatchAgain) {
                    TvCard(onClick = onAgain, tint = Ink.accent, width = 170, height = 60, modifier = Modifier.focusRequester(first)) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("🔁  Watch again", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = Color.White)
                        }
                    }
                }
                TvCard(onClick = onHome, tint = Ink.blue, width = 170, height = 60,
                    modifier = if (allowWatchAgain) Modifier else Modifier.focusRequester(first)) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("🏠  Home", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = Color.White)
                    }
                }
            }
        }
    }
}

package com.doodletheater.tv.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import java.util.Calendar

/**
 * The clock's idea of bedtime: 19:00 up to (not including) 06:00, local device time.
 * Calendar rather than java.time, because minSdk 25 (Fire OS 6) predates java.time.
 */
fun isBedtimeHour(hour: Int = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)): Boolean = hour >= 19 || hour < 6

private val Amber = Color(0xFFFF9A3C)

/** Deeper, dusky paper for Home while bedtime is on. */
val DuskPaper = Color(0xFFF1DEC0)
val DuskPaper2 = Color(0xFFE6CCA6)

/**
 * Wraps every screen. When [on], a warm amber wash plus a gentle dim is painted over whatever
 * the screen draws. It is drawn in the same layer as the content (no extra node), so it can never
 * take focus or swallow a key press.
 */
@Composable
fun BedtimeOverlay(on: Boolean, content: @Composable () -> Unit) {
    val t by animateFloatAsState(if (on) 1f else 0f, tween(900), label = "bedtime")
    Box(
        Modifier.fillMaxSize().drawWithContent {
            drawContent()
            if (t > 0f) {
                drawRect(Amber.copy(alpha = 0.14f * t))
                drawRect(Color.Black.copy(alpha = 0.22f * t))
            }
        },
    ) { content() }
}

/** "🌙 Bedtime" toggle for the Home header; focus looks like the TvCards (ink outline, warm glow). */
@Composable
fun BedtimeChip(on: Boolean, onToggle: () -> Unit, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(50)
    Surface(
        onClick = onToggle,
        modifier = modifier,
        shape = ClickableSurfaceDefaults.shape(shape),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (on) Ink.night else Ink.card,
            focusedContainerColor = if (on) Ink.night else Ink.card,
            pressedContainerColor = if (on) Ink.night else Ink.card,
            contentColor = if (on) Color.White else Ink.ink,
            focusedContentColor = if (on) Color.White else Ink.ink,
        ),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
        border = ClickableSurfaceDefaults.border(
            border = Border(BorderStroke(2.dp, Ink.line), shape = shape),
            focusedBorder = Border(BorderStroke(3.dp, if (on) Color(0xFFFFC26B) else Ink.ink), shape = shape),
        ),
        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(Ink.accent.copy(alpha = 0.55f), 10.dp)),
    ) {
        Row(Modifier.padding(start = 10.dp, end = 5.dp, top = 3.dp, bottom = 3.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("🌙 Bedtime", fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 12.sp,
                color = if (on) Color.White else Ink.ink)
            Spacer(Modifier.width(6.dp))
            // A little on/off switch label, so the state never relies on colour alone.
            Box(
                Modifier.background(if (on) Color(0xFFFFC26B) else Ink.line, RoundedCornerShape(50))
                    .padding(horizontal = 7.dp),
            ) {
                Text(if (on) "ON" else "OFF", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 11.sp,
                    color = if (on) Ink.night else Ink.soft)
            }
        }
    }
}

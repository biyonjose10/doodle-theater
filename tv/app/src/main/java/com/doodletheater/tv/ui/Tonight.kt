package com.doodletheater.tv.ui

import android.content.Context
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
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
 * "Stories tonight": a parent's limit on how many stories play per day (0 = no limit).
 * The count resets each morning at 06:00, so a late story still counts towards that night.
 */
class Tonight(context: Context) {
    private val prefs = context.getSharedPreferences("tonight", Context.MODE_PRIVATE)

    var limit: Int
        get() = prefs.getInt("limit", 0)
        set(v) { prefs.edit().putInt("limit", v).apply() }

    val watched: Int
        get() = if (prefs.getString("night", "") == night()) prefs.getInt("watched", 0) else 0

    /** Stories still allowed tonight, or null when there is no limit. */
    val left: Int?
        get() = limit.takeIf { it > 0 }?.let { (it - watched).coerceAtLeast(0) }

    fun markWatched() {
        prefs.edit().putString("night", night()).putInt("watched", watched + 1).apply()
    }

    /** The calendar day a night belongs to: hours before 06:00 count as the previous evening. */
    private fun night(): String {
        val c = Calendar.getInstance().apply { add(Calendar.HOUR_OF_DAY, -6) }
        return "${c.get(Calendar.YEAR)}-${c.get(Calendar.DAY_OF_YEAR)}"
    }

    companion object {
        val CHOICES = listOf(0, 1, 2, 3)
        fun label(limit: Int) = if (limit == 0) "no limit" else "$limit"
    }
}

/** "📖 Stories tonight: 2" for the Home header; OK cycles no limit → 1 → 2 → 3. */
@Composable
fun StoriesChip(limit: Int, left: Int?, onCycle: () -> Unit, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(50)
    Surface(
        onClick = onCycle,
        modifier = modifier,
        shape = ClickableSurfaceDefaults.shape(shape),
        colors = ClickableSurfaceDefaults.colors(containerColor = Ink.card, focusedContainerColor = Ink.card,
            contentColor = Ink.ink, focusedContentColor = Ink.ink),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
        border = ClickableSurfaceDefaults.border(
            border = Border(BorderStroke(2.dp, Ink.line), shape = shape),
            focusedBorder = Border(BorderStroke(3.dp, Ink.ink), shape = shape),
        ),
        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(Ink.accent.copy(alpha = 0.55f), 10.dp)),
    ) {
        val text = if (limit == 0) "📖 Stories tonight: no limit" else "📖 Stories tonight: $limit  ($left left)"
        Text(text, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 12.sp,
            color = if (left == 0) Color(0xFF9A3A22) else Ink.ink,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 3.dp))
    }
}

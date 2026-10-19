package com.doodletheater.tv.stage

import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize

/** Seconds on the frame clock: the one time base every actor animates against. */
fun nowSeconds(frameNanos: Long) = frameNanos / 1_000_000_000.0

/** Rolling frames-per-second over the last second, for the on-screen performance readout. */
class FpsMeter {
    private val stamps = ArrayDeque<Long>()
    fun tick(nanos: Long): Int {
        stamps.addLast(nanos)
        while (stamps.isNotEmpty() && nanos - stamps.first() > 1_000_000_000L) stamps.removeFirst()
        return stamps.size
    }
}

/**
 * The theatre: a backdrop and any number of puppets, redrawn every vsync.
 * Only the draw phase reads the frame clock, so nothing recomposes per frame.
 */
@Composable
fun Stage(
    actors: List<Actor>,
    modifier: Modifier = Modifier,
    backdrop: ImageBitmap? = null,
    showFps: Boolean = false,
    spotlight: Actor? = null,
    onFrame: (Double) -> Unit = {},
) {
    var frame by remember { mutableLongStateOf(0L) }
    val fps = remember { FpsMeter() }
    val hud = remember {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.WHITE; textSize = 28f; typeface = Typeface.MONOSPACE
            setShadowLayer(4f, 0f, 0f, android.graphics.Color.BLACK)
        }
    }
    LaunchedEffect(Unit) { while (true) withFrameNanos { frame = it } }

    Canvas(modifier.fillMaxSize()) {
        val f = frame
        if (f == 0L) return@Canvas
        val now = nowSeconds(f)
        onFrame(now)
        if (backdrop != null) {
            drawImage(backdrop, dstOffset = IntOffset.Zero, dstSize = IntSize(size.width.toInt(), size.height.toInt()))
        } else {
            paperBackdrop()
        }
        spotlight?.let { a ->
            drawOval(
                Brush.radialGradient(listOf(Color(0x55FFF2B0), Color.Transparent),
                    center = Offset(a.x * size.width, a.feetY * size.height), radius = size.height * 0.18f),
                topLeft = Offset(a.x * size.width - size.height * 0.2f, a.feetY * size.height - size.height * 0.05f),
                size = Size(size.height * 0.4f, size.height * 0.1f),
            )
        }
        drawIntoCanvas { c ->
            for (a in actors) {
                a.update(now)
                a.draw(c.nativeCanvas, size.width, size.height, now)
            }
            if (showFps) c.nativeCanvas.drawText("${fps.tick(f)} fps  ${actors.size} puppets", 24f, 44f, hud)
        }
    }
}

/** Default backdrop: warm paper with a crayon-blue floor line. */
private fun DrawScope.paperBackdrop() {
    drawRect(Brush.verticalGradient(listOf(Color(0xFFFFF8E7), Color(0xFFF5E6C8))))
    val floor = size.height * 0.9f
    drawRect(Color(0xFFE9D3A8), topLeft = Offset(0f, floor), size = Size(size.width, size.height - floor))
    drawLine(Color(0xFF5B7BD5), Offset(0f, floor), Offset(size.width, floor), strokeWidth = 6f)
}

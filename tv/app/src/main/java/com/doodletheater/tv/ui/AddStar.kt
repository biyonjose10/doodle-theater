package com.doodletheater.tv.ui

import android.content.Context
import android.graphics.Paint
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.res.ResourcesCompat
import androidx.tv.material3.Text
import com.doodletheater.tv.R
import com.doodletheater.tv.net.Pairing
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.rig.RigStore
import com.doodletheater.tv.stage.Actor
import com.doodletheater.tv.stage.Stage
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import com.doodletheater.tv.net.CastMember

/** Name labels drawn above puppets' heads, in the app's rounded crayon font. */
fun labelPaint(context: Context, size: Float = 40f) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
    typeface = ResourcesCompat.getFont(context, R.font.baloo2)
    textSize = size
    textAlign = Paint.Align.CENTER
    color = android.graphics.Color.rgb(43, 43, 58)
    isFakeBoldText = true
}

private val SLOTS = listOf(0.5f, 0.24f, 0.76f, 0.37f, 0.63f)
private const val FEET = 0.86f

/**
 * "Add a star": a QR code for the parent's phone on the left; on the right a stage where each
 * new drawing walks in from the wings, into a warm spotlight, and waves the moment the phone sends it.
 */
@Composable
fun AddStar(api: ServerApi) {
    val context = LocalContext.current
    val motions = remember { RigStore.motions(context) }
    val actors = remember { mutableStateListOf<Actor>() }
    val clock = remember { DoubleArray(1) }
    var pairing by remember { mutableStateOf<Pairing?>(null) }
    var status by remember { mutableStateOf("Getting a code…") }
    var arrived by remember { mutableStateOf<String?>(null) }
    var arrivals by remember { mutableIntStateOf(0) }
    var spotX by remember { mutableStateOf(SLOTS[0]) }
    val paint = remember { labelPaint(context) }
    val scope = rememberCoroutineScope()
    var samplesBusy by remember { mutableStateOf(false) }

    /** A new star walks in from the wings into the spotlight and waves. */
    suspend fun arrive(member: CastMember) {
        val rig = runCatching { api.rig(member) }.getOrNull() ?: return
        val actor = Actor(rig, motions).apply {
            label = member.name
            x = 1.15f
            heightFraction = 0.5f
            feetY = FEET
        }
        if (actors.size >= SLOTS.size) actors.removeAt(0)
        actors.add(actor)
        val slot = SLOTS[(actors.size - 1) % SLOTS.size]
        actor.walkTo(slot, clock[0], arrive = "wave")
        spotX = slot            // the light swings over to wherever the newcomer is heading
        arrived = member.name
        arrivals++
    }

    // No drawing to hand: the bundled sample stars walk in one after another, like phone arrivals.
    fun useSamples() {
        if (samplesBusy) return
        samplesBusy = true
        status = "Fetching the sample stars…"
        scope.launch {
            runCatching { api.addSamples() }
                .onSuccess { added ->
                    if (added.isEmpty()) status = "The sample stars are already in your cast!"
                    for (m in added) { arrive(m); delay(1500) }
                }
                .onFailure { status = "Can't reach the Doodle Theater server. Is the laptop on?" }
            samplesBusy = false
        }
    }

    LaunchedEffect(Unit) {
        val p = runCatching { api.pair() }.getOrElse {
            status = "Can't reach the Doodle Theater server. Is the laptop on?"; return@LaunchedEffect
        }
        pairing = p
        status = "Waiting for a drawing…"
        var after = 0
        while (true) {
            val news = runCatching { api.events(p.code, after) }.getOrDefault(emptyList())
            for ((n, member) in news) {
                after = n
                arrive(member)
            }
            delay(1000)
        }
    }

    Row(Modifier.fillMaxSize().background(Ink.paper)) {
        Column(
            Modifier.width(310.dp).fillMaxHeight().padding(horizontal = 24.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Add a star!", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp, color = Ink.ink)
            Spacer(Modifier.height(6.dp))
            Box(
                Modifier.size(196.dp).clip(RoundedCornerShape(16.dp)).background(Ink.card)
                    .border(BorderStroke(3.dp, Ink.ink), RoundedCornerShape(16.dp)).padding(11.dp),
                contentAlignment = Alignment.Center,
            ) {
                pairing?.let { Image(it.qr, contentDescription = "QR code to open on a phone", Modifier.fillMaxSize()) }
            }
            Spacer(Modifier.height(10.dp))
            pairing?.let {
                Row(
                    Modifier.background(Ink.card, RoundedCornerShape(50)).border(BorderStroke(2.dp, Ink.line), RoundedCornerShape(50))
                        .padding(horizontal = 14.dp, vertical = 1.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("CODE", fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 11.sp, color = Ink.soft, letterSpacing = 1.sp)
                    Spacer(Modifier.width(8.dp))
                    Text(it.code, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp,
                        color = Ink.accent, letterSpacing = 4.sp)
                }
            }
            Spacer(Modifier.height(14.dp))
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Step("📷", "Scan with a grown-up's phone")
                Step("✂️", "Photograph your drawing")
                Step("✨", "Watch it walk in!")
            }
            Spacer(Modifier.height(14.dp))
            TvCard(onClick = ::useSamples, tint = Ink.card, width = 250, height = 40) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(if (samplesBusy) "Building the sample stars…" else "No drawing? Use sample stars",
                        fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Ink.ink)
                }
            }
        }
        Box(Modifier.weight(1f).fillMaxHeight()) {
            val x by animateFloatAsState(spotX, tween(1200), label = "spot")
            val breathe by rememberInfiniteTransition(label = "breathe")
                .animateFloat(0.85f, 1f, infiniteRepeatable(tween(1800), RepeatMode.Reverse), label = "breathe")
            Canvas(Modifier.fillMaxSize()) {
                paperStage()
                spotlight(x, FEET, breathe)
            }
            Stage(actors, transparent = true, labelPaint = paint, onFrame = { clock[0] = it })
            StatusPill(arrived, status, arrivals, Modifier.align(Alignment.TopCenter).padding(top = 22.dp))
        }
    }
}

/** One instruction row: an emoji badge, then the words. */
@Composable
private fun Step(icon: String, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(28.dp).background(Ink.paper2, RoundedCornerShape(50)), contentAlignment = Alignment.Center) {
            Text(icon, fontSize = 14.sp)
        }
        Spacer(Modifier.width(10.dp))
        Text(text, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Ink.ink,
            modifier = Modifier.width(210.dp))
    }
}

/** "X has arrived!" as a bright pill that pops in; a quieter paper pill for the waiting messages. */
@Composable
private fun StatusPill(arrived: String?, status: String, arrivals: Int, modifier: Modifier) {
    if (arrived == null) {
        Text(status, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 14.sp, color = Ink.soft,
            textAlign = TextAlign.Center,
            modifier = modifier.background(Ink.card, RoundedCornerShape(50)).border(BorderStroke(2.dp, Ink.line), RoundedCornerShape(50))
                .padding(horizontal = 16.dp, vertical = 3.dp))
        return
    }
    // Restart the pop each time someone new arrives.
    var popped by remember(arrivals) { mutableStateOf(false) }
    LaunchedEffect(arrivals) { popped = true }
    val pop by animateFloatAsState(if (popped) 1f else 0.6f,
        spring(dampingRatio = 0.45f, stiffness = Spring.StiffnessMediumLow), label = "pop")
    Row(
        modifier.scale(pop).background(Ink.accent, RoundedCornerShape(50)).border(BorderStroke(3.dp, Color.White), RoundedCornerShape(50))
            .padding(horizontal = 18.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("🎉", fontSize = 16.sp)
        Spacer(Modifier.width(8.dp))
        Text("$arrived has arrived!", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 18.sp, color = Color.White)
    }
}

/** Warm paper with a crayon-blue floor line (matches the Stage's default backdrop). */
internal fun DrawScope.paperStage() {
    drawRect(Brush.verticalGradient(listOf(Ink.paper, Ink.paper2)))
    val floor = size.height * 0.9f
    drawRect(Color(0xFFE9D3A8), topLeft = Offset(0f, floor), size = Size(size.width, size.height - floor))
    drawLine(Ink.blue, Offset(0f, floor), Offset(size.width, floor), strokeWidth = 6f)
}

/**
 * A soft stage light at stage fraction [x]: a faint cone from the top and a warm pool on the
 * floor at [feetY]. Several stacked, widening cones give the beam a soft edge without a blur.
 */
internal fun DrawScope.spotlight(x: Float, feetY: Float, strength: Float = 1f, coneAlpha: Float = 1f, poolScale: Float = 1f) {
    val cx = x * size.width
    val fy = feetY * size.height
    val pool = size.height * 0.26f * poolScale
    if (coneAlpha > 0f) {
        for (k in 0 until 4) {
            val spread = 0.55f + k * 0.18f
            val path = Path().apply {
                moveTo(cx - pool * 0.12f * spread, 0f)
                lineTo(cx + pool * 0.12f * spread, 0f)
                lineTo(cx + pool * spread, fy)
                lineTo(cx - pool * spread, fy)
                close()
            }
            // Flat fills: a faint vertical gradient bands visibly on 8-bit TV panels, nested flat cones don't.
            drawPath(path, Color(0xFFFFD98A).copy(alpha = 0.05f * coneAlpha * strength))
        }
    }
    // The pool: a circular radial gradient squashed into an ellipse, so it fades out on every edge.
    withTransform({ scale(1f, 0.24f, pivot = Offset(cx, fy)) }) {
        drawCircle(
            Brush.radialGradient(
                0f to Color(0xFFFFF0B8).copy(alpha = 0.95f * strength),
                0.45f to Color(0xFFFFD27A).copy(alpha = 0.55f * strength),
                1f to Color.Transparent,
                center = Offset(cx, fy), radius = pool * 1.15f,
            ),
            radius = pool * 1.15f, center = Offset(cx, fy),
        )
    }
}

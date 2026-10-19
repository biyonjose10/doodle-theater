package com.doodletheater.tv.ui

import android.content.Context
import android.graphics.Paint
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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

/** Name labels drawn above puppets' heads, in the app's rounded crayon font. */
fun labelPaint(context: Context, size: Float = 40f) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
    typeface = ResourcesCompat.getFont(context, R.font.baloo2)
    textSize = size
    textAlign = Paint.Align.CENTER
    color = android.graphics.Color.rgb(43, 43, 58)
    isFakeBoldText = true
}

private val SLOTS = listOf(0.5f, 0.24f, 0.76f, 0.37f, 0.63f)

/**
 * "Add a star": a QR code for the parent's phone on the left; on the right a stage where each
 * new drawing walks in from the wings and waves the moment the phone sends it.
 */
@Composable
fun AddStar(api: ServerApi) {
    val context = LocalContext.current
    val motions = remember { RigStore.motions(context) }
    val actors = remember { mutableStateListOf<Actor>() }
    val clock = remember { DoubleArray(1) }
    var pairing by remember { mutableStateOf<Pairing?>(null) }
    var status by remember { mutableStateOf("Getting a code…") }
    val paint = remember { labelPaint(context) }

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
                val rig = runCatching { api.rig(member) }.getOrNull() ?: continue
                val actor = Actor(rig, motions).apply {
                    label = member.name
                    x = 1.15f
                    heightFraction = 0.5f
                    feetY = 0.86f
                }
                if (actors.size >= SLOTS.size) actors.removeAt(0)
                actors.add(actor)
                actor.walkTo(SLOTS[(actors.size - 1) % SLOTS.size], clock[0], arrive = "wave")
                status = "${member.name} has arrived!"
            }
            delay(1000)
        }
    }

    Row(Modifier.fillMaxSize().background(Ink.paper)) {
        Column(
            Modifier.width(310.dp).fillMaxHeight().padding(24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Add a star!", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp, color = Ink.ink)
            Spacer(Modifier.height(8.dp))
            Box(
                Modifier.size(180.dp).clip(RoundedCornerShape(14.dp)).background(Ink.card).padding(10.dp),
                contentAlignment = Alignment.Center,
            ) {
                pairing?.let { Image(it.qr, contentDescription = "QR code to open on a phone", Modifier.fillMaxSize()) }
            }
            Spacer(Modifier.height(9.dp))
            pairing?.let {
                Text("Code  ${it.code}", fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 17.sp,
                    color = Ink.accent, letterSpacing = 3.sp)
            }
            Spacer(Modifier.height(9.dp))
            Text(
                "1  Scan with a grown-up's phone\n2  Photograph your drawing\n3  Watch it walk in!",
                fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 13.sp, color = Ink.soft,
                lineHeight = 19.sp,
            )
        }
        Box(Modifier.weight(1f).fillMaxHeight()) {
            Stage(actors, labelPaint = paint, onFrame = { clock[0] = it })
            Text(
                status, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Ink.ink,
                textAlign = TextAlign.Center,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 24.dp),
            )
        }
    }
}

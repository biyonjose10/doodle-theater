package com.doodletheater.tv.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import com.doodletheater.tv.net.CastMember
import com.doodletheater.tv.net.ServerApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Parent corner: remove a drawing, set tonight's story limit and bedtime, and read where the
 * family's drawings go. Reached from the "👪 Parents" chip on Home; Back returns home.
 */
@Composable
fun ParentCorner(
    api: ServerApi,
    bedtime: Boolean,
    onToggleBedtime: () -> Unit,
    storyLimit: Int,
    storiesLeft: Int?,
    onCycleLimit: () -> Unit,
) {
    var cast by remember { mutableStateOf<List<CastMember>>(emptyList()) }
    var thumbs by remember { mutableStateOf<Map<String, ImageBitmap?>>(emptyMap()) }
    var status by remember { mutableStateOf<String?>(null) }
    var confirming by remember { mutableStateOf<CastMember?>(null) }
    val firstStar = remember { FocusRequester() }
    val firstSetting = remember { FocusRequester() }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        runCatching { api.cast() }.onSuccess { list ->
            cast = list.reversed()
            thumbs = api.thumbnails(list)     // a broken drawing shows a placeholder; the rest still load
        }.onFailure { status = "Can't reach the laptop at ${api.base}." }
    }

    LaunchedEffect(Unit) {
        load()
        delay(100)
        runCatching { if (cast.isNotEmpty()) firstStar.requestFocus() else firstSetting.requestFocus() }
    }

    Box(Modifier.fillMaxSize().background(Ink.paper)) {
        Column(Modifier.fillMaxSize().padding(horizontal = 32.dp, vertical = 18.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("👪 Parent corner", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 28.sp,
                    color = Ink.ink, modifier = Modifier.weight(1f))
                KeyHint("BACK", "home")
            }
            Spacer(Modifier.height(4.dp))
            Heading("Your stars")
            Text(status ?: if (cast.isEmpty()) "No drawings on this laptop yet." else "Choose a star to remove its drawing.",
                fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 12.sp, color = Ink.soft)
            LazyRow(horizontalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 10.dp)) {
                items(cast, key = { it.id }) { m ->
                    TvCard(onClick = { confirming = m }, tint = Ink.card, width = 108, height = 118,
                        modifier = if (m == cast.first()) Modifier.focusRequester(firstStar) else Modifier) {
                        Column(Modifier.fillMaxSize().padding(6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(Modifier.weight(1f).fillMaxWidth().background(Ink.paper, RoundedCornerShape(8.dp)).padding(3.dp)) {
                                StarThumb(thumbs[m.id], m.name, failed = m.id in thumbs)
                            }
                            Text(m.name, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 11.sp, color = Ink.ink, maxLines = 1)
                            TagPill("🗑 Delete", color = Color(0xFF9A3A22), size = 9)
                        }
                    }
                }
            }
            Heading("Tonight")
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                StoriesChip(limit = storyLimit, left = storiesLeft, onCycle = onCycleLimit, modifier = Modifier.focusRequester(firstSetting))
                Spacer(Modifier.width(10.dp))
                Note("How many stories may start tonight. OK changes it: no limit, 1, 2 or 3. Resets at 6 am.")
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                BedtimeChip(on = bedtime, onToggle = onToggleBedtime)
                Spacer(Modifier.width(10.dp))
                Note("Calmer stories and a slower, softer voice. Turns on by itself from 7 pm to 6 am.")
            }
            Spacer(Modifier.height(12.dp))
            Heading("Privacy")
            Text(
                "Drawings, puppets and stories are kept only on the laptop running Doodle Theater " +
                    "(this TV keeps a copy of each puppet so shows start quickly). Nothing is uploaded unless the " +
                    "laptop is set up with Amazon Web Services: then the cut-out drawing goes to Amazon Bedrock to " +
                    "find its arms and legs, the stars' names and one-line descriptions go to Bedrock to write the " +
                    "story, and the story text goes to Amazon Polly to be read aloud. No accounts, no ads, no " +
                    "tracking. Delete any drawing here at any time.",
                fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 12.sp, color = Ink.ink, lineHeight = 16.sp,
                modifier = Modifier.padding(top = 4.dp).background(Ink.card, RoundedCornerShape(14.dp))
                    .border(BorderStroke(2.dp, Ink.line), RoundedCornerShape(14.dp)).padding(horizontal = 14.dp, vertical = 8.dp),
            )
        }

        confirming?.let { m ->
            ConfirmRemove(m.name, onKeep = { confirming = null; runCatching { firstStar.requestFocus() } }) {
                confirming = null
                scope.launch {
                    runCatching { api.deleteOne(m.id) }
                        .onSuccess { status = "${m.name} was removed." }
                        .onFailure { status = "Couldn't remove ${m.name}: is the laptop on?" }
                    load()
                    delay(100)
                    runCatching { if (cast.isNotEmpty()) firstStar.requestFocus() else firstSetting.requestFocus() }
                }
            }
        }
    }
}

/** "Remove X?" in a dialog (which keeps focus and Back to itself). Focus starts on Keep, so a stray OK never deletes. */
@Composable
private fun ConfirmRemove(name: String, onKeep: () -> Unit, onRemove: () -> Unit) {
    val keep = remember { FocusRequester() }
    Dialog(onDismissRequest = onKeep) {
        LaunchedEffect(Unit) { delay(100); runCatching { keep.requestFocus() } }
        Column(
            Modifier.widthIn(max = 460.dp).background(Ink.paper, RoundedCornerShape(22.dp))
                .border(BorderStroke(3.dp, Ink.ink), RoundedCornerShape(22.dp)).padding(horizontal = 28.dp, vertical = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Remove $name?", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, color = Ink.ink,
                textAlign = TextAlign.Center)
            Text("This deletes the drawing from this laptop.", fontFamily = Baloo, fontWeight = FontWeight.Medium,
                fontSize = 14.sp, color = Ink.soft, textAlign = TextAlign.Center)
            Spacer(Modifier.height(16.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                PillButton("Keep", onKeep, Modifier.focusRequester(keep))
                PillButton("🗑 Remove", onRemove, danger = true)
            }
        }
    }
}

/** A rounded button with the same focus look as the Home chips. */
@Composable
fun PillButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, danger: Boolean = false) {
    val shape = RoundedCornerShape(50)
    val bg = if (danger) Color(0xFF9A3A22) else Ink.card
    val fg = if (danger) Color.White else Ink.ink
    Surface(
        onClick = onClick,
        modifier = modifier,
        shape = ClickableSurfaceDefaults.shape(shape),
        colors = ClickableSurfaceDefaults.colors(containerColor = bg, focusedContainerColor = bg,
            contentColor = fg, focusedContentColor = fg),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
        border = ClickableSurfaceDefaults.border(
            border = Border(BorderStroke(2.dp, Ink.line), shape = shape),
            focusedBorder = Border(BorderStroke(3.dp, Ink.ink), shape = shape),
        ),
        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(Ink.accent.copy(alpha = 0.55f), 10.dp)),
    ) {
        Text(text, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = fg,
            modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp))
    }
}

@Composable
private fun Heading(text: String) =
    Text(text, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Ink.ink)

@Composable
private fun Note(text: String) =
    Text(text, fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 12.sp, color = Ink.soft)

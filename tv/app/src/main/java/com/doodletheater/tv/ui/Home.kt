package com.doodletheater.tv.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Border
import androidx.tv.material3.Card
import androidx.tv.material3.CardDefaults
import androidx.tv.material3.Text
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.width
import androidx.tv.material3.Glow
import com.doodletheater.tv.net.CastMember
import com.doodletheater.tv.net.ServerApi

data class Theme(val id: String, val title: String, val emoji: String, val tint: Color, val blurb: String)

val THEMES = listOf(
    Theme("space", "Space Adventure", "🚀", Color(0xFF3B3F8F), "Station, moon, comet"),
    Theme("jungle", "Jungle Explorer", "🌴", Color(0xFF2F7D4E), "Paths, river, temple"),
    Theme("ocean", "Under the Sea", "🐠", Color(0xFF1F7AA8), "Reef, shipwreck, kelp"),
    Theme("castle", "Dragon Castle", "🏰", Color(0xFF8C4A9E), "Gate, throne, dragon cave"),
    Theme("snow", "Snowy Mountain", "❄️", Color(0xFF5B8FB9), "Village, ice cave, summit"),
    Theme("dino", "Dinosaur Valley", "🦕", Color(0xFFB0662B), "Valley, volcano, nest"),
)

/** Home: tonight's stars (the child's drawings) and the stories they can star in. */
@Composable
fun Home(api: ServerApi, onAddStar: () -> Unit, onStory: (Theme) -> Unit, onDanceParty: () -> Unit) {
    var cast by remember { mutableStateOf<List<CastMember>>(emptyList()) }
    var thumbs by remember { mutableStateOf<Map<String, ImageBitmap>>(emptyMap()) }
    var offline by remember { mutableStateOf(false) }
    val first = remember { FocusRequester() }

    LaunchedEffect(Unit) {
        runCatching { api.cast() }.onSuccess { list ->
            cast = list.reversed()
            thumbs = list.associate { m -> m.id to api.image("/rigs/${m.id}/texture.png") }
        }.onFailure { offline = true }
        runCatching { first.requestFocus() }
    }

    Column(
        Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Ink.paper, Ink.paper2)))
            .padding(horizontal = 32.dp, vertical = 20.dp),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Doodle Theater", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 32.sp, color = Ink.ink,
                modifier = Modifier.weight(1f))
            KeyHint("◀ ▶ ▲ ▼", "move")
            Spacer(Modifier.width(8.dp))
            KeyHint("OK", "choose")
        }
        Text(
            if (offline) "Can't reach the laptop. Start the Doodle Theater server, then come back."
            else if (cast.isEmpty()) "Draw a character, then add them as a star!"
            else "Tonight's stars: ${cast.joinToString(", ") { it.name }}",
            fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 13.sp, color = Ink.soft,
        )
        Spacer(Modifier.height(12.dp))
        RowTitle("Your stars")
        LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp), contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)) {
            item {
                TvCard(onClick = onAddStar, modifier = Modifier.focusRequester(first), tint = Ink.accent) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("＋\nAdd a star", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 17.sp,
                            color = Color.White, lineHeight = 20.sp, textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                    }
                }
            }
            items(cast, key = { it.id }) { m ->
                TvCard(onClick = onDanceParty, tint = Ink.card) {
                    Column(Modifier.fillMaxSize().padding(7.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        // The drawing sits on its own paper mat, like a sticker on a page.
                        Box(Modifier.weight(1f).fillMaxWidth().background(Ink.paper, RoundedCornerShape(9.dp)).padding(4.dp)) {
                            thumbs[m.id]?.let { Image(it, m.name, Modifier.fillMaxSize(), contentScale = ContentScale.Fit) }
                        }
                        Spacer(Modifier.height(4.dp))
                        Text(m.name, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 12.sp, color = Ink.ink, maxLines = 1)
                    }
                }
            }
        }
        Spacer(Modifier.height(6.dp))
        RowTitle(if (cast.isEmpty()) "Stories (add a star first)" else "Start tonight's story")
        LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp), contentPadding = PaddingValues(horizontal = 8.dp, vertical = 12.dp)) {
            items(THEMES, key = { it.id }) { t ->
                TvCard(onClick = { if (cast.isNotEmpty()) onStory(t) }, tint = t.tint, width = 150, height = 100) {
                    Column(Modifier.fillMaxSize().padding(9.dp), verticalArrangement = Arrangement.SpaceBetween) {
                        Text(t.emoji, fontSize = 30.sp)
                        Column {
                            Text(t.title, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 15.sp, color = Color.White,
                                lineHeight = 16.sp)
                            Text(t.blurb, fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 10.sp,
                                color = Color.White.copy(alpha = 0.85f), maxLines = 1)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RowTitle(text: String) =
    Text(text, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Ink.ink)

@Composable
fun TvCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    tint: Color,
    width: Int = 120,
    height: Int = 130,
    content: @Composable () -> Unit,
) {
    Card(
        onClick = onClick,
        modifier = modifier.size(width.dp, height.dp),
        shape = CardDefaults.shape(RoundedCornerShape(18.dp)),
        colors = CardDefaults.colors(containerColor = tint, focusedContainerColor = tint),
        scale = CardDefaults.scale(focusedScale = 1.1f),
        // Readable from the sofa: a thick ink outline plus a warm glow, so focus never relies on colour alone.
        border = CardDefaults.border(
            border = Border(BorderStroke(2.dp, Ink.line), shape = RoundedCornerShape(18.dp)),
            focusedBorder = Border(BorderStroke(4.dp, Ink.ink), shape = RoundedCornerShape(18.dp)),
        ),
        glow = CardDefaults.glow(focusedGlow = Glow(Ink.accent.copy(alpha = 0.55f), 14.dp)),
    ) { content() }
}

/** A small remote-control hint, e.g. "OK" + "select". */
@Composable
fun KeyHint(key: String, label: String) {
    Row(
        Modifier.background(Ink.card, RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(key, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 12.sp, color = Color.White,
            modifier = Modifier.background(Ink.ink, RoundedCornerShape(6.dp)).padding(horizontal = 6.dp))
        Spacer(Modifier.width(6.dp))
        Text(label, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 12.sp, color = Ink.ink)
    }
}

package com.doodletheater.tv.ui

import android.content.Context
import android.view.KeyEvent as AndroidKey
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.Text
import com.doodletheater.tv.net.ServerApi
import com.doodletheater.tv.net.ServerConfig
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.net.Inet4Address
import java.net.NetworkInterface

private val ADDRESS = Regex("""^https?://(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3}):(\d{1,5})$""")

/**
 * "Set server address": the laptop's IP and port as 16 digit wheels, so a remote with only a
 * D-pad can enter it. ◀ ▶ move between digits, ▲ ▼ turn the focused one, number keys type it.
 */
@Composable
fun ServerSetup(api: ServerApi, onDone: () -> Unit) {
    val context = LocalContext.current
    val digits = remember { mutableStateListOf<Int>().apply { addAll(initialDigits(context)) } }
    var status by remember { mutableStateOf("Now using ${api.base}") }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val first = remember { FocusRequester() }
    val focus = LocalFocusManager.current

    LaunchedEffect(Unit) { runCatching { delay(100); first.requestFocus() } }

    fun octet(g: Int) = octetOf(digits, g)
    fun port() = portOf(digits)
    fun address() = addressOf(digits)

    fun connect() {
        if (busy) return
        if ((0 until 4).any { octet(it) > 255 }) { status = "Each of the four numbers must be 255 or less."; return }
        if (port() == 0) { status = "The port can't be 0000 (the server uses 8787)."; return }
        // Saved exactly as normalise() writes it ("0080" -> ":80"), so the wheels show the same address next time.
        val url = ServerConfig.normalise(address()) ?: run { status = "That address doesn't look right."; return }
        ServerConfig.save(context, url)
        busy = true
        status = "Trying $url…"
        scope.launch {
            runCatching { api.cast() }
                .onSuccess { status = "Connected to $url!"; delay(700); onDone() }
                .onFailure { status = "Can't reach $url. Is the server running, on the same Wi-Fi as this TV?" }
            busy = false
        }
    }

    Box(Modifier.fillMaxSize().background(Ink.paper), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Where is the Doodle Theater laptop?", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold,
                fontSize = 28.sp, color = Ink.ink)
            Text("run.ps1 / run.sh prints it as \"TV: http://192.168.x.x:8787\"",
                fontFamily = Baloo, fontWeight = FontWeight.Medium, fontSize = 14.sp, color = Ink.soft)
            Spacer(Modifier.height(22.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("http://", fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 18.sp, color = Ink.soft)
                Spacer(Modifier.width(6.dp))
                for (i in 0 until 16) {
                    DigitWheel(digits[i], { digits[i] = it }, onTyped = { focus.moveFocus(FocusDirection.Right) }, onEnter = ::connect,
                        modifier = if (i == 0) Modifier.focusRequester(first) else Modifier)
                    when (i) {
                        2, 5, 8 -> Separator(".")
                        11 -> Separator(":")
                        else -> if (i < 15) Spacer(Modifier.width(3.dp))
                    }
                }
                Spacer(Modifier.width(18.dp))
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    TvCard(onClick = ::connect, tint = Ink.accent, width = 150, height = 44) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(if (busy) "Trying…" else "Connect", fontFamily = Baloo, fontWeight = FontWeight.ExtraBold,
                                fontSize = 16.sp, color = Color.White)
                        }
                    }
                    TvCard(onClick = {
                        ServerConfig.save(context, null)
                        digits.clear(); digits.addAll(digitsOf(ServerConfig.default) ?: digitsOf("http://10.0.2.2:8787")!!)
                        status = "Back to the emulator address, ${ServerConfig.default}"
                    }, tint = Ink.card, width = 150, height = 44) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("Emulator default", fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 13.sp, color = Ink.ink)
                        }
                    }
                }
            }
            Spacer(Modifier.height(18.dp))
            Text(status, fontFamily = Baloo, fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Ink.ink,
                textAlign = TextAlign.Center)
            Spacer(Modifier.height(10.dp))
            Row {
                KeyHint("◀ ▶", "digit"); Spacer(Modifier.width(8.dp))
                KeyHint("▲ ▼", "change"); Spacer(Modifier.width(8.dp))
                KeyHint("OK", "connect"); Spacer(Modifier.width(8.dp))
                KeyHint("BACK", "home")
            }
        }
    }
}

@Composable
private fun Separator(c: String) =
    Text(c, fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 24.sp, color = Ink.ink,
        modifier = Modifier.padding(horizontal = 3.dp))

/** One digit: ▲ ▼ turn it (wrapping 9 -> 0), a number key sets it and moves on, OK connects. */
@Composable
private fun DigitWheel(value: Int, onChange: (Int) -> Unit, onTyped: () -> Unit, onEnter: () -> Unit,
                       modifier: Modifier = Modifier) {
    var focused by remember { mutableStateOf(false) }
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text("▲", fontSize = 10.sp, color = if (focused) Ink.accent else Color.Transparent)
        Box(
            modifier.size(30.dp, 42.dp)
                .background(if (focused) Ink.accent else Ink.card, RoundedCornerShape(8.dp))
                .border(2.dp, if (focused) Ink.ink else Ink.line, RoundedCornerShape(8.dp))
                .onFocusChanged { focused = it.isFocused }
                .onPreviewKeyEvent { e ->
                    if (e.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                    val code = e.key.nativeKeyCode
                    when {
                        e.key == Key.DirectionUp -> onChange((value + 1) % 10)
                        e.key == Key.DirectionDown -> onChange((value + 9) % 10)
                        e.key == Key.DirectionCenter || e.key == Key.Enter -> onEnter()
                        code in AndroidKey.KEYCODE_0..AndroidKey.KEYCODE_9 -> { onChange(code - AndroidKey.KEYCODE_0); onTyped() }
                        code in AndroidKey.KEYCODE_NUMPAD_0..AndroidKey.KEYCODE_NUMPAD_9 -> {
                            onChange(code - AndroidKey.KEYCODE_NUMPAD_0); onTyped()
                        }
                        else -> return@onPreviewKeyEvent false
                    }
                    true
                }
                .focusable(),
            contentAlignment = Alignment.Center,
        ) {
            Text(value.toString(), fontFamily = Baloo, fontWeight = FontWeight.ExtraBold, fontSize = 22.sp,
                color = if (focused) Color.White else Ink.ink)
        }
        Text("▼", fontSize = 10.sp, color = if (focused) Ink.accent else Color.Transparent)
    }
}

internal fun octetOf(digits: List<Int>, g: Int) = digits[g * 3] * 100 + digits[g * 3 + 1] * 10 + digits[g * 3 + 2]
internal fun portOf(digits: List<Int>) = digits.subList(12, 16).fold(0) { a, d -> a * 10 + d }
/** What the 16 wheels say, e.g. 192 168 001 005 : 0080 -> "http://192.168.1.5:80". */
internal fun addressOf(digits: List<Int>) =
    "http://" + (0 until 4).joinToString(".") { octetOf(digits, it).toString() } + ":" + portOf(digits)

/** The 16 wheels for "http://a.b.c.d:port"; null unless it's an IPv4 address whose port fits the 4 port wheels. */
internal fun digitsOf(url: String): List<Int>? {
    val m = ADDRESS.matchEntire(url) ?: return null
    val (a, b, c, d, port) = m.destructured
    if (listOf(a, b, c, d).any { it.toInt() > 255 } || port.toInt() !in 1..9999) return null
    return (listOf(a, b, c, d).joinToString("") { it.padStart(3, '0') } + port.padStart(4, '0')).map { it - '0' }
}

/** The saved address; else, on a real TV, this TV's own Wi-Fi address (same network, fix the last number). */
private fun initialDigits(context: Context): List<Int> {
    ServerConfig.saved(context)?.let { digitsOf(it) }?.let { return it }
    val own = runCatching {
        NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }.filterIsInstance<Inet4Address>()
            .firstOrNull { it.isSiteLocalAddress }?.hostAddress
    }.getOrNull()
    if (own != null && !own.startsWith("10.0.2.")) digitsOf("http://$own:${ServerConfig.DEFAULT_PORT}")?.let { return it }
    return digitsOf(ServerConfig.default) ?: digitsOf("http://10.0.2.2:8787")!!
}

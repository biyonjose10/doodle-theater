package com.doodletheater.tv.story

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import java.io.File
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.selects.select
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.util.Locale
import java.util.UUID
import kotlin.coroutines.resume

/**
 * Reads a beat aloud and reports each word as it is spoken, for read-along highlighting
 * and word-timed stage directions.
 *
 * Uses Polly audio + speech marks from the server when the beat has them; otherwise the
 * TV's own text-to-speech engine (Fire TV ships one), so stories work with no cloud at all.
 */
class Narrator(context: Context) {
    private val cacheDir = context.cacheDir
    private val ready = CompletableDeferred<Boolean>()
    private var player: MediaPlayer? = null
    private val tts: TextToSpeech = TextToSpeech(context.applicationContext) { status ->
        ready.complete(status == TextToSpeech.SUCCESS)
    }

    init {
        // Lines rendered just before the app was killed never reached their finally block.
        cacheDir.listFiles { f -> f.name.startsWith("speech-") && f.name.endsWith(".wav") }?.forEach { it.delete() }
    }

    suspend fun init(): Boolean = ready.await().also { ok ->
        if (ok) {
            tts.language = Locale.US
            tts.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
        }
    }

    /**
     * Speak [text]; [onWord] gets the [start, end) of each word as it is heard. Returns when finished.
     *
     * The engine renders to a WAV file (recording when each word starts), and our own MediaPlayer
     * plays it. Owning playback makes this app the media-button session, so "Alexa, pause" and
     * the remote's ⏯ reach us; it also means TTS and Polly audio share one code path.
     */
    suspend fun speak(text: String, pitch: Float, rate: Float, onWord: (Int, Int) -> Unit) {
        if (!ready.await()) { delay(2500); return }
        // Deleted however the line ends: played, failed, or cancelled mid-synthesis.
        val file = File(cacheDir, "speech-${UUID.randomUUID()}.wav")
        try {
            val marks = synthesize(text, pitch, rate, file) ?: return
            play(file.absolutePath, marks, onWord)
        } finally { file.delete() }
    }

    private suspend fun synthesize(text: String, pitch: Float, rate: Float, file: File): List<Mark>? {
        tts.setPitch(pitch)
        tts.setSpeechRate(rate)
        val marks = mutableListOf<Mark>()
        var sampleRate = 22050
        val ok = suspendCancellableCoroutine { cont ->
            val id = UUID.randomUUID().toString()
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {}
                override fun onBeginSynthesis(utteranceId: String?, rate: Int, format: Int, channels: Int) {
                    if (utteranceId == id) sampleRate = rate
                }
                override fun onRangeStart(utteranceId: String?, start: Int, end: Int, frame: Int) {
                    if (utteranceId != id) return
                    // Google's engine, when rendering to a file, passes (frame, start, end) instead of
                    // (start, end, frame). A real word range always has start < end, so detect the swap.
                    val (s, e, f) = if (end < start && frame > end) Triple(end, frame, start) else Triple(start, end, frame)
                    synchronized(marks) { marks.add(Mark(f * 1000L / sampleRate, s, e)) }
                }
                override fun onDone(utteranceId: String?) { if (utteranceId == id && cont.isActive) cont.resume(true) }
                override fun onStop(utteranceId: String?, interrupted: Boolean) { if (utteranceId == id && cont.isActive) cont.resume(false) }
                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) { if (utteranceId == id && cont.isActive) cont.resume(false) }
            })
            tts.synthesizeToFile(text, null, file, id)
            cont.invokeOnCancellation { tts.stop() }
        }
        return if (ok && file.length() > 0) synchronized(marks) { marks.sortedBy { it.timeMs } } else null
    }

    /**
     * Play a Polly clip, firing [onWord] from its speech marks. Returns when the clip ends: true if it
     * played (or was stopped), false if it couldn't be loaded or the stream died part-way (the laptop
     * asleep, a missing mp3), so the caller can read the line with the TV's own voice instead.
     * Loading happens off the main thread, so a slow laptop never freezes the screen.
     */
    suspend fun play(url: String, marks: List<Mark>, onWord: (Int, Int) -> Unit): Boolean {
        val done = CompletableDeferred<Unit>().also { playing = it }
        val prepared = CompletableDeferred<Unit>()
        var failed = false
        val mp = MediaPlayer()
        player = mp
        held = false
        try {
            mp.setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build())
            mp.setOnPreparedListener { prepared.complete(Unit) }
            mp.setOnCompletionListener { done.complete(Unit) }
            mp.setOnErrorListener { _, what, extra ->
                Log.w(TAG, "can't play $url ($what/$extra)"); failed = true; done.complete(Unit); true
            }
            withContext(Dispatchers.IO) { mp.setDataSource(url) }
            mp.prepareAsync()
            val loaded = withTimeoutOrNull(LOAD_TIMEOUT_MS) {
                select { prepared.onAwait { true }; done.onAwait { false } }
            }
            if (loaded == null) { Log.w(TAG, "timed out loading $url"); return false }
            if (!loaded) return !failed               // stopped while loading, or an error
            mp.start()
            var next = 0
            var last = -1
            var stalledSince = System.nanoTime()
            while (!done.isCompleted) {
                val t = mp.currentPosition
                while (next < marks.size && marks[next].timeMs <= t) {
                    onWord(marks[next].start, marks[next].end); next++
                }
                // A stream cut off mid-clip can sit buffering forever without an error.
                if (t != last || held) { last = t; stalledSince = System.nanoTime() }
                else if (System.nanoTime() - stalledSince > STALL_TIMEOUT_MS * 1_000_000) {
                    Log.w(TAG, "stalled at $t ms in $url"); return false
                }
                delay(30)
            }
            return !failed
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            Log.w(TAG, "can't play $url", e)
            return false
        } finally {
            player = null
            mp.release()
        }
    }

    private var playing: CompletableDeferred<Unit>? = null
    private var held = false

    /** Hold the current line mid-word; [resume] carries on from the same spot. */
    fun pause() { held = true; player?.let { runCatching { if (it.isPlaying) it.pause() } } }
    fun resume() { held = false; player?.let { runCatching { it.start() } } }

    fun stop() {
        tts.stop()
        player?.let { runCatching { it.stop() } }
        playing?.complete(Unit)
    }

    fun shutdown() {
        stop()
        tts.shutdown()
    }

    private companion object {
        const val TAG = "DoodleNarrator"
        const val LOAD_TIMEOUT_MS = 8000L
        const val STALL_TIMEOUT_MS = 6000L
    }
}

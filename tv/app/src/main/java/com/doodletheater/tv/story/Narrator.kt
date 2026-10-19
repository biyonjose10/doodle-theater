package com.doodletheater.tv.story

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import java.io.File
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.suspendCancellableCoroutine
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
        val (file, marks) = synthesize(text, pitch, rate) ?: return
        try { play(file.absolutePath, marks, onWord) } finally { file.delete() }
    }

    private suspend fun synthesize(text: String, pitch: Float, rate: Float): Pair<File, List<Mark>>? {
        tts.setPitch(pitch)
        tts.setSpeechRate(rate)
        val file = File(cacheDir, "speech-${UUID.randomUUID()}.wav")
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
        return if (ok && file.length() > 0) file to synchronized(marks) { marks.sortedBy { it.timeMs } } else null
    }

    /** Play a Polly clip, firing [onWord] from its speech marks. Returns when the clip ends. */
    suspend fun play(url: String, marks: List<Mark>, onWord: (Int, Int) -> Unit) {
        val done = CompletableDeferred<Unit>().also { playing = it }
        val mp = MediaPlayer().apply {
            setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build())
            setDataSource(url)
            setOnCompletionListener { done.complete(Unit) }
            setOnErrorListener { _, _, _ -> done.complete(Unit); true }
        }
        player = mp
        try {
            mp.prepare()
            mp.start()
            var next = 0
            while (!done.isCompleted) {
                val t = mp.currentPosition
                while (next < marks.size && marks[next].timeMs <= t) {
                    onWord(marks[next].start, marks[next].end); next++
                }
                delay(30)
            }
        } finally {
            player = null
            mp.release()
        }
    }

    private var playing: CompletableDeferred<Unit>? = null

    /** Hold the current line mid-word; [resume] carries on from the same spot. */
    fun pause() { player?.let { runCatching { if (it.isPlaying) it.pause() } } }
    fun resume() { player?.let { runCatching { it.start() } } }

    fun stop() {
        tts.stop()
        player?.let { runCatching { it.stop() } }
        playing?.complete(Unit)
    }

    fun shutdown() {
        stop()
        tts.shutdown()
    }
}

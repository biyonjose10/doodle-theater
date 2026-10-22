package com.doodletheater.tv.net

import android.content.Context
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.doodletheater.tv.rig.Rig
import com.doodletheater.tv.rig.RigStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ConcurrentHashMap

data class CastMember(val id: String, val name: String, val description: String)
data class Pairing(val code: String, val phoneUrl: String, val qr: ImageBitmap)

/** The server answered, but not with 2xx; [code] lets callers tell "gone" (404) from "down". */
class HttpError(val code: Int, message: String) : IllegalStateException(message)

/** Talks to the Doodle Theater server on the family laptop. Plain HttpURLConnection: no extra libraries. */
class ServerApi(private val context: Context) {
    /** Read on every call, so a new address from the "Set server address" screen takes effect at once. */
    val base: String get() = ServerConfig.url(context)

    private fun open(path: String, method: String = "GET", body: String? = null): HttpURLConnection {
        val c = URL(base + path).openConnection() as HttpURLConnection
        c.requestMethod = method
        c.connectTimeout = 4000
        c.readTimeout = 60000
        if (body != null) {
            c.doOutput = true
            c.setRequestProperty("Content-Type", "application/json")
            c.outputStream.use { it.write(body.toByteArray()) }
        }
        if (c.responseCode !in 200..299) {
            val err = c.errorStream?.bufferedReader()?.readText().orEmpty()
            throw HttpError(c.responseCode, "HTTP ${c.responseCode} for $path: $err")
        }
        return c
    }

    private fun text(path: String, method: String = "GET", body: String? = null) =
        open(path, method, body).inputStream.bufferedReader().use { it.readText() }

    private fun bytes(path: String) = open(path).inputStream.use { it.readBytes() }

    suspend fun pair(): Pairing = withContext(Dispatchers.IO) {
        val o = JSONObject(text("/api/pair", "POST"))
        val png = bytes(o.getString("qr"))
        Pairing(o.getString("code"), o.getString("phone_url"),
            BitmapFactory.decodeByteArray(png, 0, png.size).asImageBitmap())
    }

    /** New characters the phone sent since event number [after]. */
    suspend fun events(code: String, after: Int): List<Pair<Int, CastMember>> = withContext(Dispatchers.IO) {
        val arr = JSONObject(text("/api/tv/$code/events?after=$after")).getJSONArray("events")
        (0 until arr.length()).map { arr.getJSONObject(it) }
            .filter { it.getString("type") == "character" }
            .map { it.getInt("n") to member(it) }
    }

    suspend fun cast(): List<CastMember> = withContext(Dispatchers.IO) {
        val arr: JSONArray = JSONObject(text("/api/cast")).getJSONArray("cast")
        (0 until arr.length()).map { member(arr.getJSONObject(it)) }
    }

    /** Add the bundled sample stars (no drawing needed); returns the ones that were new. */
    suspend fun addSamples(): List<CastMember> = withContext(Dispatchers.IO) {
        val o = JSONObject(text("/api/cast/samples", "POST"))
        val added = o.getJSONArray("added").let { a -> (0 until a.length()).map { a.getString(it) }.toSet() }
        val arr = o.getJSONArray("cast")
        (0 until arr.length()).map { member(arr.getJSONObject(it)) }.filter { it.id in added }
    }

    /** Remove one star from the laptop, and this TV's cached copy of its puppet. */
    suspend fun deleteOne(id: String) = withContext(Dispatchers.IO) {
        text("/api/cast/$id", "DELETE")
        lockFor(id).withLock { File(context.cacheDir, "rigs/$id").deleteRecursively() }
        Unit
    }

    suspend fun deleteEveryone() = withContext(Dispatchers.IO) { text("/api/cast", "DELETE"); Unit }

    /**
     * Load a character's rig, cached on the TV. rig.json is small, so it is re-checked every time:
     * if the laptop rebuilt the puppet (a fixed cut-out, a rigger update) the texture is fetched
     * again too. When the laptop can't be reached, or the new copy only half arrives, the cached
     * copy is used. Both files land in temp files first and replace the cache only once both are in,
     * and one lock per star stops two screens fetching the same puppet over each other.
     */
    suspend fun rig(member: CastMember): Rig = lockFor(member.id).withLock {
        withContext(Dispatchers.IO) {
            val dir = File(context.cacheDir, "rigs/${member.id}").apply { mkdirs() }
            val json = File(dir, "rig.json")
            val texture = File(dir, "texture.png")
            runCatching { refreshRig(member.id, json, texture) }.onFailure {
                if (!json.exists() || !texture.exists()) throw it   // nothing cached to fall back on
                android.util.Log.w("DoodleApi", "using the cached puppet for ${member.id}: ${it.message}")
            }
            RigStore.fromDir(dir, member.name)
        }
    }

    private fun refreshRig(id: String, json: File, texture: File) {
        val fresh = runCatching { bytes("/rigs/$id/rig.json") }.getOrNull()
        val cached = json.exists() && texture.exists()
        if (cached && (fresh == null || json.readBytes().contentEquals(fresh))) return   // up to date, or offline
        val newJson = fresh ?: bytes("/rigs/$id/rig.json")
        val newTexture = bytes("/rigs/$id/texture.png")
        val tmpJson = File(json.parentFile, "rig.json.part")
        val tmpTexture = File(texture.parentFile, "texture.png.part")
        try {
            tmpJson.writeBytes(newJson)
            tmpTexture.writeBytes(newTexture)
            // Texture first: rig.json is what marks the cache as current, so if we die in between,
            // the next call sees an old rig.json and fetches both again.
            replace(tmpTexture, texture)
            replace(tmpJson, json)
        } finally {
            tmpJson.delete(); tmpTexture.delete()
        }
    }

    /** rename(2) replaces the target in one step on Android; java.nio's Files.move needs API 26. */
    private fun replace(from: File, to: File) {
        if (from.renameTo(to)) return
        to.delete()
        if (!from.renameTo(to)) throw IOException("couldn't move $from to $to")
    }

    suspend fun image(path: String): ImageBitmap = withContext(Dispatchers.IO) {
        val b = bytes(path)
        (BitmapFactory.decodeByteArray(b, 0, b.size) ?: throw IOException("not an image: $path")).asImageBitmap()
    }

    /** Each star's drawing, fetched one by one: a drawing that fails maps to null, and the rest still load. */
    suspend fun thumbnails(members: List<CastMember>): Map<String, ImageBitmap?> =
        members.associate { m -> m.id to runCatching { image("/rigs/${m.id}/texture.png") }.getOrNull() }

    suspend fun json(path: String, method: String = "GET", body: JSONObject? = null): JSONObject =
        withContext(Dispatchers.IO) { JSONObject(text(path, method, body?.toString())) }

    fun url(path: String) = base + path

    private fun member(o: JSONObject) = CastMember(o.getString("id"), o.getString("name"), o.optString("description"))

    private companion object {
        /** Shared by every ServerApi: the cache directory is shared too. */
        val rigLocks = ConcurrentHashMap<String, Mutex>()
        fun lockFor(id: String): Mutex = rigLocks.getOrPut(id) { Mutex() }
    }
}

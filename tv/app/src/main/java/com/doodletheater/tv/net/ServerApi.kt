package com.doodletheater.tv.net

import android.content.Context
import android.graphics.BitmapFactory
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.doodletheater.tv.BuildConfig
import com.doodletheater.tv.rig.Rig
import com.doodletheater.tv.rig.RigStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

data class CastMember(val id: String, val name: String, val description: String)
data class Pairing(val code: String, val phoneUrl: String, val qr: ImageBitmap)

/** Talks to the Doodle Theater server on the family laptop. Plain HttpURLConnection: no extra libraries. */
class ServerApi(private val context: Context, private val base: String = BuildConfig.SERVER_URL) {

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
            throw IllegalStateException("HTTP ${c.responseCode} for $path: $err")
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

    suspend fun deleteEveryone() = withContext(Dispatchers.IO) { text("/api/cast", "DELETE"); Unit }

    /** Download (once) and load a character's rig. Cached on the TV so shows start instantly. */
    suspend fun rig(member: CastMember): Rig = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "rigs/${member.id}").apply { mkdirs() }
        for (name in listOf("rig.json", "texture.png")) {
            val f = File(dir, name)
            if (!f.exists()) f.writeBytes(bytes("/rigs/${member.id}/$name"))
        }
        RigStore.fromDir(dir, member.name)
    }

    suspend fun image(path: String): ImageBitmap = withContext(Dispatchers.IO) {
        val b = bytes(path)
        BitmapFactory.decodeByteArray(b, 0, b.size).asImageBitmap()
    }

    suspend fun json(path: String, method: String = "GET", body: JSONObject? = null): JSONObject =
        withContext(Dispatchers.IO) { JSONObject(text(path, method, body?.toString())) }

    fun url(path: String) = base + path

    private fun member(o: JSONObject) = CastMember(o.getString("id"), o.getString("name"), o.optString("description"))
}

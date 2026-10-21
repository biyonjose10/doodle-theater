package com.doodletheater.tv.net

import android.content.Context
import com.doodletheater.tv.BuildConfig

/**
 * Where the Doodle Theater server is. Defaults to the build's SERVER_URL (the emulator's host);
 * a real Fire TV sets the laptop's address once, on the "Set server address" screen or with
 * `adb shell am start -n com.doodletheater.tv/.MainActivity --es server 192.168.1.23:8787`.
 */
object ServerConfig {
    private const val PREFS = "server"
    private const val KEY = "url"
    const val DEFAULT_PORT = 8787

    fun url(context: Context): String = saved(context) ?: BuildConfig.SERVER_URL

    /** The address someone set on this TV, or null when it still uses the build's default. */
    fun saved(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)

    val default: String get() = BuildConfig.SERVER_URL

    /** Save [url] (already normalised); null goes back to the build's default. */
    fun save(context: Context, url: String?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().apply {
            if (url == null) remove(KEY) else putString(KEY, url)
        }.apply()
    }

    /** "192.168.1.23" or "192.168.1.23:8787" or "http://host:port/" -> "http://host:port"; null if unusable. */
    fun normalise(raw: String): String? {
        var s = raw.trim().trimEnd('/')
        if (s.isEmpty() || s.any { it.isWhitespace() }) return null
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
        val host = s.substringAfter("://").substringBefore('/')
        if (host.isEmpty() || host.startsWith(":")) return null
        if (':' !in host) s = s.replaceFirst(host, "$host:$DEFAULT_PORT")
        return s
    }
}

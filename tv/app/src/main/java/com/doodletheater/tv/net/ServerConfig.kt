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

    private val HOST = Regex("[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*")

    /**
     * "192.168.1.23" or "192.168.1.23:8787" or "http://host:port/" -> "http://host:port"; null if unusable.
     * The port must be 1-65535 (8787 when none is given) and is written without leading zeros, so
     * "0080" saves as 80. Any path is dropped: the app adds its own.
     */
    fun normalise(raw: String): String? {
        val s = raw.trim()
        if (s.isEmpty() || s.any { it.isWhitespace() }) return null
        val scheme = if ("://" in s) s.substringBefore("://").lowercase() else "http"
        if (scheme != "http" && scheme != "https") return null
        val authority = s.substringAfter("://").substringBefore('/').substringBefore('?').substringBefore('#')
        val host = authority.substringBeforeLast(':').lowercase()
        val port = if (':' in authority) {
            val p = authority.substringAfterLast(':')
            if (p.isEmpty() || p.length > 5 || !p.all { it in '0'..'9' }) return null
            p.toInt().takeIf { it in 1..65535 } ?: return null
        } else DEFAULT_PORT
        if (!HOST.matches(host)) return null
        return "$scheme://$host:$port"
    }
}

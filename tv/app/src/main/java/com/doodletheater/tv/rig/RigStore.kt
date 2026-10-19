package com.doodletheater.tv.rig

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.File

/** Loads rigs bundled in assets and motions.json. Network-delivered rigs arrive as files. */
object RigStore {
    @Volatile private var motions: Map<String, Motion>? = null

    fun motions(context: Context): Map<String, Motion> =
        motions ?: Motions.parse(context.assets.open("motions.json").bufferedReader().readText()).also { motions = it }

    fun fromAssets(context: Context, dir: String, name: String = dir.substringAfterLast('/')): Rig {
        val json = context.assets.open("$dir/rig.json").bufferedReader().readText()
        val tex = context.assets.open("$dir/texture.png").use { decode(it.readBytes()) }
        return Rig.parse(dir, json, tex, name)
    }

    fun fromDir(dir: File, name: String): Rig =
        Rig.parse(dir.name, File(dir, "rig.json").readText(), decode(File(dir, "texture.png").readBytes()), name)

    /** Textures stay small (doodlerig caps them at 1024 px), so a Fire TV Stick Lite's 1 GB is plenty. */
    private fun decode(bytes: ByteArray): Bitmap =
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply {
            inPreferredConfig = Bitmap.Config.ARGB_8888
            inPremultiplied = true
        })
}

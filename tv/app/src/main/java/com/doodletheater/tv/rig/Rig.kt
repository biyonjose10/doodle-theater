package com.doodletheater.tv.rig

import android.graphics.Bitmap
import org.json.JSONObject

/** The 16-joint skeleton, parents before children (same order as doodlerig/joints.py). */
val JOINT_NAMES = listOf(
    "root", "hip", "torso", "neck",
    "right_shoulder", "right_elbow", "right_hand",
    "left_shoulder", "left_elbow", "left_hand",
    "right_hip", "right_knee", "right_foot",
    "left_hip", "left_knee", "left_foot",
)

/**
 * A doodlerig v1 puppet: texture + rest mesh + skeleton + two skin influences per vertex.
 * Coordinates are texture pixels, y down. See doodle-rig/SCHEMA.md.
 */
class Rig(
    val id: String,
    val name: String,
    val texture: Bitmap?,              // null in JVM unit tests
    val width: Int,
    val height: Int,
    val groundY: Float,
    val parent: IntArray,              // -1 for the root
    val rest: DoubleArray,             // x0, y0, x1, y1, ... per joint
    val vertices: FloatArray,          // rest mesh, also the texture coordinates
    val triangles: ShortArray,         // draw order
    val influenceJoint: IntArray,      // 2 per vertex
    val influenceWeight: FloatArray,   // 2 per vertex
    val description: String,
) {
    val vertexCount get() = vertices.size / 2

    /** Height of the rest mesh: the unit for root offsets and for on-screen sizing. */
    val meshHeight: Float = run {
        var lo = Float.MAX_VALUE
        var hi = -Float.MAX_VALUE
        for (i in 1 until vertices.size step 2) {
            lo = minOf(lo, vertices[i]); hi = maxOf(hi, vertices[i])
        }
        hi - lo
    }

    companion object {
        fun parse(id: String, json: String, texture: Bitmap?, name: String = id): Rig {
            val o = JSONObject(json)
            require(o.getString("format") == "doodlerig" && o.getInt("version") == 1) { "not a doodlerig v1 rig" }
            val sk = o.getJSONArray("skeleton")
            val parent = IntArray(JOINT_NAMES.size)
            val rest = DoubleArray(JOINT_NAMES.size * 2)
            for (k in 0 until sk.length()) {
                val j = sk.getJSONObject(k)
                val i = JOINT_NAMES.indexOf(j.getString("name"))
                parent[i] = if (j.isNull("parent")) -1 else JOINT_NAMES.indexOf(j.getString("parent"))
                rest[2 * i] = j.getDouble("x")
                rest[2 * i + 1] = j.getDouble("y")
            }
            val v = o.getJSONArray("vertices")
            val t = o.getJSONArray("triangles")
            val inf = o.getJSONObject("influences")
            val ij = inf.getJSONArray("joints")
            val iw = inf.getJSONArray("weights")
            return Rig(
                id = id,
                name = name,
                texture = texture,
                width = o.getInt("width"),
                height = o.getInt("height"),
                groundY = o.getDouble("ground_y").toFloat(),
                parent = parent,
                rest = rest,
                vertices = FloatArray(v.length()) { v.getDouble(it).toFloat() },
                triangles = ShortArray(t.length()) { t.getInt(it).toShort() },
                influenceJoint = IntArray(ij.length()) { ij.getInt(it) },
                influenceWeight = FloatArray(iw.length()) { iw.getDouble(it).toFloat() },
                description = o.optString("description", ""),
            )
        }
    }
}

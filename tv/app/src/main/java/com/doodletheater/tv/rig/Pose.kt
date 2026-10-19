package com.doodletheater.tv.rig

import org.json.JSONObject
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * Motion curves -> joint transforms -> skinned mesh. A port of doodlerig/pose.py;
 * PoseTest checks it against vertices the Python reference produced.
 */
class Motion(val name: String, val duration: Double, val loop: Boolean, val channels: Map<String, Curve>)

sealed interface Curve {
    fun at(t: Double, duration: Double): Double

    /** offset + amp * f(sin(2π(cycles·t/duration + phase))) where f is identity, |x| or max(0, x). */
    class Wave(private val amp: Double, private val cycles: Double, private val phase: Double,
               private val offset: Double, private val kind: String) : Curve {
        override fun at(t: Double, duration: Double): Double {
            var s = sin(2 * PI * (cycles * t / duration + phase))
            if (kind == "abs_sin") s = abs(s) else if (kind == "pos_sin") s = max(0.0, s)
            return offset + amp * s
        }
    }

    /** Smoothstep between [t, v] keys, held at both ends. */
    class Keys(private val t: DoubleArray, private val v: DoubleArray) : Curve {
        override fun at(t: Double, duration: Double): Double {
            if (t <= this.t[0]) return v[0]
            for (i in 0 until this.t.size - 1) {
                if (t <= this.t[i + 1]) {
                    val a = (t - this.t[i]) / max(this.t[i + 1] - this.t[i], 1e-9)
                    return v[i] + (v[i + 1] - v[i]) * a * a * (3 - 2 * a)
                }
            }
            return v.last()
        }
    }
}

object Motions {
    fun parse(json: String): Map<String, Motion> {
        val all = JSONObject(json).getJSONObject("motions")
        return all.keys().asSequence().associateWith { name ->
            val m = all.getJSONObject(name)
            val ch = m.getJSONObject("channels")
            val curves = ch.keys().asSequence().associateWith { key ->
                val c = ch.getJSONObject(key)
                if (c.has("keys")) {
                    val k = c.getJSONArray("keys")
                    Curve.Keys(DoubleArray(k.length()) { k.getJSONArray(it).getDouble(0) },
                               DoubleArray(k.length()) { k.getJSONArray(it).getDouble(1) })
                } else {
                    val kind = c.keys().next()
                    val a = c.getJSONArray(kind)
                    Curve.Wave(a.getDouble(0), a.getDouble(1), a.getDouble(2), a.getDouble(3), kind)
                }
            }
            Motion(name, m.getDouble("duration"), m.getBoolean("loop"), curves)
        }
    }
}

/** Joint angles in degrees plus the four root channels. Reused every frame to avoid garbage. */
class PoseSample {
    val angles = DoubleArray(JOINT_NAMES.size)
    var rootX = 0.0
    var rootY = 0.0
    var rootSx = 1.0
    var rootSy = 1.0

    fun sample(m: Motion, time: Double): PoseSample {
        val d = m.duration
        val t = if (m.loop) ((time % d) + d) % d else min(max(time, 0.0), d)
        angles.fill(0.0); rootX = 0.0; rootY = 0.0; rootSx = 1.0; rootSy = 1.0
        for ((ch, c) in m.channels) {
            val v = c.at(t, d)
            when (ch) {
                "root.x" -> rootX = v
                "root.y" -> rootY = v
                "root.sx" -> rootSx = v
                "root.sy" -> rootSy = v
                else -> angles[JOINT_NAMES.indexOf(ch)] = v
            }
        }
        return this
    }
}

/**
 * Per-actor posing buffers. `pose()` fills [out] with skinned vertices; no allocation per frame.
 * Affine matrices are [a, b, c, d, e, f]: x' = a·x + c·y + e, y' = b·x + d·y + f.
 */
class Skinner(private val rig: Rig) {
    private val world = Array(JOINT_NAMES.size) { DoubleArray(6) }
    private val skin = Array(JOINT_NAMES.size) { DoubleArray(6) }
    private val tmp = DoubleArray(6)
    val out = FloatArray(rig.vertices.size)

    private fun set(m: DoubleArray, a: Double, b: Double, c: Double, d: Double, e: Double, f: Double) {
        m[0] = a; m[1] = b; m[2] = c; m[3] = d; m[4] = e; m[5] = f
    }

    /** m = m · [a b c d e f] in place. */
    private fun mulInto(m: DoubleArray, a: Double, b: Double, c: Double, d: Double, e: Double, f: Double) {
        set(tmp, m[0] * a + m[2] * b, m[1] * a + m[3] * b, m[0] * c + m[2] * d, m[1] * c + m[3] * d,
            m[0] * e + m[2] * f + m[4], m[1] * e + m[3] * f + m[5])
        tmp.copyInto(m)
    }

    private fun rotate(m: DoubleArray, deg: Double) {
        val r = Math.toRadians(deg)
        val c = cos(r); val s = sin(r)
        mulInto(m, c, s, -s, c, 0.0, 0.0)
    }

    fun pose(p: PoseSample): FloatArray {
        val rest = rig.rest
        val h = rig.meshHeight.toDouble()
        val g = rig.groundY.toDouble()
        val w0 = world[0]
        set(w0, 1.0, 0.0, 0.0, 1.0, rest[0] + p.rootX * h, g + p.rootY * h)
        mulInto(w0, p.rootSx, 0.0, 0.0, p.rootSy, 0.0, 0.0)
        mulInto(w0, 1.0, 0.0, 0.0, 1.0, 0.0, rest[1] - g)
        rotate(w0, p.angles[0])
        for (j in 1 until JOINT_NAMES.size) {
            val par = rig.parent[j]
            world[par].copyInto(world[j])
            mulInto(world[j], 1.0, 0.0, 0.0, 1.0, rest[2 * j] - rest[2 * par], rest[2 * j + 1] - rest[2 * par + 1])
            rotate(world[j], p.angles[j])
        }
        for (j in JOINT_NAMES.indices) {
            world[j].copyInto(skin[j])
            mulInto(skin[j], 1.0, 0.0, 0.0, 1.0, -rest[2 * j], -rest[2 * j + 1])
        }
        val v = rig.vertices
        val ij = rig.influenceJoint
        val iw = rig.influenceWeight
        for (i in 0 until rig.vertexCount) {
            val x = v[2 * i].toDouble()
            val y = v[2 * i + 1].toDouble()
            var ox = 0.0
            var oy = 0.0
            for (k in 0..1) {
                val w = iw[2 * i + k].toDouble()
                if (w == 0.0) continue
                val m = skin[ij[2 * i + k]]
                ox += w * (m[0] * x + m[2] * y + m[4])
                oy += w * (m[1] * x + m[3] * y + m[5])
            }
            out[2 * i] = ox.toFloat()
            out[2 * i + 1] = oy.toFloat()
        }
        return out
    }
}

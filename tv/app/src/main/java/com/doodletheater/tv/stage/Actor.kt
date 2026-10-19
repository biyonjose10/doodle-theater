package com.doodletheater.tv.stage

import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Shader
import com.doodletheater.tv.rig.Motion
import com.doodletheater.tv.rig.PoseSample
import com.doodletheater.tv.rig.Rig
import com.doodletheater.tv.rig.Skinner
import kotlin.math.abs
import kotlin.math.sign

/**
 * One puppet on the stage: where it stands, what it is doing, and how to draw it.
 * Positions are fractions of the stage (x: 0 = left edge, 1 = right edge; feetY: 0 = top).
 */
class Actor(val rig: Rig, private val motions: Map<String, Motion>) {
    private val skinner = Skinner(rig)
    private val sample = PoseSample()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG).apply {
        rig.texture?.let { shader = BitmapShader(it, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP) }
    }

    var x = 0.5f
    var feetY = 0.9f
    var heightFraction = 0.42f        // how tall the puppet is, as a fraction of stage height
    var motionName = "idle"; private set
    private var motion: Motion = motions.getValue("idle")
    private var started = 0.0
    private var then: String = "idle"
    private var targetX: Float? = null
    private var speed = 0f            // stage widths per second
    private var lastNow = Double.NaN

    /** Play [name]; a one-shot motion returns to [then] when it finishes. */
    fun play(name: String, now: Double, then: String = "idle") {
        motion = motions[name] ?: return
        motionName = name
        started = now
        this.then = then
    }

    fun walkTo(x: Float, now: Double, run: Boolean = false) {
        targetX = x
        speed = if (run) 0.32f else 0.16f
        play(if (run) "run" else "walk", now)
    }

    val busy get() = targetX != null || (!motion.loop && motionName != "idle")

    fun update(now: Double) {
        val dt = if (lastNow.isNaN()) 0.0 else (now - lastNow).coerceIn(0.0, 0.1)
        lastNow = now
        targetX?.let { tx ->
            val step = (speed * dt).toFloat()
            val gap = tx - x
            if (abs(gap) <= step) {
                x = tx; targetX = null; play("idle", now)
            } else {
                x += step * sign(gap)
            }
        }
        if (!motion.loop && now - started >= motion.duration) play(then, now)
    }

    fun draw(canvas: Canvas, stageW: Float, stageH: Float, now: Double) {
        val verts = skinner.pose(sample.sample(motion, now - started))
        val s = heightFraction * stageH / rig.meshHeight
        canvas.save()
        canvas.translate(x * stageW - rig.rest[0].toFloat() * s, feetY * stageH - rig.groundY * s)
        canvas.scale(s, s)
        canvas.drawVertices(
            Canvas.VertexMode.TRIANGLES, verts.size, verts, 0, rig.vertices, 0,
            null, 0, rig.triangles, 0, rig.triangles.size, paint,
        )
        canvas.restore()
    }
}

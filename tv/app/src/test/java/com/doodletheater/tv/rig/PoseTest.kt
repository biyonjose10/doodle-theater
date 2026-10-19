package com.doodletheater.tv.rig

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.abs
import kotlin.math.max

/** The Kotlin port must pose vertices exactly like doodlerig's Python reference. */
class PoseTest {
    private fun res(name: String) = javaClass.classLoader!!.getResource(name)!!.readText()
    private val rig = Rig.parse("char1", res("char1_rig.json"), texture = null)
    private val motions = Motions.parse(File("src/main/assets/motions.json").readText())

    @Test
    fun matchesPythonReference() {
        val gold = JSONObject(res("golden_char1.json")).getJSONArray("cases")
        val skinner = Skinner(rig)
        val sample = PoseSample()
        for (i in 0 until gold.length()) {
            val c = gold.getJSONObject(i)
            val want = c.getJSONArray("vertices")
            val got = skinner.pose(sample.sample(motions.getValue(c.getString("motion")), c.getDouble("t")))
            var worst = 0.0
            for (k in 0 until want.length()) worst = max(worst, abs(got[k] - want.getDouble(k)))
            assertTrue("${c.getString("motion")} @ ${c.getDouble("t")}: off by $worst px", worst < 0.05)
        }
    }

    @Test
    fun restPoseIsIdentity() {
        val got = Skinner(rig).pose(PoseSample())
        for (k in rig.vertices.indices) assertEquals(rig.vertices[k], got[k], 1e-3f)
    }

    @Test
    fun oneShotMotionsEndAtRest() {
        for (m in motions.values.filter { !it.loop }) {
            val s = PoseSample().sample(m, m.duration)
            assertTrue(m.name, s.angles.all { abs(it) < 1e-6 } && abs(s.rootY) < 1e-6)
        }
    }
}

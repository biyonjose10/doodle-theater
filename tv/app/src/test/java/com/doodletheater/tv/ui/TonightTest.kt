package com.doodletheater.tv.ui

import android.content.SharedPreferences
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.util.Calendar

/** "Stories tonight" counts per night, and the night turns over at 06:00, not midnight. */
class TonightTest {
    private var now = at(2026, 10, 22, 19, 0)
    private val tonight = Tonight(FakePrefs()) { now }

    private fun at(y: Int, mo: Int, d: Int, h: Int, mi: Int): Long =
        Calendar.getInstance().apply { clear(); set(y, mo - 1, d, h, mi) }.timeInMillis

    @Test
    fun noLimitMeansNoCount() {
        assertNull(tonight.left)
        tonight.markWatched()
        assertNull(tonight.left)
    }

    @Test
    fun aLateStoryStillCountsForTheSameNight() {
        tonight.limit = 2
        tonight.markWatched()                       // 19:00
        now = at(2026, 10, 23, 1, 30)               // after midnight, same night
        assertEquals(1, tonight.left)
        tonight.markWatched()
        now = at(2026, 10, 23, 5, 59)
        assertEquals(0, tonight.left)
    }

    @Test
    fun theCountResetsAtSixInTheMorning() {
        tonight.limit = 1
        tonight.markWatched()
        assertEquals(0, tonight.left)
        now = at(2026, 10, 23, 6, 0)                // the same Tonight object, i.e. the app never closed
        assertEquals(1, tonight.left)
        assertEquals(0, tonight.watched)
        tonight.markWatched()
        assertEquals(0, tonight.left)
    }

    @Test
    fun resetsAcrossTheNewYear() {
        tonight.limit = 3
        now = at(2026, 12, 31, 20, 0)
        tonight.markWatched()
        now = at(2027, 1, 1, 2, 0)
        assertEquals(2, tonight.left)
        now = at(2027, 1, 1, 6, 0)
        assertEquals(3, tonight.left)
    }

    /** Just enough SharedPreferences for Tonight; the real one needs a device. */
    private class FakePrefs : SharedPreferences {
        val map = mutableMapOf<String, Any?>()
        override fun getAll(): Map<String, *> = map
        override fun getString(key: String, defValue: String?) = map[key] as String? ?: defValue
        @Suppress("UNCHECKED_CAST")
        override fun getStringSet(key: String, defValues: Set<String>?) = map[key] as Set<String>? ?: defValues
        override fun getInt(key: String, defValue: Int) = map[key] as Int? ?: defValue
        override fun getLong(key: String, defValue: Long) = map[key] as Long? ?: defValue
        override fun getFloat(key: String, defValue: Float) = map[key] as Float? ?: defValue
        override fun getBoolean(key: String, defValue: Boolean) = map[key] as Boolean? ?: defValue
        override fun contains(key: String) = key in map
        override fun registerOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
        override fun unregisterOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
        override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
            val pending = mutableMapOf<String, Any?>()
            override fun putString(key: String, value: String?) = apply { pending[key] = value }
            override fun putStringSet(key: String, values: Set<String>?) = apply { pending[key] = values }
            override fun putInt(key: String, value: Int) = apply { pending[key] = value }
            override fun putLong(key: String, value: Long) = apply { pending[key] = value }
            override fun putFloat(key: String, value: Float) = apply { pending[key] = value }
            override fun putBoolean(key: String, value: Boolean) = apply { pending[key] = value }
            override fun remove(key: String) = apply { pending[key] = null }
            override fun clear() = apply { map.clear() }
            override fun commit(): Boolean { apply(); return true }
            override fun apply() {
                pending.forEach { (k, v) -> if (v == null) map.remove(k) else map[k] = v }
                pending.clear()
            }
        }
    }
}

package com.doodletheater.tv.ui

import com.doodletheater.tv.net.ServerConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The 16 digit wheels and the saved address must survive a save and a reopen unchanged. */
class ServerSetupTest {
    private fun wheels(s: String) = s.filter { it.isDigit() }.map { it - '0' }

    private fun roundTrip(typed: String) {
        val saved = ServerConfig.normalise(addressOf(wheels(typed)))!!
        assertEquals(wheels(typed), digitsOf(saved))                                   // the wheels show what was saved
        assertEquals(saved, ServerConfig.normalise(addressOf(digitsOf(saved)!!)))      // and saving again changes nothing
    }

    @Test
    fun wheelsRoundTripThroughTheSavedAddress() {
        roundTrip("192.168.001.005:8787")
        roundTrip("192.168.001.005:0080")
        roundTrip("010.000.002.002:0001")
        roundTrip("255.255.255.255:9999")
    }

    @Test
    fun portWithLeadingZerosSavesWithout() {
        assertEquals("http://192.168.1.5:80", ServerConfig.normalise(addressOf(wheels("192.168.001.005:0080"))))
        assertEquals(wheels("192.168.001.005:0080"), digitsOf("http://192.168.1.5:80"))
    }

    @Test
    fun addressesTheWheelsCantShowAreNotForcedOntoThem() {
        assertNull(digitsOf("http://192.168.1.5:65535"))   // five-digit port
        assertNull(digitsOf("http://laptop.local:8787"))   // a name, not numbers
        assertNull(digitsOf("http://300.1.1.1:8787"))
    }
}

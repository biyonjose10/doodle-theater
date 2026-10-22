package com.doodletheater.tv.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** What someone types (or `--es server` passes) is saved as http://host:port, or refused. */
class ServerConfigTest {
    private fun n(s: String) = ServerConfig.normalise(s)

    @Test
    fun addsSchemeAndDefaultPort() {
        assertEquals("http://192.168.1.5:8787", n("192.168.1.5"))
        assertEquals("http://192.168.1.5:8787", n("  192.168.1.5/  "))
        assertEquals("http://laptop.local:8787", n("Laptop.local"))
    }

    @Test
    fun keepsAGoodPortAndDropsAnyPath() {
        assertEquals("http://192.168.1.5:9000", n("192.168.1.5:9000"))
        assertEquals("http://192.168.1.5:8787", n("http://192.168.1.5:8787/"))
        assertEquals("http://192.168.1.5:8787", n("http://192.168.1.5:8787/api/cast?x=1"))
        assertEquals("https://example.com:443", n("HTTPS://example.com:443"))
        assertEquals("http://10.0.2.2:65535", n("10.0.2.2:65535"))
        assertEquals("http://10.0.2.2:1", n("10.0.2.2:1"))
    }

    @Test
    fun leadingZerosInThePortAreDropped() {
        assertEquals("http://192.168.1.5:80", n("192.168.1.5:0080"))
        assertEquals("http://192.168.1.5:8787", n("http://192.168.1.5:08787"))
    }

    @Test
    fun refusesWhatItCantUse() {
        for (bad in listOf(
            "", "   ", "192.168.1.5:", "192.168.1.5:abc", "192.168.1.5:0", "192.168.1.5:0000",
            "192.168.1.5:65536", "192.168.1.5:999999", "192.168.1.5:-1", ":8787", "http://", "http://:8787",
            "ftp://192.168.1.5", "192.168 .1.5", "user@host:8787", "host..local", ".host", "host-", "a:b:c",
        )) assertNull("should refuse \"$bad\"", n(bad))
    }
}

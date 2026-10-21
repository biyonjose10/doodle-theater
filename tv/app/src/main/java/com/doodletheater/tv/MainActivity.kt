package com.doodletheater.tv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.doodletheater.tv.net.ServerConfig
import com.doodletheater.tv.ui.App
import com.doodletheater.tv.ui.Screen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // `adb shell am start ... --es server 192.168.1.23:8787` points the app at a laptop (saved).
        intent.getStringExtra("server")?.let { ServerConfig.normalise(it) }?.let { ServerConfig.save(this, it) }
        // `adb shell am start ... --es screen lab` opens the Puppet Lab (developer screen).
        val start = when (intent.getStringExtra("screen")) {
            "lab" -> Screen.Lab
            "add" -> Screen.AddStar
            "party" -> Screen.DanceParty
            "server" -> Screen.ServerSetup
            "parents" -> Screen.Parents
            else -> Screen.Home
        }
        setContent { App(start) }
    }
}

package com.doodletheater.tv

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.doodletheater.tv.ui.App
import com.doodletheater.tv.ui.Screen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // `adb shell am start ... --es screen lab` opens the Puppet Lab (developer screen).
        val start = when (intent.getStringExtra("screen")) {
            "lab" -> Screen.Lab
            "add" -> Screen.AddStar
            "party" -> Screen.DanceParty
            else -> Screen.Home
        }
        setContent { App(start) }
    }
}

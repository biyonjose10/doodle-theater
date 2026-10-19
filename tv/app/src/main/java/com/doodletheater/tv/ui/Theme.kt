package com.doodletheater.tv.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import com.doodletheater.tv.R

/** Crayon-box palette: warm paper, marker ink, one hot accent. */
object Ink {
    val paper = Color(0xFFFFF8E7)
    val paper2 = Color(0xFFF5E6C8)
    val ink = Color(0xFF2B2B3A)
    val soft = Color(0xFF6B6577)
    val accent = Color(0xFFD65434)
    val blue = Color(0xFF5B7BD5)
    val card = Color(0xFFFFFFFF)
    val line = Color(0xFFE8DCC0)
    val night = Color(0xFF1D1B2E)
}

/** Baloo 2 ships as one variable font; each weight is an instance of its wght axis. */
@OptIn(ExperimentalTextApi::class)
private fun baloo(weight: FontWeight) =
    Font(R.font.baloo2, weight, variationSettings = FontVariation.Settings(FontVariation.weight(weight.weight)))

val Baloo = FontFamily(
    baloo(FontWeight.Medium),
    baloo(FontWeight.Bold),
    baloo(FontWeight.ExtraBold),
)

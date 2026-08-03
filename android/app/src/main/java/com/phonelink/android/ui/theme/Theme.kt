package com.phonelink.android.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val DarkColors = darkColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF4CAF50),
    background = androidx.compose.ui.graphics.Color(0xFF121212),
    surface = androidx.compose.ui.graphics.Color(0xFF1E1E1E),
    error = androidx.compose.ui.graphics.Color(0xFFFF4D4D),
)

private val LightColors = lightColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF2E7D32),
)

@Composable
fun PhoneLinkTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}

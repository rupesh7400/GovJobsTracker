package app.govjobs.tracker.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import app.govjobs.tracker.data.Prefs

@Composable
fun GovJobsTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val scheme = when {
        Prefs.highContrast -> darkColorScheme(
            primary = Color(0xFFFFEB3B), onPrimary = Color.Black, background = Color.Black, onBackground = Color.White,
            surface = Color.Black, onSurface = Color.White, surfaceVariant = Color(0xFF1C1C1C), onSurfaceVariant = Color.White,
            secondaryContainer = Color(0xFF3A3A3A), onSecondaryContainer = Color.White, outline = Color.White,
            error = Color(0xFFFF8A80))
        dark -> darkColorScheme()
        else -> lightColorScheme(primary = Color(0xFF0B3D91), onPrimary = Color.White)
    }
    val d = LocalDensity.current
    CompositionLocalProvider(LocalDensity provides Density(d.density, d.fontScale * Prefs.textScale)) {
        MaterialTheme(colorScheme = scheme, content = content)
    }
}

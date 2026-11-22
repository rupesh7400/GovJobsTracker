package app.govjobs.tracker.data

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.govjobs.tracker.BuildConfig
import java.util.UUID

object Prefs {
    private lateinit var sp: SharedPreferences
    private var _scale by mutableFloatStateOf(1f)
    private var _contrast by mutableStateOf(false)

    fun init(c: Context) {
        sp = c.getSharedPreferences("govjobs", Context.MODE_PRIVATE)
        _scale = sp.getFloat("scale", 1f)
        _contrast = sp.getBoolean("contrast", false)
    }

    var baseUrl: String
        get() = sp.getString("base", null) ?: BuildConfig.DEFAULT_BACKEND_URL
        set(v) { sp.edit().putString("base", v.trim().trimEnd('/')).putString("token", null).apply() }
    var token: String?
        get() = sp.getString("token", null)
        set(v) { sp.edit().putString("token", v).apply() }
    val installId: String
        get() = sp.getString("iid", null) ?: UUID.randomUUID().toString().also { sp.edit().putString("iid", it).apply() }
    var onboarded: Boolean
        get() = sp.getBoolean("onboarded", false)
        set(v) { sp.edit().putBoolean("onboarded", v).apply() }
    var textScale: Float
        get() = _scale
        set(v) { _scale = v; sp.edit().putFloat("scale", v).apply() }
    var highContrast: Boolean
        get() = _contrast
        set(v) { _contrast = v; sp.edit().putBoolean("contrast", v).apply() }
}

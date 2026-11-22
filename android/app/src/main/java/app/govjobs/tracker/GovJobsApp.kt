package app.govjobs.tracker

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import app.govjobs.tracker.data.Prefs

class GovJobsApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Prefs.init(this)
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel("alerts", "Government job alerts", NotificationManager.IMPORTANCE_HIGH)
            ch.description = "New jobs, results, admit cards, answer keys, exam updates and corrigenda"
            getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }
}

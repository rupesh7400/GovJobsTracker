package app.govjobs.tracker

import android.Manifest
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import app.govjobs.tracker.data.Api
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        Api.fcmToken = token
        CoroutineScope(Dispatchers.IO).launch { runCatching { Api.putFcm(token) } }
    }

    /** Called when the app is in the foreground (in background FCM shows the notification itself). */
    override fun onMessageReceived(msg: RemoteMessage) {
        val n = msg.notification ?: return
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val notif = NotificationCompat.Builder(this, "alerts")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(n.title).setContentText(n.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(n.body))
            .setContentIntent(open).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_HIGH).build()
        NotificationManagerCompat.from(this).notify((msg.data["notification_id"] ?: System.nanoTime().toString()).hashCode(), notif)
    }
}

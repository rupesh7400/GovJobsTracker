package app.govjobs.tracker.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class ApiException(val code: Int, message: String) : Exception(message)

object Api {
    val json = Json { ignoreUnknownKeys = true; coerceInputValues = true; explicitNulls = false; encodeDefaults = true }
    private val client = OkHttpClient.Builder().connectTimeout(20, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS).build()
    private val JSON = "application/json".toMediaType()
    @Volatile var fcmToken: String? = null

    private fun build(method: String, path: String, params: Map<String, String?>, body: String?, auth: Boolean): Request {
        val url = try { (Prefs.baseUrl + path).toHttpUrl() } catch (e: IllegalArgumentException) {
            throw ApiException(0, "The server address '${Prefs.baseUrl}' is not valid. It must start with http:// or https://. Change it in Settings.")
        }.newBuilder().apply {
            params.forEach { (k, v) -> if (!v.isNullOrBlank()) addQueryParameter(k, v) }
        }.build()
        val b = Request.Builder().url(url)
        if (auth) Prefs.token?.let { b.header("Authorization", "Bearer $it") }
        b.method(method, body?.toRequestBody(JSON) ?: if (method == "GET" || method == "DELETE") null else "".toRequestBody(JSON))
        return b.build()
    }

    private suspend fun exec(req: Request): String = withContext(Dispatchers.IO) {
        try {
            client.newCall(req).execute().use { r ->
                val text = r.body?.string().orEmpty()
                if (!r.isSuccessful) {
                    val detail = runCatching { json.decodeFromString(ErrBody.serializer(), text).detail }.getOrNull()
                    throw ApiException(r.code, detail ?: "Server error (HTTP ${r.code})")
                }
                text
            }
        } catch (e: java.io.IOException) {
            throw ApiException(0, "Cannot reach the server at ${Prefs.baseUrl}. Check your internet connection and the server address in Settings.")
        }
    }

    suspend fun register(): String {
        val r = exec(build("POST", "/v1/devices", emptyMap(), json.encodeToString(DeviceBody.serializer(), DeviceBody(Prefs.installId, fcmToken)), false))
        val d = json.decodeFromString(DeviceResp.serializer(), r)
        Prefs.token = d.token
        return d.token
    }

    private suspend fun request(method: String, path: String, params: Map<String, String?> = emptyMap(), body: String? = null, auth: Boolean = false): String {
        if (auth && Prefs.token == null) register()
        return try { exec(build(method, path, params, body, auth)) }
        catch (e: ApiException) {
            if (auth && e.code == 401) { register(); exec(build(method, path, params, body, auth)) } else throw e
        }
    }

    // ---- public read endpoints
    suspend fun notes(types: List<String>? = null, q: String? = null, recruitmentId: Long? = null, limit: Int = 60): List<Note> =
        json.decodeFromString(ListSerializer(Note.serializer()), request("GET", "/v1/notifications",
            mapOf("types" to types?.joinToString(","), "q" to q, "recruitment_id" to recruitmentId?.toString(), "limit" to limit.toString())))
    suspend fun recs(filters: Map<String, String?>): List<Rec> =
        json.decodeFromString(ListSerializer(Rec.serializer()), request("GET", "/v1/recruitments", filters))
    suspend fun rec(id: Long): Rec = json.decodeFromString(Rec.serializer(), request("GET", "/v1/recruitments/$id"))
    suspend fun home(): Home = json.decodeFromString(Home.serializer(), request("GET", "/v1/home"))
    suspend fun orgs(q: String? = null): List<Org> =
        json.decodeFromString(ListSerializer(Org.serializer()), request("GET", "/v1/organizations", mapOf("q" to q)))
    suspend fun categories(): List<Cat> = json.decodeFromString(ListSerializer(Cat.serializer()), request("GET", "/v1/org-categories"))
    suspend fun sources(status: String?): List<Src> =
        json.decodeFromString(ListSerializer(Src.serializer()), request("GET", "/v1/sources/status", mapOf("status" to status)))
    suspend fun sourceSummary(): List<StatusCount> =
        json.decodeFromString(ListSerializer(StatusCount.serializer()), request("GET", "/v1/sources/summary"))

    // ---- per-user endpoints (Bearer token)
    suspend fun me(): Me = json.decodeFromString(Me.serializer(), request("GET", "/v1/me", auth = true))
    suspend fun putMe(allAlerts: Boolean, subs: List<List<String>>) {
        request("PUT", "/v1/me", body = json.encodeToString(MeBody.serializer(), MeBody(allAlerts, subs)), auth = true)
    }
    suspend fun putFcm(token: String) {
        fcmToken = token
        request("PUT", "/v1/me/fcm", body = json.encodeToString(FcmBody.serializer(), FcmBody(token)), auth = true)
    }
    suspend fun saved(): List<Deadline> =
        json.decodeFromString(ListSerializer(Deadline.serializer()), request("GET", "/v1/me/saved", auth = true))
    suspend fun save(id: Long) { request("PUT", "/v1/me/saved/$id", auth = true) }
    suspend fun unsave(id: Long) { request("DELETE", "/v1/me/saved/$id", auth = true) }
    suspend fun feed(): List<Note> = json.decodeFromString(ListSerializer(Note.serializer()), request("GET", "/v1/me/feed", auth = true))
}

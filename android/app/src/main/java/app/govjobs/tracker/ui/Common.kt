package app.govjobs.tracker.ui

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import androidx.navigation.compose.currentBackStackEntryAsState
import app.govjobs.tracker.data.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.time.LocalDate
import java.time.temporal.ChronoUnit

sealed interface Load<out T> {
    data object Loading : Load<Nothing>
    data class Ok<T>(val v: T) : Load<T>
    data class Err(val msg: String) : Load<Nothing>
}

@Composable
fun <T> Loader(key: Any?, load: suspend () -> T, refreshMs: Long = 0, content: @Composable (T) -> Unit) {
    var state by remember(key) { mutableStateOf<Load<T>>(Load.Loading) }
    var attempt by remember(key) { mutableIntStateOf(0) }
    LaunchedEffect(key, attempt) {
        state = Load.Loading
        state = try { Load.Ok(load()) } catch (e: CancellationException) { throw e } catch (e: Exception) { Load.Err(e.message ?: "Something went wrong") }
        // Auto-refresh: keep showing the old data if a refresh fails; new data replaces it silently.
        while (refreshMs > 0) {
            delay(refreshMs)
            try { state = Load.Ok(load()) } catch (e: CancellationException) { throw e } catch (e: Exception) { }
        }
    }
    when (val s = state) {
        Load.Loading -> Box(Modifier.fillMaxWidth().padding(32.dp)) {
            CircularProgressIndicator(Modifier.semantics { contentDescription = "Loading" })
        }
        is Load.Err -> Column(Modifier.padding(16.dp).semantics { liveRegion = LiveRegionMode.Polite }) {
            Text("Could not load. ${s.msg}", color = MaterialTheme.colorScheme.error)
            Spacer(Modifier.height(8.dp))
            BigButton("Try again") { attempt++ }
        }
        is Load.Ok -> content(s.v)
    }
}

@Composable
fun Heading(text: String, modifier: Modifier = Modifier) =
    Text(text, style = MaterialTheme.typography.titleLarge, modifier = modifier.semantics { heading() }.padding(vertical = 8.dp))

@Composable
fun BigButton(label: String, desc: String? = null, enabled: Boolean = true, outlined: Boolean = false, onClick: () -> Unit) {
    val m = Modifier.fillMaxWidth().heightIn(min = 56.dp).semantics { if (desc != null) contentDescription = desc }
    if (outlined) OutlinedButton(onClick, m, enabled = enabled) { Text(label) } else Button(onClick, m, enabled = enabled) { Text(label) }
}

@Composable
fun Field(label: String, value: String?) {
    val v = if (value.isNullOrBlank()) "Not specified in official notification" else value
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp).semantics(mergeDescendants = true) { contentDescription = "$label: $v" }) {
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(v, style = MaterialTheme.typography.bodyLarge)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Frame(title: String, nav: NavController, showBack: Boolean = true, showBottom: Boolean = false, content: @Composable (PaddingValues) -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title, modifier = Modifier.semantics { heading() }) },
                navigationIcon = { if (showBack) TextButton(onClick = { nav.popBackStack() }, modifier = Modifier.heightIn(min = 48.dp)) { Text("Back") } })
        },
        bottomBar = { if (showBottom) BottomBar(nav) },
        content = content)
}

@Composable
fun BottomBar(nav: NavController) {
    val route = nav.currentBackStackEntryAsState().value?.destination?.route
    val items = listOf("home" to "Home", "latest" to "Jobs", "results" to "Results", "history" to "Alerts", "more" to "More")
    NavigationBar {
        items.forEach { (r, label) ->
            NavigationBarItem(
                selected = route == r, label = { Text(label) }, icon = {},
                onClick = { nav.navigate(r) { popUpTo("home") { saveState = true }; launchSingleTop = true; restoreState = true } },
                modifier = Modifier.semantics { contentDescription = "$label tab" })
        }
    }
}

fun toast(c: Context, m: String) = Toast.makeText(c, m, Toast.LENGTH_LONG).show()

fun openUrl(ctx: Context, url: String?) {
    val u = url?.trim()
    if (u.isNullOrEmpty() || !(u.startsWith("https://") || u.startsWith("http://"))) { toast(ctx, "No official link is available for this item"); return }
    try { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
    catch (e: Exception) { toast(ctx, "No app available to open this link") }
}

fun downloadPdf(ctx: Context, url: String?, title: String) {
    val u = url?.trim()
    if (u.isNullOrEmpty() || !u.startsWith("http")) { toast(ctx, "No official PDF is available for this item"); return }
    try {
        val name = title.replace(Regex("[^A-Za-z0-9 ._-]"), "").trim().take(60).ifEmpty { "notification" }.replace(' ', '_') + ".pdf"
        val req = DownloadManager.Request(Uri.parse(u)).setTitle(title).setDescription("Official notification PDF")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(ctx, Environment.DIRECTORY_DOWNLOADS, name)
        ctx.getSystemService(DownloadManager::class.java).enqueue(req)
        toast(ctx, "Download started. You will get a notification when it finishes.")
    } catch (e: Exception) { toast(ctx, "Could not start the download. Use Open PDF instead.") }
}

fun typeLabel(t: String) = when (t) {
    "recruitment" -> "New recruitment"; "corrigendum" -> "Corrigendum"; "extension" -> "Date extension"
    "exam_date" -> "Exam date"; "admit_card" -> "Admit card"; "answer_key" -> "Answer key"; "result" -> "Result"
    "merit_list" -> "Merit list"; "cutoff" -> "Cut-off marks"; "document_verification" -> "Document verification"
    "interview" -> "Interview"; "final_selection" -> "Final selection"; "waiting_list" -> "Waiting list"
    "cancellation" -> "Cancellation"; "postponement" -> "Postponement"; "vacancy_revision" -> "Vacancy revision"
    else -> "Update"
}
val ALL_TYPES = listOf("recruitment", "corrigendum", "extension", "exam_date", "admit_card", "answer_key", "result", "merit_list", "cutoff",
    "document_verification", "interview", "final_selection", "waiting_list", "cancellation", "postponement", "vacancy_revision")
val RESULT_TYPES = listOf("result", "merit_list", "cutoff", "final_selection", "waiting_list", "document_verification", "interview")
val EXAM_TYPES = listOf("exam_date", "postponement", "cancellation", "extension", "corrigendum", "vacancy_revision")
val QUALS = listOf("10th", "12th", "graduate", "pg", "diploma", "iti", "engineering")
val RESERVATIONS = listOf("UR", "SC", "ST", "OBC", "OBC-NCL", "EWS", "PwBD", "ESM")
val STATES = listOf("Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh",
    "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands",
    "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry")

fun day(s: String?) = s?.take(10)?.takeIf { it.length == 10 }
fun daysLeft(end: String?): Int? = day(end)?.let { runCatching { ChronoUnit.DAYS.between(LocalDate.now(), LocalDate.parse(it)).toInt() }.getOrNull() }
fun daysLeftText(end: String?): String = when (val d = daysLeft(end)) {
    null -> "Last date not specified"; in Int.MIN_VALUE..-1 -> "Closed on ${day(end)}"; 0 -> "Last date is today"
    1 -> "1 day left, last date ${day(end)}"; else -> "$d days left, last date ${day(end)}"
}
fun verifiedText(v: String?) = when (v) {
    "admin_verified" -> "Verified by administrator"; "auto_verified" -> "Link verified on the official website domain"; else -> "Not yet verified"
}

@Composable
fun NoteCard(n: Note, nav: NavController) {
    val ctx = LocalContext.current
    val label = typeLabel(n.type)
    val desc = "$label. ${n.title}. ${n.organization.orEmpty()}. ${n.state?.let { "$it. " }.orEmpty()}First seen ${day(n.first_seen_at) ?: "recently"}. ${verifiedText(n.verification)}."
    Card(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Column(Modifier.padding(12.dp)) {
            Column(Modifier.semantics(mergeDescendants = true) { contentDescription = desc }) {
                Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                Text(n.title, style = MaterialTheme.typography.titleMedium)
                Text(listOfNotNull(n.organization, n.state).joinToString(" · "), style = MaterialTheme.typography.bodyMedium)
                Text("First seen ${day(n.first_seen_at) ?: "recently"} · ${verifiedText(n.verification)}", style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(8.dp))
            n.recruitment_id?.let { rid -> BigButton("View recruitment details", "View recruitment details for ${n.title}", outlined = true) { nav.navigate("detail/$rid") } }
            BigButton("Open official page", "Open official page for ${n.title}", outlined = true) { openUrl(ctx, n.official_url) }
            if (n.pdf_url != null) BigButton("Open official PDF", "Open official PDF for ${n.title}", outlined = true) { openUrl(ctx, n.pdf_url) }
        }
    }
}

@Composable
fun RecCard(r: Rec, nav: NavController) {
    val vac = r.total_vacancies?.let { "$it vacancies" } ?: "Vacancies not specified in official notification"
    val st = when (r.status) {
        "upcoming" -> "Upcoming: applications start ${day(r.apply_start) ?: "soon"}"
        "closed" -> "Closed (past)"; "open" -> "Open now"; else -> ""
    }
    val desc = "${r.title}. ${r.organization.orEmpty()}. $st. $vac. ${daysLeftText(r.apply_end)}. Double tap to open details."
    Card(onClick = { nav.navigate("detail/${r.id}") }, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp).semantics(mergeDescendants = true) { contentDescription = desc }) {
        Column(Modifier.padding(12.dp).heightIn(min = 56.dp)) {
            if (st.isNotEmpty()) Text(st, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
            Text(r.title, style = MaterialTheme.typography.titleMedium)
            Text(r.organization.orEmpty(), style = MaterialTheme.typography.bodyMedium)
            Text(vac, style = MaterialTheme.typography.bodyMedium)
            Text(daysLeftText(r.apply_end), style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun ChipRow(options: List<String>, selected: String?, label: (String) -> String = { it }, onSelect: (String?) -> Unit) {
    LazyRow(Modifier.padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(options) { o ->
            FilterChip(selected = selected == o, onClick = { onSelect(if (selected == o) null else o) },
                label = { Text(label(o)) }, modifier = Modifier.heightIn(min = 48.dp))
        }
    }
}

@Composable
fun PickerButton(title: String, value: String?, options: List<String>, onSelect: (String?) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        OutlinedButton({ open = true }, Modifier.fillMaxWidth().heightIn(min = 56.dp).semantics { contentDescription = "$title: ${value ?: "Any"}. Double tap to change." }) {
            Text("$title: ${value ?: "Any"}")
        }
        DropdownMenu(open, { open = false }) {
            DropdownMenuItem(text = { Text("Any") }, onClick = { onSelect(null); open = false })
            options.forEach { o -> DropdownMenuItem(text = { Text(o) }, onClick = { onSelect(o); open = false }) }
        }
    }
}

object FilterHolder { var filters: Map<String, String?> = emptyMap(); var title: String = "Search results" }

object SubsStore {
    var allAlerts by mutableStateOf(false)
    val subs = mutableStateListOf<List<String>>()
    private var loaded = false
    suspend fun load(force: Boolean = false) {
        if (loaded && !force) return
        val me = Api.me(); allAlerts = me.all_alerts; subs.clear(); subs.addAll(me.subscriptions); loaded = true
    }
    fun has(dim: String, v: String) = subs.any { it[0] == dim && it[1] == v }
    fun toggle(dim: String, v: String) { val i = subs.indexOfFirst { it[0] == dim && it[1] == v }; if (i >= 0) subs.removeAt(i) else subs.add(listOf(dim, v)) }
    suspend fun save() = Api.putMe(allAlerts, subs.toList())
}

@Composable
fun NoteListBody(pad: PaddingValues, nav: NavController, types: List<String>?, typeFilter: Boolean, empty: String) {
    var sel by remember { mutableStateOf<String?>(null) }
    var q by remember { mutableStateOf("") }
    Column(Modifier.padding(pad)) {
        OutlinedTextField(q, { q = it }, label = { Text("Search by keyword") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(12.dp))
        if (typeFilter) ChipRow(ALL_TYPES, sel, ::typeLabel) { sel = it }
        Loader(Triple(types, sel, q.trim()), { Api.notes(types = sel?.let { listOf(it) } ?: types, q = q.trim().ifEmpty { null }) }, refreshMs = 60_000) { list ->
            if (list.isEmpty()) Text(empty, Modifier.padding(16.dp))
            else LazyColumn(Modifier.padding(horizontal = 12.dp)) { items(list, key = { it.id }) { NoteCard(it, nav) } }
        }
    }
}

@Composable
fun RecListBody(pad: PaddingValues, nav: NavController, filters: Map<String, String?>, empty: String) {
    Column(Modifier.padding(pad)) {
        Loader(filters, { Api.recs(filters) }, refreshMs = 60_000) { list ->
            if (list.isEmpty()) Text(empty, Modifier.padding(16.dp))
            else LazyColumn(Modifier.padding(horizontal = 12.dp)) {
                item { Text("${list.size} recruitments found", Modifier.semantics { liveRegion = LiveRegionMode.Polite }.padding(8.dp)) }
                items(list, key = { it.id }) { RecCard(it, nav) }
            }
        }
    }
}

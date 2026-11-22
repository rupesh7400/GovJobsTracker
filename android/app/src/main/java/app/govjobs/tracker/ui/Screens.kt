package app.govjobs.tracker.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import app.govjobs.tracker.data.*
import com.google.firebase.FirebaseApp
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

// 1 ───────── Splash
@Composable
fun SplashScreen(nav: NavController) {
    val ctx = LocalContext.current
    LaunchedEffect(Unit) {
        runCatching {
            if (FirebaseApp.getApps(ctx).isNotEmpty()) Api.fcmToken = FirebaseMessaging.getInstance().token.await()
        }
        runCatching { Api.register() }          // server may be unreachable; the app still opens and shows a clear error
        delay(600)
        nav.navigate(if (Prefs.onboarded) "home" else "onboarding") { popUpTo("splash") { inclusive = true } }
    }
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.semantics(mergeDescendants = true) {
            contentDescription = "Govt Jobs Tracker. Loading."
        }) {
            Text("Govt Jobs Tracker", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.semantics { heading() })
            Spacer(Modifier.height(16.dp)); CircularProgressIndicator()
        }
    }
}

// 2 ───────── Onboarding
@Composable
fun OnboardingScreen(nav: NavController) {
    val pages = listOf(
        "Welcome" to "One app for Indian government job notifications, collected from official websites and checked before they reach you.",
        "Official sources only" to "Every job links to its official notification PDF and official application page. Items we could not verify are labelled.",
        "Never miss an update" to "Turn on All Government Job Alerts, or choose states, qualifications and organizations in My Subscriptions. Allow notifications when asked.",
        "Made for TalkBack" to "All screens work with screen readers. You can change text size and enable high contrast in Settings.")
    var i by remember { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center) {
        Text("Step ${i + 1} of ${pages.size}", style = MaterialTheme.typography.labelLarge)
        Heading(pages[i].first)
        Text(pages[i].second, style = MaterialTheme.typography.bodyLarge, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        Spacer(Modifier.height(24.dp))
        val done = i == pages.lastIndex
        BigButton(if (done) "Get started" else "Next") {
            if (done) { Prefs.onboarded = true; nav.navigate("home") { popUpTo("onboarding") { inclusive = true } } } else i++
        }
        if (!done) BigButton("Skip introduction", outlined = true) { Prefs.onboarded = true; nav.navigate("home") { popUpTo("onboarding") { inclusive = true } } }
    }
}

// 3 ───────── Home
@Composable
fun HomeScreen(nav: NavController) = Frame("Home", nav, showBack = false, showBottom = true) { pad ->
    Loader(Unit, { Api.home() }, refreshMs = 60_000) { h ->
        LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
            item {
                if (h.latest_jobs.isEmpty() && h.recently_updated.isEmpty() && h.results_today.isEmpty() && h.admit_cards.isEmpty() && h.important.isEmpty() && h.deadlines.isEmpty())
                    Text("The server has not collected any verified notifications yet. This screen refreshes automatically every minute. " +
                        "Check More > Source Verification Dashboard to see which sources are being checked.",
                        Modifier.padding(8.dp).semantics { liveRegion = LiveRegionMode.Polite })
            }
            fun section(title: String, list: List<Note>, route: String) {
                item { Heading(title) }
                if (list.isEmpty()) item { Text("Nothing yet.", Modifier.padding(bottom = 8.dp)) }
                else items(list.take(4), key = { "$title-${it.id}" }) { NoteCard(it, nav) }
                item { BigButton("See all: $title", outlined = true) { nav.navigate(route) } }
            }
            section("Latest government jobs", h.latest_jobs, "latest")
            item { Heading("Upcoming deadlines") }
            if (h.deadlines.isEmpty()) item { Text("No open deadlines recorded yet.") }
            else items(h.deadlines.take(5), key = { "dl-${it.id}" }) { d ->
                Card(onClick = { nav.navigate("detail/${d.id}") }, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).semantics(mergeDescendants = true) { contentDescription = "${d.title}. ${daysLeftText(d.apply_end)}" }) {
                    Column(Modifier.padding(12.dp).heightIn(min = 56.dp)) { Text(d.title); Text(daysLeftText(d.apply_end)) }
                }
            }
            item { BigButton("See all deadlines", outlined = true) { nav.navigate("deadlines") } }
            section("Results released today", h.results_today, "results")
            section("Admit cards", h.admit_cards, "admit")
            section("Recently updated recruitment", h.recently_updated, "notifications")
            section("Important announcements", h.important, "examupdates")
        }
    }
}

// 4, 5, 7–10 ───────── notification lists
@Composable fun LatestJobsScreen(nav: NavController) = Frame("Latest Government Jobs", nav, false, true) { NoteListBody(it, nav, listOf("recruitment"), false, "No recruitment notifications collected yet.") }
@Composable fun AllNotificationsScreen(nav: NavController) = Frame("All Notifications", nav, true, false) { NoteListBody(it, nav, null, true, "No notifications found.") }
@Composable fun ResultsScreen(nav: NavController) = Frame("Results", nav, false, true) { NoteListBody(it, nav, RESULT_TYPES, false, "No results published yet.") }
@Composable fun AdmitCardsScreen(nav: NavController) = Frame("Admit Cards", nav) { NoteListBody(it, nav, listOf("admit_card"), false, "No admit cards yet.") }
@Composable fun AnswerKeysScreen(nav: NavController) = Frame("Answer Keys", nav) { NoteListBody(it, nav, listOf("answer_key"), false, "No answer keys yet.") }
@Composable fun ExamUpdatesScreen(nav: NavController) = Frame("Exam Updates", nav) { NoteListBody(it, nav, EXAM_TYPES, false, "No exam updates yet.") }

// 6 ───────── Category-wise vacancies
@Composable
fun CategoryVacanciesScreen(nav: NavController) = Frame("Category-wise Vacancies", nav) { pad ->
    var sel by remember { mutableStateOf<String?>(null) }
    Column(Modifier.padding(pad)) {
        Text("Choose a reservation category to see recruitments that list vacancies for it in the official notification.", Modifier.padding(12.dp))
        ChipRow(RESERVATIONS, sel) { sel = it }
        RecListBody(PaddingValues(), nav, mapOf("reservation_category" to sel, "open_only" to "false", "sort" to "newest"),
            "No recruitments with extracted category-wise vacancies yet. Vacancy tables appear after the official PDF is processed.")
    }
}

// 11 ───────── Deadline tracker: Past / Open now / Upcoming
@Composable
fun DeadlinesScreen(nav: NavController) = Frame("Application Deadline Tracker", nav) { pad ->
    var st by remember { mutableStateOf("open") }
    val names = mapOf("open" to "Open now", "upcoming" to "Upcoming", "closed" to "Closed (past)")
    Column(Modifier.padding(pad)) {
        ChipRow(names.keys.toList(), st, { names[it] ?: it }) { st = it ?: "open" }
        RecListBody(PaddingValues(), nav, mapOf("status" to st, "sort" to if (st == "closed") "newest" else "deadline"),
            "No ${(names[st] ?: "").lowercase()} recruitments with official dates recorded yet. Dates appear after the official PDF is processed.")
    }
}

// 12 ───────── Organization directory
@Composable
fun OrganizationsScreen(nav: NavController) = Frame("Organization Directory", nav) { pad ->
    val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    var q by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { runCatching { SubsStore.load() } }
    Column(Modifier.padding(pad)) {
        OutlinedTextField(q, { q = it }, label = { Text("Search organizations") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(12.dp))
        Loader(q.trim(), { Api.orgs(q.trim().ifEmpty { null }) }) { list ->
            LazyColumn(Modifier.padding(horizontal = 12.dp)) {
                item { Text("${list.size} organizations", Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                items(list, key = { it.id }) { o ->
                    val subscribed = SubsStore.has("organization", o.name)
                    Card(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                        Column(Modifier.padding(12.dp)) {
                            Column(Modifier.semantics(mergeDescendants = true) {
                                contentDescription = "${o.name}. ${o.category.orEmpty()}. ${o.state ?: "All India"}. ${o.open_recruitments} open recruitments. ${if (subscribed) "Subscribed." else ""}"
                            }) {
                                Text(o.name, style = MaterialTheme.typography.titleMedium)
                                Text("${o.category.orEmpty()} · ${o.state ?: "All India"} · ${o.official_domain.orEmpty()}")
                                Text("${o.open_recruitments} open recruitments")
                            }
                            BigButton("View jobs", "View jobs of ${o.name}", outlined = true) {
                                FilterHolder.filters = mapOf("organization_id" to o.id.toString(), "open_only" to "false", "sort" to "newest"); FilterHolder.title = o.name
                                nav.navigate("recs")
                            }
                            BigButton(if (subscribed) "Unsubscribe" else "Subscribe to alerts", "${if (subscribed) "Unsubscribe from" else "Subscribe to alerts for"} ${o.name}", outlined = true) {
                                SubsStore.toggle("organization", o.name)
                                scope.launch { try { SubsStore.save(); toast(ctx, "Subscriptions saved") } catch (e: Exception) { toast(ctx, e.message ?: "Could not save") } }
                            }
                        }
                    }
                }
            }
        }
    }
}

// 13 ───────── Search and advanced filters
@Composable
fun SearchScreen(nav: NavController) = Frame("Search and Filters", nav) { pad ->
    var q by remember { mutableStateOf("") }; var dept by remember { mutableStateOf("") }; var district by remember { mutableStateOf("") }
    var loc by remember { mutableStateOf("") }; var age by remember { mutableStateOf("") }; var minV by remember { mutableStateOf("") }
    var state by remember { mutableStateOf<String?>(null) }; var qual by remember { mutableStateOf<String?>(null) }
    var rc by remember { mutableStateOf<String?>(null) }; var pwbd by remember { mutableStateOf(false) }; var closed by remember { mutableStateOf(false) }
    var sort by remember { mutableStateOf("deadline") }
    LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
        fun tf(l: String, v: String, set: (String) -> Unit, num: Boolean = false) = item {
            OutlinedTextField(v, set, label = { Text(l) }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = if (num) androidx.compose.ui.text.input.KeyboardType.Number else androidx.compose.ui.text.input.KeyboardType.Text))
        }
        tf("Keyword (job title or department)", q, { q = it })
        item { PickerButton("State", state, STATES) { state = it } }
        tf("District", district, { district = it }); tf("Job location", loc, { loc = it }); tf("Department", dept, { dept = it })
        item { Heading("Qualification") }; item { ChipRow(QUALS, qual) { qual = it } }
        item { Heading("Reservation category with vacancies") }; item { ChipRow(RESERVATIONS, rc) { rc = it } }
        tf("Your age (years)", age, { age = it.filter(Char::isDigit) }, true); tf("Minimum total vacancies", minV, { minV = it.filter(Char::isDigit) }, true)
        item { PickerButton("Sort by", when (sort) { "newest" -> "Newest"; "vacancies" -> "Most vacancies"; else -> "Nearest last date" }, listOf("Nearest last date", "Newest", "Most vacancies")) {
            sort = when (it) { "Newest" -> "newest"; "Most vacancies" -> "vacancies"; else -> "deadline" } } }
        item { ToggleRow("PwBD candidates: show only recruitments open to PwBD", pwbd) { pwbd = it } }
        item { ToggleRow("Include closed recruitments", closed) { closed = it } }
        item {
            BigButton("Search", "Search government jobs with these filters") {
                FilterHolder.filters = mapOf("q" to q.trim(), "state" to state, "district" to district.trim(), "location" to loc.trim(), "department" to dept.trim(),
                    "qualification" to qual, "reservation_category" to rc, "age" to age, "min_vacancies" to minV, "pwbd" to if (pwbd) "true" else null,
                    "open_only" to if (closed) "false" else "true", "sort" to sort)
                FilterHolder.title = "Search results"; nav.navigate("recs")
            }
        }
    }
}

@Composable
fun ToggleRow(label: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).toggleable(value, role = androidx.compose.ui.semantics.Role.Switch, onValueChange = onChange).padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Text(label, Modifier.weight(1f)); Switch(value, null)
    }
}

@Composable
fun RecResultsScreen(nav: NavController) = Frame(FilterHolder.title, nav) { pad ->
    RecListBody(pad, nav, FilterHolder.filters, "No recruitments match these filters. Try fewer filters.")
}

// 14 ───────── Saved jobs
@Composable
fun SavedScreen(nav: NavController) = Frame("Saved Jobs", nav) { pad ->
    Loader(Unit, { Api.saved() }) { list ->
        if (list.isEmpty()) Text("You have not saved any jobs. Open a job and choose Save job.", Modifier.padding(pad).padding(16.dp))
        else LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
            items(list, key = { it.id }) { d ->
                Card(onClick = { nav.navigate("detail/${d.id}") }, modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp).semantics(mergeDescendants = true) { contentDescription = "${d.title}. ${d.organization.orEmpty()}. ${daysLeftText(d.apply_end)}" }) {
                    Column(Modifier.padding(12.dp).heightIn(min = 56.dp)) { Text(d.title, style = MaterialTheme.typography.titleMedium); Text(d.organization.orEmpty()); Text(daysLeftText(d.apply_end)) }
                }
            }
        }
    }
}

// 15 ───────── My subscriptions
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SubscriptionsScreen(nav: NavController) = Frame("My Subscriptions", nav) { pad ->
    val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf("") }
    Loader(Unit, { SubsStore.load(force = true); Api.categories() }) { cats ->
        LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
            item { ToggleRow("All Government Job Alerts (every verified new job and update)", SubsStore.allAlerts) { SubsStore.allAlerts = it } }
            fun group(title: String, dim: String, opts: List<String>, label: (String) -> String = { it }) {
                item { Heading(title) }
                item { FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    opts.forEach { o -> FilterChip(SubsStore.has(dim, o), { SubsStore.toggle(dim, o) }, { Text(label(o)) }, Modifier.heightIn(min = 48.dp)) } } }
            }
            group("Update types", "type", ALL_TYPES, ::typeLabel)
            group("Qualifications", "qualification", QUALS)
            group("States", "state", STATES)
            group("Organization categories", "category", cats.map { it.name })
            val orgs = SubsStore.subs.filter { it[0] == "organization" }.map { it[1] }
            item { Heading("Subscribed organizations") }
            item { Text(if (orgs.isEmpty()) "None. Add organizations from the Organization Directory." else orgs.joinToString(", ")) }
            item { Column { Spacer(Modifier.height(8.dp)); BigButton("Save subscriptions") {
                scope.launch { status = try { SubsStore.save(); "Subscriptions saved" } catch (e: Exception) { e.message ?: "Could not save" }; toast(ctx, status) } } } }
            item { Text(status, Modifier.semantics { liveRegion = LiveRegionMode.Polite }.padding(8.dp)) }
        }
    }
}

// 16 ───────── Notification history
@Composable
fun HistoryScreen(nav: NavController) = Frame("Notification History", nav, false, true) { pad ->
    Loader(Unit, { SubsStore.load(force = true); Api.feed() }, refreshMs = 60_000) { list ->
        LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
            if (!SubsStore.allAlerts && SubsStore.subs.isEmpty())
                item { Text("You are not subscribed to anything yet. Turn on All Government Job Alerts or choose subscriptions to see updates here.", Modifier.padding(8.dp)) }
            else if (list.isEmpty()) item { Text("No matching updates yet.", Modifier.padding(8.dp)) }
            items(list, key = { it.id }) { NoteCard(it, nav) }
            item { BigButton("Manage subscriptions", outlined = true) { nav.navigate("subs") } }
        }
    }
}

// 17 ───────── Settings
@Composable
fun SettingsScreen(nav: NavController) = Frame("Settings", nav) { pad ->
    val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf(Prefs.baseUrl) }; var msg by remember { mutableStateOf("") }
    LaunchedEffect(Unit) { runCatching { SubsStore.load() } }
    LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
        item { Heading("Notifications") }
        item { ToggleRow("All Government Job Alerts", SubsStore.allAlerts) { v -> SubsStore.allAlerts = v
            scope.launch { msg = try { SubsStore.save(); "Saved" } catch (e: Exception) { e.message ?: "Could not save" } } } }
        item { Text(if (FirebaseApp.getApps(ctx).isNotEmpty()) "Push notifications are configured in this build." else
            "Push notifications are NOT configured in this build (no google-services.json). You can still see updates in Notification History.") }
        item { Heading("Appearance and accessibility") }
        item {
            val pct = (Prefs.textScale * 100).toInt()
            Column {
                Text("Text size: $pct percent")
                Slider(Prefs.textScale, { Prefs.textScale = (Math.round(it * 10) / 10f) }, valueRange = 0.8f..2.0f, steps = 11,
                    modifier = Modifier.semantics { stateDescription = "Text size $pct percent" })
            }
        }
        item { ToggleRow("High contrast mode", Prefs.highContrast) { Prefs.highContrast = it } }
        item { Heading("Server") }
        item { OutlinedTextField(url, { url = it }, label = { Text("Backend server address") }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        item { BigButton("Save server address and reconnect") {
            Prefs.baseUrl = url
            scope.launch { msg = try { Api.register(); "Connected to ${Prefs.baseUrl}" } catch (e: Exception) { e.message ?: "Could not connect" } } } }
        item { Text(msg, Modifier.semantics { liveRegion = LiveRegionMode.Polite }.padding(8.dp)) }
        item { Text("Govt Jobs Tracker 1.0. Information is collected from official websites; always confirm on the official notification before applying.", Modifier.padding(vertical = 12.dp)) }
    }
}

// 18 ───────── Source verification dashboard
@Composable
fun SourcesScreen(nav: NavController) = Frame("Source Verification Dashboard", nav) { pad ->
    val ctx = LocalContext.current
    var sel by remember { mutableStateOf<String?>(null) }
    val names = mapOf("monitored" to "Monitored", "pending_integration" to "Pending integration", "manual_verification" to "Manual verification needed", "unavailable" to "Temporarily unavailable", "disabled" to "Disabled")
    Column(Modifier.padding(pad)) {
        Loader(Unit, { Api.sourceSummary() }) { sum ->
            Text(sum.joinToString(". ") { "${names[it.status] ?: it.status}: ${it.n}" }.ifEmpty { "No sources registered." }, Modifier.padding(12.dp))
        }
        Text("We only call a source Monitored after a real check found notification links. Pending means not integrated yet.", Modifier.padding(horizontal = 12.dp))
        ChipRow(names.keys.toList(), sel, { names[it] ?: it }) { sel = it }
        Loader(sel, { Api.sources(sel) }) { list ->
            LazyColumn(Modifier.padding(horizontal = 12.dp)) {
                items(list, key = { it.id }) { s ->
                    Card(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
                        Column(Modifier.padding(12.dp)) {
                            Column(Modifier.semantics(mergeDescendants = true) {
                                contentDescription = "${s.organization}. Status: ${names[s.status] ?: s.status}. Last successful check: ${day(s.last_success_at) ?: "never"}. ${s.last_error?.let { "Problem: $it" }.orEmpty()}"
                            }) {
                                Text(s.organization, style = MaterialTheme.typography.titleMedium)
                                Text("Status: ${names[s.status] ?: s.status}")
                                Text("Last successful check: ${day(s.last_success_at) ?: "never"}")
                                s.last_error?.let { Text("Problem: $it", color = MaterialTheme.colorScheme.error) }
                            }
                            BigButton("Open official website", "Open official website of ${s.organization}", outlined = true) { openUrl(ctx, s.url) }
                        }
                    }
                }
            }
        }
    }
}

// More menu
@Composable
fun MoreScreen(nav: NavController) = Frame("More", nav, false, true) { pad ->
    val items = listOf("Search and Filters" to "search", "Category-wise Vacancies" to "categories", "Application Deadline Tracker" to "deadlines",
        "Admit Cards" to "admit", "Answer Keys" to "answerkeys", "Exam Updates" to "examupdates", "All Notifications" to "notifications",
        "Organization Directory" to "orgs", "Saved Jobs" to "saved", "My Subscriptions" to "subs", "Source Verification Dashboard" to "sources", "Settings" to "settings")
    LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) { items(items) { (l, r) -> Column { BigButton(l, outlined = true) { nav.navigate(r) }; Spacer(Modifier.height(8.dp)) } } }
}

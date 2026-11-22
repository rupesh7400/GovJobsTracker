package app.govjobs.tracker.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicText
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import app.govjobs.tracker.data.*
import kotlinx.coroutines.launch

@Composable
fun DetailScreen(nav: NavController, id: Long) = Frame("Recruitment Details", nav) { pad ->
    val ctx = LocalContext.current; val scope = rememberCoroutineScope()
    var saved by remember { mutableStateOf(false) }
    LaunchedEffect(id) { runCatching { saved = Api.saved().any { it.id == id } } }
    Loader(id, { Api.rec(id) }) { r ->
        LazyColumn(Modifier.padding(pad).padding(horizontal = 12.dp)) {
            item { Heading(r.title) }
            item { Text(r.vacancy_verification ?: "", style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(bottom = 8.dp)) }
            item { Column {
                val pdf = r.notification_pdf_url
                BigButton("Download Official Notification PDF", "Download official notification PDF for ${r.title}", enabled = pdf != null) { downloadPdf(ctx, pdf, r.title) }
                Spacer(Modifier.height(8.dp))
                BigButton("Open PDF in viewer", "Open official notification PDF in a viewer", enabled = pdf != null, outlined = true) { openUrl(ctx, pdf) }
                Spacer(Modifier.height(8.dp))
                BigButton("Apply Online", "Apply online on the official website for ${r.title}", enabled = r.apply_url != null) { openUrl(ctx, r.apply_url) }
                if (r.apply_url == null) Text("The official application link is not in our records yet. Use the official website below.", Modifier.padding(vertical = 4.dp))
                Spacer(Modifier.height(8.dp))
                BigButton("Open official recruitment website", enabled = r.official_site_url != null, outlined = true) { openUrl(ctx, r.official_site_url) }
                Spacer(Modifier.height(8.dp))
                BigButton(if (saved) "Remove from saved jobs" else "Save job", outlined = true) {
                    scope.launch { try { if (saved) Api.unsave(id) else Api.save(id); saved = !saved; toast(ctx, if (saved) "Job saved" else "Removed from saved jobs") } catch (e: Exception) { toast(ctx, e.message ?: "Could not update") } }
                }
            } }
            item { Heading("Overview") }
            item { Column { Field("Organization", r.organization); Field("Department", r.department); Field("Advertisement number", r.advertisement_no)
                Field("Total vacancies", r.total_vacancies?.toString()); Field("Job location", listOfNotNull(r.location, r.district, r.state).joinToString(", ")) } }
            item { Heading("Eligibility") }
            item { Column { Field("Educational qualification", r.qualification_levels?.joinToString(", "))
                Field("Age limit", if (r.min_age != null || r.max_age != null) "${r.min_age ?: "–"} to ${r.max_age ?: "–"} years" else null)
                Field("Age relaxation", r.age_relaxation_text); Field("Nationality", r.nationality_text)
                Field("Open to PwBD candidates", r.pwbd_eligible?.let { if (it) "Yes" else "No" }) } }
            item { Heading("Dates, fee and selection") }
            item { Column { Field("Application start date", day(r.apply_start)); Field("Application closing date", day(r.apply_end)); Field("Time remaining", if (r.apply_end != null) daysLeftText(r.apply_end) else null)
                Field("Application fee", r.fee_text); Field("Selection process", r.selection_process); Field("Examination pattern", r.exam_pattern); Field("Salary / pay scale", r.pay_text) } }
            item { Heading("Category-wise vacancies") }
            item { if (r.vacancies.isEmpty()) Text(r.vacancy_note ?: "Not specified in official notification") else VacancyTable(r.vacancies) }
            item { Heading("Updates for this recruitment") }
            if (r.updates.isEmpty()) item { Text("No results, admit cards or other updates linked yet.") }
            items(r.updates, key = { "u${it.id}" }) { NoteCard(it, nav) }
            item { Column { Field("Last updated", day(r.updated_at)); Spacer(Modifier.height(24.dp)) } }
        }
    }
}

/** Screen-reader-friendly table: one focusable row per post, read as "Post. UR 10. SC 3 ..." instead of dozens of loose cells. */
@Composable
fun VacancyTable(vacs: List<Vac>) {
    fun label(v: Vac) = listOfNotNull(v.category, v.pwbd_subcategory?.let { "($it)" }, v.gender?.let { "[$it]" }).joinToString(" ")
    val cols = vacs.map { label(it) }.distinct()
    val groups = vacs.groupBy { Triple(v0(it.post_name), it.department, it.state) }
    val scroll = rememberScrollState()
    Column(Modifier.semantics { collectionInfo = CollectionInfo(rowCount = groups.size, columnCount = 1) }) {
        Text("Vacancies as printed in the official notification. ${groups.size} post group${if (groups.size == 1) "" else "s"}.", Modifier.padding(bottom = 8.dp))
        Column(Modifier.horizontalScroll(scroll)) {
            Row(Modifier.clearAndSetSemantics { }) {
                Text("Post", Modifier.width(160.dp), style = MaterialTheme.typography.labelLarge)
                cols.forEach { Text(it, Modifier.width(84.dp), style = MaterialTheme.typography.labelLarge) }
            }
            groups.entries.forEachIndexed { i, (k, rows) ->
                val byCol = rows.associateBy { label(it) }
                val postName = listOfNotNull(k.first, k.second, k.third).joinToString(", ")
                val review = rows.any { it.needs_review }
                val spoken = postName + ". " + cols.mapNotNull { c -> byCol[c]?.let { "$c ${it.count}" } }.joinToString(". ") +
                    if (review) ". Not yet verified by an administrator; check the official PDF." else ""
                Row(Modifier.heightIn(min = 48.dp).clearAndSetSemantics {
                    contentDescription = spoken; collectionItemInfo = CollectionItemInfo(i, 1, 0, 1)
                }) {
                    Text(postName, Modifier.width(160.dp))
                    cols.forEach { c -> Text(byCol[c]?.count?.toString() ?: "–", Modifier.width(84.dp)) }
                }
                HorizontalDivider()
            }
        }
        if (vacs.any { it.needs_review }) Text("Some figures were extracted automatically and are not yet verified by an administrator. Confirm them in the official PDF.", Modifier.padding(top = 8.dp), color = MaterialTheme.colorScheme.error)
    }
}
private fun v0(s: String?) = s ?: "All posts"

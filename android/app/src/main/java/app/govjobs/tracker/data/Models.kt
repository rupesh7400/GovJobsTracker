package app.govjobs.tracker.data

import kotlinx.serialization.Serializable

@Serializable data class Note(
    val id: Long, val type: String, val title: String, val official_url: String,
    val pdf_url: String? = null, val published_on: String? = null, val first_seen_at: String? = null,
    val last_verified_at: String? = null, val verification: String? = null, val recruitment_id: Long? = null,
    val organization: String? = null, val state: String? = null)

@Serializable data class Vac(
    val post_name: String? = null, val department: String? = null, val state: String? = null, val gender: String? = null,
    val category: String, val pwbd_subcategory: String? = null, val count: Int = 0, val needs_review: Boolean = false)

@Serializable data class Rec(
    val id: Long, val title: String, val organization: String? = null, val organization_id: Int? = null,
    val advertisement_no: String? = null, val department: String? = null, val state: String? = null,
    val district: String? = null, val location: String? = null, val total_vacancies: Int? = null,
    val qualification_levels: List<String>? = null, val min_age: Int? = null, val max_age: Int? = null,
    val age_relaxation_text: String? = null, val nationality_text: String? = null,
    val apply_start: String? = null, val apply_end: String? = null, val fee_text: String? = null,
    val selection_process: String? = null, val exam_pattern: String? = null, val pay_text: String? = null,
    val notification_pdf_url: String? = null, val apply_url: String? = null, val official_site_url: String? = null,
    val pwbd_eligible: Boolean? = null, val admin_verified: Boolean = false, val updated_at: String? = null, val status: String? = null,
    val vacancies: List<Vac> = emptyList(), val vacancy_note: String? = null, val vacancy_verification: String? = null,
    val updates: List<Note> = emptyList())

@Serializable data class Deadline(val id: Long, val title: String, val apply_end: String? = null, val organization: String? = null)

@Serializable data class Home(
    val latest_jobs: List<Note> = emptyList(), val recently_updated: List<Note> = emptyList(),
    val results_today: List<Note> = emptyList(), val admit_cards: List<Note> = emptyList(),
    val important: List<Note> = emptyList(), val deadlines: List<Deadline> = emptyList())

@Serializable data class Org(
    val id: Int, val name: String, val short_name: String? = null, val state: String? = null,
    val official_domain: String? = null, val category: String? = null, val open_recruitments: Int = 0)

@Serializable data class Cat(val id: Int, val name: String, val parent_id: Int? = null)

@Serializable data class Src(
    val id: Int, val organization: String, val state: String? = null, val url: String, val status: String,
    val kind: String? = null, val last_checked_at: String? = null, val last_success_at: String? = null, val last_error: String? = null)

@Serializable data class StatusCount(val status: String, val n: Int)

@Serializable data class Me(val all_alerts: Boolean = false, val subscriptions: List<List<String>> = emptyList())
@Serializable data class MeBody(val all_alerts: Boolean, val subscriptions: List<List<String>>)
@Serializable data class DeviceBody(val install_id: String, val fcm_token: String? = null)
@Serializable data class DeviceResp(val user_id: String, val token: String)
@Serializable data class FcmBody(val fcm_token: String)
@Serializable data class ErrBody(val detail: String? = null)

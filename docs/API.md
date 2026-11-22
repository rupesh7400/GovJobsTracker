# API reference
Interactive docs (try every endpoint): `http://<server>:8000/docs`. Base path `/v1` is for the app, `/admin` for the dashboard.

## Auth
* **App users** are anonymous per install: `POST /v1/devices {"install_id","fcm_token"?}` → `{"user_id","token"}`. Send `Authorization: Bearer <token>` on `/v1/me*`.
* **Admin**: header `X-Admin-Key: <ADMIN_API_KEY>` on every `/admin/*` call. Dashboard: `/admin-ui`.

## Public (no login)
| Endpoint | Purpose / main filters |
|---|---|
| `GET /v1/home` | Dashboard sections: latest jobs, recently updated, results today, admit cards, important, deadlines |
| `GET /v1/notifications` | `type`, `types=a,b`, `state`, `organization_id`, `recruitment_id`, `q`, `limit`, `offset` (verified, non-duplicate only) |
| `GET /v1/recruitments` | `q, organization_id, category_id, department, state, district, location, qualification, pwbd, open_only, min_vacancies, reservation_category, age, last_date_before, sort(deadline/newest/vacancies)` |
| `GET /v1/recruitments/{id}` | Full details + `vacancies[]` (as printed) + `vacancy_note` + `vacancy_verification` + linked `updates[]` |
| `GET /v1/organizations`, `/v1/org-categories` | Directory |
| `GET /v1/sources/status`, `/v1/sources/summary` | Public monitoring transparency (monitored / pending / unavailable) |

## App user (Bearer token)
`GET/PUT /v1/me` (all_alerts + subscriptions `[[dimension,value]]`, dimensions: organization, state, qualification, category, type) · `PUT /v1/me/fcm` · `GET /v1/me/saved` · `PUT|DELETE /v1/me/saved/{id}` · `GET /v1/me/feed` (notification history)

## Admin
`GET /admin/health` · `GET /admin/analytics` · `POST /admin/alerts/{id}/ack` · `GET|POST /admin/sources` · `PATCH /admin/sources/{id}` · `POST /admin/sources/{id}/check` · `POST /admin/sources/discover` · `GET /admin/logs` ·
`POST /admin/organizations` · `POST /admin/org-categories` · `GET /admin/notifications` · `PATCH /admin/notifications/{id}` · `GET /admin/duplicates` ·
`GET /admin/drafts[/{id}]` · `POST /admin/drafts/{id}/approve|reject|reprocess` · `GET|POST /admin/recruitments` · `PUT /admin/recruitments/{id}` · `POST /admin/pipeline/run`

Errors are JSON `{"detail": "..."}` with 401 (auth), 404, 409 (site blocks automation), 422 (validation).

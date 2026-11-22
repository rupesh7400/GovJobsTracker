# Govt Jobs Tracker – All-India government recruitment tracker

One integrated project: **Android app** (Kotlin, Jetpack Compose, TalkBack-first) ⇄ **FastAPI backend** ⇄ **PostgreSQL**, with an automatic **monitoring worker**, **PDF vacancy extraction + admin verification**, **Firebase push**, and a web **admin dashboard**.

```
android/            Android Studio project (open this folder)  – 18 screens, package app.govjobs.tracker
backend/app/        FastAPI API, monitor, PDF/vacancy extraction, verify, notify (FCM), scheduler, migrations runner
backend/app/static/admin.html   Admin dashboard  (served at /admin-ui)
backend/sql/migrations/         Versioned DB schema (applied automatically)
backend/sql/registry.txt        Official source registry: 222 organizations + domains (extendable)
backend/tests/      Unit + integration tests
docs/               WINDOWS_SETUP.md (start here), API.md, TESTING.md
docker-compose.yml  db + api + worker      secrets/  (put firebase.json here)
```
**Start with `docs/WINDOWS_SETUP.md`.**

## How it works
1. **Registry** → each organization gets a pending source (its official home page). 2. **Worker** polls each source on its own interval (robots.txt honoured, retries, change detection by content hash, de-duplication by fingerprint and by org+title). Sources become *monitored* only after a real fetch finds notification links; blocked/failed ones become *manual verification* / *unavailable* with alerts. 3. **Classifier** tags each item (recruitment, corrigendum, extension, exam date, admit card, answer key, result, merit list, cut-off, DV, interview, final selection, waiting list, cancellation, postponement, vacancy revision). 4. **Verification**: only items whose URL (and PDF) are on the organization's registered official domain are auto-verified; the rest wait for an admin. 5. **PDF pipeline** downloads the official PDF, extracts the reservation table (UR/SC/ST/OBC/OBC-NCL/EWS/PwBD with sub-categories/ESM/others as printed) and checks every row against the printed total. Only fully consistent tables auto-publish (labelled "extracted automatically"); everything else becomes a draft for an admin to correct and approve. Vacancies are **never computed or invented**; absent data shows "Not specified in official notification". 6. Results/admit cards/etc. are **linked to their recruitment** by advertisement number (or manually). 7. **Push** via FCM to users with *All Government Job Alerts* or matching subscriptions (organization, state, qualification, category, type); `push_log` guarantees no duplicate pushes. The first crawl of a source is silent (baseline) so users are not flooded.

## Honest status (what has and has not been verified)
| Area | Status |
|---|---|
| Vacancy/PwBD parser, sum validation, classifier, link extraction, dedupe keys, tokens, domain check | **Tested** (12 automated tests pass) |
| Admin dashboard JavaScript | Syntax-checked only; **not run in a browser** |
| FastAPI endpoints, SQL, migrations, scheduler, PDF download, FCM sending | Written and Python-compiled; **not run** (no PostgreSQL/network/dependencies in the build environment). Integration tests are provided: `docs/TESTING.md` |
| Android app (all 18 screens) | Source complete and brace-balanced; **never compiled or run** (no Android SDK/Gradle available). Expect to fix a few compile errors on first build; no APK is included |
| Live coverage | The registry lists 222 official organizations, but **no source is verified to work until you run it**. Many government sites need a hand-tuned page URL/selector, some block automation. Do not assume 100 % coverage; the dashboard and the in-app *Source Verification Dashboard* show the real state |
| Not implemented | OCR for scanned PDFs; Zilla Parishads / Panchayats / most district bodies (add via dashboard); per-state municipal councils (add via `registry.txt`); app-side deep links from a push; iOS |

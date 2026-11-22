# Testing
| Suite | Command | Needs |
|---|---|---|
| Pure logic (classification, link extraction, dedupe keys, vacancy/PwBD parser, sum checks, tokens, domain check) | `cd backend && python -m pytest tests/test_pure.py` or `python tests/run_without_pytest.py` | Python only |
| Integration (API, DB, auth, search filters, verification, push de-duplication, draft approval, result linking, saved jobs) | `docker compose up -d db` then `cd backend && python -m pytest tests/test_integration.py` | PostgreSQL |
| Dashboard | open `http://localhost:8000/admin-ui` and follow the checklist below | running stack |
| Android | Android Studio: build, run on a phone, follow the TalkBack checklist | Android Studio + phone |

## Manual checklists
**Dashboard**: sign in → Health shows counts → Sources: click *Check now* on a few sources and read status/errors → Review: verify/reject/change type → Vacancy drafts: open, compare with the PDF, edit rows, approve → Recruitments lists it → Logs shows the checks.
**Android / TalkBack** (Settings → Accessibility → TalkBack): every button is announced with a meaningful label; vacancy rows are read as one sentence per post; text size slider at 200 % keeps all content reachable; High contrast on; no screen needs sight; Back works everywhere; notifications are read with title and body.
**Push**: Settings in app → All Government Job Alerts on → in dashboard *Run pipeline now* with a verified unpushed notification → phone receives one push; running again sends no duplicate.

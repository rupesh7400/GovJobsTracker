"""Polite source monitor: honours robots.txt, retries transient errors, never bypasses CAPTCHA/login/blocks.
Status is honest: 'monitored' only after a fetch that actually yielded notification links."""
import hashlib, logging, time, urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from sqlalchemy import text
from .config import settings
from .db import SessionLocal
from .classify import classify
from .extract import extract_items, fingerprint, dedupe_key, is_pdf

log = logging.getLogger("monitor")
HEADERS = {"User-Agent": settings.user_agent}
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}
PUSHABLE = {"recruitment", "corrigendum", "extension", "exam_date", "admit_card", "answer_key", "result", "merit_list",
            "cutoff", "document_verification", "interview", "final_selection", "waiting_list", "cancellation",
            "postponement", "vacancy_revision"}

def robots_allowed(url: str) -> bool:
    p = urlparse(url); host = f"{p.scheme}://{p.netloc}"
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = httpx.get(host + "/robots.txt", headers=HEADERS, timeout=15, follow_redirects=True)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[host] = rp
    return _robots[host].can_fetch(HEADERS["User-Agent"], url)

def fetch(url: str) -> httpx.Response:
    last = None
    for attempt, wait in enumerate((0, 2, 6)):          # retries for network errors / 5xx only
        if wait: time.sleep(wait)
        try:
            r = httpx.get(url, headers=HEADERS, timeout=settings.request_timeout, follow_redirects=True)
            if r.status_code >= 500:
                last = RuntimeError(f"HTTP {r.status_code}"); continue
            return r
        except httpx.HTTPError as ex:
            last = ex
    raise RuntimeError(f"fetch failed after retries: {last}")

def check_source(source_id: int) -> dict:
    with SessionLocal() as s:
        src = s.execute(text("select * from source where id=:i"), {"i": source_id}).one()
        now, code, err, new, count, status = datetime.now(timezone.utc), None, None, 0, 0, src.status
        if src.kind == "manual_only":
            return {"skipped": True}
        try:
            if not robots_allowed(src.url):
                raise RuntimeError("robots.txt disallows automated fetching; needs manual verification")
            r = fetch(src.url)
            code = r.status_code
            if code in (401, 403, 429) or "captcha" in r.text[:5000].lower():
                raise RuntimeError(f"Access restricted (HTTP {code} or CAPTCHA); needs manual verification")
            r.raise_for_status()
            h = hashlib.sha256(r.content).hexdigest()
            items = extract_items(src.kind, src.css_selector, src.url, r.content)
            count = len(items)
            if h != src.content_hash or not src.baselined:      # change detection
                for it in items:
                    title, url = it["title"], it["url"]
                    typ = classify(title)
                    dk = dedupe_key(src.organization_id, title)
                    dup = s.execute(text("""select id from notification n join source sc on sc.id=n.source_id
                        where sc.organization_id=:o and n.dedupe_key=:k and n.duplicate_of is null limit 1"""),
                        {"o": src.organization_id, "k": dk}).scalar()
                    quiet = (not src.baselined) or dup is not None or typ not in PUSHABLE   # no push for backlog/dups/other
                    res = s.execute(text("""insert into notification(source_id,type,title,official_url,pdf_url,fingerprint,
                        dedupe_key,duplicate_of,push_sent_at) values (:sid,:t,:title,:url,:pdf,:fp,:dk,:dup,
                        case when :quiet then now() end) on conflict (fingerprint) do nothing"""),
                        {"sid": src.id, "t": typ, "title": title, "url": url, "pdf": url if is_pdf(url) else None,
                         "fp": fingerprint(src.id, url, title), "dk": dk, "dup": dup, "quiet": quiet})
                    new += res.rowcount
                s.execute(text("update source set content_hash=:h where id=:i"), {"h": h, "i": src.id})
            if count > 0:
                s.execute(text("""update source set status='monitored',baselined=true,last_error=null where id=:i"""), {"i": src.id})
                status = "monitored"
            else:
                s.execute(text("""update source set status='pending_integration',last_error=:e where id=:i"""),
                          {"e": "Page fetched but no notification links recognised; set a CSS selector or feed URL", "i": src.id})
                status = "pending_integration"
            s.execute(text("""update source set last_checked_at=:n,last_success_at=:n,consecutive_failures=0,
                last_item_count=:c where id=:i"""), {"n": now, "c": count, "i": src.id})
        except Exception as ex:
            err = str(ex)[:500]
            fails = src.consecutive_failures + 1
            status = ("manual_verification" if "manual verification" in err
                      else "unavailable" if fails >= settings.max_failures_before_unavailable else src.status)
            s.execute(text("""update source set last_checked_at=:n,last_error=:e,consecutive_failures=:f,status=:st
                where id=:i"""), {"n": now, "e": err, "f": fails, "st": status, "i": src.id})
            if status != src.status and status in ("unavailable", "manual_verification"):
                s.execute(text("insert into system_alert(kind,message) values ('source_down',:m)"),
                          {"m": f"Source {src.url} is now {status}: {err}"})
            log.warning("source %s failed: %s", src.url, err)
        s.execute(text("insert into source_check_log(source_id,ok,http_status,new_items,error) values (:i,:ok,:h,:n,:e)"),
                  {"i": src.id, "ok": err is None, "h": code, "n": new, "e": err})
        s.commit()
        return {"status": status, "items": count, "new": new, "error": err}

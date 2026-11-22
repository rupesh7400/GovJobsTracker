"""Official PDF download -> table extraction -> recruitment draft. Auto-publishes only high-confidence
parses (every row's categories add up to the printed total); everything else waits for admin review."""
import io, json, logging
from datetime import date
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text
from .config import settings
from .db import SessionLocal
from .monitor import HEADERS, robots_allowed, fetch
from .extract import on_domain
from .vacancy import extract

log = logging.getLogger("pdfs")
FIELDS = ["advertisement_no", "department", "state", "district", "location", "total_vacancies", "qualification_levels",
          "min_age", "max_age", "age_relaxation_text", "nationality_text", "apply_start", "apply_end", "fee_text",
          "selection_process", "exam_pattern", "pay_text", "notification_pdf_url", "apply_url", "official_site_url",
          "pwbd_eligible"]
DATES = {"apply_start", "apply_end"}

def download(url: str, domain: str) -> bytes:
    if not on_domain(url, domain):
        raise RuntimeError("PDF is not hosted on the organization's official domain")
    if not robots_allowed(url):
        raise RuntimeError("robots.txt disallows fetching this PDF")
    limit = settings.max_pdf_mb * 1024 * 1024
    buf = bytearray()
    with httpx.stream("GET", url, headers=HEADERS, timeout=60, follow_redirects=True) as r:
        r.raise_for_status()
        if not on_domain(str(r.url), domain):
            raise RuntimeError("PDF redirected away from the official domain")
        for chunk in r.iter_bytes():
            buf += chunk
            if len(buf) > limit:
                raise RuntimeError(f"PDF larger than {settings.max_pdf_mb} MB")
    if not buf.startswith(b"%PDF"):
        raise RuntimeError("Downloaded file is not a PDF")
    return bytes(buf)

def read_pdf(data: bytes):
    import pdfplumber
    tables, texts = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:40]:
            texts.append(page.extract_text() or "")
            tables += page.extract_tables()
    return tables, "\n".join(texts)

def discover_pdf(page_url: str, domain: str) -> str | None:
    r = fetch(page_url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    for a in soup.find_all("a", href=True):
        u = urljoin(page_url, a["href"])
        label = (a.get_text(" ", strip=True) + " " + u).lower()
        if u.lower().split("?")[0].endswith(".pdf") and on_domain(u, domain) and any(k in label for k in ("notif", "advt", "advert", "detail", "vacanc", "recruit")):
            return u
    return None

def _coerce(k, v):
    if k in DATES and isinstance(v, str):
        return date.fromisoformat(v) if v else None
    return v

def publish_recruitment(s, *, org_id, title, fields, vacancies, notif_id, admin_verified, confidence, flags, recruitment_id=None) -> int:
    f = {k: _coerce(k, fields[k]) for k in FIELDS if k in fields}
    base = {"extraction_confidence": confidence, "extraction_flags": list(flags), "admin_verified": admin_verified,
            "source_notification_id": notif_id}
    if recruitment_id:
        sets = ", ".join(f"{k}=:{k}" for k in [*f, *base]) + ", title=:title, updated_at=now()"
        s.execute(text(f"update recruitment set {sets} where id=:rid"), {**f, **base, "title": title, "rid": recruitment_id})
        rid = recruitment_id
    else:
        cols = [*f, *base]
        rid = s.execute(text(f"insert into recruitment(organization_id,title,{','.join(cols)}) "
                             f"values (:org,:title,{','.join(':' + c for c in cols)}) returning id"),
                        {**f, **base, "org": org_id, "title": title}).scalar()
    s.execute(text("delete from vacancy where recruitment_id=:r"), {"r": rid})
    for v in vacancies:
        s.execute(text("""insert into vacancy(recruitment_id,post_name,department,state,gender,category,pwbd_subcategory,count,needs_review)
            values (:r,:p,:d,:st,:g,:c,:sub,:n,:nr)"""),
            {"r": rid, "p": v.get("post_name"), "d": v.get("department"), "st": v.get("state"), "g": v.get("gender"),
             "c": v["category"], "sub": v.get("pwbd_subcategory"), "n": int(v["count"]),
             "nr": (not admin_verified) and confidence != "high"})
    if notif_id:
        s.execute(text("update notification set recruitment_id=:r where id=:n"), {"r": rid, "n": notif_id})
    return rid

def process_one(s, n) -> str:
    pdf_url = n.pdf_url
    try:
        if not pdf_url:
            pdf_url = discover_pdf(n.official_url, n.official_domain)
            if not pdf_url:
                s.execute(text("""insert into recruitment_draft(notification_id,status,flags,error) values (:n,'needs_review',
                    array['no_pdf_found'],'No official PDF found on the notification page; add the PDF URL in the dashboard')
                    on conflict do nothing"""), {"n": n.id})
                return "no_pdf"
            s.execute(text("update notification set pdf_url=:u where id=:i"), {"u": pdf_url, "i": n.id})
        data = download(pdf_url, n.official_domain)
        tables, txt = read_pdf(data)
        res = extract(tables, txt)
        if not txt.strip():
            res["flags"].append("no_text_layer_scanned_pdf"); res["confidence"] = "low"
        status, rid = "needs_review", None
        if res["confidence"] == "high":
            fields = {**res["meta"], "state": n.org_state, "notification_pdf_url": pdf_url, "official_site_url": n.official_url}
            rid = publish_recruitment(s, org_id=n.organization_id, title=n.title, fields=fields, vacancies=res["vacancies"],
                                      notif_id=n.id, admin_verified=False, confidence="high", flags=res["flags"])
            status = "auto_published"
        s.execute(text("""insert into recruitment_draft(notification_id,pdf_url,status,extracted,flags,recruitment_id)
            values (:n,:u,:st,cast(:x as jsonb),:f,:r) on conflict (notification_id) do update set pdf_url=:u,status=:st,
            extracted=cast(:x as jsonb),flags=:f,recruitment_id=:r,error=null"""),
            {"n": n.id, "u": pdf_url, "st": status, "x": json.dumps(res, default=str), "f": res["flags"], "r": rid})
        return status
    except Exception as ex:
        log.warning("pdf processing failed for notification %s: %s", n.id, ex)
        s.execute(text("""insert into recruitment_draft(notification_id,pdf_url,status,error) values (:n,:u,'failed',:e)
            on conflict (notification_id) do update set status='failed',error=:e"""), {"n": n.id, "u": pdf_url, "e": str(ex)[:500]})
        return "failed"

def process_pending(limit: int = 10) -> int:
    done = 0
    with SessionLocal() as s:
        rows = s.execute(text("""select n.id,n.title,n.official_url,n.pdf_url,o.id organization_id,o.official_domain,o.state org_state
            from notification n join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id
            where n.type='recruitment' and n.verification in ('auto_verified','admin_verified') and n.duplicate_of is null
            and not exists (select 1 from recruitment_draft d where d.notification_id=n.id)
            order by n.first_seen_at desc limit :l"""), {"l": limit}).all()
        for n in rows:
            process_one(s, n); s.commit(); done += 1
    return done

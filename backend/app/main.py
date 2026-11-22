"""REST API for the Android app (/v1) and the admin dashboard (/admin). Interactive docs at /docs."""
import uuid, pathlib
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from .config import settings
from .db import SessionLocal
from .auth import current_user, admin
from .tokens import make_token
from . import notify, pdfs, monitor, verify
from .extract import extract_items

app = FastAPI(title="Govt Jobs Tracker API", version="1.0")
STATUS_SQL = "(case when r.apply_start > current_date then 'upcoming' when r.apply_end is not null and r.apply_end < current_date then 'closed' else 'open' end)"
OK = "n.verification in ('auto_verified','admin_verified') and n.duplicate_of is null"
NOTE_COLS = """n.id,n.type,n.title,n.official_url,n.pdf_url,n.published_on,n.first_seen_at,n.last_verified_at,
  n.verification,n.recruitment_id,o.name organization,o.state"""
NOTE_FROM = "from notification n join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id"

def db():
    with SessionLocal() as s:
        yield s

def rows(r): return [dict(x._mapping) for x in r]
def one(r):
    x = r.first()
    return dict(x._mapping) if x else None

@app.get("/health")
def health(s=Depends(db)):
    s.execute(text("select 1")); return {"ok": True}

# ------------------------------------------------------------------ public read API
@app.get("/v1/notifications")
def notifications(type: str | None = None, types: str | None = Query(None, description="comma separated"),
                  state: str | None = None, organization_id: int | None = None, q: str | None = None,
                  recruitment_id: int | None = None, limit: int = Query(50, le=100), offset: int = 0, s=Depends(db)):
    tl = types.split(",") if types else None
    return rows(s.execute(text(f"""select {NOTE_COLS} {NOTE_FROM} where {OK}
        and (cast(:type as text) is null or n.type=:type)
        and (cast(:types as text[]) is null or n.type = any(cast(:types as text[])))
        and (cast(:state as text) is null or o.state=:state)
        and (cast(:org as int) is null or o.id=:org)
        and (cast(:rid as bigint) is null or n.recruitment_id=:rid)
        and (cast(:q as text) is null or n.title ilike '%'||:q||'%')
        order by n.first_seen_at desc limit :l offset :o"""),
        {"type": type, "types": tl, "state": state, "org": organization_id, "rid": recruitment_id, "q": q, "l": limit, "o": offset}))

@app.get("/v1/recruitments")
def recruitments(q: str | None = None, organization_id: int | None = None, department: str | None = None,
                 state: str | None = None, district: str | None = None, location: str | None = None,
                 qualification: str | None = None, pwbd: bool | None = None, open_only: bool = True,
                 min_vacancies: int | None = None, reservation_category: str | None = None,
                 age: int | None = None, category_id: int | None = None, last_date_before: date | None = None,
                 status: str | None = Query(None, description="open | upcoming | closed"),
                 sort: str = "deadline", limit: int = Query(50, le=100), offset: int = 0, s=Depends(db)):
    order = {"deadline": "r.apply_end nulls last", "newest": "r.updated_at desc", "vacancies": "r.total_vacancies desc nulls last"}.get(sort, "r.apply_end nulls last")
    return rows(s.execute(text(f"""select r.id,r.title,r.advertisement_no,r.department,r.state,r.district,r.location,r.total_vacancies,
        r.qualification_levels,r.min_age,r.max_age,r.apply_start,r.apply_end,r.pwbd_eligible,r.notification_pdf_url,r.apply_url,
        r.official_site_url,r.admin_verified,r.extraction_confidence,r.updated_at,{STATUS_SQL} as status,o.id organization_id,o.name organization
        from recruitment r join organization o on o.id=r.organization_id
        where (cast(:q as text) is null or r.title ilike '%'||:q||'%' or r.department ilike '%'||:q||'%')
        and (cast(:org as int) is null or o.id=:org) and (cast(:cat as int) is null or o.category_id=:cat)
        and (cast(:dept as text) is null or r.department ilike '%'||:dept||'%')
        and (cast(:state as text) is null or r.state=:state) and (cast(:dist as text) is null or r.district ilike '%'||:dist||'%')
        and (cast(:loc as text) is null or r.location ilike '%'||:loc||'%')
        and (cast(:qual as text) is null or :qual = any(r.qualification_levels))
        and (cast(:pwbd as boolean) is null or r.pwbd_eligible=:pwbd)
        and (not :open or r.apply_end is null or r.apply_end >= current_date)
        and (cast(:status as text) is null or {STATUS_SQL}=:status)
        and (cast(:mv as int) is null or r.total_vacancies >= :mv)
        and (cast(:rc as text) is null or exists (select 1 from vacancy v where v.recruitment_id=r.id and v.category=:rc and v.count>0))
        and (cast(:age as int) is null or ((r.min_age is null or r.min_age<=:age) and (r.max_age is null or r.max_age>=:age)))
        and (cast(:lb as date) is null or r.apply_end <= :lb)
        order by {order} limit :l offset :o"""),
        {"q": q, "org": organization_id, "cat": category_id, "dept": department, "state": state, "dist": district,
         "loc": location, "qual": qualification, "pwbd": pwbd, "open": open_only and not status, "status": status, "mv": min_vacancies,
         "rc": reservation_category, "age": age, "lb": last_date_before, "l": limit, "o": offset}))

@app.get("/v1/recruitments/{rid}")
def recruitment(rid: int, s=Depends(db)):
    r = one(s.execute(text("""select r.*,o.name organization,o.official_domain from recruitment r
        join organization o on o.id=r.organization_id where r.id=:i"""), {"i": rid}))
    if not r: raise HTTPException(404, "Recruitment not found")
    vac = rows(s.execute(text("""select post_name,department,state,gender,category,pwbd_subcategory,count,needs_review
        from vacancy where recruitment_id=:i order by post_name nulls first,category,pwbd_subcategory"""), {"i": rid}))
    r["vacancies"] = vac
    r["vacancy_note"] = None if vac else "Not specified in official notification"
    r["vacancy_verification"] = ("Verified by administrator" if r["admin_verified"] else
        "Extracted automatically from the official PDF; every row matched its printed total" if r["extraction_confidence"] == "high"
        else "Not yet verified; check the official notification PDF")
    r["updates"] = rows(s.execute(text(f"select {NOTE_COLS} {NOTE_FROM} where {OK} and n.recruitment_id=:i order by n.first_seen_at desc"), {"i": rid}))
    return r

@app.get("/v1/home")
def home(s=Depends(db)):
    def q(where, order="n.first_seen_at desc", lim=8):
        return rows(s.execute(text(f"select {NOTE_COLS} {NOTE_FROM} where {OK} and {where} order by {order} limit {lim}")))
    return {
        "latest_jobs": q("n.type='recruitment'"),
        "recently_updated": q("n.type not in ('recruitment','other')"),
        "results_today": q("n.type in ('result','merit_list','final_selection','cutoff') and n.first_seen_at::date = current_date"),
        "admit_cards": q("n.type='admit_card'"),
        "important": q("n.type in ('corrigendum','extension','cancellation','postponement','vacancy_revision','exam_date')"),
        "deadlines": rows(s.execute(text("""select r.id,r.title,r.apply_end,o.name organization from recruitment r
            join organization o on o.id=r.organization_id where r.apply_end >= current_date order by r.apply_end limit 8"""))),
    }

@app.get("/v1/organizations")
def organizations(category_id: int | None = None, state: str | None = None, q: str | None = None, s=Depends(db)):
    return rows(s.execute(text("""select o.id,o.name,o.short_name,o.state,o.official_domain,c.name category,
        (select count(*) from recruitment r where r.organization_id=o.id and (r.apply_end is null or r.apply_end>=current_date)) open_recruitments
        from organization o left join org_category c on c.id=o.category_id
        where (cast(:c as int) is null or o.category_id=:c) and (cast(:s as text) is null or o.state=:s)
        and (cast(:q as text) is null or o.name ilike '%'||:q||'%' or o.short_name ilike '%'||:q||'%')
        order by c.name,o.name"""), {"c": category_id, "s": state, "q": q}))

@app.get("/v1/org-categories")
def org_categories(s=Depends(db)):
    return rows(s.execute(text("select id,parent_id,name from org_category order by name")))

@app.get("/v1/sources/status")
def sources_status(status: str | None = None, s=Depends(db)):
    """Public transparency: which organizations are monitored, pending, or unavailable."""
    return rows(s.execute(text("""select sc.id,o.name organization,o.state,sc.url,sc.status,sc.kind,sc.last_checked_at,
        sc.last_success_at,sc.last_error from source sc join organization o on o.id=sc.organization_id
        where cast(:st as text) is null or sc.status=:st order by sc.status,o.name"""), {"st": status}))

@app.get("/v1/sources/summary")
def sources_summary(s=Depends(db)):
    return rows(s.execute(text("select status,count(*) n from source group by status order by status")))

# ------------------------------------------------------------------ device / user API
class Device(BaseModel):
    install_id: str = Field(min_length=8, max_length=64)
    fcm_token: str | None = None

@app.post("/v1/devices")
def register(d: Device, s=Depends(db)):
    uid = s.execute(text("""insert into app_user(id,install_id,fcm_token) values (:i,:iid,:t)
        on conflict (install_id) do update set fcm_token=coalesce(:t,app_user.fcm_token) returning id"""),
        {"i": uuid.uuid4(), "iid": d.install_id, "t": d.fcm_token}).scalar()
    s.commit()
    return {"user_id": str(uid), "token": make_token(uid)}

class Me(BaseModel):
    all_alerts: bool = False
    subscriptions: list[tuple[str, str]] = []

@app.get("/v1/me")
def me(u=Depends(current_user), s=Depends(db)):
    a = s.execute(text("select all_alerts from app_user where id=:u"), {"u": u}).scalar()
    subs = [[r.dimension, r.value] for r in s.execute(text("select dimension,value from subscription where user_id=:u order by 1,2"), {"u": u})]
    return {"all_alerts": bool(a), "subscriptions": subs}

@app.put("/v1/me")
def update_me(b: Me, u=Depends(current_user), s=Depends(db)):
    s.execute(text("update app_user set all_alerts=:a where id=:u"), {"a": b.all_alerts, "u": u})
    s.execute(text("delete from subscription where user_id=:u"), {"u": u})
    for dim, val in b.subscriptions:
        if dim not in ("organization", "state", "qualification", "category", "type"):
            raise HTTPException(422, f"Unknown subscription dimension {dim}")
        s.execute(text("insert into subscription values (:u,:d,:v) on conflict do nothing"), {"u": u, "d": dim, "v": val})
    s.commit(); return {"ok": True}

class Fcm(BaseModel):
    fcm_token: str

@app.put("/v1/me/fcm")
def set_fcm(b: Fcm, u=Depends(current_user), s=Depends(db)):
    s.execute(text("update app_user set fcm_token=null where fcm_token=:t and id<>:u"), {"t": b.fcm_token, "u": u})
    s.execute(text("update app_user set fcm_token=:t where id=:u"), {"t": b.fcm_token, "u": u}); s.commit(); return {"ok": True}

@app.get("/v1/me/saved")
def saved(u=Depends(current_user), s=Depends(db)):
    return rows(s.execute(text("""select r.id,r.title,r.apply_end,r.total_vacancies,o.name organization from saved_job j
        join recruitment r on r.id=j.recruitment_id join organization o on o.id=r.organization_id
        where j.user_id=:u order by r.apply_end nulls last"""), {"u": u}))

@app.put("/v1/me/saved/{rid}")
def save_job(rid: int, u=Depends(current_user), s=Depends(db)):
    if not s.execute(text("select 1 from recruitment where id=:r"), {"r": rid}).first(): raise HTTPException(404)
    s.execute(text("insert into saved_job values (:u,:r) on conflict do nothing"), {"u": u, "r": rid}); s.commit(); return {"saved": True}

@app.delete("/v1/me/saved/{rid}")
def unsave_job(rid: int, u=Depends(current_user), s=Depends(db)):
    s.execute(text("delete from saved_job where user_id=:u and recruitment_id=:r"), {"u": u, "r": rid}); s.commit(); return {"saved": False}

@app.get("/v1/me/feed")
def feed(limit: int = Query(100, le=200), u=Depends(current_user), s=Depends(db)):
    """Notification History: verified updates matching this user's subscriptions / All Government Job Alerts."""
    return rows(s.execute(text(f"""select {NOTE_COLS} {notify.BASE} cross join app_user u
        where u.id=:u and {OK} and n.type<>'other' and {notify.MATCH} order by n.first_seen_at desc limit :l"""), {"u": u, "l": limit}))

# ------------------------------------------------------------------ admin API
A = [Depends(admin)]

@app.get("/admin-ui", include_in_schema=False)
def admin_ui():
    return FileResponse(pathlib.Path(__file__).parent / "static" / "admin.html")

@app.get("/admin/health", dependencies=A)
def admin_health(s=Depends(db)):
    g = lambda q: s.execute(text(q)).scalar()
    return {
        "sources_by_status": rows(s.execute(text("select status,count(*) n from source group by status"))),
        "checks_24h": g("select count(*) from source_check_log where checked_at>now()-interval '24 hours'"),
        "failed_checks_24h": g("select count(*) from source_check_log where not ok and checked_at>now()-interval '24 hours'"),
        "unverified_notifications": g("select count(*) from notification where verification='unverified'"),
        "drafts_needing_review": g("select count(*) from recruitment_draft where status in ('needs_review','failed')"),
        "pushes_24h": g("select count(*) from push_log where sent_at>now()-interval '24 hours'"),
        "users": g("select count(*) from app_user"),
        "users_all_alerts": g("select count(*) from app_user where all_alerts"),
        "users_with_push_token": g("select count(*) from app_user where fcm_token is not null"),
        "firebase_configured": bool(settings.firebase_credentials),
        "notifications_total": g("select count(*) from notification"),
        "recruitments_total": g("select count(*) from recruitment"),
        "open_alerts": rows(s.execute(text("select id,created_at,kind,message from system_alert where not acknowledged order by id desc limit 50"))),
        "subscriptions_by_dimension": rows(s.execute(text("select dimension,count(*) n from subscription group by dimension"))),
    }

@app.post("/admin/alerts/{aid}/ack", dependencies=A)
def ack_alert(aid: int, s=Depends(db)):
    s.execute(text("update system_alert set acknowledged=true where id=:i"), {"i": aid}); s.commit(); return {"ok": True}

@app.get("/admin/sources", dependencies=A)
def admin_sources(status: str | None = None, q: str | None = None, limit: int = Query(300, le=1000), s=Depends(db)):
    return rows(s.execute(text("""select sc.id,sc.organization_id,o.name organization,sc.url,sc.kind,sc.css_selector,sc.status,
        sc.interval_minutes,sc.last_checked_at,sc.last_success_at,sc.last_error,sc.consecutive_failures,sc.last_item_count
        from source sc join organization o on o.id=sc.organization_id
        where (cast(:st as text) is null or sc.status=:st) and (cast(:q as text) is null or o.name ilike '%'||:q||'%' or sc.url ilike '%'||:q||'%')
        order by sc.status,o.name limit :l"""), {"st": status, "q": q, "l": limit}))

class SourceIn(BaseModel):
    organization_id: int; url: str; kind: str = "html_list"; css_selector: str | None = None; interval_minutes: int = 60

@app.post("/admin/sources", dependencies=A)
def add_source(b: SourceIn, s=Depends(db)):
    if b.kind not in ("html_list", "rss", "sitemap", "api", "manual_only"): raise HTTPException(422, "bad kind")
    sid = s.execute(text("""insert into source(organization_id,url,kind,css_selector,interval_minutes) values (:o,:u,:k,:c,:i) returning id"""),
        {"o": b.organization_id, "u": b.url, "k": b.kind, "c": b.css_selector, "i": b.interval_minutes}).scalar()
    s.commit(); return {"id": sid, "status": "pending_integration"}

class SourcePatch(BaseModel):
    url: str | None = None; kind: str | None = None; css_selector: str | None = None
    interval_minutes: int | None = None; status: str | None = None

@app.patch("/admin/sources/{sid}", dependencies=A)
def patch_source(sid: int, b: SourcePatch, s=Depends(db)):
    d = b.model_dump(exclude_none=True)
    if "status" in d and d["status"] not in ("monitored", "pending_integration", "manual_verification", "unavailable", "disabled"):
        raise HTTPException(422, "bad status")
    if d:
        if "url" in d or "css_selector" in d or "kind" in d:
            d["content_hash"] = None; d["baselined"] = False if "url" in d else None
            d = {k: v for k, v in d.items() if v is not None or k == "content_hash"}
        s.execute(text(f"update source set {','.join(f'{k}=:{k}' for k in d)} where id=:id"), {**d, "id": sid}); s.commit()
    return {"ok": True}

@app.post("/admin/sources/{sid}/check", dependencies=A)
def check_now(sid: int):
    return monitor.check_source(sid)

class Probe(BaseModel):
    url: str; kind: str = "html_list"; css_selector: str | None = None

@app.post("/admin/sources/discover", dependencies=A)
def discover(b: Probe):
    """New-source workflow: preview what links the monitor would extract from a page before adding it."""
    if not monitor.robots_allowed(b.url): raise HTTPException(409, "robots.txt disallows automated fetching")
    r = monitor.fetch(b.url)
    if r.status_code in (401, 403, 429): raise HTTPException(409, f"Access restricted (HTTP {r.status_code}); manual verification needed")
    return {"http_status": r.status_code, "items": extract_items(b.kind, b.css_selector, b.url, r.content)[:50]}

def _check_all(ids):
    def one(i):
        try: monitor.check_source(i)
        except Exception: pass
    with ThreadPoolExecutor(6) as ex: list(ex.map(one, ids))
    verify.run()

@app.post("/admin/sources/check-all", dependencies=A)
def check_all(bg: BackgroundTasks, only_unchecked: bool = False, s=Depends(db)):
    """Check every active source now (in the background). Use after first start so the app fills up immediately."""
    ids = [r.id for r in s.execute(text("""select id from source where status<>'disabled' and kind<>'manual_only'
        and (not :u or last_checked_at is null) order by id"""), {"u": only_unchecked})]
    bg.add_task(_check_all, ids); return {"started": len(ids)}

@app.get("/admin/logs", dependencies=A)
def logs(source_id: int | None = None, only_failed: bool = False, limit: int = Query(100, le=500), s=Depends(db)):
    return rows(s.execute(text("""select l.id,l.checked_at,l.ok,l.http_status,l.new_items,l.error,l.source_id,o.name organization,sc.url
        from source_check_log l join source sc on sc.id=l.source_id join organization o on o.id=sc.organization_id
        where (cast(:s as int) is null or l.source_id=:s) and (not :f or not l.ok) order by l.id desc limit :l"""),
        {"s": source_id, "f": only_failed, "l": limit}))

class OrgIn(BaseModel):
    name: str; official_domain: str; category_id: int | None = None; short_name: str | None = None; state: str | None = None

@app.post("/admin/organizations", dependencies=A)
def add_org(b: OrgIn, s=Depends(db)):
    oid = s.execute(text("insert into organization(category_id,name,short_name,state,official_domain) values (:c,:n,:s,:st,:d) returning id"),
                    {"c": b.category_id, "n": b.name, "s": b.short_name, "st": b.state, "d": b.official_domain}).scalar()
    s.commit(); return {"id": oid}

class CatIn(BaseModel):
    name: str; parent_id: int | None = None

@app.post("/admin/org-categories", dependencies=A)
def add_cat(b: CatIn, s=Depends(db)):
    cid = s.execute(text("insert into org_category(name,parent_id) values (:n,:p) returning id"), {"n": b.name, "p": b.parent_id}).scalar()
    s.commit(); return {"id": cid}

@app.get("/admin/notifications", dependencies=A)
def admin_notes(verification: str = "unverified", type: str | None = None, include_duplicates: bool = False,
                limit: int = Query(100, le=300), s=Depends(db)):
    return rows(s.execute(text(f"""select {NOTE_COLS},n.duplicate_of,sc.url source_url {NOTE_FROM}
        where n.verification=:v and (cast(:t as text) is null or n.type=:t) and (:d or n.duplicate_of is null)
        order by n.first_seen_at desc limit :l"""), {"v": verification, "t": type, "d": include_duplicates, "l": limit}))

class NotePatch(BaseModel):
    verification: str | None = None; type: str | None = None; recruitment_id: int | None = None
    pdf_url: str | None = None; duplicate_of: int | None = None; clear_duplicate: bool = False

@app.patch("/admin/notifications/{nid}", dependencies=A)
def patch_note(nid: int, b: NotePatch, s=Depends(db)):
    if b.verification and b.verification not in ("unverified", "auto_verified", "admin_verified", "rejected"): raise HTTPException(422, "bad verification")
    s.execute(text("""update notification set verification=coalesce(:v,verification),type=coalesce(:t,type),
        recruitment_id=coalesce(:r,recruitment_id),pdf_url=coalesce(:p,pdf_url),
        duplicate_of=case when :cd then null else coalesce(:dup,duplicate_of) end,
        last_verified_at=case when cast(:v as text) is not null then now() else last_verified_at end where id=:i"""),
        {"v": b.verification, "t": b.type, "r": b.recruitment_id, "p": b.pdf_url, "dup": b.duplicate_of, "cd": b.clear_duplicate, "i": nid})
    if b.pdf_url:   # new PDF supplied -> allow re-extraction
        s.execute(text("delete from recruitment_draft where notification_id=:i and status in ('needs_review','failed')"), {"i": nid})
    s.commit(); return {"ok": True}

@app.get("/admin/duplicates", dependencies=A)
def duplicates(s=Depends(db)):
    return rows(s.execute(text("""select n.dedupe_key,count(*) n,array_agg(n.id order by n.id) ids,min(n.title) title
        from notification n where n.duplicate_of is null and n.dedupe_key is not null group by n.dedupe_key having count(*)>1 limit 100""")))

@app.get("/admin/drafts", dependencies=A)
def drafts(status: str = "needs_review", s=Depends(db)):
    return rows(s.execute(text("""select d.id,d.notification_id,d.status,d.pdf_url,d.flags,d.error,d.created_at,n.title,n.official_url,
        o.name organization,o.id organization_id from recruitment_draft d join notification n on n.id=d.notification_id
        join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id
        where d.status=:s or (:s='needs_review' and d.status='failed') order by d.id desc limit 200"""), {"s": status}))

@app.get("/admin/drafts/{did}", dependencies=A)
def draft(did: int, s=Depends(db)):
    d = one(s.execute(text("""select d.*,n.title,o.id organization_id from recruitment_draft d join notification n on n.id=d.notification_id
        join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id where d.id=:i"""), {"i": did}))
    if not d: raise HTTPException(404)
    return d

class Approve(BaseModel):
    fields: dict = {}
    vacancies: list[dict] = []
    title: str | None = None

@app.post("/admin/drafts/{did}/approve", dependencies=A)
def approve(did: int, b: Approve, s=Depends(db)):
    d = one(s.execute(text("""select d.*,n.title ntitle,o.id org_id,o.state ostate,n.official_url from recruitment_draft d
        join notification n on n.id=d.notification_id join source sc on sc.id=n.source_id
        join organization o on o.id=sc.organization_id where d.id=:i"""), {"i": did}))
    if not d: raise HTTPException(404)
    for v in b.vacancies:
        if "category" not in v or not isinstance(v.get("count"), int) or v["count"] < 0:
            raise HTTPException(422, "each vacancy needs category and a non-negative integer count")
    fields = {"state": d["ostate"], "notification_pdf_url": d["pdf_url"], "official_site_url": d["official_url"], **b.fields}
    rid = pdfs.publish_recruitment(s, org_id=d["org_id"], title=b.title or d["ntitle"], fields=fields, vacancies=b.vacancies,
                                   notif_id=d["notification_id"], admin_verified=True, confidence="manual", flags=[], recruitment_id=d["recruitment_id"])
    s.execute(text("update recruitment_draft set status='approved',recruitment_id=:r where id=:i"), {"r": rid, "i": did}); s.commit()
    return {"recruitment_id": rid}

@app.post("/admin/drafts/{did}/reject", dependencies=A)
def reject_draft(did: int, s=Depends(db)):
    s.execute(text("update recruitment_draft set status='rejected' where id=:i"), {"i": did}); s.commit(); return {"ok": True}

@app.post("/admin/drafts/{did}/reprocess", dependencies=A)
def reprocess(did: int, s=Depends(db)):
    s.execute(text("delete from recruitment_draft where id=:i and status<>'approved'"), {"i": did}); s.commit(); return {"ok": True}

@app.get("/admin/recruitments", dependencies=A)
def admin_recruitments(q: str | None = None, limit: int = Query(100, le=300), s=Depends(db)):
    return rows(s.execute(text("""select r.id,r.title,r.advertisement_no,r.total_vacancies,r.apply_end,r.admin_verified,r.extraction_confidence,
        o.name organization from recruitment r join organization o on o.id=r.organization_id
        where cast(:q as text) is null or r.title ilike '%'||:q||'%' order by r.id desc limit :l"""), {"q": q, "l": limit}))

class RecruitmentIn(BaseModel):
    organization_id: int | None = None
    title: str
    fields: dict = {}
    vacancies: list[dict] | None = None

@app.post("/admin/recruitments", dependencies=A)
def create_recruitment(b: RecruitmentIn, s=Depends(db)):
    if not b.organization_id: raise HTTPException(422, "organization_id required")
    rid = pdfs.publish_recruitment(s, org_id=b.organization_id, title=b.title, fields=b.fields, vacancies=b.vacancies or [],
                                   notif_id=None, admin_verified=True, confidence="manual", flags=[]); s.commit(); return {"id": rid}

@app.put("/admin/recruitments/{rid}", dependencies=A)
def update_recruitment(rid: int, b: RecruitmentIn, s=Depends(db)):
    cur = one(s.execute(text("select organization_id from recruitment where id=:i"), {"i": rid}))
    if not cur: raise HTTPException(404)
    if b.vacancies is None:
        vac = rows(s.execute(text("select post_name,department,state,gender,category,pwbd_subcategory,count from vacancy where recruitment_id=:i"), {"i": rid}))
    else:
        vac = b.vacancies
    pdfs.publish_recruitment(s, org_id=cur["organization_id"], title=b.title, fields=b.fields, vacancies=vac, notif_id=None,
                             admin_verified=True, confidence="manual", flags=[], recruitment_id=rid); s.commit(); return {"id": rid}

@app.get("/admin/analytics", dependencies=A)
def analytics(s=Depends(db)):
    return {"pushes_by_day": rows(s.execute(text("select sent_at::date d,count(*) n from push_log group by 1 order by 1 desc limit 30"))),
            "notifications_by_type": rows(s.execute(text("select type,count(*) n from notification where duplicate_of is null group by 1 order by 2 desc"))),
            "new_users_by_day": rows(s.execute(text("select created_at::date d,count(*) n from app_user group by 1 order by 1 desc limit 30")))}

@app.post("/admin/pipeline/run", dependencies=A)
def run_pipeline():
    v = verify.run(); p = pdfs.process_pending(); n = notify.dispatch_pending()
    return {"verified": v, "pdfs_processed": p, "pushes_sent": n}

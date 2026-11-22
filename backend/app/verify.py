"""Auto-verify only when the notification URL host is on the organization's registered official domain.
Also links result/admit-card/etc. notifications to their original recruitment by advertisement number."""
from sqlalchemy import text
from .db import SessionLocal
from .extract import on_domain

def run() -> int:
    n = 0
    with SessionLocal() as s:
        rows = s.execute(text("""select n.id, n.official_url, n.pdf_url, o.official_domain from notification n
            join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id
            where n.verification='unverified'""")).all()
        for r in rows:
            if on_domain(r.official_url, r.official_domain) and (not r.pdf_url or on_domain(r.pdf_url, r.official_domain)):
                s.execute(text("update notification set verification='auto_verified', last_verified_at=now() where id=:i"), {"i": r.id})
                n += 1
        s.execute(text("""update notification n set recruitment_id=r.id from source sc, recruitment r
            where n.source_id=sc.id and r.organization_id=sc.organization_id and n.recruitment_id is null
            and n.type<>'recruitment' and r.advertisement_no is not null and length(r.advertisement_no)>=4
            and position(lower(r.advertisement_no) in lower(n.title))>0"""))
        s.commit()
    return n

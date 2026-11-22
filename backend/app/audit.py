"""Periodic source audit: flag monitored sources that silently went stale."""
from sqlalchemy import text
from .db import SessionLocal

def run() -> int:
    with SessionLocal() as s:
        rows = s.execute(text("""update source set status='unavailable' where status='monitored'
            and last_success_at < now() - (interval_minutes * 4 || ' minutes')::interval
            returning id,url""")).all()
        for r in rows:
            s.execute(text("insert into system_alert(kind,message) values ('source_stale',:m)"),
                      {"m": f"Source {r.url} has not succeeded recently; marked unavailable"})
        s.commit()
        return len(rows)

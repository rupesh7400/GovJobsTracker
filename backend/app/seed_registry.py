"""Load sql/registry.txt: organizations + categories + one pending source per organization (its official home page).
Idempotent. A source only becomes 'monitored' after a real fetch finds notification links."""
import pathlib, logging
from sqlalchemy import text
from .db import SessionLocal
log = logging.getLogger("seed")

def run() -> tuple[int, int]:
    path = pathlib.Path(__file__).resolve().parent.parent / "sql" / "registry.txt"
    orgs = srcs = 0
    with SessionLocal() as s:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cat, name, short, state, domain = [p.strip() for p in line.split("|")]
            cid = s.execute(text("""insert into org_category(name) values (:n) on conflict (name) do update set name=excluded.name returning id"""), {"n": cat}).scalar()
            oid = s.execute(text("""insert into organization(category_id,name,short_name,state,official_domain) values (:c,:n,:s,nullif(:st,''),:d)
                on conflict (name) do update set category_id=excluded.category_id,short_name=excluded.short_name,
                state=excluded.state,official_domain=excluded.official_domain returning id"""),
                {"c": cid, "n": name, "s": short, "st": state, "d": domain}).scalar()
            orgs += 1
            r = s.execute(text("""insert into source(organization_id,url,kind) values (:o,:u,'html_list') on conflict (url) do nothing"""),
                          {"o": oid, "u": f"https://{domain}/"})
            srcs += r.rowcount
        s.commit()
    log.info("registry: %d organizations, %d new sources", orgs, srcs)
    return orgs, srcs

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); print(run())

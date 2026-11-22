import pathlib, logging
from sqlalchemy import text
from .db import engine
log = logging.getLogger("migrate")

def run() -> None:
    d = pathlib.Path(__file__).resolve().parent.parent / "sql" / "migrations"
    with engine.begin() as c:
        c.execute(text("create table if not exists schema_migrations(name text primary key, applied_at timestamptz default now())"))
        done = {r[0] for r in c.execute(text("select name from schema_migrations"))}
        for f in sorted(d.glob("*.sql")):
            if f.name in done:
                continue
            log.info("applying %s", f.name)
            c.exec_driver_sql(f.read_text(encoding="utf-8"))
            c.execute(text("insert into schema_migrations(name) values (:n)"), {"n": f.name})

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO); run()

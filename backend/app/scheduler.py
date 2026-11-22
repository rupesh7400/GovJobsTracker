import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import text
from .db import SessionLocal
from . import monitor, verify, notify, pdfs, audit

logging.basicConfig(level=logging.INFO)
sched = BlockingScheduler()

def sync_jobs():
    """One job per active source. Existing jobs are NEVER re-created (that used to reset their timers so nothing ever ran).
    Sources that were never checked, or are overdue, are scheduled to run soon, staggered 3 s apart to stay polite."""
    with SessionLocal() as s:
        rows = s.execute(text("""select id, interval_minutes, last_checked_at,
              (last_checked_at is null or last_checked_at < now() - (interval_minutes || ' minutes')::interval) as due
            from source where status not in ('disabled','manual_verification') and kind<>'manual_only'
            order by last_checked_at nulls first, id""")).all()
    keep, n = set(), 0
    for r in rows:
        jid = f"src-{r.id}"; keep.add(jid)
        job = sched.get_job(jid)
        if job is None:
            kw = {}
            if r.due:
                kw["next_run_time"] = datetime.now(timezone.utc) + timedelta(seconds=15 + n * 3); n += 1
            sched.add_job(monitor.check_source, "interval", minutes=r.interval_minutes, args=[r.id], id=jid,
                          max_instances=1, coalesce=True, jitter=120, **kw)
        elif job.trigger.interval != timedelta(minutes=r.interval_minutes):
            sched.reschedule_job(jid, trigger="interval", minutes=r.interval_minutes)
    for j in sched.get_jobs():
        if j.id.startswith("src-") and j.id not in keep:
            j.remove()
    logging.info("sync_jobs: %d active sources, %d scheduled to run now", len(keep), n)

def safe(fn):
    def run():
        try: fn()
        except Exception: logging.exception("job %s failed", fn.__name__)
    run.__name__ = fn.__name__
    return run

def pipeline():
    verify.run(); pdfs.process_pending(); notify.dispatch_pending()

if __name__ == "__main__":
    sync_jobs()
    sched.add_job(safe(sync_jobs), "interval", minutes=10, id="sync")
    sched.add_job(safe(pipeline), "interval", minutes=3, id="pipeline")
    sched.add_job(safe(audit.run), "interval", hours=6, id="audit")
    sched.start()

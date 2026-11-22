"""FCM push. Only verified, non-duplicate notifications; (user, notification) unique in push_log."""
import logging
from sqlalchemy import text
from .config import settings
from .db import SessionLocal
log = logging.getLogger("notify")
_app = None

def _fcm():
    global _app
    if _app is None and settings.firebase_credentials:
        import firebase_admin
        from firebase_admin import credentials
        _app = firebase_admin.initialize_app(credentials.Certificate(settings.firebase_credentials))
    return _app

# A user matches when all_alerts is on, or any subscription (organization/state/type/category/qualification) matches.
MATCH = """(u.all_alerts or exists (select 1 from subscription s where s.user_id=u.id and (
       (s.dimension='organization' and s.value=o.name)
    or (s.dimension='state' and s.value=o.state)
    or (s.dimension='type' and s.value=n.type)
    or (s.dimension='category' and s.value=oc.name)
    or (s.dimension='qualification' and r.qualification_levels is not null and s.value = any(r.qualification_levels)))))"""

BASE = """from notification n join source sc on sc.id=n.source_id join organization o on o.id=sc.organization_id
          left join org_category oc on oc.id=o.category_id left join recruitment r on r.id=n.recruitment_id"""

def dispatch_pending() -> int:
    sent = 0
    with SessionLocal() as s:
        rows = s.execute(text(f"""select n.id,n.title,n.type,o.name org {BASE}
          where n.verification in ('auto_verified','admin_verified') and n.push_sent_at is null and n.duplicate_of is null
          order by n.first_seen_at limit 200""")).all()
        for n in rows:
            users = s.execute(text(f"""select u.id,u.fcm_token {BASE.replace('from notification n','from notification n cross join app_user u',1)}
                where n.id=:nid and u.fcm_token is not null and {MATCH}
                and not exists (select 1 from push_log p where p.user_id=u.id and p.notification_id=n.id)"""), {"nid": n.id}).all()
            if users and not _fcm():
                log.warning("Firebase not configured; %d pushes pending for notification %s", len(users), n.id)
                continue
            for u in users:
                try:
                    from firebase_admin import messaging
                    messaging.send(messaging.Message(
                        token=u.fcm_token,
                        notification=messaging.Notification(title=f"{n.org}: {n.type.replace('_', ' ').title()}", body=n.title[:180]),
                        data={"notification_id": str(n.id)},
                        android=messaging.AndroidConfig(priority="high")))
                    s.execute(text("insert into push_log(user_id,notification_id) values (:u,:n) on conflict do nothing"), {"u": u.id, "n": n.id})
                    sent += 1
                except Exception as ex:
                    log.warning("push failed for user %s: %s", u.id, ex)
            s.execute(text("update notification set push_sent_at=now() where id=:i"), {"i": n.id})
        s.commit()
    return sent

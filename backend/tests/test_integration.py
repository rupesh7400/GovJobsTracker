import sys, types, uuid
import pytest
from sqlalchemy import text
from app.db import SessionLocal

def _org(s, domain="test-upsc.gov.in"):
    return s.execute(text("""insert into organization(name,official_domain,state) values (:n,:d,'Maharashtra')
        on conflict (name) do update set official_domain=:d returning id"""), {"n": "TEST ORG " + domain, "d": domain}).scalar()

def _source(s, org, url):
    return s.execute(text("insert into source(organization_id,url) values (:o,:u) on conflict (url) do update set url=:u returning id"), {"o": org, "u": url}).scalar()

def _note(s, src, title, url, typ="recruitment"):
    from app.extract import fingerprint
    return s.execute(text("""insert into notification(source_id,type,title,official_url,fingerprint) values (:s,:t,:ti,:u,:f)
        on conflict (fingerprint) do update set title=:ti returning id"""), {"s": src, "t": typ, "ti": title, "u": url, "f": fingerprint(src, url, title)}).scalar()

def test_health_and_admin_auth(client, admin):
    assert client.get("/health").json() == {"ok": True}
    assert client.get("/admin/sources").status_code == 401
    assert client.get("/admin/sources", headers=admin).status_code == 200
    assert client.get("/admin-ui").status_code == 200

def test_device_token_and_subscriptions(client):
    iid = str(uuid.uuid4())
    r = client.post("/v1/devices", json={"install_id": iid}).json()
    h = {"Authorization": "Bearer " + r["token"]}
    assert client.get("/v1/me").status_code == 401
    assert client.put("/v1/me", headers=h, json={"all_alerts": True, "subscriptions": [["state", "Maharashtra"]]}).status_code == 200
    me = client.get("/v1/me", headers=h).json()
    assert me["all_alerts"] is True and me["subscriptions"] == [["state", "Maharashtra"]]
    assert client.put("/v1/me", headers=h, json={"all_alerts": False, "subscriptions": [["bogus", "x"]]}).status_code == 422
    assert client.post("/v1/devices", json={"install_id": iid}).json()["user_id"] == r["user_id"]   # idempotent

def test_verification_search_and_feed(client):
    with SessionLocal() as s:
        org = _org(s); src = _source(s, org, "https://test-upsc.gov.in/x")
        good = _note(s, src, "Recruitment of Analysts 2026 TESTMARK", "https://test-upsc.gov.in/a.pdf")
        bad = _note(s, src, "Recruitment of Fakes 2026 TESTMARK", "https://evil.example.com/a.pdf")
        s.commit()
    assert client.post("/admin/pipeline/run", headers={"X-Admin-Key": "test-admin"}).status_code == 200
    titles = [n["title"] for n in client.get("/v1/notifications", params={"q": "TESTMARK"}).json()]
    assert "Recruitment of Analysts 2026 TESTMARK" in titles and "Recruitment of Fakes 2026 TESTMARK" not in titles  # off-domain never public

def test_push_no_duplicates(client, monkeypatch):
    from app import notify, verify
    sent = []
    fa, msg = types.ModuleType("firebase_admin"), types.ModuleType("firebase_admin.messaging")
    class Obj:
        def __init__(self, **kw): self.kw = kw
    msg.Message = msg.Notification = msg.AndroidConfig = Obj
    msg.send = lambda m: sent.append(m.kw["token"]); fa.messaging = msg
    monkeypatch.setitem(sys.modules, "firebase_admin", fa); monkeypatch.setitem(sys.modules, "firebase_admin.messaging", msg)
    monkeypatch.setattr(notify, "_fcm", lambda: True)
    tok = "tok-" + uuid.uuid4().hex
    t = client.post("/v1/devices", json={"install_id": str(uuid.uuid4()), "fcm_token": tok}).json()["token"]
    client.put("/v1/me", headers={"Authorization": "Bearer " + t}, json={"all_alerts": True, "subscriptions": []})
    with SessionLocal() as s:
        org = _org(s, "test-push.gov.in"); src = _source(s, org, "https://test-push.gov.in/")
        nid = _note(s, src, "Admit Card for Test Exam PUSHMARK", "https://test-push.gov.in/ac", "admit_card"); s.commit()
    verify.run(); notify.dispatch_pending()
    assert sent.count(tok) == 1
    with SessionLocal() as s:
        s.execute(text("update notification set push_sent_at=null where id=:i"), {"i": nid}); s.commit()
    notify.dispatch_pending()
    assert sent.count(tok) == 1        # push_log prevents a second push to the same user

def test_draft_approval_and_vacancy_api(client, admin):
    with SessionLocal() as s:
        org = _org(s, "test-draft.gov.in"); src = _source(s, org, "https://test-draft.gov.in/")
        nid = _note(s, src, "Recruitment DRAFTMARK Advt 9/2026", "https://test-draft.gov.in/n.pdf")
        s.execute(text("""insert into recruitment_draft(notification_id,status,flags) values (:n,'needs_review','{row_sum_mismatch:x}')
            on conflict (notification_id) do update set status='needs_review'"""), {"n": nid}); s.commit()
        did = s.execute(text("select id from recruitment_draft where notification_id=:n"), {"n": nid}).scalar()
    bad = client.post(f"/admin/drafts/{did}/approve", headers=admin, json={"vacancies": [{"category": "UR", "count": -1}]})
    assert bad.status_code == 422
    ok = client.post(f"/admin/drafts/{did}/approve", headers=admin, json={
        "fields": {"advertisement_no": "9/2026", "apply_end": "2099-01-01", "qualification_levels": ["graduate"], "pwbd_eligible": True},
        "vacancies": [{"post_name": "Analyst", "category": "UR", "count": 4}, {"post_name": "Analyst", "category": "SC", "count": 1}, {"post_name": "Analyst", "category": "TOTAL", "count": 5}]})
    rid = ok.json()["recruitment_id"]
    r = client.get(f"/v1/recruitments/{rid}").json()
    assert r["admin_verified"] is True and len(r["vacancies"]) == 3 and r["vacancy_note"] is None
    assert any(x["id"] == rid for x in client.get("/v1/recruitments", params={"qualification": "graduate", "pwbd": "true", "reservation_category": "SC"}).json())
    assert all(x["id"] != rid for x in client.get("/v1/recruitments", params={"reservation_category": "ST"}).json())
    # a result mentioning the advertisement number gets linked to the recruitment
    with SessionLocal() as s:
        _note(s, src, "Result of Advt 9/2026 declared", "https://test-draft.gov.in/res", "result"); s.commit()
    client.post("/admin/pipeline/run", headers=admin)
    assert any(u["type"] == "result" for u in client.get(f"/v1/recruitments/{rid}").json()["updates"])

def test_recruitment_without_vacancies_says_not_specified(client, admin):
    with SessionLocal() as s: org = _org(s, "test-nov.gov.in"); s.commit()
    rid = client.post("/admin/recruitments", headers=admin, json={"organization_id": org, "title": "NOVAC TEST", "fields": {}, "vacancies": []}).json()["id"]
    assert client.get(f"/v1/recruitments/{rid}").json()["vacancy_note"] == "Not specified in official notification"

def test_saved_jobs(client, admin):
    t = client.post("/v1/devices", json={"install_id": str(uuid.uuid4())}).json()["token"]; h = {"Authorization": "Bearer " + t}
    with SessionLocal() as s: org = _org(s, "test-nov.gov.in"); s.commit()
    rid = client.post("/admin/recruitments", headers=admin, json={"organization_id": org, "title": "SAVE TEST", "fields": {}}).json()["id"]
    assert client.put(f"/v1/me/saved/{rid}", headers=h).json() == {"saved": True}
    assert [x["id"] for x in client.get("/v1/me/saved", headers=h).json()] == [rid]
    client.delete(f"/v1/me/saved/{rid}", headers=h); assert client.get("/v1/me/saved", headers=h).json() == []

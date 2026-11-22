"""Tests that need no database or network. Run: python -m pytest tests/test_pure.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("TOKEN_SECRET", "test-secret")
from app.classify import classify
from app.extract import extract_items, fingerprint, dedupe_key
from app import vacancy

def test_classify():
    assert classify("SSC CGL 2026 Admit Card") == "admit_card"
    assert classify("IBPS PO Final Result") == "final_selection"
    assert classify("Corrigendum to Advt No 5") == "corrigendum"
    assert classify("Recruitment of Clerks") == "recruitment"
    assert classify("Last date extended for X") == "extension"
    assert classify("Tender notification for printing") == "other"
    assert classify("Press release") == "other"

def test_fingerprint_dedupe():
    assert fingerprint(1, "http://a/b#x", "A  b") == fingerprint(1, "http://a/b", "a b")
    assert fingerprint(1, "http://a/b", "x") != fingerprint(2, "http://a/b", "x")
    assert dedupe_key(1, "Recruitment  of Clerks!") == dedupe_key(1, "recruitment of clerks")

HTML = b"""<html><body><a href="/about">About Us Page Link Here</a><a href="/careers">Careers</a>
<a href="/files/advt-2026.pdf">Detailed Advertisement for Recruitment of Clerks 2026</a>
<a href="/r">Result of Preliminary Examination 2026 declared</a><a href="javascript:void(0)">Recruitment javascript link</a></body></html>"""

def test_extract_items_generic_filters_menu_noise():
    items = extract_items("html_list", None, "https://x.gov.in/", HTML)
    titles = [i["title"] for i in items]
    assert any("Advertisement" in t for t in titles) and any("Result" in t for t in titles)
    assert not any(t in ("Careers",) for t in titles) and not any("javascript" in i["url"] for i in items)
    assert items[0]["url"].startswith("https://x.gov.in/")

def test_extract_items_selector():
    items = extract_items("html_list", "a[href$='.pdf']", "https://x.gov.in/", HTML)
    assert len(items) == 1 and items[0]["url"].endswith("advt-2026.pdf")

TABLE = [["Sr", "Name of Post", "UR", "SC", "ST", "OBC (NCL)", "EWS", "Total", "PwBD"],
         ["1", "Junior Assistant", "10", "3", "2", "5", "2", "22", "1"],
         ["2", "Steno", "4", "1", "0", "2", "1", "8", "-"],
         ["", "Total", "14", "4", "2", "7", "3", "30", "1"]]

def test_table_parse_ok_high_confidence():
    r = vacancy.extract([TABLE], "Advt. No. 03/2026 Total Vacancies: 30\nLast date for online application: 15/12/2026")
    assert r["confidence"] == "high", r["flags"]
    got = {(v["post_name"], v["category"]): v["count"] for v in r["vacancies"]}
    assert got[("Junior Assistant", "OBC-NCL")] == 5 and got[("Steno", "PwBD")] == 0
    assert r["meta"]["advertisement_no"] == "03/2026" and r["meta"]["total_vacancies"] == 30
    assert r["meta"]["apply_end"] == "2026-12-15"

def test_row_sum_mismatch_goes_to_review():
    bad = [list(r) for r in TABLE]; bad[1][7] = "23"
    r = vacancy.extract([bad], "")
    assert r["confidence"] == "low" and any(f.startswith("row_sum_mismatch") for f in r["flags"])

def test_no_total_column_is_never_high():
    t = [["Post", "UR", "SC", "ST", "OBC"], ["Clerk", "5", "2", "1", "3"]]
    r = vacancy.extract([t], "")
    assert r["confidence"] == "low" and r["vacancies"]
    assert "total_vacancies" not in r["meta"]            # never computed

def test_non_numeric_cell_flagged():
    t = [["Post", "UR", "SC", "ST", "Total"], ["Clerk", "5", "x", "1", "6"]]
    assert any(f.startswith("non_numeric") for f in vacancy.extract([t], "")["flags"])

def test_pwbd_subcategories():
    t = [["Post", "UR", "SC", "ST", "OBC", "PwBD", "", "", "Total"], ["", "", "", "", "", "VI", "HI", "LD", ""],
         ["Clerk", "5", "2", "1", "3", "1", "0", "2", "11"]]
    r = vacancy.extract([t], "")
    subs = {v["pwbd_subcategory"]: v["count"] for v in r["vacancies"] if v["category"] == "PwBD"}
    assert subs == {"VI": 1, "HI": 0, "LD": 2}

def test_text_fallback_low_confidence():
    txt = "Vacancy details\nPost UR SC ST OBC Total\nClerk 5 2 1 3 11\nPeon 2 1 0 1 4\nNote: see below"
    r = vacancy.extract([], txt)
    assert r["confidence"] == "low" and len(r["vacancies"]) == 10 and "text_layout_parsed" in r["flags"]

def test_no_table_flagged():
    r = vacancy.extract([], "nothing useful")
    assert r["vacancies"] == [] and "no_vacancy_table_found" in r["flags"] and r["confidence"] == "low"

def test_tokens():
    from app.tokens import make_token, parse_token
    import uuid
    u = uuid.uuid4(); t = make_token(u)
    assert parse_token(t) == u and parse_token(t[:-1] + ("0" if t[-1] != "0" else "1")) is None and parse_token("junk") is None

def test_on_domain():
    from app.extract import on_domain
    assert on_domain("https://www.upsc.gov.in/x.pdf", "upsc.gov.in")
    assert not on_domain("https://upsc.gov.in.evil.com/x", "upsc.gov.in")
    assert not on_domain("https://fakeupsc.gov.in/x", "upsc.gov.in")

"""Category-wise vacancy extraction from tables/text of an official PDF. PURE functions.
Rules: never invent or compute vacancies. Numbers come only from printed cells. Every parse is validated
against printed totals; anything uncertain is returned with flags so it goes to admin review."""
import re
from datetime import date

_CAT = {"UR": "UR", "GEN": "UR", "GENERAL": "UR", "UNRESERVED": "UR", "GENUR": "UR", "URGEN": "UR",
        "GENERALUR": "UR", "URGENERAL": "UR", "SC": "SC", "ST": "ST", "OBC": "OBC", "OBCNCL": "OBC-NCL",
        "OBCNONCREAMYLAYER": "OBC-NCL", "EWS": "EWS", "PWBD": "PwBD", "PWD": "PwBD", "PH": "PwBD",
        "PWWD": "PwBD", "DIVYANG": "PwBD", "ESM": "ESM", "EXSM": "ESM", "EXSERVICEMEN": "ESM",
        "EXSERVICEMAN": "ESM", "TOTAL": "TOTAL", "TOT": "TOTAL", "GRANDTOTAL": "TOTAL",
        "TOTALVACANCIES": "TOTAL", "VACANCIES": "TOTAL", "NOOFVACANCIES": "TOTAL", "TOTALPOSTS": "TOTAL",
        "TOTALNOOFPOSTS": "TOTAL", "TOTALNOOFVACANCIES": "TOTAL"}
_SUBS = {"VI", "HI", "LD", "OC", "MD", "LV", "CP", "HH", "ID", "SLD", "MI", "ASD", "AAV", "DW", "LC", "BLV",
         "B", "D", "A", "E", "OH", "OA", "OL", "BL"}
_HORIZONTAL = {"TOTAL", "PwBD", "ESM"}          # reservations that overlap the vertical ones; excluded from row sums
_DASH = {"-", "–", "—", "nil", "NIL", "Nil"}

def norm_header(cell: str | None):
    up = re.sub(r"\s+", " ", (cell or "").upper()).strip()
    if not up:
        return None, None
    m = re.fullmatch(r"(?:PWBD|PWD|PH)\s*[-(\[/]\s*([A-Z/]{1,4})\s*[)\]]?", up)
    if m:
        return "PwBD", m.group(1)
    return _CAT.get(re.sub(r"[^A-Z0-9]", "", up)), None

def _clean(tbl):
    return [[re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip() for c in r] for r in tbl if r]

def _parse_table(tbl):
    cells = _clean(tbl)
    hdr, cols = None, {}
    for hi, r in enumerate(cells):
        cols = {i: norm_header(c) for i, c in enumerate(r) if norm_header(c)[0]}
        if sum(1 for v in cols.values() if v[0] != "TOTAL") >= 3:
            hdr = hi; break
    if hdr is None:
        return [], [], False
    start = hdr + 1
    if start < len(cells):                                   # optional PwBD sub-category header row
        nxt = {i: c.upper() for i, c in enumerate(cells[start]) if c}
        if len(nxt) >= 2 and all(v in _SUBS for v in nxt.values()) and any(v[0] == "PwBD" for v in cols.values()):
            cols = {i: v for i, v in cols.items() if v[0] != "PwBD"}
            for i, v in nxt.items():
                cols[i] = ("PwBD", v)
            start += 1
    out, flags, checked, post_rows, totals = [], [], True, 0, None
    for r in cells[start:]:
        if not any(r):
            continue
        name = " ".join(c for i, c in enumerate(r) if i not in cols and c and not re.fullmatch(r"\d{1,3}[.)]?", c)).strip()
        vals, bad = {}, False
        for i, key in cols.items():
            v = r[i] if i < len(r) else ""
            if re.fullmatch(r"\d{1,6}", v):
                vals[key] = int(v)
            elif v in _DASH:
                vals[key] = 0
            else:
                bad = True
        if re.match(r"(grand\s+)?total\b", name, re.I):
            totals = vals; continue
        if not vals:
            flags.append(f"unparsed_row:{name[:40]}"); continue
        if bad:
            flags.append(f"non_numeric_cell:{name[:40]}")
        if ("TOTAL", None) in vals:
            s = sum(v for (c, sub), v in vals.items() if c not in _HORIZONTAL)
            if s != vals[("TOTAL", None)]:
                flags.append(f"row_sum_mismatch:{name[:40]}")
        else:
            checked = False
        post_rows += 1
        for (c, sub), v in vals.items():
            out.append({"post_name": name or None, "category": c, "pwbd_subcategory": sub, "count": v})
    if post_rows > 1 and any(o["post_name"] is None for o in out):
        flags.append("missing_post_name")
    if totals and out:
        for key, tv in totals.items():
            s = sum(o["count"] for o in out if (o["category"], o["pwbd_subcategory"]) == key)
            if s != tv:
                flags.append(f"column_total_mismatch:{key[0]}")
    if not out:
        return [], [], False
    return out, flags, checked

def parse_tables(tables):
    rows, flags, checked = [], [], False
    for t in tables or []:
        r, f, c = _parse_table(t)
        rows += r; flags += f; checked = checked or (c and bool(r))
    return rows, flags, checked

def parse_text(text: str):
    """Fallback for PDFs whose tables are not detected. Always low confidence (flagged)."""
    lines = [re.sub(r"\s+", " ", l).strip() for l in (text or "").splitlines()]
    for i, l in enumerate(lines):
        toks = [norm_header(t)[0] for t in l.split(" ")]
        cats = [t for t in toks if t]
        if len(cats) >= 3 and len(cats) >= len(toks) - 3:
            n, rows = len(cats), []
            for d in lines[i + 1:i + 60]:
                m = re.match(rf"^(?P<name>.*?[A-Za-z].*?)\s+(?P<nums>(?:\d{{1,6}}\s+){{{n - 1}}}\d{{1,6}})$", d)
                if not m:
                    if rows: break
                    continue
                nums = [int(x) for x in m.group("nums").split()]
                for c, v in zip(cats, nums):
                    rows.append({"post_name": m.group("name").strip(), "category": c, "pwbd_subcategory": None, "count": v})
            if rows:
                return rows, ["text_layout_parsed"], False
    return [], [], False

_MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

def _find_date(s: str):
    m = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", s)
    if m:
        d, mo, y = map(int, m.groups())
    else:
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[,.]?\s+(\d{4})\b", s)
        if not m or m.group(2)[:3].lower() not in _MONTHS:
            return None
        d, mo, y = int(m.group(1)), _MONTHS[m.group(2)[:3].lower()], int(m.group(3))
    try:
        return date(y, mo, d)
    except ValueError:
        return None

def extract_meta(text: str) -> dict:
    meta = {}
    m = re.search(r"(?:Advt\.?|Advertisement|Notification)\s*(?:No\.?|Number)\s*[:.\-]?\s*([A-Za-z0-9][A-Za-z0-9/\-.]{3,40})", text, re.I)
    if m:
        meta["advertisement_no"] = m.group(1).rstrip(".")
    tots = {int(x) for x in re.findall(r"total\s+(?:number\s+of\s+)?(?:vacancies|posts)\s*[:\-–]?\s*(\d{1,6})\b", text, re.I)}
    if len(tots) == 1:
        meta["total_vacancies"] = tots.pop()
    for m in re.finditer(r"last\s+date", text, re.I):
        ctx = text[max(0, m.start() - 60):m.end() + 100]
        if re.search(r"appl|regist|submi", ctx, re.I):
            d = _find_date(text[m.end():m.end() + 100])
            if d:
                meta["apply_end"] = d.isoformat(); break
    return meta

def extract(tables, text: str) -> dict:
    rows, flags, checked = parse_tables(tables)
    if not rows:
        rows, flags, checked = parse_text(text)
    meta = extract_meta(text)
    if "apply_end" in meta:
        flags.append("dates_auto_extracted")
    if not rows:
        flags.append("no_vacancy_table_found")
    printed_totals = [r["count"] for r in rows if r["category"] == "TOTAL"]
    if printed_totals and "total_vacancies" not in meta:
        meta["total_vacancies"] = sum(printed_totals)       # sum of printed per-post totals only
    blocking = [f for f in flags if f != "dates_auto_extracted"]
    confidence = "high" if rows and checked and not blocking else "low"
    return {"meta": meta, "vacancies": rows, "flags": flags, "confidence": confidence}

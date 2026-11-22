"""Pure helpers (no network/DB): link extraction, fingerprints, dedupe keys."""
import hashlib, re
from urllib.parse import urljoin, urlparse

KEYWORDS = re.compile(
    r"recruit|vacanc|advertis|advt|apply|admit|hall ticket|call letter|result|answer key|corrigendum|"
    r"cut.?off|merit|interview|exam|walk.?in|appointment|selection|opening|engagement|notification", re.I)

def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()

def fingerprint(source_id: int, url: str, title: str) -> str:
    return hashlib.sha256(f"{source_id}|{url.split('#')[0]}|{norm_title(title)}".encode()).hexdigest()

def dedupe_key(org_id: int, title: str) -> str:
    return hashlib.sha256(f"{org_id}|{norm_title(title)}".encode()).hexdigest()

def is_pdf(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")

def extract_items(kind: str, css_selector: str | None, base_url: str, body: bytes) -> list[dict]:
    items: list[dict] = []
    if kind == "rss":
        import feedparser
        items = [{"title": (e.get("title") or "").strip(), "url": e.get("link") or ""} for e in feedparser.parse(body).entries]
    elif kind == "sitemap":
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(body, "xml")
        items = [{"title": l.text.strip().rsplit("/", 1)[-1].replace("-", " ").replace("_", " "), "url": l.text.strip()}
                 for l in soup.find_all("loc")]
    else:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(body, "html.parser")
        generic = not css_selector
        for a in soup.select(css_selector or "a[href]"):
            title, href = a.get_text(" ", strip=True), a.get("href")
            if not title or not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            url = urljoin(base_url, href)
            if generic:   # no selector configured: keep only plausible notification links, drop menu noise
                if len(title) < 20 and not is_pdf(url):
                    continue
                if not (KEYWORDS.search(title) or (is_pdf(url) and KEYWORDS.search(url))):
                    continue
            items.append({"title": title, "url": url})
    seen, out = set(), []
    for i in items:
        if i["url"] and len(i["title"]) > 5 and (i["url"], i["title"]) not in seen:
            seen.add((i["url"], i["title"])); out.append(i)
    return out

def on_domain(url: str, domain: str) -> bool:
    host, dom = (urlparse(url).hostname or "").lower(), domain.lower()
    return host == dom or host.endswith("." + dom)

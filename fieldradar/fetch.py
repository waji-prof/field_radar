"""Fetchers for each free source type. Only the Python standard library is used."""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .textutil import clean, parse_date

USER_AGENT = "FieldRadar/1.0 (personal, non-commercial research digest)"
JUNK_TITLES = re.compile(
    r"^(issue information|editorial board|front matter|back matter|table of contents|cover image|"
    r"corrigendum|erratum|correction to|correction:|retraction|expression of concern|"
    r"reviewer acknowledg|masthead|in this issue|call for papers)", re.I)


def http_get(url, timeout=30, user_agent=USER_AGENT):
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "*/*"})
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:  # network hiccup: try once more
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


# ── generic RSS / Atom ────────────────────────────────────────

def _local(tag):
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def parse_feed(data):
    """Parse RSS 2.0 or Atom into simple dicts. Tolerates odd namespaces."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return _parse_feed_regex(data.decode("utf-8", "replace"))
    out = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        d = {"title": "", "link": "", "summary": "", "content": "", "date": "", "source_name": ""}
        for ch in el:
            n = _local(ch.tag)
            text = "".join(ch.itertext()).strip()
            if n == "title":
                d["title"] = text
            elif n == "link":
                href = ch.get("href")
                if href and ch.get("rel", "alternate") == "alternate" and not d["link"]:
                    d["link"] = href
                elif text and not d["link"]:
                    d["link"] = text
            elif n in ("description", "summary") and not d["summary"]:
                d["summary"] = text
            elif n in ("encoded", "content") and not d["content"]:
                d["content"] = text
            elif n in ("pubdate", "published", "date", "updated", "issued") and not d["date"]:
                d["date"] = text
            elif n == "source":
                d["source_name"] = text
            elif n == "id" and not d["link"] and text.startswith("http"):
                d["link"] = text
        if not d["summary"]:
            d["summary"] = d["content"]
        out.append(d)
    return out


def _parse_feed_regex(text):
    """Fallback for feeds with broken XML."""
    out = []
    for m in re.finditer(r"<(?:item|entry)[\s>](.*?)</(?:item|entry)>", text, re.S):
        b = m.group(1)

        def grab(tag):
            mm = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", b, re.S)
            return re.sub(r"<!\[CDATA\[|\]\]>", "", mm.group(1)).strip() if mm else ""
        link = grab("link") or (re.search(r'<link[^>]*href="([^"]+)"', b) or [None, ""])[1]
        out.append({"title": grab("title"), "link": link,
                    "summary": grab("description") or grab("summary"),
                    "date": grab("pubDate") or grab("published") or grab("updated"),
                    "source_name": grab("source")})
    return out


def _item(src, title, link, summary="", published=None, venue="", extra=None):
    d = {
        "title": clean(title),
        "link": (link or "").strip(),
        "summary": clean(summary),
        "published": published.isoformat() if published else None,
        "source": src["name"],
        "venue": venue,
        "kind": src.get("kind", "news"),
        "hint": src.get("hint", ""),
        "filter": bool(src.get("filter", True)),
    }
    if extra:
        d.update(extra)
    return d


def fetch_rss(src, settings):
    items = []
    for e in parse_feed(http_get(src["url"])):
        if not e["title"] or not e["link"]:
            continue
        items.append(_item(src, e["title"], e["link"], e["summary"], parse_date(e["date"])))
    return items


def fetch_arxiv(src, settings):
    return fetch_rss(src, settings)


# ── Google News search RSS ───────────────────────────────────

def fetch_gnews(src, settings):
    region = src.get("region", "US").upper()
    locale = "hl=en-IN&gl=IN&ceid=IN:en" if region == "IN" else f"hl=en&gl={region}&ceid={region}:en"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(src["query"]) + "&" + locale
    items = []
    for e in parse_feed(http_get(url)):
        title, publisher = e["title"], e.get("source_name", "")
        # Google appends " - Publisher" to every headline
        if " - " in title:
            head, tail = title.rsplit(" - ", 1)
            if len(tail) < 60:
                title, publisher = head, publisher or tail
        # Google's description is just the headline again, so skip it
        items.append(_item(src, title, e["link"], "", parse_date(e["date"]), venue=publisher))
    return items


# ── Crossref (peer-reviewed journals) ────────────────────────

def fetch_crossref(src, settings):
    since = (datetime.now(timezone.utc) - timedelta(days=int(settings.get("fetch_days", 10)))).date()
    mailto = settings.get("crossref_mailto", "").strip()
    ua = USER_AGENT + (f" mailto:{mailto}" if mailto else "")
    items, errors = [], []
    for issn in src["issns"]:
        url = (f"https://api.crossref.org/journals/{issn}/works?"
               f"filter=from-created-date:{since},type:journal-article"
               f"&sort=created&order=desc&rows=60"
               f"&select=DOI,title,abstract,created,container-title,URL")
        try:
            data = json.loads(http_get(url, user_agent=ua))
        except Exception as e:
            errors.append(f"{issn}: {e}")
            continue
        for w in data.get("message", {}).get("items", []):
            title = (w.get("title") or [""])[0]
            if not title or JUNK_TITLES.search(title.strip()):
                continue
            created = parse_date((w.get("created") or {}).get("date-time", ""))
            venue = (w.get("container-title") or [""])[0]
            link = f"https://doi.org/{w['DOI']}" if w.get("DOI") else w.get("URL", "")
            items.append(_item(src, title, link, w.get("abstract", ""), created, venue=venue))
        time.sleep(0.2)  # be gentle with the free API
    if errors and not items:
        raise RuntimeError("; ".join(errors[:3]))
    return items


# ── PsyArXiv (via the free OSF API) ──────────────────────────

def fetch_psyarxiv(src, settings):
    since = (datetime.now(timezone.utc) - timedelta(days=min(int(settings.get("fetch_days", 10)), 5))).date()
    url = ("https://api.osf.io/v2/preprints/?filter[provider]=psyarxiv"
           f"&filter[date_created][gte]={since}&page[size]=100")
    items = []
    for _ in range(4):  # up to 400 newest preprints
        data = json.loads(http_get(url))
        for p in data.get("data", []):
            a = p.get("attributes", {})
            link = p.get("links", {}).get("html") or p.get("links", {}).get("preprint_doi", "")
            items.append(_item(src, a.get("title", ""), link, a.get("description", ""),
                               parse_date(a.get("date_created", "")), venue="PsyArXiv"))
        url = (data.get("links") or {}).get("next")
        if not url:
            break
    return items


FETCHERS = {
    "rss": fetch_rss,
    "arxiv": fetch_arxiv,
    "gnews": fetch_gnews,
    "crossref": fetch_crossref,
    "psyarxiv": fetch_psyarxiv,
}


def fetch_source(src, settings):
    fn = FETCHERS.get(src.get("type"))
    if not fn:
        raise ValueError(f"unknown source type: {src.get('type')}")
    return fn(src, settings)

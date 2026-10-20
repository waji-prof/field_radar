"""Fetchers for each free source type. Only the Python standard library is used."""
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .textutil import clean, find_first_date, parse_date

_CROSSREF_LOCK = threading.Lock()
USER_AGENT = "FieldRadar/1.0 (personal, non-commercial research digest)"
JUNK_TITLES = re.compile(
    r"^(issue information|editorial board|front matter|back matter|table of contents|cover image|"
    r"corrigendum|erratum|correction to|correction:|retraction|expression of concern|"
    r"reviewer acknowledg|masthead|in this issue|call for papers)", re.I)


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def http_get(url, timeout=30, user_agent=USER_AGENT, headers=None):
    h = {"User-Agent": user_agent, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:  # "too many requests": wait longer, then retry
                time.sleep(6 * (attempt + 1))
            elif e.code >= 500:
                time.sleep(2 * (attempt + 1))
            else:
                break  # 404 etc. won't fix itself
        except Exception as e:  # network hiccup: try again
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
        d = {"title": "", "link": "", "summary": "", "content": "", "date": "", "source_name": "",
             "enclosure": "", "duration": "", "image": ""}
        for ch in el:
            n = _local(ch.tag)
            text = "".join(ch.itertext()).strip()
            if n == "enclosure" and (ch.get("type", "").startswith("audio") or not d["enclosure"]):
                d["enclosure"] = ch.get("url", "")
                continue
            if n == "duration":
                d["duration"] = text
                continue
            if n == "image" and ch.get("href"):
                d["image"] = ch.get("href")
                continue
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
            with _CROSSREF_LOCK:  # one journal request at a time across all Crossref sources
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
        time.sleep(0.7)  # be gentle with the free API (it limits rapid requests)
    if errors and not items:
        raise RuntimeError("; ".join(errors[:3]))
    return items


# ── Preprints via the free OSF API (PsyArXiv, EdArXiv, …) ────

def fetch_osf(src, settings):
    provider = src.get("provider", "psyarxiv")
    # PsyArXiv is busy (5 days is plenty); smaller servers like EdArXiv need a longer look-back
    days = int(src.get("days", 5 if provider == "psyarxiv" else settings.get("fetch_days", 10)))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    url = (f"https://api.osf.io/v2/preprints/?filter[provider]={provider}"
           f"&filter[date_created][gte]={since}&page[size]=100")
    venue = {"psyarxiv": "PsyArXiv", "edarxiv": "EdArXiv"}.get(provider, provider)
    items = []
    for _ in range(4):  # up to 400 newest preprints
        data = json.loads(http_get(url))
        for p in data.get("data", []):
            a = p.get("attributes", {})
            link = p.get("links", {}).get("html") or p.get("links", {}).get("preprint_doi", "")
            items.append(_item(src, a.get("title", ""), link, a.get("description", ""),
                               parse_date(a.get("date_created", "")), venue=venue))
        url = (data.get("links") or {}).get("next")
        if not url:
            break
    return items


# ── Podcasts (RSS with audio files) ──────────────────────────

def _fmt_duration(value):
    """'3725' or '01:02:05' → '1:02:05'."""
    v = (value or "").strip()
    if v.isdigit():
        secs = int(v)
        h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    return v


def fetch_podcast(src, settings):
    items = []
    for e in parse_feed(http_get(src["url"]))[:15]:
        if not e["title"] or not e.get("enclosure"):
            continue
        media = {"type": "podcast", "audio": e["enclosure"], "duration": _fmt_duration(e.get("duration")),
                 "thumb": e.get("image", "")}
        items.append(_item(src, e["title"], e["link"] or e["enclosure"], e["summary"], parse_date(e["date"]),
                           venue=src["name"], extra={"kind": "podcast", "media": media}))
    return items


# ── YouTube channels (public Videos / Shorts pages) ──────────
# YouTube's robots.txt blocks its RSS feeds for automated tools but allows
# channel pages, so we read the same lists a visitor sees.

_YT_HEADERS = {"Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1"}
_AGO = re.compile(r"(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?|wks?|months?|mo|years?|yrs?|[smhdwy])\b",
                  re.I)
_UNIT_HOURS = {"s": 1 / 3600, "m": 1 / 60, "h": 1, "d": 24, "w": 168, "y": 8760}


def _ago_to_date(text):
    """'2d ago', '3 weeks ago', '1 month ago' → an approximate datetime."""
    m = _AGO.search(text or "")
    if not m:
        return None
    unit = m[2].lower()
    hours = 730 if unit.startswith("mo") else _UNIT_HOURS.get(unit[0], 24)
    if unit.startswith("min"):
        hours = 1 / 60
    return datetime.now(timezone.utc) - timedelta(hours=int(m[1]) * hours)


def _yt_initial_data(page):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page, re.S)
    return json.loads(m.group(1)) if m else {}


def _walk(obj, key, out):
    """Collect every value stored under `key` anywhere inside nested JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            _walk(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, key, out)
    return out


def _yt_page(channel, tab):
    return http_get(f"https://www.youtube.com/channel/{channel}/{tab}", user_agent=BROWSER_UA,
                    headers=_YT_HEADERS).decode("utf-8", "replace")


def fetch_youtube(src, settings):
    ch, per, items = src["channel"], int(src.get("max_per_fetch", 12)), []
    if src.get("videos", True):
        for v in _walk(_yt_initial_data(_yt_page(ch, "videos")), "lockupViewModel", [])[:per]:
            vid = v.get("contentId")
            md = (v.get("metadata") or {}).get("lockupMetadataViewModel") or {}
            title = (md.get("title") or {}).get("content", "")
            if not vid or not title:
                continue
            parts = [p.get("text", {}).get("content", "") for row in _walk(md, "metadataParts", []) for p in row]
            badges = [b.get("text", "") for b in _walk(v.get("contentImage", {}), "thumbnailBadgeViewModel", [])]
            duration = next((b for b in badges if re.fullmatch(r"\d+(:\d\d)+", b or "")), "")
            views = next((p for p in parts if "view" in p.lower() or re.fullmatch(r"[\d.,]+[KMB]?", p)), "")
            when = next((_ago_to_date(p) for p in parts if "ago" in p.lower()), None)
            media = {"type": "video", "video_id": vid, "duration": duration, "views": views,
                     "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
            items.append(_item(src, title, f"https://www.youtube.com/watch?v={vid}", "", when,
                               venue=src["name"], extra={"kind": "video", "media": media}))
    if src.get("shorts", True):
        for v in _walk(_yt_initial_data(_yt_page(ch, "shorts")), "shortsLockupViewModel", [])[:per]:
            cmd = ((v.get("onTap") or {}).get("innertubeCommand") or {}).get("reelWatchEndpoint") or {}
            vid = cmd.get("videoId")
            ov = v.get("overlayMetadata") or {}
            title = (ov.get("primaryText") or {}).get("content", "")
            if not vid or not title:
                continue
            thumbs = _walk(v.get("thumbnail") or {}, "url", [])
            media = {"type": "short", "video_id": vid, "views": (ov.get("secondaryText") or {}).get("content", ""),
                     "thumb": thumbs[0] if thumbs else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
            items.append(_item(src, title, f"https://www.youtube.com/shorts/{vid}", "", None,
                               venue=src["name"], extra={"kind": "short", "media": media}))
    return items


# ── AcademicTransfer (Dutch academic jobs; salaried PhDs) ────

_AT_DATE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+\S?(\d{2})\b")


def _at_date(text):
    """'10 Nov ’26' → datetime(2026, 11, 10)."""
    m = _AT_DATE.search(text or "")
    return find_first_date(f"{m[1]} {m[2]} 20{m[3]}") if m else None


def fetch_academictransfer(src, settings):
    items, seen = [], set()
    for q in src.get("queries", ["phd psychology"]):
        page = http_get("https://www.academictransfer.com/en/jobs/?q=" + urllib.parse.quote_plus(q),
                        user_agent=BROWSER_UA).decode("utf-8", "replace")
        for block in re.split(r'(?=<a[^>]+href="/en/jobs/\d+/)', page)[1:]:
            m = re.search(r'href="(/en/jobs/\d+/[^"]+)"', block)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            card = block[:8000]
            h3 = re.search(r"<h3[^>]*>(.*?)</h3>", card, re.S)
            if not h3:
                continue
            title = clean(h3.group(1))
            p = re.search(r"</h3>\s*<p[^>]*>(.*?)</p>", card, re.S)
            teaser = clean(p.group(1)) if p else ""
            if teaser.startswith(title[:40]):  # teaser repeats the title first
                teaser = teaser[len(title):].strip() if teaser.startswith(title) else teaser
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(card))).strip()
            rest = text.partition(" Deadline ")[2]
            deadline = _at_date(rest)
            pub_text = rest.split("Published", 1)[1] if "Published" in rest else ""
            published = _at_date(pub_text)
            where = re.sub(r"^\s*\d{1,2}\s+\w+\.?\s+\S?\d{2}\s*", "", pub_text).strip()
            summary = teaser
            if deadline:
                summary += f" Deadline: {deadline:%d %B %Y}."
            if where:
                summary += f" {where}."
            items.append(_item(src, title, "https://www.academictransfer.com" + m.group(1), summary,
                               published, venue="AcademicTransfer · Netherlands"))
        time.sleep(1)
    return items


FETCHERS = {
    "rss": fetch_rss,
    "arxiv": fetch_arxiv,
    "gnews": fetch_gnews,
    "crossref": fetch_crossref,
    "psyarxiv": fetch_osf,
    "osf": fetch_osf,
    "podcast": fetch_podcast,
    "youtube": fetch_youtube,
    "academictransfer": fetch_academictransfer,
}


def fetch_source(src, settings):
    fn = FETCHERS.get(src.get("type"))
    if not fn:
        raise ValueError(f"unknown source type: {src.get('type')}")
    return fn(src, settings)

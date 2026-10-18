"""Small text helpers: cleaning HTML, shortening, parsing dates."""
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def clean(text):
    """Strip HTML/JATS tags and entities, collapse whitespace."""
    if not text:
        return ""
    text = html.unescape(html.unescape(text))
    text = _TAG.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    # Crossref abstracts often start with the word "Abstract"
    text = re.sub(r"^(abstract|summary)\s*[:.]?\s+", "", text, flags=re.I)
    return text


def shorten(text, limit=320):
    """Cut to `limit` chars, preferring a sentence end, else a word end."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    if end > limit * 0.55:
        return cut[: end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def normalize_title(title):
    """Used to spot the same story arriving from two feeds."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return _WS.sub(" ", t).strip()[:120]


def parse_date(value):
    """Return an aware UTC datetime from RSS/Atom/ISO strings, or None."""
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE_PATTERNS = [
    re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r",?\s+(\d{4})", re.I),   # 12 November 2026
    re.compile(_MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I),          # November 12, 2026
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),                                           # 2026-11-12
]
_DEADLINE_CUE = re.compile(
    r"(deadline|closing date|closes|close on|apply by|apply before|applications? (?:close|due)|"
    r"due date|due by|submission due|until)\W{0,25}", re.I)


def _date_from_match(m, pattern_index):
    try:
        if pattern_index == 0:
            return datetime(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1]), tzinfo=timezone.utc)
        if pattern_index == 1:
            return datetime(int(m[3]), _MONTHS[m[1][:3].lower()], int(m[2]), tzinfo=timezone.utc)
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc)
    except (ValueError, KeyError):
        return None


def find_first_date(text):
    for i, pat in enumerate(_DATE_PATTERNS):
        m = pat.search(text)
        if m:
            d = _date_from_match(m, i)
            if d:
                return d
    return None


def find_deadline(text):
    """Find a date that follows a word like 'deadline' or 'apply by'."""
    if not text:
        return None
    for cue in _DEADLINE_CUE.finditer(text):
        window = text[cue.end(): cue.end() + 40]
        d = find_first_date(window)
        if d and 2020 <= d.year <= 2035:
            return d
    return None

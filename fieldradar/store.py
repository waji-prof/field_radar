"""Local SQLite database (a single file in data/) that remembers what you've seen."""
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from .textutil import normalize_title

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    title_norm  TEXT NOT NULL,
    link        TEXT NOT NULL,
    summary     TEXT,
    ai_summary  TEXT,
    source      TEXT,
    venue       TEXT,
    kind        TEXT,
    hint        TEXT,
    filter      INTEGER,
    published   TEXT,
    first_seen  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_title_norm ON items(title_norm);
CREATE TABLE IF NOT EXISTS runs (
    at        TEXT PRIMARY KEY,
    new_items INTEGER,
    errors    TEXT
);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    @staticmethod
    def _keys(item):
        return hashlib.sha1(item["link"].encode()).hexdigest()[:16], normalize_title(item["title"])

    def seen(self, item):
        """True if this link — or the same headline from another feed — is already stored."""
        iid, tnorm = self._keys(item)
        if not tnorm:
            return True
        cur = self.db.execute("SELECT 1 FROM items WHERE id=? OR title_norm=? LIMIT 1", (iid, tnorm))
        return cur.fetchone() is not None

    def add(self, item, now):
        """Insert a new item (call seen() first)."""
        link = item["link"]
        iid, tnorm = self._keys(item)
        self.db.execute(
            "INSERT INTO items (id,title,title_norm,link,summary,ai_summary,source,venue,kind,hint,filter,"
            "published,first_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, item["title"], tnorm, link, item.get("summary", ""), item.get("ai_summary"),
             item["source"], item.get("venue", ""), item["kind"], item.get("hint", ""),
             1 if item.get("filter") else 0, item.get("published"), now.isoformat()))

    def recent(self, days):
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        # Judge by publication date when known, else by when we first saw it
        rows = self.db.execute(
            "SELECT * FROM items WHERE kind NOT IN ('phd','cfp') AND "
            "((published IS NULL AND first_seen >= ?) OR published >= ?)", (since, since)).fetchall()
        return [dict(r) for r in rows]

    def opportunities(self, days):
        """PhD and call-for-paper items stay visible longer (until their deadline passes)."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self.db.execute(
            "SELECT * FROM items WHERE kind IN ('phd','cfp') AND "
            "((published IS NULL AND first_seen >= ?) OR published >= ?)", (since, since)).fetchall()
        return [dict(r) for r in rows]

    def prune(self, keep_days):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
        self.db.execute("DELETE FROM items WHERE first_seen < ?", (cutoff,))

    def log_run(self, now, new_items, errors):
        self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?)", (now.isoformat(), new_items, errors))

    def last_runs(self, n=2):
        return [dict(r) for r in self.db.execute("SELECT * FROM runs ORDER BY at DESC LIMIT ?", (n,))]

    def commit(self):
        self.db.commit()

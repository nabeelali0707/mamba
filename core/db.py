from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .models import NewsItem

DB_PATH = Path(__file__).resolve().parent.parent / "mamba.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT,
    category TEXT,
    lab TEXT,
    summary TEXT,
    published REAL,
    score INTEGER DEFAULT 0,
    seen INTEGER DEFAULT 0,
    added REAL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_pub ON items(published DESC);
"""


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def add_many(self, items: list[NewsItem]) -> list[NewsItem]:
        """Insert items; return only the ones that were new."""
        new: list[NewsItem] = []
        with self._lock, self._conn:
            for it in items:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO items (id,title,url,source,category,lab,summary,published,score)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (it.id, it.title, it.url, it.source, it.category, it.lab,
                     it.summary, it.published, it.score),
                )
                if cur.rowcount:
                    new.append(it)
        return new

    def latest(self, limit: int = 100, category: str | None = None,
               lab: str | None = None) -> list[NewsItem]:
        q = "SELECT * FROM items"
        where, args = [], []
        if category:
            where.append("category=?"); args.append(category)
        if lab:
            where.append("lab=?"); args.append(lab)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY published DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [NewsItem(title=r["title"], url=r["url"], source=r["source"] or "",
                         category=r["category"] or "news", lab=r["lab"] or "",
                         summary=r["summary"] or "", published=r["published"] or 0,
                         score=r["score"] or 0, id=r["id"]) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

"""Qt-free feed navigator: ranks stored items and lets the UI step through them."""
from __future__ import annotations

import time

from .config import load_labs
from .db import Store
from .models import NewsItem
from .relevance import boost, drop_near_duplicates, keep

MAX_AGE_DAYS = 14


def rank(it: NewsItem, now: float | None = None) -> float:
    """Higher = shown earlier. Mixes category priority, freshness and popularity."""
    now = now or time.time()
    age_h = max(0.0, (now - it.published) / 3600)
    return it.priority * 8 - age_h * 0.5 + min(it.score, 300) / 30 + boost(it)


def diversify(pool: list[NewsItem], now: float) -> list[NewsItem]:
    """Greedy re-rank: each time a lab/source was already picked, its next item loses points,
    so one chatty lab can't fill the whole rotation."""
    scored = [(rank(i, now), i) for i in pool]
    seen: dict[str, int] = {}
    out: list[NewsItem] = []
    while scored:
        best = max(range(len(scored)),
                   key=lambda n: scored[n][0] - 5 * seen.get(scored[n][1].lab or scored[n][1].source, 0))
        _, it = scored.pop(best)
        k = it.lab or it.source
        seen[k] = seen.get(k, 0) + 1
        out.append(it)
    return out


class Feed:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.category: str | None = None
        self.items: list[NewsItem] = []
        self.index = 0
        self.reload()

    def reload(self, keep_id: str | None = None) -> None:
        now = time.time()
        cutoff = now - MAX_AGE_DAYS * 86400
        strict = frozenset(l["name"] for l in load_labs().get("labs", []) if l.get("strict"))
        pool = [i for i in self.store.latest(600, category=self.category)
                if i.published >= cutoff and keep(i, strict)]
        pool.sort(key=lambda i: rank(i, now), reverse=True)
        self.items = diversify(drop_near_duplicates(pool), now)
        self.index = 0
        if keep_id:
            self.goto(keep_id)

    @property
    def current(self) -> NewsItem | None:
        return self.items[self.index] if self.items else None

    def __len__(self) -> int:
        return len(self.items)

    def next(self) -> NewsItem | None:
        if self.items:
            self.index = (self.index + 1) % len(self.items)
        return self.current

    def prev(self) -> NewsItem | None:
        if self.items:
            self.index = (self.index - 1) % len(self.items)
        return self.current

    def goto(self, item_id: str) -> bool:
        for n, it in enumerate(self.items):
            if it.id == item_id:
                self.index = n
                return True
        return False

    def set_category(self, category: str | None) -> None:
        self.category = category or None
        self.reload()

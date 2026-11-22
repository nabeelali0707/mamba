from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

# Categories and their pet-facing emoji / priority (higher = more important)
CATEGORIES = {
    "model": ("🚨", 3),      # new model / weights release
    "product": ("🚀", 2),
    "research": ("🔬", 2),   # lab research blog
    "paper": ("📄", 1),
    "open_source": ("🧰", 2),
    "funding": ("💰", 1),
    "buzz": ("🔥", 1),       # HN / Reddit
    "news": ("📰", 1),
}


@dataclass
class NewsItem:
    title: str
    url: str
    source: str                 # e.g. "OpenAI blog", "arXiv cs.LG"
    category: str = "news"
    lab: str = ""               # lab name from labs.yaml, if any
    summary: str = ""
    published: float = field(default_factory=time.time)
    score: int = 0              # extra weight (upvotes etc.)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:16]

    @property
    def emoji(self) -> str:
        return CATEGORIES.get(self.category, ("📰", 1))[0]

    @property
    def priority(self) -> int:
        return CATEGORIES.get(self.category, ("📰", 1))[1]

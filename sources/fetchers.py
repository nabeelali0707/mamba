"""All fetchers. Each returns list[NewsItem] and never raises (errors are logged)."""
from __future__ import annotations

import logging
import os
import re
import time
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from core.models import NewsItem

log = logging.getLogger("mamba.fetch")
HEADERS = {"User-Agent": "mamba-ai-news-pet/0.1 (personal desktop app)"}
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEADLINE = 60.0   # hard cap (seconds) for one full fetch round
AI_WORDS = re.compile(
    r"\b(ai|llm|gpt|model|neural|transformer|diffusion|machine learning|deep learning|"
    r"agent|claude|gemini|llama|deepseek|qwen|mistral|openai|anthropic|nvidia|benchmark|"
    r"reasoning|multimodal|robot|inference|fine-?tun)\w*", re.I)


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True)


def _clean(text: str, n: int = 300) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:n]


def _entry_time(e) -> float:
    for k in ("published_parsed", "updated_parsed"):
        t = getattr(e, k, None) or e.get(k)
        if t:
            return float(timegm(t))
    return time.time()


def _parse_feed(url: str, source: str, category: str, lab: str = "",
                limit: int = 15, ai_only: bool = False) -> list[NewsItem]:
    try:
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as ex:  # noqa: BLE001
        log.warning("feed failed %s: %s", source, ex)
        return []
    out = []
    for e in feed.entries[:limit]:
        title = _clean(e.get("title", ""), 200)
        link = e.get("link", "")
        if not title or not link:
            continue
        summ = _clean(e.get("summary", ""))
        if ai_only and not AI_WORDS.search(title + " " + summ):
            continue
        out.append(NewsItem(title=title, url=link, source=source, category=category,
                            lab=lab, summary=summ, published=_entry_time(e)))
    return out


# ---------- general sources ----------
def fetch_arxiv(categories: list[str], per_cat: int = 15) -> list[NewsItem]:
    out = []
    for cat in categories:
        url = (f"https://export.arxiv.org/api/query?search_query=cat:{cat}"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={per_cat}")
        out += _parse_feed(url, f"arXiv {cat}", "paper", limit=per_cat)
    return out


def fetch_hf_papers() -> list[NewsItem]:
    """Hugging Face Daily Papers (community-curated trending papers)."""
    try:
        with _client() as c:
            r = c.get("https://huggingface.co/api/daily_papers")
            r.raise_for_status()
            data = r.json()
    except Exception as ex:  # noqa: BLE001
        log.warning("hf papers failed: %s", ex)
        return []
    out = []
    for d in data[:30]:
        p = d.get("paper", {})
        pid = p.get("id")
        if not pid:
            continue
        up = p.get("upvotes", 0) or 0
        try:
            ts = datetime.fromisoformat(p.get("publishedAt", "").replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            ts = time.time()
        out.append(NewsItem(
            title=_clean(p.get("title", ""), 200), url=f"https://huggingface.co/papers/{pid}",
            source=f"HF Daily Papers ▲{up}", category="paper", score=up,
            summary=_clean(p.get("summary", "")), published=ts))
    return out


def fetch_hn() -> list[NewsItem]:
    """Hacker News front page filtered for AI via the Algolia API."""
    url = ("https://hn.algolia.com/api/v1/search?tags=story&numericFilters=points>80"
           "&query=AI%20OR%20LLM%20OR%20GPT%20OR%20Claude%20OR%20machine%20learning&hitsPerPage=25")
    try:
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
            hits = r.json().get("hits", [])
    except Exception as ex:  # noqa: BLE001
        log.warning("hn failed: %s", ex)
        return []
    out = []
    for h in hits:
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
        out.append(NewsItem(
            title=_clean(h.get("title", ""), 200), url=link,
            source=f"Hacker News ▲{h.get('points', 0)}", category="buzz",
            score=h.get("points", 0), published=float(h.get("created_at_i", time.time()))))
    return out


# ---------- lab-specific ----------
def fetch_hf_org(org: str, lab: str, limit: int = 3, max_age_days: int = 10) -> list[NewsItem]:
    """Newest models from a Hugging Face org: catches releases before announcements."""
    url = f"https://huggingface.co/api/models?author={org}&sort=createdAt&direction=-1&limit={limit}"
    try:
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
            models = r.json()
    except Exception as ex:  # noqa: BLE001
        log.warning("hf org %s failed: %s", org, ex)
        return []
    out = []
    for m in models:
        mid = m.get("id") or m.get("modelId")
        if not mid:
            continue
        try:
            ts = datetime.fromisoformat(m["createdAt"].replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            ts = time.time()
        if time.time() - ts > max_age_days * 86400:
            continue
        out.append(NewsItem(
            title=f"{lab} released model: {mid}", url=f"https://huggingface.co/{mid}",
            source=f"HF · {org}", category="model", lab=lab, published=ts,
            summary=f"Task: {m.get('pipeline_tag') or 'n/a'} · downloads: {m.get('downloads', 0)}"))
    return out


_gh_last: dict[str, float] = {}
GH_MIN_INTERVAL = 3600   # anonymous API allows only 60 req/hour; set GITHUB_TOKEN to lift this


def fetch_github_org(org: str, lab: str, limit: int = 5) -> list[NewsItem]:
    interval = 300 if os.environ.get("GITHUB_TOKEN") else GH_MIN_INTERVAL
    if time.time() - _gh_last.get(org, 0) < interval:
        return []
    _gh_last[org] = time.time()
    url = f"https://api.github.com/orgs/{org}/repos?sort=created&direction=desc&per_page={limit}"
    try:
        with _client() as c:
            hdr = {**HEADERS, "Accept": "application/vnd.github+json"}
            if os.environ.get("GITHUB_TOKEN"):
                hdr["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
            r = c.get(url, headers=hdr)
            r.raise_for_status()
            repos = r.json()
    except Exception as ex:  # noqa: BLE001
        log.warning("github %s failed: %s", org, ex)
        return []
    out = []
    for rp in repos:
        try:
            ts = datetime.fromisoformat(rp["created_at"].replace("Z", "+00:00")).timestamp()
        except Exception:  # noqa: BLE001
            ts = time.time()
        out.append(NewsItem(
            title=f"{lab} new repo: {rp['name']}", url=rp["html_url"],
            source=f"GitHub · {org}", category="open_source", lab=lab, published=ts,
            summary=_clean(rp.get("description") or "")))
    return out


def fetch_google_news(query: str, lab: str, limit: int = 6) -> list[NewsItem]:
    url = (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:2d"
           "&hl=en-US&gl=US&ceid=US:en")
    items = _parse_feed(url, f"News · {lab}", "news", lab=lab, limit=limit)
    return items


def classify(item: NewsItem) -> NewsItem:
    """Cheap keyword classifier to upgrade 'news' items to product / funding / model."""
    t = item.title.lower()
    if item.category in ("news", "research"):
        if re.search(r"\b(raises|funding|series [a-e]|valuation|acquires|acquisition)\b", t):
            item.category = "funding"
        elif re.search(r"\b(launch|introduc|release|unveil|announc|rolls out|debut|new model)\w*", t):
            item.category = "product"
    return item


# ---------- orchestration ----------
def fetch_all(cfg: dict) -> list[NewsItem]:
    jobs = []
    gen = cfg.get("general", {})
    for f in gen.get("rss", []):
        jobs.append(lambda f=f: _parse_feed(f["url"], f["name"], f.get("category", "news"),
                                            ai_only=f["name"].startswith(("The Verge", "MIT"))))
    jobs.append(lambda: fetch_arxiv(gen.get("arxiv_categories", ["cs.AI"])))
    jobs.append(fetch_hf_papers)
    jobs.append(fetch_hn)

    for lab in cfg.get("labs", []):
        if lab.get("enabled", True) is False:
            continue
        name = lab["name"]
        for u in lab.get("rss", []) or []:
            jobs.append(lambda u=u, n=name: _parse_feed(u, f"{n} blog", "research", lab=n))
        for org in lab.get("hf", []) or []:
            jobs.append(lambda o=org, n=name: fetch_hf_org(o, n))
        for org in lab.get("github", []) or []:
            jobs.append(lambda o=org, n=name: fetch_github_org(o, n, limit=3))
        if lab.get("news"):
            jobs.append(lambda q=lab["news"], n=name: fetch_google_news(q, n))

    results: list[NewsItem] = []
    pool = ThreadPoolExecutor(max_workers=16)
    futures = [pool.submit(j) for j in jobs]
    try:
        for fut in as_completed(futures, timeout=DEADLINE):
            try:
                results.extend(fut.result())
            except Exception as ex:  # noqa: BLE001
                log.warning("job crashed: %s", ex)
    except FuturesTimeout:
        stuck = sum(not f.done() for f in futures)
        log.warning("deadline hit; abandoning %d slow jobs", stuck)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return [classify(i) for i in results]

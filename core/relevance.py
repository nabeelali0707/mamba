"""Relevance filter: keep what helps you LEARN AI (models, lab research, papers, tech reports);
drop finance, politics, consumer chatter, events and junk uploads."""
from __future__ import annotations

import re

from .models import NewsItem

# Business / politics / consumer noise (checked against the title)
BLOCK = re.compile(
    r"\b(stocks?|shares|valuation|raises?|raised|funding|series [a-e]|ipo|acquir\w*|acquisition|"
    r"lawsuits?|sues?|sued|senators?|congress|white house|regulat\w*|tariffs?|layoffs?|pricing|"
    r"deals?|billion|trillion|meetups?|webinar|podcast|giveaway|tool of the week|how to|review|"
    r"vs\.?|compare[sd]?|best|top \d+|crypto|bitcoin|nft|election|trump|biden|policy|bans?|banned|"
    r"hiring|jobs?|salary|earnings|revenue|investors?|investment|partnership|invests?|"
    r"iphones?|android|siri|alexa|your (?:mac|phone|screen|messages|browser)|text messages|app store|apps?|chrome extension|windows \d+|ios \d+|rumou?rs?|leaks?|leaked|what is|what are|release date|price|safety guide|subscription|discount|coupon|unveils? (?:new )?(?:iphone|phone|laptop))\b"
    r"|\$\s?\d|€\s?\d",
    re.I)

# Technical signal: something worth reading about how AI works / what shipped
TECH = re.compile(
    r"\b(llms?|language models?|foundation models?|transformers?|diffusion|multimodal|reasoning|"
    r"agentic|agents?|fine-?tun\w*|pre-?train\w*|post-?train\w*|reinforcement learning|rlhf|"
    r"distillation|inference|benchmarks?|open-?weights?|open[- ]source|weights|technical report|"
    r"architecture|mixture[- ]of[- ]experts|moe|attention|tokeniz\w*|context window|neural|"
    r"training|datasets?|papers?|research|arxiv|models?|releases?|released|introduc\w*|"
    r"launch\w*|gpt-?\d*|claude|gemini|llama|qwen\d*|deepseek|mistral|grok|nemotron|kimi|glm|"
    r"sora|veo|flux|whisper|embedding\w*|rag|robot\w*|vision|speech)\b",
    re.I)

# Stricter ML-only signal, for mixed corporate blogs (NVIDIA, Microsoft, Amazon...)
STRICT = re.compile(
    r"\b(llms?|language models?|foundation models?|transformers?|diffusion|multimodal|reasoning|"
    r"agentic|agents?|fine-?tun\w*|pre-?train\w*|post-?train\w*|reinforcement learning|"
    r"distillation|inference|benchmarks?|open-?weights?|neural|machine learning|deep learning|"
    r"training|nemotron|phi-\d|nova|gpt|attention|mixture[- ]of[- ]experts|moe|embedding\w*|"
    r"generative|vision-language|speech recognition|world models?|physical ai)\b",
    re.I)

AI_WORDS = re.compile(r"\b(llm|ai|ml|gpt|model|neural|transformer|diffusion|agent|inference|"
                      r"training|rag|embedding|reasoning|vision|speech|benchmark|dataset)\w*", re.I)

# Things you can actually learn from
LEARN = re.compile(r"\b(survey|tutorial|technical report|primer|explained|from scratch|"
                   r"architecture|scaling laws?|open-?weights?|benchmark\w*|a review|"
                   r"introduc\w* .*(model|paper)|how we (trained|built))\b", re.I)

GITHUB_OK = {
    "openai", "anthropics", "google-deepmind", "deepseek-ai", "QwenLM", "MoonshotAI", "zai-org",
    "THUDM", "mistralai", "allenai", "meta-llama", "xai-org", "EleutherAI", "NousResearch",
    "MiniMax-AI", "01-ai", "Physical-Intelligence", "huggingface", "Stability-AI", "cohere-ai",
}
JUNK_REPO = re.compile(r"(copy|test|demo|sample|template|landing-zone|fork|[-_]old|tmp|hack|"
                       r"tutorial-|hello|example|starter|sandbox|_)", re.I)

# Model repo names that are noise: quantised/format conversions, hash-named experiments
NOISY_MODEL = re.compile(
    r"(onnx|gguf|gptq|awq|fp8|fp4|nvfp4|mxfp4|mlx|bnb|int4|int8|webgpu|quantiz|"
    r"\blora\b|-lora|adapter|checkpoint|-ckpt|-sft-|-dpo-|-test|-debug|-dev\b|-tmp|-copy|-old)",
    re.I)
GOOD_TASKS = {
    "text-generation", "image-text-to-text", "any-to-any", "text-to-image", "text-to-video",
    "video-text-to-text", "audio-text-to-text", "text-to-speech", "automatic-speech-recognition",
    "robotics", "reinforcement-learning", "image-to-video", "text-to-audio",
}


def good_model_name(name: str) -> bool:
    """False for quantised builds and hash-like experiment names."""
    if NOISY_MODEL.search(name):
        return False
    repo = name.split("/")[-1]
    for tok in re.split(r"[-_.]", repo):
        if len(tok) >= 6 and re.fullmatch(r"[a-z]+\d+[a-z]+\d*", tok, re.I):   # e.g. lg7eae
            return False
    return True


# Third-party news is only accepted from publishers that cover AI properly
TRUSTED = re.compile(
    r"(techcrunch|venturebeat|ars technica|technology review|mit tech|wired|ieee spectrum|"
    r"nature|science|reuters|bloomberg|the information|the decoder|marktechpost|"
    r"testingcatalog|zdnet|infoq|the register|semianalysis|import ai|hugging face|"
    r"towards data science|the batch|deeplearning\.ai|stanford|berkeley|mit news|"
    r"google research|ai news|synced|ai business)", re.I)


def publisher(it: NewsItem) -> str:
    """Publisher of a third-party story (from 'X (news)' source or the ' - Publisher' title suffix)."""
    if it.source.endswith(" (news)"):
        return it.source[: -len(" (news)")]
    if it.source.startswith("News ·"):
        return it.title.rpartition(" - ")[2]
    return it.source


def model_ok(it: NewsItem) -> bool:
    """Re-check stored HF model rows: real model name + a sensible task."""
    mid = it.url.split("huggingface.co/", 1)[-1]
    task = it.summary.split("Task:", 1)[-1].split("·")[0].strip() if "Task:" in it.summary else ""
    return good_model_name(mid) and (not task or task in GOOD_TASKS)


def keep(it: NewsItem, strict_labs: frozenset[str] = frozenset()) -> bool:
    title = it.title
    cat = it.category
    if cat == "funding":
        return False
    is_blog = it.source.endswith(" blog")

    if cat == "model":
        return model_ok(it)
    if cat == "paper":
        if it.source.startswith("HF Daily"):
            return it.score >= 10                     # only genuinely trending papers
        return it.source.startswith("arXiv survey") or bool(LEARN.search(title))
    if cat == "open_source":
        org = it.source.split("·")[-1].strip()
        if org not in GITHUB_OK or JUNK_REPO.search(title):
            return False
        return bool(AI_WORDS.search(title + " " + it.summary)) and len(it.summary) >= 25 \
            and not BLOCK.search(title)
    if cat == "buzz":
        return it.score >= 100 and bool(TECH.search(title)) and not BLOCK.search(title)

    if is_blog:                                       # a lab's own blog
        if it.lab in strict_labs:
            return bool(STRICT.search(title + " " + it.summary))
        return True
    # third-party news: trusted publisher, technical, and not business/politics/consumer fluff
    return bool(TRUSTED.search(publisher(it))) and bool(TECH.search(title))         and not BLOCK.search(title)


def boost(it: NewsItem) -> float:
    """Rank bonus for items you can learn something from."""
    return 4.0 if LEARN.search(it.title) else 0.0


def _tokens(title: str) -> set[str]:
    t = re.sub(r"\s[-–|]\s[^-–|]+$", "", title.lower())       # drop " - Publisher"
    return {w for w in re.findall(r"[a-z0-9.]+", t) if len(w) > 2}


def drop_near_duplicates(items: list[NewsItem], threshold: float = 0.5) -> list[NewsItem]:
    """Same story reported by several outlets -> keep the first (items should be best-first)."""
    kept: list[tuple[set[str], NewsItem]] = []
    for it in items:
        tk = _tokens(it.title)
        if tk and any(len(tk & k) / len(tk | k) >= threshold for k, _ in kept):
            continue
        kept.append((tk, it))
    return [it for _, it in kept]

"""Find trending tech problems people search for and ask about.

Sources (free, no account):
  - YouTube search suggestions (what people type in the YouTube search box)
  - Reddit help communities (top posts of the week)
  - Hacker News front page (tech news, new tools)
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import requests

from .llm import LLMError, Ollama

UA = {"User-Agent": "techtube-trends/0.1 (personal content research script)"}

DEFAULT_SEEDS = ["windows 11", "laptop", "android", "iphone", "wifi", "chrome", "pc"]
DEFAULT_SUBS = ["techsupport", "Windows11", "Windows10", "computers", "laptops",
                "AndroidQuestions", "iphonehelp", "software"]
PATTERNS = ["how to fix {s}", "{s} not working", "why is my {s}", "{s} slow", "{s} problem"]

QUESTION = re.compile(r"\b(how|why|can't|cannot|won'?t|not working|fix|help|error|slow|"
                      r"stuck|keeps|issue|problem|crash|freez|black screen|no sound)\b", re.I)


@dataclass
class Item:
    text: str
    source: str
    score: float
    url: str = ""


def _get_json(url: str, params: dict | None = None, timeout: int = 10):
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def youtube_suggestions(query: str) -> list[str]:
    data = _get_json("https://suggestqueries.google.com/complete/search",
                     {"client": "firefox", "ds": "yt", "hl": "en", "gl": "US", "q": query})
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [str(s) for s in data[1]]
    return []


def from_youtube(seeds: list[str], deep: bool = False, delay: float = 0.3) -> list[Item]:
    items = []
    queries = [p.format(s=s) for s in seeds for p in PATTERNS]
    if deep:
        queries += [f"{s} {ch}" for s in seeds for ch in "abcdefghijklmnopqrstuvwxyz"]
    for q in queries:
        try:
            sugg = youtube_suggestions(q)
        except (requests.RequestException, ValueError):
            continue
        for rank, s in enumerate(sugg):
            items.append(Item(s, "youtube", round(3.0 / (1 + rank), 3),
                              "https://www.youtube.com/results?search_query="
                              + requests.utils.quote(s)))
        time.sleep(delay)
    return items


def from_reddit(subs: list[str], period: str = "week", limit: int = 50) -> list[Item]:
    items = []
    for sub in subs:
        try:
            data = _get_json(f"https://www.reddit.com/r/{sub}/top.json",
                             {"t": period, "limit": limit})
        except (requests.RequestException, ValueError):
            continue
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = d.get("title", "")
            if not title or not QUESTION.search(title):
                continue
            score = math.log1p(max(d.get("score", 0), 0) + 2 * max(d.get("num_comments", 0), 0))
            items.append(Item(title, f"reddit/r/{sub}", round(score, 3),
                              "https://www.reddit.com" + d.get("permalink", "")))
        time.sleep(1.0)
    return items


def from_hackernews(limit: int = 40) -> list[Item]:
    try:
        data = _get_json("https://hn.algolia.com/api/v1/search",
                         {"tags": "front_page", "hitsPerPage": limit})
    except (requests.RequestException, ValueError):
        return []
    items = []
    for h in data.get("hits", []):
        if h.get("title"):
            items.append(Item(h["title"], "hackernews",
                              round(math.log1p(h.get("points", 0) or 0) * 0.6, 3),
                              h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"))
    return items


def merge(items: list[Item]) -> list[Item]:
    """Combine duplicates (same normalized text); repeated suggestions add up."""
    best: dict[str, Item] = {}
    for it in items:
        key = re.sub(r"[^a-z0-9 ]", "", it.text.lower()).strip()
        key = re.sub(r"\s+", " ", key)
        if not key:
            continue
        if key in best:
            best[key].score = round(best[key].score + it.score * 0.5, 3)
        else:
            best[key] = Item(it.text, it.source, it.score, it.url)
    return sorted(best.values(), key=lambda i: i.score, reverse=True)


IDEA_PROMPT = """You plan videos for an English faceless YouTube channel that fixes tech problems
(PC, laptop, Windows, phones, apps). Below are real search suggestions, Reddit help posts and
tech news with a popularity score.

{items}

Pick the 15 best video ideas: problems many people have, that can be solved clearly in a
6-10 minute tutorial, preferably evergreen (people will still search it next year).
Return ONE JSON object:
{{"ideas": [{{"title": "honest searchable YouTube title", "problem": "short problem phrase for the
script command", "why": "one sentence: why it will get views", "evergreen": true,
"difficulty": "easy|medium|hard"}}]}}"""


def rank_ideas(llm: Ollama, items: list[Item], top: int = 80) -> list[dict]:
    listing = "\n".join(f"- [{i.source}, {i.score}] {i.text}" for i in items[:top])
    data = llm.chat_json(IDEA_PROMPT.format(items=listing), temperature=0.4)
    ideas = data.get("ideas", []) if isinstance(data, dict) else []
    return [i for i in ideas if isinstance(i, dict) and i.get("title")]


def write_report(out_dir: Path, items: list[Item], ideas: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    lines = [f"# المواضيع الرائجة — {today}", ""]
    if ideas:
        lines += ["## أفضل أفكار الفيديوهات (رتّبها الذكاء الاصطناعي)", "",
                  "لصناعة فيديو من فكرة: `python tt.py script \"<problem>\"`", ""]
        for n, i in enumerate(ideas, 1):
            ever = "دائم" if i.get("evergreen") else "مؤقت/ترند"
            lines.append(f"{n}. **{i['title']}**  ")
            lines.append(f"   problem: `{i.get('problem', '')}` · الصعوبة: {i.get('difficulty', '?')}"
                         f" · {ever}  ")
            if i.get("why"):
                lines.append(f"   {i['why']}")
        lines.append("")
    by_source: dict[str, list[Item]] = {}
    for it in items:
        by_source.setdefault(it.source.split("/")[0], []).append(it)
    names = {"youtube": "ما يبحث عنه الناس في يوتيوب", "reddit": "مشاكل يسأل عنها الناس في Reddit",
             "hackernews": "أخبار وأدوات تقنية (Hacker News)"}
    for src, lst in by_source.items():
        lines += [f"## {names.get(src, src)}", ""]
        for it in lst[:25]:
            lines.append(f"- {it.text}  ·  {it.score}  ·  [رابط]({it.url})")
        lines.append("")
    if not items:
        lines.append("لم يتم جلب أي بيانات. تحقق من اتصال الإنترنت.")
    path = out_dir / f"trends-{today}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"trends-{today}.json").write_text(
        json.dumps({"ideas": ideas, "items": [asdict(i) for i in items]}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    return path


def run_trends(out_dir: Path, seeds: list[str], subs: list[str], llm: Ollama | None,
               deep: bool = False) -> Path:
    print("  YouTube suggestions...")
    items = from_youtube(seeds, deep)
    print(f"    {len(items)} suggestions")
    print("  Reddit...")
    r = from_reddit(subs)
    print(f"    {len(r)} posts")
    print("  Hacker News...")
    h = from_hackernews()
    print(f"    {len(h)} stories")
    merged = merge(items + r + h)
    ideas: list[dict] = []
    if llm is not None and merged:
        try:
            print("  Ranking ideas with the local AI...")
            ideas = rank_ideas(llm, merged)
        except LLMError as e:
            print(f"  [!] {e}")
    return write_report(out_dir, merged, ideas)

"""YouTube title options, description, tags and chapters."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .llm import LLMError, Ollama
from .script import Script
from .slides import split_step
from .util import Project, fmt_ts

STOP = set("""a an the and or but if then so to of in on at by for with from is are was were be been
it its this that these those you your yours we our i me my he she they them his her their as not no
yes do does did can could will would should how what why when where which who whom into out up down
over under again more most very just than too also about after before here there all any each few
other some such only own same both now get got make made use using fix fixes way ways""".split())


def keywords(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9][a-z0-9+#.\-]*", text.lower())
            if w not in STOP and len(w) > 2]


def chapters(timeline: list[dict], min_len: float = 10.0) -> list[tuple[float, str]]:
    """YouTube rules: first chapter at 0:00, at least 3 chapters, each >= 10 s."""
    merged: list[list[Any]] = []
    for seg in timeline:
        title = seg["heading"]
        if merged and seg["duration"] < min_len:
            merged[-1][2] += seg["duration"]
            continue
        if merged and merged[-1][2] < min_len:
            merged[-1][2] += seg["duration"]
            continue
        merged.append([seg["start"], title, seg["duration"]])
    if merged:
        merged[0][0] = 0.0
        if merged[0][1] and len(timeline) and timeline[0]["visual"] == "title":
            merged[0][1] = "Intro"
    if len(merged) < 3:
        return []
    return [(m[0], m[1]) for m in merged]


def load_assets(project: Project) -> dict[str, dict]:
    if project.assets_json.exists():
        try:
            return json.loads(project.assets_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def credits(project: Project) -> list[str]:
    out = []
    for path, info in load_assets(project).items():
        src = (info or {}).get("source", "").strip()
        lic = (info or {}).get("license", "").strip()
        if src and src.lower() not in ("own", "me", "my own screenshot") and lic.lower() != "own":
            out.append(f"{Path(path).name}: {src}" + (f" ({lic})" if lic else ""))
    return out


META_PROMPT = """You write YouTube metadata for an English tech-help video.
Video title draft: {title}
Problem solved: {problem}
Sections: {headings}
Script summary: {summary}

Return ONE JSON object:
{{
  "titles": ["5 different honest, searchable titles, max 70 chars, main keyword first"],
  "description": "2 short paragraphs: what the viewer will fix and who it is for. No hashtags, no links.",
  "tags": ["15 search tags, lowercase, mix of short and long-tail"],
  "hashtags": ["3 hashtags"],
  "thumbnail_text": "2-4 punchy words for the thumbnail"
}}
No clickbait, no promises the video does not keep."""


def fallback_meta(script: Script) -> dict[str, Any]:
    problem = script.problem or script.title
    numbered = [split_step(s.heading) for s in script.sections]
    steps = [h for n, h in numbered if n]
    if not steps:
        steps = [s.heading for s in script.sections if s.visual not in ("title", "outro", "tip")]
    kw = keywords(problem)
    base = problem[:1].upper() + problem[1:]
    titles = [
        script.title,
        f"{base}: {len(steps)} Fixes That Work",
        f"How to Fix {base} (Step by Step)",
        f"{base}? Try These Fixes First",
        f"{base} - Easy Fix for Beginners",
    ]
    tags = list(dict.fromkeys([problem.lower(), f"how to fix {problem.lower()}",
                               f"{problem.lower()} fix", *kw, "tech tips", "tutorial"]))
    return {
        "titles": [t[:100] for t in dict.fromkeys(titles)],
        "description": f"In this video you'll learn how to fix {problem.lower()} step by step: "
                       + ", ".join(steps[:5]) + ".",
        "tags": tags[:15],
        "hashtags": ["#techtips", "#" + (kw[0] if kw else "howto"), "#tutorial"],
        "thumbnail_text": " ".join(problem.upper().split()[:3]),
    }


def make_meta(project: Project, script: Script, llm: Ollama | None) -> Path:
    data = None
    if llm is not None:
        try:
            summary = " ".join(s.narration for s in script.sections)[:2500]
            data = llm.chat_json(META_PROMPT.format(
                title=script.title, problem=script.problem,
                headings="; ".join(s.heading for s in script.sections), summary=summary))
        except LLMError as e:
            print(f"  [!] LLM metadata failed ({e}); using simple metadata.")
    fb = fallback_meta(script)
    if not isinstance(data, dict):
        data = fb
    for k, v in fb.items():
        if not data.get(k):
            data[k] = v
    tl_path = project.build_dir / "timeline_main.json"
    chaps = chapters(json.loads(tl_path.read_text())) if tl_path.exists() else []
    lines = ["TITLE OPTIONS (pick one):"]
    lines += [f"  {i}. {t}" for i, t in enumerate(data["titles"][:5], 1)]
    lines += ["", "THUMBNAIL TEXT:", f"  {data['thumbnail_text']}", "", "DESCRIPTION:",
              data["description"].strip(), ""]
    if chaps:
        lines.append("Chapters:")
        lines += [f"{fmt_ts(t)} {name}" for t, name in chaps]
        lines.append("")
    cmds = [c for s in script.sections for c in s.code]
    if cmds:
        lines.append("Commands used in this video:")
        lines += [f"  {c}" for c in cmds]
        lines.append("")
    creds = credits(project)
    if creds:
        lines.append("Credits:")
        lines += [f"  {c}" for c in creds]
        lines.append("")
    lines.append(" ".join(data["hashtags"][:3]))
    lines += ["", "TAGS (paste in the tags box):", ", ".join(data["tags"][:15])]
    out = project.dir / "youtube.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (project.dir / "meta.json").write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    return out

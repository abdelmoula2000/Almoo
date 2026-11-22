"""Script format (script.md), parser, and LLM script writer.

script.md looks like this:

    # Laptop Overheating? 7 Fixes That Actually Work
    problem: laptop overheating

    ## Why your laptop gets hot
    [visual: title]
    Narration text...

    ## Step 1: Check what is using your CPU
    [visual: terminal]
    [code: Get-Process | Sort-Object CPU -Descending | Select-Object -First 5]
    Narration text...

    ## Step 2: Clean the fan
    [visual: steps]
    [bullets: Shut down and unplug; Use compressed air; Hold the fan still]
    [short: yes]
    Narration text...

    ## Step 3: Change the power plan
    [visual: shot: 01.png focus=0.62,0.35 zoom=1.8 box=0.5,0.25,0.3,0.2]
    Narration text...

Visuals: title | steps | terminal | tip | shot | outro
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import Ollama

VISUALS = ("title", "steps", "terminal", "tip", "shot", "outro")

_DIRECTIVE = re.compile(r"^\[(\w+)\s*:\s*(.*)\]\s*$")


@dataclass
class Shot:
    file: str
    focus: tuple[float, float] = (0.5, 0.5)
    zoom: float = 1.6
    box: tuple[float, float, float, float] | None = None


@dataclass
class Section:
    heading: str
    visual: str = "steps"
    narration: str = ""
    bullets: list[str] = field(default_factory=list)
    code: list[str] = field(default_factory=list)
    shot: Shot | None = None
    short: bool = False

    @property
    def words(self) -> int:
        return len(self.narration.split())


@dataclass
class Script:
    title: str
    problem: str = ""
    sections: list[Section] = field(default_factory=list)

    @property
    def narration(self) -> str:
        return "\n".join(s.narration for s in self.sections)

    @property
    def word_count(self) -> int:
        return sum(s.words for s in self.sections)

    def estimated_minutes(self, wpm: int = 150) -> float:
        return self.word_count / wpm


# ------------------------------------------------------------------ parse

def _parse_floats(text: str, n: int) -> tuple[float, ...] | None:
    try:
        vals = tuple(float(x) for x in text.split(","))
    except ValueError:
        return None
    return vals if len(vals) == n else None


def parse_shot(value: str) -> Shot:
    """'01.png focus=0.6,0.3 zoom=1.8 box=0.5,0.2,0.3,0.2'"""
    parts = value.split()
    if not parts:
        raise ValueError("shot directive needs a file name, e.g. [visual: shot: 01.png]")
    shot = Shot(file=parts[0])
    for p in parts[1:]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.lower()
        if k == "focus" and (f := _parse_floats(v, 2)):
            shot.focus = (min(max(f[0], 0), 1), min(max(f[1], 0), 1))
        elif k == "zoom":
            try:
                shot.zoom = min(max(float(v), 1.0), 4.0)
            except ValueError:
                pass
        elif k == "box" and (b := _parse_floats(v, 4)):
            shot.box = b  # type: ignore[assignment]
    return shot


def parse_script(text: str) -> Script:
    title, problem = "", ""
    sections: list[Section] = []
    cur: Section | None = None
    narration: list[str] = []

    def flush():
        if cur is not None:
            cur.narration = " ".join(" ".join(narration).split())
            sections.append(cur)

    in_comment = False
    for raw in text.splitlines():
        line = raw.strip()
        # skip HTML comments (used for notes in the file)
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.startswith("<!--"):
            in_comment = "-->" not in line
            continue
        if line.startswith("## "):
            flush()
            cur, narration = Section(heading=line[3:].strip()), []
            continue
        if line.startswith("# ") and cur is None:
            title = line[2:].strip()
            continue
        m = _DIRECTIVE.match(line)
        if m:
            key, value = m.group(1).lower(), m.group(2).strip()
            if cur is None:
                if key == "problem":
                    problem = value
                continue
            if key == "visual":
                kind = value.split(":", 1)[0].strip().lower()
                if kind == "shot":
                    cur.visual = "shot"
                    cur.shot = parse_shot(value.split(":", 1)[1].strip() if ":" in value else "")
                elif kind in VISUALS:
                    cur.visual = kind
                else:
                    raise ValueError(f"Unknown visual '{kind}' in section '{cur.heading}'. "
                                     f"Use one of: {', '.join(VISUALS)}")
            elif key == "bullets":
                cur.bullets.extend(b.strip() for b in value.split(";") if b.strip())
            elif key == "code":
                cur.code.append(value)
            elif key == "short":
                cur.short = value.lower() in ("yes", "true", "1", "y")
            continue
        if cur is None:
            if line.lower().startswith("problem:"):
                problem = line.split(":", 1)[1].strip()
            continue
        if line:
            narration.append(line)
    flush()
    if not sections:
        raise ValueError("script.md has no sections (lines starting with '## ').")
    for s in sections:
        if s.visual == "terminal" and not s.code:
            s.visual = "steps"
    return Script(title=title or sections[0].heading, problem=problem, sections=sections)


def load_script(path: str | Path) -> Script:
    return parse_script(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ write

def render_script(script: Script) -> str:
    out = [f"# {script.title}", f"problem: {script.problem}", "",
           "<!-- Edit freely: add your own tips, fix anything wrong, test every step yourself. -->",
           ""]
    for s in script.sections:
        out.append(f"## {s.heading}")
        if s.visual == "shot" and s.shot:
            shot = f"shot: {s.shot.file} focus={s.shot.focus[0]:g},{s.shot.focus[1]:g} zoom={s.shot.zoom:g}"
            if s.shot.box:
                shot += " box=" + ",".join(f"{v:g}" for v in s.shot.box)
            out.append(f"[visual: {shot}]")
        else:
            out.append(f"[visual: {s.visual}]")
        if s.bullets:
            out.append("[bullets: " + "; ".join(s.bullets) + "]")
        for c in s.code:
            out.append(f"[code: {c}]")
        if s.short:
            out.append("[short: yes]")
        out.append(s.narration)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------ LLM

SYSTEM = (
    "You are a senior IT support technician who writes scripts for a faceless YouTube tech "
    "channel. You give accurate, safe, tested-in-practice fixes. You never invent menu names, "
    "settings or commands that do not exist. You warn before risky steps (registry, BIOS, "
    "deleting files) and recommend a backup. Your tone is friendly, clear and direct, "
    "for an English-speaking audience. No filler, no fake hype."
)

PROMPT = """Write a YouTube video script that solves this problem: "{problem}"
Platform/context: {context}
Target length: about {minutes} minutes of narration (~{words} words total).

Return ONE JSON object:
{{
  "title": "honest, searchable title, max 70 chars",
  "sections": [
    {{
      "heading": "short on-screen heading",
      "visual": "title | steps | terminal | tip | outro",
      "bullets": ["2-5 short on-screen points, max 6 words each"],
      "code": ["exact command(s) to show, only for visual=terminal"],
      "short": true or false,
      "narration": "what the narrator says, spoken English, 40-140 words"
    }}
  ]
}}

Rules:
- First section: visual "title" - hook in the first sentence (state the problem and promise the fix), no greeting.
- Then 4-8 sections of concrete fixes, ordered from easiest/safest to advanced. Use "Step N: ..." headings.
- Use visual "terminal" only when there is a real command (Windows: PowerShell/CMD, macOS/Linux: Terminal).
- Include one "tip" section with a useful extra tip or a safety warning.
- Mark exactly 2 strong, self-contained fix sections with "short": true (they become YouTube Shorts).
- Last section: visual "outro" - short recap and ask viewers to comment which fix worked. No begging.
- Do not claim anything you are not sure about. No clickbait.
"""


def write_script(llm: Ollama, problem: str, context: str = "Windows 10/11",
                 minutes: float = 7) -> Script:
    data = llm.chat_json(
        PROMPT.format(problem=problem, context=context, minutes=minutes, words=int(minutes * 150)),
        system=SYSTEM,
    )
    return script_from_json(data, problem)


def script_from_json(data: Any, problem: str) -> Script:
    if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
        raise ValueError("LLM answer has no 'sections' list.")
    sections: list[Section] = []
    for raw in data["sections"]:
        if not isinstance(raw, dict):
            continue
        narration = " ".join(str(raw.get("narration", "")).split())
        if not narration:
            continue
        visual = str(raw.get("visual", "steps")).strip().lower()
        if visual not in VISUALS or visual == "shot":
            visual = "steps"
        code = [str(c).strip() for c in _as_list(raw.get("code")) if str(c).strip()]
        if visual == "terminal" and not code:
            visual = "steps"
        if visual != "terminal":
            code = []
        bullets = [str(b).strip().strip("-• ") for b in _as_list(raw.get("bullets"))]
        sections.append(Section(
            heading=str(raw.get("heading", "")).strip() or f"Part {len(sections) + 1}",
            visual=visual,
            narration=narration,
            bullets=[b.replace(";", ",") for b in bullets if b][:5],
            code=code[:4],
            short=bool(raw.get("short")) and visual not in ("title", "outro"),
        ))
    if len(sections) < 2:
        raise ValueError("LLM returned too few usable sections; try again or a bigger model.")
    title = str(data.get("title", "")).strip() or problem.title()
    return Script(title=title[:100], problem=problem, sections=sections)


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

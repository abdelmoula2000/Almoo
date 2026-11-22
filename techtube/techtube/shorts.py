"""Vertical 9:16 Shorts, rendered natively for the phone screen (not cropped)."""

from __future__ import annotations

import re
from pathlib import Path

from .build import build_video
from .script import Script
from .slides import first_sentence, split_step
from .themes import Theme
from .util import Project, probe_duration
from .voice import section_audio


def choose_sections(script: Script, requested: list[int] | None = None,
                    durations: dict[int, float] | None = None, limit: int = 3) -> list[int]:
    """Sections (1-based) to turn into Shorts.

    Priority: --sections flag > [short: yes] in script.md > good fix sections 12-60 s long.
    """
    n = len(script.sections)
    if requested:
        bad = [i for i in requested if not 1 <= i <= n]
        if bad:
            raise SystemExit(f"[x] Section numbers must be between 1 and {n}: {bad}")
        return requested
    marked = [i for i, s in enumerate(script.sections, 1) if s.short]
    if marked:
        return marked[:limit]
    durations = durations or {}
    cands = []
    for i, s in enumerate(script.sections, 1):
        if s.visual in ("title", "outro"):
            continue
        d = durations.get(i, s.words / 2.5)
        if 12 <= d <= 60:
            cands.append((s.words, i))
    cands.sort(reverse=True)
    return sorted(i for _, i in cands[:min(limit, 2)])


def short_text(script: Script, index: int, channel: str = "") -> str:
    sec = script.sections[index - 1]
    _, heading = split_step(sec.heading)
    topic = script.problem or script.title
    title = f"{heading} ({topic})" if topic and topic.lower() not in heading.lower() else heading
    title = title[:90]
    tags = {"#shorts", "#techtips"}
    for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", topic)[:3]:
        if len(w) > 3:
            tags.add("#" + w.lower())
    lines = [
        "TITLE:",
        f"{title} #shorts",
        "",
        "DESCRIPTION:",
        first_sentence(sec.narration, 30),
        f"Full step-by-step video on the channel{(' ' + channel) if channel else ''}.",
        "",
        " ".join(sorted(tags)),
    ]
    return "\n".join(lines) + "\n"


def make_shorts(project: Project, script: Script, theme: Theme, cfg: dict,
                requested: list[int] | None = None, captions_mode: str = "auto") -> list[Path]:
    durations = {}
    for i in range(1, len(script.sections) + 1):
        wav = section_audio(project, i)
        if wav.exists():
            durations[i] = probe_duration(wav)
    picks = choose_sections(script, requested, durations)
    if not picks:
        print("  No section fits a Short (12-60 s). Mark one with [short: yes] in script.md.")
        return []
    project.shorts_dir.mkdir(parents=True, exist_ok=True)
    outs = []
    for n, idx in enumerate(picks, 1):
        d = durations.get(idx, 0)
        if d > 175:
            print(f"  [!] Section {idx} is {d:.0f}s; Shorts must be under 3 minutes. Skipped.")
            continue
        if d > 60:
            print(f"  [!] Section {idx} is {d:.0f}s; 30-60 s usually performs best for Shorts.")
        out = project.shorts_dir / f"short_{n:02d}.mp4"
        build_video(project, script, theme, cfg, vertical=True, indices=[idx], out=out,
                    tag=f"short{idx:02d}", captions_mode=captions_mode, music="")
        (project.shorts_dir / f"short_{n:02d}.txt").write_text(
            short_text(script, idx, cfg.get("channel_name", "")), encoding="utf-8")
        outs.append(out)
        print(f"  short {n}: section {idx} -> {out.name}")
    return outs

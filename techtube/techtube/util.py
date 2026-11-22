"""Shared helpers: config, project paths, ffmpeg/ffprobe, fonts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CONFIG: dict[str, Any] = {
    "channel_name": "Fix It Fast",
    "model": "llama3.2:3b",
    "ollama_host": "http://localhost:11434",
    "voice": "af_heart",
    "voice_speed": 1.0,
    "whisper_model": "small",
    "fps": 30,
    "music": "",
    "music_volume": 0.08,
    "projects_dir": "projects",
}


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Load config.json (next to tt.py) on top of the defaults."""
    cfg = dict(DEFAULT_CONFIG)
    p = Path(path) if path else ROOT / "config.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
    if os.environ.get("OLLAMA_HOST"):
        host = os.environ["OLLAMA_HOST"]
        cfg["ollama_host"] = host if host.startswith("http") else f"http://{host}"
    return cfg


def slugify(text: str, max_len: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (text[:max_len].rstrip("-")) or "video"


@dataclass
class Project:
    """All the paths of one video project."""

    dir: Path

    @property
    def name(self) -> str:
        return self.dir.name

    @property
    def script(self) -> Path:
        return self.dir / "script.md"

    @property
    def draft(self) -> Path:
        return self.dir / "script.draft.md"

    @property
    def meta_json(self) -> Path:
        return self.dir / "project.json"

    @property
    def audio_dir(self) -> Path:
        return self.dir / "audio"

    @property
    def myvoice_dir(self) -> Path:
        return self.dir / "myvoice"

    @property
    def shots_dir(self) -> Path:
        return self.dir / "shots"

    @property
    def build_dir(self) -> Path:
        return self.dir / "build"

    @property
    def shorts_dir(self) -> Path:
        return self.dir / "shorts"

    @property
    def final(self) -> Path:
        return self.dir / "final.mp4"

    @property
    def assets_json(self) -> Path:
        return self.dir / "assets.json"

    def ensure(self) -> "Project":
        for d in (self.dir, self.audio_dir, self.shots_dir, self.build_dir):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def read_info(self) -> dict[str, Any]:
        if self.meta_json.exists():
            return json.loads(self.meta_json.read_text(encoding="utf-8"))
        return {}

    def write_info(self, info: dict[str, Any]) -> None:
        self.meta_json.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def projects_root(cfg: dict[str, Any]) -> Path:
    p = Path(cfg["projects_dir"])
    if not p.is_absolute():
        p = ROOT / p
    return p


def get_project(cfg: dict[str, Any], name: str) -> Project:
    p = Path(name)
    if p.is_dir() and (p / "script.md").exists():
        return Project(p.resolve())
    return Project(projects_root(cfg) / name)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        sys.exit(f"[x] '{name}' is not installed or not on PATH. See README.md.")
    return path


def run(cmd: list[str], cwd: str | os.PathLike | None = None, quiet: bool = True) -> None:
    """Run a command; on failure show the tail of stderr and exit."""
    res = subprocess.run(cmd, cwd=cwd, capture_output=quiet, text=True)
    if res.returncode != 0:
        tail = (res.stderr or "")[-2000:] if quiet else ""
        raise RuntimeError(f"Command failed: {' '.join(map(str, cmd[:6]))} ...\n{tail}")


def ffmpeg_cmd(*args: str) -> list[str]:
    return [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args]


def probe_duration(path: str | os.PathLike) -> float:
    out = subprocess.run(
        [require_tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError as e:
        raise RuntimeError(f"Could not read duration of {path}") from e


def probe_size(path: str | os.PathLike) -> tuple[int, int]:
    out = subprocess.run(
        [require_tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True,
    )
    w, h = out.stdout.strip().split("x")[:2]
    return int(w), int(h)


# ---------------------------------------------------------------- fonts

_FONT_CANDIDATES = {
    "bold": [
        "fonts/Inter-Bold.ttf", "fonts/bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "regular": [
        "fonts/Inter-Regular.ttf", "fonts/regular.ttf",
        "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ],
    "mono": [
        "fonts/mono.ttf",
        "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf",
        "/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ],
}


def find_font(kind: str) -> str | None:
    for cand in _FONT_CANDIDATES[kind]:
        p = Path(cand)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            return str(p)
    return None


@dataclass
class Fonts:
    bold: str | None = field(default_factory=lambda: find_font("bold"))
    regular: str | None = field(default_factory=lambda: find_font("regular"))
    mono: str | None = field(default_factory=lambda: find_font("mono"))

    def get(self, kind: str, size: int):
        from PIL import ImageFont

        path = getattr(self, kind) or self.regular or self.bold
        if path:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default(size)


def fmt_ts(seconds: float) -> str:
    """Seconds -> YouTube chapter timestamp (M:SS or H:MM:SS)."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

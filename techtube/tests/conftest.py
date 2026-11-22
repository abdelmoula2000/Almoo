import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from techtube.script import load_script  # noqa: E402
from techtube.util import Project  # noqa: E402
from techtube.voice import SAMPLE_RATE, write_wav  # noqa: E402

EXAMPLE = ROOT / "examples" / "laptop-overheating.md"

SMALL = """# How to Fix Slow Wi-Fi: 3 Quick Fixes
problem: slow wifi

## Slow Wi-Fi?
[visual: title]
Is your Wi-Fi slow? Here are three quick fixes.

## Step 1: Restart the router
[visual: steps]
[bullets: Unplug the router; Wait 30 seconds; Plug it back in]
[short: yes]
Unplug your router, wait thirty seconds, and plug it back in.

## Step 2: Flush DNS
[visual: terminal]
[code: ipconfig /flushdns]
Open Command Prompt and run this command to clear the DNS cache.

## Step 3: Check the band
[visual: shot: 01.png focus=0.3,0.3 zoom=2 box=0.1,0.1,0.3,0.2]
Pick the five gigahertz band if your device supports it.

## Did it work?
[visual: outro]
Tell me in the comments which fix worked.
"""


def make_screenshot(path: Path) -> None:
    im = Image.new("RGB", (800, 500), "#f0f0f0")
    d = ImageDraw.Draw(im)
    d.rectangle((80, 50, 320, 150), fill="#3366ff")
    d.text((100, 90), "5 GHz", fill="white")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


@pytest.fixture
def small_project(tmp_path) -> Project:
    """A tiny project with fake voice audio and a screenshot."""
    proj = Project(tmp_path / "projects" / "slow-wifi").ensure()
    proj.script.write_text(SMALL, encoding="utf-8")
    proj.write_info({"theme": "midnight", "created": "2026-01-01T00:00:00"})
    make_screenshot(proj.shots_dir / "01.png")
    script = load_script(proj.script)
    for i, _ in enumerate(script.sections, 1):
        t = np.arange(int(1.2 * SAMPLE_RATE)) / SAMPLE_RATE
        write_wav(proj.audio_dir / f"{i:02d}.wav", 0.1 * np.sin(2 * np.pi * 330 * t))
    return proj


needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")

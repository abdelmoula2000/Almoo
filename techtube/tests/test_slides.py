import numpy as np
import pytest
from conftest import SMALL

from techtube.script import parse_script
from techtube.shots import ShotVisual
from techtube.slides import (Canvas, FrameSource, TerminalVisual, make_visual, split_step,
                             wrap_code)
from techtube.themes import THEMES, get_theme, pick_theme


@pytest.mark.parametrize("size", [(1920, 1080), (1080, 1920)])
def test_every_visual_renders(small_project, size):
    script = parse_script(SMALL)
    canvas = Canvas(*size, get_theme("ocean"), channel="Test")
    for sec in script.sections:
        vis = make_visual(canvas, sec, 5.0, script, small_project.shots_dir)
        for t in (0.0, 0.3, 4.9):
            img = vis.draw(vis.state(t))
            assert img.size == size and img.mode == "RGB"


def test_animation_settles_to_static_state(small_project):
    script = parse_script(SMALL)
    canvas = Canvas(1920, 1080, get_theme("midnight"))
    vis = make_visual(canvas, script.sections[1], 6.0, script)
    assert vis.state(0.1) != vis.state(5.5)
    assert vis.state(5.5) == vis.state(5.9)   # nothing moves at the end -> frame reused


def test_terminal_types_progressively():
    script = parse_script(SMALL)
    canvas = Canvas(1920, 1080, get_theme("midnight"))
    vis = TerminalVisual(canvas, script.sections[2], 6.0, script)
    assert vis.shell == "Terminal"
    typed = [vis.state(t)[2] for t in (0.5, 1.2, 5.9)]
    assert typed[0] == 0 and typed[0] < typed[1] <= typed[2] == len("ipconfig /flushdns")


def test_powershell_detection():
    s = parse_script("# T\n## A\n[visual: terminal]\n[code: Get-Process]\nRun it.\n")
    vis = TerminalVisual(Canvas(1920, 1080, THEMES[0]), s.sections[0], 4, s)
    assert vis.shell == "PowerShell" and vis.prompt.startswith("PS")


def test_wrap_code_prefers_spaces():
    rows = wrap_code("Get-Process | Sort-Object CPU -Descending", 20)
    assert all(len(r) <= 20 for r in rows)
    assert "".join(rows) == "Get-Process | Sort-Object CPU -Descending"
    assert rows[0].endswith(" ")


def test_split_step():
    assert split_step("Step 3: Clean the fan") == ("3", "Clean the fan")
    assert split_step("Before you start") == (None, "Before you start")


def test_shot_zooms_toward_box(small_project):
    script = parse_script(SMALL)
    canvas = Canvas(1920, 1080, THEMES[0])
    vis = ShotVisual(canvas, script.sections[3], 5.0, script, small_project.shots_dir)
    # focus moves to the box center and zoom is limited so the box stays visible
    assert vis.shot.focus == pytest.approx((0.25, 0.2))
    l, t, r, b = vis.view(1.0)
    w, h = vis.src.size
    assert l <= 0.1 * w and r >= 0.4 * w and t <= 0.1 * h and b >= 0.3 * h


def test_missing_screenshot_errors(tmp_path):
    script = parse_script(SMALL)
    with pytest.raises(FileNotFoundError):
        ShotVisual(Canvas(1920, 1080, THEMES[0]), script.sections[3], 5, script, tmp_path)


def test_frame_source_counts_and_bar():
    script = parse_script(SMALL)
    canvas = Canvas(320, 180, THEMES[0])
    src = FrameSource(canvas, 10, total=2.0)
    vis = make_visual(canvas, script.sections[1], 1.0, script)
    frames = list(src.frames(vis, 10, 0.0))
    assert len(frames) == 10
    assert all(len(f) == 320 * 180 * 3 for f in frames)
    last = np.frombuffer(frames[-1], np.uint8).reshape(180, 320, 3)
    bar_px = (last[0] == np.array([0x4F, 0x8C, 0xFF])).all(axis=1).sum()
    assert 130 <= bar_px <= 150       # ~45% of the way through a 2 s video


def test_pick_theme_avoids_recent():
    recent = [t.name for t in THEMES[:3]]
    for seed in range(20):
        assert pick_theme(recent, seed=str(seed)).name not in recent

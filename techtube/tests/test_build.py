"""End-to-end render with real ffmpeg (small and fast)."""

import json

from conftest import SMALL, needs_ffmpeg

from techtube.build import GAP, build_video, plan
from techtube.script import parse_script
from techtube.shorts import make_shorts
from techtube.themes import get_theme
from techtube.util import probe_duration, probe_size

CFG = {"fps": 30, "channel_name": "Test", "preset": "ultrafast", "music": ""}


def test_plan_whole_frames(small_project):
    script = parse_script(SMALL)
    segs, audios = plan(small_project, script, [1, 2], 30)
    for s, a in zip(segs, audios):
        assert s.frames == round(s.duration * 30)
        assert abs(len(a) / 24000 - s.duration) < 1e-3
        assert s.duration >= 1.2 + GAP
    assert segs[1].start == segs[0].duration


@needs_ffmpeg
def test_full_build_and_short(small_project):
    script = parse_script(SMALL)
    theme = get_theme("emerald")
    out = build_video(small_project, script, theme, CFG, captions_mode="estimate")
    assert out.exists()
    assert probe_size(out) == (1920, 1080)
    tl = json.loads((small_project.build_dir / "timeline_main.json").read_text())
    expected = sum(s["duration"] for s in tl)
    assert abs(probe_duration(out) - expected) < 0.15
    assert (small_project.build_dir / "captions_main.ass").exists()

    shorts = make_shorts(small_project, script, theme, CFG, captions_mode="estimate")
    assert len(shorts) == 1
    assert probe_size(shorts[0]) == (1080, 1920)
    assert (small_project.shorts_dir / "short_01.txt").exists()


@needs_ffmpeg
def test_build_with_music_and_no_captions(small_project, tmp_path):
    import numpy as np

    from techtube.voice import write_wav
    music = tmp_path / "music.wav"
    t = np.arange(24000 * 2) / 24000
    write_wav(music, 0.3 * np.sin(2 * np.pi * 440 * t))
    script = parse_script(SMALL)
    out = build_video(small_project, script, get_theme("paper"), CFG, indices=[1, 2],
                      out=tmp_path / "m.mp4", tag="m", captions_mode="off", music=str(music))
    assert out.exists() and probe_duration(out) > 2.5

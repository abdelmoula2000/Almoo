"""Assemble slides + voice + captions (+ music) into a video with a single ffmpeg pass."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import captions as cap
from .script import Script
from .slides import Canvas, FrameSource, make_visual
from .themes import Theme
from .util import Fonts, Project, ffmpeg_cmd, run
from .voice import SAMPLE_RATE, section_audio

GAP = 0.35          # silence after each section
EXTRA_HOLD = {"title": 0.25, "outro": 1.2}


@dataclass
class Segment:
    index: int          # 1-based section number
    heading: str
    visual: str
    start: float
    duration: float
    frames: int
    voice: float        # length of the spoken audio (without padding)


def read_wav(path: Path) -> np.ndarray:
    """Mono float32 at SAMPLE_RATE (converts with ffmpeg if needed)."""
    try:
        with wave.open(str(path), "rb") as w:
            ok = w.getnchannels() == 1 and w.getframerate() == SAMPLE_RATE and w.getsampwidth() == 2
            if ok:
                data = np.frombuffer(w.readframes(w.getnframes()), "<i2")
                return data.astype(np.float32) / 32768.0
    except wave.Error:
        pass
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "a.wav"
        run(ffmpeg_cmd("-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt",
                       "s16", str(tmp)))
        return read_wav(tmp)


def write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


def plan(project: Project, script: Script, indices: list[int], fps: int):
    """Exact per-section timing (whole frames) and the padded audio for each section."""
    segs, audios, t = [], [], 0.0
    for i in indices:
        wav = section_audio(project, i)
        if not wav.exists():
            raise SystemExit(f"[x] Missing voice for section {i}: {wav}\n"
                             f"    Run first: python tt.py voice {project.name}")
        sec = script.sections[i - 1]
        audio = read_wav(wav)
        voice_len = len(audio) / SAMPLE_RATE
        dur = voice_len + GAP + EXTRA_HOLD.get(sec.visual, 0.0)
        frames = max(int(math.ceil(dur * fps)), 1)
        real = frames / fps
        target = int(round(real * SAMPLE_RATE))
        audio = np.pad(audio, (0, max(target - len(audio), 0)))[:target]
        segs.append(Segment(i, sec.heading, sec.visual, round(t, 3), round(real, 3), frames,
                            round(voice_len, 3)))
        audios.append(audio)
        t += real
    return segs, audios


def build_video(project: Project, script: Script, theme: Theme, cfg: dict, *,
                vertical: bool = False, indices: list[int] | None = None,
                out: Path | None = None, tag: str = "main", captions_mode: str = "auto",
                music: str | None = None, fonts: Fonts | None = None) -> Path:
    fps = int(cfg.get("fps", 30))
    W, H = (1080, 1920) if vertical else (1920, 1080)
    indices = indices or list(range(1, len(script.sections) + 1))
    out = Path(out or project.final).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    bdir = project.build_dir
    bdir.mkdir(parents=True, exist_ok=True)
    fonts = fonts or Fonts()

    segs, audios = plan(project, script, indices, fps)
    total = sum(s.duration for s in segs)
    write_wav(bdir / f"voice_{tag}.wav", np.concatenate(audios))
    (bdir / f"timeline_{tag}.json").write_text(
        json.dumps([asdict(s) for s in segs], indent=2), encoding="utf-8")

    # ---- captions
    vf = "null"
    if captions_mode != "off":
        words: list[cap.Word] = []
        for seg in segs:
            sec = script.sections[seg.index - 1]
            wav = section_audio(project, seg.index)
            ws = cap.section_words(wav, sec.narration, seg.voice,
                                   captions_mode, cfg.get("whisper_model", "small"),
                                   cache=bdir / f"words_{seg.index:02d}.json",
                                   device=cfg.get("whisper_device", "cpu"))
            words += cap.shift(ws, seg.start)
        font_dir = bdir / "fonts"
        font_dir.mkdir(exist_ok=True)
        if fonts.bold:
            shutil.copy(fonts.bold, font_dir / Path(fonts.bold).name)
        ass = cap.build_ass(words, W, H, font=cap.font_family(fonts.bold),
                            highlight=theme.accent2 if theme.name not in ("paper", "mint", "graphite")
                            else "#FFD400", vertical=vertical)
        (bdir / f"captions_{tag}.ass").write_text(ass, encoding="utf-8")
        vf = f"subtitles=captions_{tag}.ass:fontsdir=fonts"

    # ---- ffmpeg (frames come through stdin)
    args = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps),
            "-i", "pipe:0", "-i", f"voice_{tag}.wav"]
    voice_chain = "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000"
    music = music if music is not None else cfg.get("music") or ""
    if music:
        mpath = Path(music)
        if not mpath.exists():
            raise SystemExit(f"[x] Music file not found: {music}")
        args += ["-stream_loop", "-1", "-i", str(mpath.resolve())]
        vol = float(cfg.get("music_volume", 0.08))
        fc = (f"[0:v]{vf}[v];[1:a]{voice_chain}[vo];"
              f"[2:a]aresample=48000,volume={vol},afade=t=out:st={max(total - 2, 0):.2f}:d=2[m];"
              f"[vo][m]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        fc = f"[0:v]{vf}[v];[1:a]{voice_chain}[a]"
    encoder = cfg.get("encoder", "libx264")
    venc = ["-c:v", encoder]
    if encoder == "libx264":
        venc += ["-preset", cfg.get("preset", "veryfast"), "-crf", str(cfg.get("crf", 20))]
    elif "nvenc" in encoder:
        venc += ["-preset", "p5", "-cq", "21"]
    args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", *venc,
             "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
             "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]

    canvas = Canvas(W, H, theme, fonts, cfg.get("channel_name", ""))
    source = FrameSource(canvas, fps, total)
    total_frames = sum(s.frames for s in segs)
    with tempfile.TemporaryFile(mode="w+") as errf:
        proc = subprocess.Popen(ffmpeg_cmd(*args), cwd=bdir, stdin=subprocess.PIPE,
                                stderr=errf)
        done, last_pct = 0, -1
        try:
            for seg in segs:
                sec = script.sections[seg.index - 1]
                visual = make_visual(canvas, sec, seg.duration, script, project.shots_dir)
                visual.fps = fps
                for frame in source.frames(visual, seg.frames, seg.start):
                    proc.stdin.write(frame)
                    done += 1
                    pct = done * 100 // total_frames
                    if pct % 10 == 0 and pct != last_pct:
                        print(f"  rendering {out.name}: {pct}%", flush=True)
                        last_pct = pct
            proc.stdin.close()
        except BrokenPipeError:
            pass
        code = proc.wait()
        if code != 0:
            errf.seek(0)
            raise RuntimeError(f"ffmpeg failed ({code}):\n{errf.read()[-2000:]}")
    return out

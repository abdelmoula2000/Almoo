"""Voiceover: Kokoro TTS (local, free) or your own recorded voice."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .script import Script
from .util import Project, ffmpeg_cmd, run

SAMPLE_RATE = 24000
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".webm")


def section_audio(project: Project, index: int) -> Path:
    """audio/01.wav for the first section (1-based numbering)."""
    return project.audio_dir / f"{index:02d}.wav"


def write_wav(path: Path, audio: np.ndarray, sr: int = SAMPLE_RATE) -> None:
    audio = np.clip(np.asarray(audio, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (audio * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


class KokoroVoice:
    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        try:
            from kokoro import KPipeline
        except ImportError as e:
            raise SystemExit(
                "[x] Kokoro is not installed. Run: pip install kokoro soundfile\n"
                "    Or use your own voice: python tt.py voice <project> --engine own"
            ) from e
        # 'a' = American English, 'b' = British English (voices starting with b*)
        lang = "b" if voice.startswith("b") else "a"
        self.pipeline = KPipeline(lang_code=lang)
        self.voice = voice
        self.speed = speed

    def synth(self, text: str) -> np.ndarray:
        chunks = []
        for result in self.pipeline(text, voice=self.voice, speed=self.speed):
            audio = getattr(result, "audio", None)
            if audio is None:
                audio = result[2]
            if audio is None:
                continue
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
            chunks.append(np.zeros(int(0.12 * SAMPLE_RATE), dtype=np.float32))
        if not chunks:
            raise RuntimeError("Kokoro produced no audio.")
        return np.concatenate(chunks)


def find_own_recording(project: Project, index: int) -> Path | None:
    for ext in AUDIO_EXT:
        p = project.myvoice_dir / f"{index:02d}{ext}"
        if p.exists():
            return p
    return None


def make_voice(project: Project, script: Script, engine: str = "kokoro",
               voice: str = "af_heart", speed: float = 1.0, force: bool = False) -> list[Path]:
    """Create audio/NN.wav for every section. Existing files are kept unless force=True."""
    project.audio_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    tts = None
    if engine == "own":
        missing = [i for i in range(1, len(script.sections) + 1)
                   if not find_own_recording(project, i)]
        if missing:
            names = ", ".join(f"{i:02d}.wav" for i in missing)
            raise SystemExit(f"[x] Missing recordings in {project.myvoice_dir}: {names}")
    for i, sec in enumerate(script.sections, 1):
        out = section_audio(project, i)
        outputs.append(out)
        own = find_own_recording(project, i)
        if engine == "own" or (own and engine == "auto"):
            # convert any recording to mono 24 kHz wav, trim long leading/trailing silence
            run(ffmpeg_cmd("-i", str(own), "-ac", "1", "-ar", str(SAMPLE_RATE), "-af",
                           "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,"
                           "areverse,silenceremove=start_periods=1:start_threshold=-45dB:"
                           "start_silence=0.25,areverse", str(out)))
            print(f"  [{i:02d}] own voice <- {own.name}")
            continue
        if out.exists() and not force:
            print(f"  [{i:02d}] exists, skipped (use --force to redo)")
            continue
        if tts is None:
            tts = KokoroVoice(voice, speed)
        write_wav(out, tts.synth(sec.narration))
        print(f"  [{i:02d}] {sec.heading}")
    return outputs

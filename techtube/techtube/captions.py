"""Word timings (Whisper, or an offline estimate) and big, readable ASS captions."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Word:
    text: str
    start: float
    end: float


# ------------------------------------------------------------- timings

def estimate_words(text: str, duration: float, lead: float = 0.05, tail: float = 0.1) -> list[Word]:
    """Spread words over the audio by length, with small pauses after punctuation.

    Good enough for TTS audio; used when faster-whisper is not installed.
    """
    tokens = text.split()
    if not tokens or duration <= 0:
        return []
    weights = []
    for t in tokens:
        w = max(len(re.sub(r"\W", "", t)), 1) + 1.5
        if t[-1] in ".!?":
            w += 4
        elif t[-1] in ",;:":
            w += 2
        weights.append(w)
    usable = max(duration - lead - tail, 0.1)
    unit = usable / sum(weights)
    words, t0 = [], lead
    for tok, w in zip(tokens, weights):
        speak = w * unit
        pause = 0.0
        if tok[-1] in ".!?":
            pause = 4 * unit
        elif tok[-1] in ",;:":
            pause = 2 * unit
        words.append(Word(tok, round(t0, 3), round(t0 + speak - pause, 3)))
        t0 += speak
    return words


_whisper_model = None


def whisper_words(wav: Path, model_size: str = "small") -> list[Word]:
    """Word-level timestamps with faster-whisper (GPU if available, else CPU int8)."""
    global _whisper_model
    from faster_whisper import WhisperModel  # imported lazily: optional dependency

    if _whisper_model is None:
        try:
            _whisper_model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
        except Exception:
            _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = _whisper_model.transcribe(str(wav), language="en", word_timestamps=True,
                                            vad_filter=False)
    out = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                out.append(Word(text, round(w.start, 3), round(w.end, 3)))
    return out


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def section_words(wav: Path, narration: str, duration: float, mode: str = "auto",
                  model_size: str = "small", cache: Path | None = None) -> list[Word]:
    """Words for one section. mode: auto | whisper | estimate."""
    if cache and cache.exists() and cache.stat().st_mtime >= wav.stat().st_mtime:
        return [Word(**w) for w in json.loads(cache.read_text(encoding="utf-8"))]
    use_whisper = mode == "whisper" or (mode == "auto" and whisper_available())
    words = whisper_words(wav, model_size) if use_whisper else []
    if not words:
        words = estimate_words(narration, duration)
    if cache:
        cache.write_text(json.dumps([asdict(w) for w in words]), encoding="utf-8")
    return words


# ------------------------------------------------------------- grouping

def group_words(words: list[Word], max_words: int = 3, max_chars: int = 18,
                max_gap: float = 0.6) -> list[list[Word]]:
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur:
            chars = sum(len(x.text) + 1 for x in cur) + len(w.text)
            gap = w.start - cur[-1].end
            if len(cur) >= max_words or chars > max_chars or gap > max_gap \
                    or cur[-1].text[-1] in ".!?,;:":
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


# ------------------------------------------------------------- ASS

def ass_time(t: float) -> str:
    t = max(t, 0.0)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    """'#RRGGBB' -> '&HAABBGGRR' (ASS uses BGR)."""
    h = hex_rgb.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _clean(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def build_ass(words: list[Word], width: int, height: int, font: str = "Arial",
              text_color: str = "#FFFFFF", highlight: str = "#FFD400",
              vertical: bool = False) -> str:
    size = int(height * (0.052 if vertical else 0.062))
    margin_v = int(height * (0.30 if vertical else 0.07))
    outline = max(2, size // 9)
    max_chars = 16 if vertical else 24
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},{ass_color(text_color)},{ass_color(highlight)},&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{max(1, outline // 2)},2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    hl = ass_color(highlight)
    lines = []
    groups = group_words(words, max_words=3, max_chars=max_chars)
    for gi, group in enumerate(groups):
        g_end = group[-1].end + 0.15
        if gi + 1 < len(groups):  # never overlap the next caption (libass would stack them)
            g_end = min(g_end, groups[gi + 1][0].start)
        for i, w in enumerate(group):
            start = w.start
            end = group[i + 1].start if i + 1 < len(group) else g_end
            if end <= start:
                end = start + 0.05
            parts = []
            for j, x in enumerate(group):
                t = _clean(x.text.upper() if vertical else x.text)
                parts.append(f"{{\\c{hl}}}{t}{{\\r}}" if j == i else t)
            pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if i == 0 else ""
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{pop}"
                         + " ".join(parts))
    return header + "\n".join(lines) + "\n"


def font_family(path: str | None) -> str:
    """Family name libass needs (e.g. 'DejaVu Sans'), read from the font file."""
    if not path:
        return "Arial"
    try:
        from PIL import ImageFont
        return ImageFont.truetype(path, 20).getname()[0]
    except Exception:
        return "Arial"


def shift(words: list[Word], offset: float) -> list[Word]:
    return [Word(w.text, round(w.start + offset, 3), round(w.end + offset, 3)) for w in words]

"""Animated slides drawn with Pillow: title, steps, terminal, tip, outro (+ shots via shots.py).

Every visual exposes:
    state(t)  -> hashable key (same key = identical frame, so it's drawn once and reused)
    draw(key) -> PIL RGB image
"""

from __future__ import annotations

import re
from typing import Hashable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .script import Script, Section
from .themes import Theme, hex_rgb
from .util import Fonts

ANIM = 0.45  # seconds for an element entrance


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 3 * x * x - 2 * x * x * x


def rgba(h: str, a: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = hex_rgb(h)
    return r, g, b, int(255 * min(max(a, 0), 1))


# ===================================================================== canvas

class Canvas:
    """Size, theme, fonts and the shared background for one video."""

    def __init__(self, width: int, height: int, theme: Theme, fonts: Fonts | None = None,
                 channel: str = ""):
        self.W, self.H = width, height
        self.vertical = height > width
        self.s = min(width, height) / 1080
        self.theme = theme
        self.fonts = fonts or Fonts()
        self.channel = channel
        self._bg: Image.Image | None = None
        self._font_cache: dict[tuple[str, int], object] = {}
        mx = int(self.W * (0.08 if self.vertical else 0.07))
        if self.vertical:
            # keep the lower part free for the big captions
            self.box = (mx, int(self.H * 0.09), self.W - mx, int(self.H * 0.60))
        else:
            self.box = (mx, int(self.H * 0.09), self.W - mx, int(self.H * 0.80))

    def font(self, kind: str, px: float):
        key = (kind, int(px))
        if key not in self._font_cache:
            self._font_cache[key] = self.fonts.get(kind, int(px))
        return self._font_cache[key]

    def px(self, v: float) -> int:
        return int(v * self.s)

    # ---- background: vertical gradient + subtle decoration, drawn once
    def background(self) -> Image.Image:
        if self._bg is None:
            self._bg = self._make_background()
        return self._bg.copy()

    def _make_background(self) -> Image.Image:
        t = self.theme
        top, bot = np.array(hex_rgb(t.bg_top), float), np.array(hex_rgb(t.bg_bottom), float)
        ys = np.linspace(0, 1, self.H)[:, None]
        xs = np.linspace(0, 1, self.W)[None, :]
        mix = np.clip(ys * 0.85 + xs * 0.15, 0, 1)[..., None]
        arr = (top * (1 - mix) + bot * mix).astype(np.uint8)
        img = Image.fromarray(arr, "RGB").convert("RGBA")
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        acc, acc2 = t.accent, t.accent2
        if t.deco == "dots":
            step = self.px(46)
            for y in range(step // 2, self.H, step):
                for x in range(step // 2, self.W, step):
                    if (x * 7 + y * 13) % 5 == 0:
                        r = self.px(2.2)
                        d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(t.muted, 0.18))
        elif t.deco == "grid":
            step = self.px(80)
            for x in range(0, self.W, step):
                d.line((x, 0, x, self.H), fill=rgba(t.muted, 0.07), width=1)
            for y in range(0, self.H, step):
                d.line((0, y, self.W, y), fill=rgba(t.muted, 0.07), width=1)
        elif t.deco == "lines":
            step = self.px(140)
            for k in range(-self.H, self.W, step):
                d.line((k, self.H, k + self.H, 0), fill=rgba(t.muted, 0.06), width=self.px(3))
        # soft glows (drawn small and blurred for speed)
        glow = Image.new("RGBA", (self.W // 4, self.H // 4), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        gw, gh = glow.size
        g.ellipse((gw * 0.62, -gh * 0.25, gw * 1.25, gh * 0.45), fill=rgba(acc, 0.30))
        g.ellipse((-gw * 0.25, gh * 0.65, gw * 0.35, gh * 1.3), fill=rgba(acc2, 0.20))
        if t.deco == "circles":
            g.ellipse((gw * 0.35, gh * 0.3, gw * 0.75, gh * 0.75), fill=rgba(acc, 0.10))
        glow = glow.filter(ImageFilter.GaussianBlur(max(gw, gh) / 14)).resize(img.size,
                                                                            Image.BILINEAR)
        img = Image.alpha_composite(img, glow)
        img = Image.alpha_composite(img, layer)
        # RGB so that ImageDraw(img, "RGBA") blends semi-transparent shapes
        return img.convert("RGB")

    # ---- drawing helpers
    def wrap(self, text: str, font, max_w: int) -> list[str]:
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if font.getlength(trial) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def fit_text(self, text: str, kind: str, size: float, max_w: int, max_lines: int,
                 min_size: float = 26) -> tuple[object, list[str]]:
        """Shrink the font until text fits in max_lines."""
        size = float(size)
        while True:
            f = self.font(kind, size)
            lines = self.wrap(text, f, max_w)
            if len(lines) <= max_lines or size <= min_size:
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines[-1] = lines[-1].rstrip(".,;:") + "…"
                return f, lines
            size *= 0.92

    @staticmethod
    def line_h(font) -> int:
        a, d = font.getmetrics()
        return int((a + d) * 1.12)

    def text_block(self, d: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], font,
                   color: str, alpha: float = 1.0, align: str = "left", width: int = 0) -> int:
        lh = self.line_h(font)
        for i, ln in enumerate(lines):
            lx = x
            if align == "center":
                lx = x + (width - int(font.getlength(ln))) // 2
            d.text((lx, y + i * lh), ln, font=font, fill=rgba(color, alpha))
        return y + lh * len(lines)

    def pill(self, d, x: int, y: int, text: str, font, bg: str, fg: str, alpha: float = 1.0,
             pad: tuple[int, int] | None = None) -> tuple[int, int]:
        px_, py_ = pad or (self.px(22), self.px(10))
        w = int(font.getlength(text)) + 2 * px_
        a, dsc = font.getmetrics()
        h = a + dsc + 2 * py_
        d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=rgba(bg, alpha))
        d.text((x + px_, y + py_), text, font=font, fill=rgba(fg, alpha))
        return w, h

    def finish(self, img: Image.Image) -> Image.Image:
        return img.convert("RGB")


# ===================================================================== visuals

_STEP_RE = re.compile(r"^\s*step\s*(\d+)\s*[:.\-–—]?\s*(.*)$", re.I)


def split_step(heading: str) -> tuple[str | None, str]:
    m = _STEP_RE.match(heading)
    if m and m.group(2).strip():
        return m.group(1), m.group(2).strip()
    return None, heading


def first_sentence(text: str, max_words: int = 18) -> str:
    sent = re.split(r"(?<=[.!?])\s+", text.strip())[0] if text.strip() else ""
    words = sent.split()
    if len(words) > max_words:
        sent = " ".join(words[:max_words]).rstrip(",;:") + "…"
    return sent


class Visual:
    def __init__(self, canvas: Canvas, section: Section, duration: float, script: Script):
        self.c = canvas
        self.sec = section
        self.dur = max(duration, 0.5)
        self.script = script
        self.fps = 30

    def appear(self, t: float, delay: float) -> float:
        return round(ease_out((t - delay) / ANIM), 2)

    def state(self, t: float) -> Hashable:
        raise NotImplementedError

    def draw(self, state) -> Image.Image:
        raise NotImplementedError

    def _heading_layout(self):
        c = self.c
        x0, _, x1, _ = c.box
        num, text = split_step(self.sec.heading)
        size = c.px(64 if not c.vertical else 70)
        badge_w = int(size * 1.15) + c.px(22) if num else 0
        f, lines = c.fit_text(text, "bold", size, (x1 - x0) - badge_w, 2, min_size=c.px(40))
        return num, size, badge_w, f, lines

    def heading_height(self) -> int:
        _, _, _, f, lines = self._heading_layout()
        return self.c.line_h(f) * len(lines) + self.c.px(14 + 44)

    def top_for(self, content_h: int, bias: float = 0.4) -> int:
        """Top y that vertically centers a block of content_h (slightly above center)."""
        _, y0, _, y1 = self.c.box
        return y0 + int(max((y1 - y0) - content_h, 0) * bias)

    # common heading (with step badge), returns y below it
    def heading(self, d, p: float, y: int | None = None) -> int:
        c = self.c
        x0, y0, x1, _ = c.box
        y = y0 if y is None else y
        center = c.theme.layout == "center" or c.vertical
        dy = int((1 - p) * c.px(28))
        num, size, badge_w, f, lines = self._heading_layout()
        f_badge = c.font("bold", size * 0.62)
        lh = c.line_h(f)
        block_w = max(int(f.getlength(ln)) for ln in lines) + badge_w
        bx = x0 + ((x1 - x0) - block_w) // 2 if center else x0
        if num:
            bh = int(size * 1.15)
            by = y + dy + (lh - bh) // 2
            d.rounded_rectangle((bx, by, bx + bh, by + bh), radius=bh // 3,
                                fill=rgba(c.theme.accent, p))
            tw = f_badge.getlength(num)
            a, ds = f_badge.getmetrics()
            d.text((bx + (bh - tw) / 2, by + (bh - (a + ds)) / 2), num, font=f_badge,
                   fill=rgba(c.theme.bg_top, p))
        for i, ln in enumerate(lines):
            lx = bx + badge_w
            if center and len(lines) > 1:
                lx = x0 + badge_w + ((x1 - x0 - badge_w) - int(f.getlength(ln))) // 2
            d.text((lx, y + dy + i * lh), ln, font=f, fill=rgba(c.theme.text, p))
        y_end = y + lh * len(lines) + c.px(14)
        # accent underline that grows
        ul = int(c.px(120) * p)
        ux = x0 + ((x1 - x0) - c.px(120)) // 2 if center else bx
        d.rounded_rectangle((ux, y_end, ux + max(ul, 1), y_end + c.px(8)), radius=c.px(4),
                            fill=rgba(c.theme.accent, p))
        return y_end + c.px(44)


class TitleVisual(Visual):
    def state(self, t):
        return (self.appear(t, 0.0), self.appear(t, 0.25), self.appear(t, 0.5))

    def draw(self, st):
        p1, p2, p3 = st
        c = self.c
        img = c.background()
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = c.box
        w = x1 - x0
        center = c.theme.layout == "center" or c.vertical
        title = self.script.title or self.sec.heading
        f, lines = c.fit_text(title, "bold", c.px(104 if not c.vertical else 96), w, 4,
                              min_size=c.px(56))
        lh = c.line_h(f)
        sub = self.sec.heading if self.sec.heading.strip().lower() != title.strip().lower() else ""
        fs = c.font("regular", c.px(44))
        sub_lines = c.wrap(sub, fs, w)[:2] if sub else []
        total = lh * len(lines) + (c.line_h(fs) * len(sub_lines) + c.px(30) if sub_lines else 0)
        y = y0 + ((y1 - y0) - total) // 2 - c.px(30)
        if c.channel:
            fp = c.font("bold", c.px(30))
            pw = int(fp.getlength(c.channel.upper())) + c.px(44)
            px_ = x0 + (w - pw) // 2 if center else x0
            c.pill(d, px_, y - c.px(100), c.channel.upper(), fp, c.theme.accent,
                   c.theme.bg_top, p1)
        dy = int((1 - p2) * c.px(40))
        c.text_block(d, x0, y + dy, lines, f, c.theme.text, p2,
                     "center" if center else "left", w)
        y += lh * len(lines) + c.px(30)
        if sub_lines:
            c.text_block(d, x0, y + int((1 - p3) * c.px(30)), sub_lines, fs, c.theme.muted, p3,
                         "center" if center else "left", w)
        return c.finish(img)


class StepsVisual(Visual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        n = len(self.sec.bullets)
        span = max(self.dur * 0.7 - 0.6, 0.3)
        self.delays = [0.6 + i * (span / max(n, 1)) for i in range(n)]
        self._layout = None

    def state(self, t):
        return (self.appear(t, 0.0), *[self.appear(t, dl) for dl in self.delays],
                self.appear(t, 0.4) if not self.sec.bullets else 1.0)

    def layout(self):
        """Card sizes (computed once): font, icon, pad, card width/x, wrapped lines, heights."""
        if self._layout:
            return self._layout
        c = self.c
        x0, y0, x1, y1 = c.box
        avail = (y1 - y0) - self.heading_height()
        size = c.px(46 if not c.vertical else 50)
        center = c.theme.layout == "center" and not c.vertical
        card_w = int((x1 - x0) * (0.78 if center else 1.0))
        cx0 = x0 + ((x1 - x0) - card_w) // 2 if center else x0
        gap = c.px(22)
        while True:
            f = c.font("regular", size)
            icon = int(size * 1.05)
            pad = c.px(22)
            wrapped = [c.wrap(b, f, card_w - icon - 3 * pad)[:2] for b in self.sec.bullets]
            heights = [max(icon, c.line_h(f) * len(ls)) + 2 * pad for ls in wrapped]
            total = sum(heights) + gap * (len(heights) - 1)
            if total <= avail or size < c.px(28):
                break
            size *= 0.9
        self._layout = (f, icon, pad, card_w, cx0, gap, wrapped, heights, total)
        return self._layout

    def draw(self, st):
        ph, *pb, pq = st
        c = self.c
        img = c.background()
        d = ImageDraw.Draw(img, "RGBA")
        if not self.sec.bullets:
            return c.finish(self._quote(img, d, ph, pq))
        f, icon, pad, card_w, cx0, gap, wrapped, heights, total = self.layout()
        y = self.heading(d, ph, self.top_for(self.heading_height() + total))
        for lines, h, p in zip(wrapped, heights, pb):
            if p <= 0:
                y += h + gap
                continue
            dx = int((1 - p) * c.px(60))
            box = (cx0 + dx, y, cx0 + card_w + dx, y + h)
            d.rounded_rectangle(box, radius=c.px(22), fill=rgba(c.theme.card, 0.92 * p))
            d.rounded_rectangle((box[0], y, box[0] + c.px(8), y + h), radius=c.px(4),
                                fill=rgba(c.theme.accent, p))
            ix, iy = box[0] + pad + c.px(6), y + (h - icon) // 2
            d.ellipse((ix, iy, ix + icon, iy + icon), fill=rgba(c.theme.accent, 0.20 * p))
            m = icon  # check mark
            d.line((ix + m * 0.28, iy + m * 0.52, ix + m * 0.44, iy + m * 0.68, ix + m * 0.74,
                    iy + m * 0.34), fill=rgba(c.theme.accent, p), width=max(3, c.px(6)),
                   joint="curve")
            ty = y + (h - c.line_h(f) * len(lines)) // 2
            c.text_block(d, ix + icon + pad, ty, lines, f, c.theme.text, p)
            y += h + gap
        return c.finish(img)

    def _quote(self, img, d, ph, p):
        c = self.c
        x0, _, x1, _ = c.box
        text = first_sentence(self.sec.narration)
        f, lines = c.fit_text(text or " ", "regular", c.px(52), (x1 - x0) - c.px(100), 5,
                              min_size=c.px(32))
        h = c.line_h(f) * len(lines) + c.px(80)
        y = self.heading(d, ph, self.top_for(self.heading_height() + h))
        if not text or p <= 0:
            return img
        dy = int((1 - p) * c.px(30))
        d.rounded_rectangle((x0, y + dy, x1, y + h + dy), radius=c.px(26),
                            fill=rgba(c.theme.card, 0.9 * p))
        d.rounded_rectangle((x0, y + dy, x0 + c.px(10), y + h + dy), radius=c.px(5),
                            fill=rgba(c.theme.accent2, p))
        c.text_block(d, x0 + c.px(50), y + c.px(40) + dy, lines, f, c.theme.text, p)
        return img


def wrap_code(text: str, cols: int) -> list[str]:
    """Split a long command into rows, preferring to break after a space."""
    rows = []
    while len(text) > cols:
        cut = text.rfind(" ", 0, cols + 1)
        if cut < cols * 0.5:
            cut = cols
        else:
            cut += 1  # keep the space at the end of the row
        rows.append(text[:cut])
        text = text[cut:]
    rows.append(text)
    return rows


class TerminalVisual(Visual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        code = self.sec.code
        self.shell = "PowerShell" if any(
            re.search(r"\b(Get|Set|New|Remove|Start|Stop)-\w+|\$env:|\.exe\b", ln, re.I)
            for ln in code) else "Terminal"
        if any(re.match(r"^\s*(sudo|brew|apt|ls|cd|defaults)\b", ln) for ln in code):
            self.shell = "Terminal"
        self.prompt = "PS C:\\> " if self.shell == "PowerShell" else "$ "
        total = sum(len(ln) for ln in code)
        budget = max(self.dur * 0.6 - 0.8, 0.5)
        self.cps = min(max(total / budget, 14.0), 45.0)
        self.start = 0.8
        c = self.c
        x0, y0, x1, y1 = c.box
        self.font = c.font("mono", c.px(38 if not c.vertical else 34))
        self.lh = c.line_h(self.font)
        self.char_w = max(self.font.getlength("M"), 1)
        cols = max(int(((x1 - x0) - c.px(80)) // self.char_w), 10)
        self.bar_h = c.px(64)
        # rows for the full text of every command (layout doesn't move while typing)
        self.rows = [wrap_code(self.prompt + ln, cols) for ln in code]
        n_rows = sum(len(r) for r in self.rows)
        avail = (y1 - y0) - self.heading_height()
        body = n_rows * self.lh + c.px(10) * (len(self.rows) - 1)
        self.win_h = int(min(max(self.bar_h + c.px(70) + body, avail * 0.45), avail))
        self.top = self.top_for(self.heading_height() + self.win_h)

    def state(self, t):
        typed = int(max(t - self.start, 0) * self.cps)
        total = sum(len(ln) for ln in self.sec.code)
        cursor = int(t * 2) % 2 == 0 if typed >= total else True
        return (self.appear(t, 0.0), self.appear(t, 0.3), min(typed, total), cursor)

    def draw(self, st):
        ph, pw, typed, cursor = st
        c = self.c
        img = c.background()
        d = ImageDraw.Draw(img, "RGBA")
        x0, _, x1, _ = c.box
        y = self.heading(d, ph, self.top)
        if pw <= 0:
            return c.finish(img)
        dy = int((1 - pw) * c.px(40))
        win = (x0, y + dy, x1, y + self.win_h + dy)
        d.rounded_rectangle((win[0] + c.px(10), win[1] + c.px(14), win[2] + c.px(10),
                             win[3] + c.px(14)), radius=c.px(22), fill=(0, 0, 0, int(90 * pw)))
        d.rounded_rectangle(win, radius=c.px(22), fill=rgba(c.theme.terminal_bg, 0.97 * pw))
        bar_h = self.bar_h
        d.rounded_rectangle((win[0], win[1], win[2], win[1] + bar_h), radius=c.px(22),
                            fill=rgba("#FFFFFF", 0.07 * pw))
        d.rectangle((win[0], win[1] + bar_h - c.px(22), win[2], win[1] + bar_h),
                    fill=rgba(c.theme.terminal_bg, 0.97 * pw))
        d.rectangle((win[0], win[1] + bar_h - c.px(22), win[2], win[1] + bar_h),
                    fill=rgba("#FFFFFF", 0.07 * pw))
        for i, col in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            cx = win[0] + c.px(36) + i * c.px(34)
            cy = win[1] + bar_h // 2
            r = c.px(10)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgba(col, pw))
        ft = c.font("bold", c.px(28))
        d.text((win[0] + c.px(150), win[1] + (bar_h - c.line_h(ft)) // 2 + c.px(4)), self.shell,
               font=ft, fill=rgba("#BBBBBB", pw))
        f, lh = self.font, self.lh
        tx, ty = win[0] + c.px(40), win[1] + bar_h + c.px(30)
        plen = len(self.prompt)
        left = typed
        last_x, last_y = tx, ty
        for ln, rows in zip(self.sec.code, self.rows):
            visible = plen + min(max(left, 0), len(ln))   # prompt is always visible
            left -= len(ln)
            pos = 0
            for row in rows:
                part = row[:max(visible - pos, 0)]
                if not part and pos > 0:
                    break
                if ty + lh > win[3] - c.px(10):
                    break
                if pos == 0:
                    d.text((tx, ty), part[:plen], font=f, fill=rgba(c.theme.accent2, pw))
                    d.text((tx + f.getlength(part[:plen]), ty), part[plen:], font=f,
                           fill=rgba("#F2F2F2", pw))
                else:
                    d.text((tx, ty), part, font=f, fill=rgba("#F2F2F2", pw))
                last_x, last_y = tx + f.getlength(part), ty
                pos += len(row)
                ty += lh
            if left < 0:
                break
            ty += c.px(10)
        if cursor:
            d.rectangle((last_x + c.px(4), last_y + c.px(6), last_x + c.px(4) + self.char_w * 0.6,
                         last_y + lh - c.px(8)), fill=rgba(c.theme.accent, pw))
        return c.finish(img)


_WARN = re.compile(r"\b(warning|careful|caution|backup|back up|risk|danger|before you)\b", re.I)


class TipVisual(Visual):
    def state(self, t):
        return (self.appear(t, 0.0), self.appear(t, 0.3), self.appear(t, 0.6))

    def draw(self, st):
        p1, p2, p3 = st
        c = self.c
        img = c.background()
        d = ImageDraw.Draw(img, "RGBA")
        x0, _, x1, _ = c.box
        warn = bool(_WARN.search(self.sec.heading + " " + self.sec.narration[:200]))
        label = "WARNING" if warn else "PRO TIP"
        color = "#F59E0B" if warn else c.theme.accent2
        fb = c.font("bold", c.px(34))
        center = c.theme.layout == "center" or c.vertical
        body = "  •  ".join(self.sec.bullets) if self.sec.bullets else first_sentence(
            self.sec.narration, 26)
        f, lines = c.fit_text(body, "regular", c.px(48), x1 - x0 - c.px(80), 5,
                              min_size=c.px(30))
        h = c.line_h(f) * len(lines) + c.px(70)
        pill_h = c.px(100)
        top = self.top_for(pill_h + self.heading_height() + h)
        pw = int(fb.getlength(label)) + c.px(44)
        lx = x0 + ((x1 - x0) - pw) // 2 if center else x0
        c.pill(d, lx, top, label, fb, color, "#111111", p1)
        y = self.heading(d, p2, top + pill_h)
        dy = int((1 - p3) * c.px(30))
        d.rounded_rectangle((x0, y + dy, x1, y + h + dy), radius=c.px(24),
                            fill=rgba(c.theme.card, 0.9 * p3), outline=rgba(color, 0.8 * p3),
                            width=max(2, c.px(3)))
        c.text_block(d, x0 + c.px(40), y + c.px(35) + dy, lines, f, c.theme.text, p3,
                     "center" if center else "left", x1 - x0 - c.px(80))
        return c.finish(img)


class OutroVisual(Visual):
    def state(self, t):
        return (self.appear(t, 0.0), self.appear(t, 0.35), self.appear(t, 0.7))

    def draw(self, st):
        p1, p2, p3 = st
        c = self.c
        img = c.background()
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = c.box
        w = x1 - x0
        f, lines = c.fit_text(self.sec.heading, "bold", c.px(84), w, 3, min_size=c.px(48))
        lh = c.line_h(f)
        y = y0 + int((y1 - y0) * 0.18)
        c.text_block(d, x0, y + int((1 - p1) * c.px(30)), lines, f, c.theme.text, p1,
                     "center", w)
        y += lh * len(lines) + c.px(40)
        if self.sec.bullets:
            fb = c.font("regular", c.px(40))
            recap = "  •  ".join(self.sec.bullets)
            rl = c.wrap(recap, fb, w)[:3]
            c.text_block(d, x0, y, rl, fb, c.theme.muted, p2, "center", w)
            y += c.line_h(fb) * len(rl) + c.px(40)
        fp = c.font("bold", c.px(42))
        label = "SUBSCRIBE" + (f"  ·  {c.channel}" if c.channel else "")
        pw = int(fp.getlength(label)) + c.px(70)
        c.pill(d, x0 + (w - pw) // 2, y + int((1 - p3) * c.px(20)), label, fp, "#FF0033",
               "#FFFFFF", p3, (c.px(35), c.px(18)))
        return c.finish(img)


# ===================================================================== factory

def make_visual(canvas: Canvas, section: Section, duration: float, script: Script,
                shots_dir=None) -> Visual:
    if section.visual == "shot":
        from .shots import ShotVisual
        return ShotVisual(canvas, section, duration, script, shots_dir)
    cls = {
        "title": TitleVisual,
        "steps": StepsVisual,
        "terminal": TerminalVisual,
        "tip": TipVisual,
        "outro": OutroVisual,
    }.get(section.visual, StepsVisual)
    return cls(canvas, section, duration, script)


class FrameSource:
    """Turns visuals into raw RGB frames, with a thin progress bar on top."""

    def __init__(self, canvas: Canvas, fps: int, total: float):
        self.c = canvas
        self.fps = fps
        self.total = max(total, 0.01)
        self.bar_h = max(canvas.px(8), 4)
        self.bar_color = np.array(hex_rgb(canvas.theme.accent), np.uint8)

    def frames(self, visual: Visual, n_frames: int, t_offset: float):
        cache_key, cache_arr = None, None
        last_bar, last_bytes = -1, b""
        for k in range(n_frames):
            t = k / self.fps
            key = visual.state(t)
            if key != cache_key:
                cache_key = key
                cache_arr = np.asarray(visual.draw(key), dtype=np.uint8)
                last_bar = -1
            bar = int(self.c.W * min((t_offset + t) / self.total, 1.0))
            if bar != last_bar:
                arr = cache_arr.copy()
                arr[: self.bar_h, :bar] = self.bar_color
                arr[: self.bar_h, bar:] = (arr[: self.bar_h, bar:] * 0.55).astype(np.uint8)
                last_bar, last_bytes = bar, arr.tobytes()
            yield last_bytes

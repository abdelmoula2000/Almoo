"""Screenshot visual: smooth zoom/pan toward a focus point, optional highlight box."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .script import Script, Section, Shot
from .slides import Canvas, Visual, ease_in_out, rgba


class ShotVisual(Visual):
    def __init__(self, canvas: Canvas, section: Section, duration: float, script: Script,
                 shots_dir: Path | None):
        super().__init__(canvas, section, duration, script)
        shot = section.shot
        if shot is None:
            raise ValueError(f"Section '{section.heading}' has visual shot but no file.")
        path = Path(shots_dir or ".") / shot.file
        if not path.exists():
            raise FileNotFoundError(
                f"Screenshot not found: {path}\nPut it in the project's shots/ folder.")
        if shot.box:
            # the highlight box must stay visible: zoom toward its center, never past it
            bx, by, bw, bh = shot.box
            max_zoom = min(1 / (bw + 0.08), 1 / (bh + 0.08))
            shot = Shot(shot.file, (bx + bw / 2, by + bh / 2), max(min(shot.zoom, max_zoom), 1.0),
                        shot.box)
        self.shot = shot
        self.src = Image.open(path).convert("RGB")
        c = canvas
        x0, y0, x1, y1 = c.box
        if not c.vertical:
            x0, x1 = int(c.W * 0.05), int(c.W * 0.95)
        label_h = c.px(110)
        ax0, ay0, ax1, ay1 = x0, y0 + label_h, x1, y1
        sw, sh = self.src.size
        scale = min((ax1 - ax0) / sw, (ay1 - ay0) / sh)
        self.dw, self.dh = max(int(sw * scale), 2), max(int(sh * scale), 2)
        self.dx = ax0 + ((ax1 - ax0) - self.dw) // 2
        self.dy = ay0 + ((ay1 - ay0) - self.dh) // 2
        radius = c.px(22)
        self.mask = Image.new("L", (self.dw, self.dh), 0)
        ImageDraw.Draw(self.mask).rounded_rectangle((0, 0, self.dw - 1, self.dh - 1),
                                                    radius=radius, fill=255)
        pad = c.px(40)
        shadow = Image.new("RGBA", (self.dw + 2 * pad, self.dh + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (pad, pad + c.px(12), pad + self.dw, pad + self.dh + c.px(12)), radius=radius,
            fill=(0, 0, 0, 140))
        self.shadow = shadow.filter(ImageFilter.GaussianBlur(c.px(18)))
        self.shadow_pad = pad
        self.z_start = 0.5
        self.z_dur = min(max(self.dur * 0.45, 1.2), 4.0)

    def view(self, p: float) -> tuple[float, float, float, float]:
        """Crop window on the source image for zoom progress p (0..1)."""
        sw, sh = self.src.size
        z = 1 + (self.shot.zoom - 1) * p
        cw, ch = sw / z, sh / z
        fx, fy = self.shot.focus
        cx = sw / 2 + (fx * sw - sw / 2) * p
        cy = sh / 2 + (fy * sh - sh / 2) * p
        left = min(max(cx - cw / 2, 0), sw - cw)
        top = min(max(cy - ch / 2, 0), sh - ch)
        return left, top, left + cw, top + ch

    def state(self, t):
        zp = round(ease_in_out((t - self.z_start) / self.z_dur), 3)
        box_p = self.appear(t, self.z_start + self.z_dur) if self.shot.box else 0.0
        return (self.appear(t, 0.0), zp, box_p)

    def draw(self, st):
        pl, zp, pb = st
        c = self.c
        img = c.background()
        img.paste(self.shadow, (self.dx - self.shadow_pad, self.dy - self.shadow_pad), self.shadow)
        crop = self.view(zp)
        frame = self.src.resize((self.dw, self.dh), Image.BICUBIC, box=crop)
        img.paste(frame, (self.dx, self.dy), self.mask)
        d = ImageDraw.Draw(img, "RGBA")
        d.rounded_rectangle((self.dx, self.dy, self.dx + self.dw - 1, self.dy + self.dh - 1),
                            radius=c.px(22), outline=rgba(c.theme.muted, 0.35),
                            width=max(1, c.px(2)))
        if self.shot.box and pb > 0:
            bx, by, bw, bh = self.shot.box
            sw, sh = self.src.size
            l, t, r, b = crop
            kx, ky = self.dw / (r - l), self.dh / (b - t)
            x0 = self.dx + (bx * sw - l) * kx
            y0 = self.dy + (by * sh - t) * ky
            x1 = self.dx + ((bx + bw) * sw - l) * kx
            y1 = self.dy + ((by + bh) * sh - t) * ky
            grow = (1 - pb) * c.px(30)
            m = c.px(6)  # keep the box on the screenshot card
            x0, x1 = max(x0 - grow, self.dx - m), min(x1 + grow, self.dx + self.dw + m)
            y0, y1 = max(y0 - grow, self.dy - m), min(y1 + grow, self.dy + self.dh + m)
            d.rounded_rectangle((x0, y0, x1, y1), radius=c.px(14),
                                outline=rgba(c.theme.accent, pb), width=max(3, c.px(7)))
        # heading label
        x0b, y0b, x1b, _ = c.box
        f = c.font("bold", c.px(52 if not c.vertical else 58))
        lines = c.wrap(self.sec.heading, f, x1b - x0b)[:2]
        lh = c.line_h(f)
        center = c.theme.layout == "center" or c.vertical
        ty = y0b - (lh * (len(lines) - 1)) // 2
        c.text_block(d, x0b if center else self.dx, ty + int((1 - pl) * c.px(20)), lines, f,
                     c.theme.text, pl, "center" if center else "left", x1b - x0b)
        return c.finish(img)

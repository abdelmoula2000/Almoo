"""Visual themes. A different theme per video keeps the channel from looking mass-produced."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg_top: str
    bg_bottom: str
    card: str
    text: str
    muted: str
    accent: str
    accent2: str
    terminal_bg: str
    layout: str = "left"   # left | center
    deco: str = "dots"     # dots | circles | grid | lines

    def to_dict(self) -> dict:
        return asdict(self)


THEMES: list[Theme] = [
    Theme("midnight", "#0B1020", "#1B2340", "#1E2747", "#F5F7FF", "#A9B3D6", "#4F8CFF",
          "#22D3EE", "#0A0E1A", "left", "dots"),
    Theme("emerald", "#05201A", "#0E3B30", "#123F35", "#F0FFF8", "#9BD3C0", "#2EE6A0",
          "#F5D547", "#03140F", "center", "circles"),
    Theme("sunset", "#2A0F1F", "#4A1730", "#4E1D36", "#FFF4F0", "#F0B9C6", "#FF7A59",
          "#FFC857", "#170811", "left", "lines"),
    Theme("graphite", "#141414", "#262626", "#2C2C2C", "#FAFAFA", "#B5B5B5", "#FACC15",
          "#60A5FA", "#0B0B0B", "center", "grid"),
    Theme("ocean", "#031C2E", "#073B5C", "#0B4466", "#EFF9FF", "#9CCBE6", "#38BDF8",
          "#F472B6", "#02111C", "left", "circles"),
    Theme("violet", "#140B2E", "#2A1657", "#2E1A5E", "#F7F2FF", "#C5B4F0", "#A78BFA",
          "#34D399", "#0B0619", "center", "dots"),
    Theme("paper", "#F4F1EA", "#E6E0D2", "#FFFFFF", "#1A1A1A", "#5C5C5C", "#E4572E",
          "#2364AA", "#1E1E1E", "left", "grid"),
    Theme("mint", "#EAF7F1", "#CDEBDD", "#FFFFFF", "#0F2A20", "#4D6B5F", "#0E9F6E",
          "#7C3AED", "#10231B", "center", "lines"),
]

BY_NAME = {t.name: t for t in THEMES}


def pick_theme(recent: list[str], seed: str | None = None, avoid_last: int = 3) -> Theme:
    """Pick a theme not used by the last `avoid_last` videos."""
    blocked = set(recent[-avoid_last:])
    options = [t for t in THEMES if t.name not in blocked] or THEMES
    return random.Random(seed).choice(options)


def get_theme(name: str | None) -> Theme:
    if name and name in BY_NAME:
        return BY_NAME[name]
    return THEMES[0]


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

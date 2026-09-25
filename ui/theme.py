"""Design tokens (SPEC section 3) and font loading."""

import os

import pygame

W, H = 480, 320

BG = (0x0E, 0x0F, 0x11)
PANEL = (0x17, 0x19, 0x1C)
CONTROL = (0x24, 0x27, 0x2B)
CONTROL_2 = (0x2C, 0x30, 0x35)
BORDER = (0x34, 0x38, 0x3D)
DIVIDER = (0x1F, 0x22, 0x26)
TEXT = (0xE8, 0xE6, 0xE1)
TEXT_MUTED = (0x9A, 0x9E, 0xA6)
TEXT_SOFT = (0xB9, 0xBC, 0xC2)
SEGMENT_TEXT = (0xC9, 0xCC, 0xD1)
ACCENT = (0xFF, 0xB0, 0x20)
ON_ACCENT = (0x14, 0x14, 0x13)
MIN_MARKER = (0x5C, 0xC8, 0xFF)
MAX_MARKER = (0xFF, 0xFF, 0xFF)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SPOT_PILL = (14, 15, 17, 204)       # rgba(14,15,17,.8)
SAVE_BG = (23, 25, 28, 235)         # rgba(23,25,28,.92)


def lighten(color, k=0.14):
    """Pressed-state colour: blend towards white."""
    return tuple(int(v + (255 - v) * k) for v in color[:3])


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIRS = [os.path.join(_ROOT, "fonts"), "/usr/share/fonts/truetype/dejavu"]
FONT_FILES = {
    "cond": "DejaVuSansCondensed.ttf",
    "cond_bold": "DejaVuSansCondensed-Bold.ttf",
    "mono": "DejaVuSansMono.ttf",
    "mono_bold": "DejaVuSansMono-Bold.ttf",
}


class Fonts:
    """fonts(kind, px) -> cached pygame Font. kind: cond | cond_bold | mono | mono_bold."""

    def __init__(self, overrides=None):
        overrides = overrides or {}
        self._paths = {}
        for kind, name in FONT_FILES.items():
            candidates = [overrides[kind]] if kind in overrides else [os.path.join(d, name) for d in FONT_DIRS]
            path = next((p for p in candidates if os.path.exists(p)), None)
            if path is None:
                raise SystemExit(f"font {kind} not found (looked in {candidates}); "
                                 f"install fonts-dejavu-core or set fonts.{kind} in the config")
            self._paths[kind] = path
        self._cache = {}

    def __call__(self, kind, px):
        key = (kind, px)
        font = self._cache.get(key)
        if font is None:
            font = self._cache[key] = pygame.font.Font(self._paths[kind], px)
        return font

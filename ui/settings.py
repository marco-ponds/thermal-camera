"""Settings (SPEC 4.2): 2-column grid of segmented controls and an emissivity stepper."""

import pygame

from palettes import NAMES

from . import theme as T
from .widgets import HEADER_H, header, header_rects, segment_rects, segmented, stepper, stepper_rects, text_mid

COL_X = (12, 246)
COL_W = 222
ROW_Y = (HEADER_H + 14, HEADER_H + 14 + 69 + 14, HEADER_H + 14 + 2 * (69 + 14))
LABEL_H, LABEL_GAP, CONTROL_H = 17, 4, 48
RATES = [2, 4, 8, 16]


def _control_rect(col, row):
    return pygame.Rect(COL_X[col], ROW_Y[row] + LABEL_H + LABEL_GAP, COL_W, CONTROL_H)


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self._back, self._sensor = header_rects(app.fonts, "LIVE", "SENSOR")
        # (key, col, row, label, options, font kind, size)
        self._segments = [
            ("palette", 0, 0, "PALETTE", ["IRON", "RAINBOW", "GREY"], "cond_bold", 15),
            ("range_mode", 1, 0, "TEMPERATURE RANGE", ["AUTO", "LOCK"], "cond_bold", 17),
            ("refresh_hz", 0, 1, "SENSOR RATE", [f"{r}Hz" for r in RATES], "mono_bold", 15),
            ("units", 1, 1, "UNITS", ["°C", "°F"], "mono_bold", 15),
            ("smoothing", 1, 2, "SMOOTHING", ["OFF", "ON"], "cond_bold", 17),
        ]

    def _selected(self, key):
        cfg = self.app.cfg
        if key == "palette":
            return NAMES.index(cfg["palette"])
        if key == "range_mode":
            return 0 if cfg["range_mode"] == "auto" else 1
        if key == "refresh_hz":
            return RATES.index(cfg["refresh_hz"]) if cfg["refresh_hz"] in RATES else None
        if key == "units":
            return 0 if cfg["units"] == "C" else 1
        if key == "smoothing":
            return 1 if cfg["smoothing"] else 0
        raise KeyError(key)

    def _choose(self, key, i):
        app = self.app
        if key == "palette":
            app.set(palette=NAMES[i])
        elif key == "range_mode":
            app.set_range_mode("auto" if i == 0 else "lock")
        elif key == "refresh_hz":
            app.set(refresh_hz=RATES[i])
        elif key == "units":
            app.set(units="C" if i == 0 else "F")
        elif key == "smoothing":
            app.set(smoothing=i == 1)

    def _step(self, delta):
        e = round(min(1.0, max(0.10, self.app.cfg["emissivity"] + delta)), 2)
        self.app.set(emissivity=e)

    def targets(self):
        app = self.app
        t = [("left", self._back, lambda pos: app.go("live")),
             ("right", self._sensor, lambda pos: app.go("info"))]
        for key, col, row, _label, options, _kind, _size in self._segments:
            for i, r in enumerate(segment_rects(_control_rect(col, row), len(options))):
                t.append(((key, i), r, lambda pos, key=key, i=i: self._choose(key, i)))
        minus, plus = stepper_rects(_control_rect(0, 2))
        t += [(("emissivity", "minus"), minus, lambda pos: self._step(-0.01)),
              (("emissivity", "plus"), plus, lambda pos: self._step(+0.01))]
        return t

    def draw(self, c, pressed):
        fonts = self.app.fonts
        c.fill(T.BG)
        header(c, fonts, "SETTINGS", "LIVE", "SENSOR", "info", pressed if pressed in ("left", "right") else None)
        label_font = fonts("cond_bold", 14)
        for key, col, row, label, options, kind, size in self._segments:
            self._label(c, label_font, label, col, row)
            p = pressed[1] if isinstance(pressed, tuple) and pressed[0] == key else None
            segmented(c, fonts, _control_rect(col, row), options, self._selected(key), kind, size, p)

        hz = self.app.cfg["refresh_hz"]
        text_mid(c, fonts("mono", 12), f"≈{hz // 2} fps", T.TEXT_SOFT, COL_X[0] + COL_W, ROW_Y[1] + 8, "right")

        self._label(c, label_font, "EMISSIVITY", 0, 2)
        p = pressed[1] if isinstance(pressed, tuple) and pressed[0] == "emissivity" else None
        stepper(c, fonts, _control_rect(0, 2), f"{self.app.cfg['emissivity']:.2f}", p)

    @staticmethod
    def _label(c, font, text, col, row):
        text_mid(c, font, text, T.TEXT_MUTED, COL_X[col], ROW_Y[row] + 8, spacing=14 * 0.08)

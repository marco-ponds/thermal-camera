"""Resistive touchscreen (STMPE610) via evdev, plus 3-point affine calibration."""

import os
import sys
import time

import numpy as np
import pygame

from ui import theme as T
from ui.widgets import text_mid

CAL_TARGETS = [(40, 40), (440, 60), (240, 280)]


class TouchInput:
    """Yields ("down" | "move" | "up", raw_x, raw_y) from an evdev touchscreen.

    Contacts lighter than `min_pressure` (when the driver reports pressure) are ignored.
    """

    EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
    SYN_REPORT, BTN_TOUCH = 0, 330
    ABS_X, ABS_Y, ABS_PRESSURE = 0, 1, 24

    def __init__(self, device, min_pressure=0):
        self.dev = device
        self.min_pressure = min_pressure
        self.x = self.y = None
        self.pressure = None
        self.down = False
        self._pending = None

    @classmethod
    def open(cls, path=None, min_pressure=0):
        import evdev
        paths = [path] if path else ["/dev/input/touchscreen"] + evdev.list_devices()
        for p in paths:
            if not os.path.exists(p):
                continue
            dev = evdev.InputDevice(p)
            caps = dev.capabilities(absinfo=False)
            if cls.BTN_TOUCH in caps.get(cls.EV_KEY, []) and {cls.ABS_X, cls.ABS_Y} <= set(caps.get(cls.EV_ABS, [])):
                print(f"touch: {p} ({dev.name})", file=sys.stderr)
                return cls(dev, min_pressure)
        if path:
            raise SystemExit(f"{path} is not a touchscreen")
        print("touch: no touchscreen found, running view-only", file=sys.stderr)
        return None

    def _light(self):
        return self.min_pressure > 0 and self.pressure is not None and self.pressure < self.min_pressure

    def poll(self):
        try:
            events = list(self.dev.read())
        except BlockingIOError:
            return []
        out = []
        for e in events:
            if e.type == self.EV_ABS:
                if e.code == self.ABS_X:
                    self.x = e.value
                elif e.code == self.ABS_Y:
                    self.y = e.value
                elif e.code == self.ABS_PRESSURE:
                    self.pressure = e.value
            elif e.type == self.EV_KEY and e.code == self.BTN_TOUCH:
                self._pending = "down" if e.value else "up"
            elif e.type == self.EV_SYN and e.code == self.SYN_REPORT:
                if self.x is not None and self.y is not None:
                    if self._pending == "down" and not self._light():
                        self.down = True
                        out.append(("down", self.x, self.y))
                    elif self._pending == "up" and self.down:
                        self.down = False
                        out.append(("up", self.x, self.y))
                    elif self._pending is None and self.down and not self._light():
                        out.append(("move", self.x, self.y))
                self._pending = None
        return out


class Calibration:
    """Affine map from raw touch to screen: x = a*rx + b*ry + c, y = d*rx + e*ry + f.

    Three points fix all six numbers, which covers swapped, inverted and skewed axes.
    """

    def __init__(self, coeffs):
        self.coeffs = [float(v) for v in coeffs]

    def map(self, rx, ry):
        a, b, c, d, e, f = self.coeffs
        return int(round(a * rx + b * ry + c)), int(round(d * rx + e * ry + f))

    @classmethod
    def solve(cls, targets, raws):
        m = np.array([[rx, ry, 1.0] for rx, ry in raws])
        if abs(np.linalg.det(m)) < 1e3:
            raise ValueError("taps too close together or in a line")
        xs = np.linalg.solve(m, [t[0] for t in targets])
        ys = np.linalg.solve(m, [t[1] for t in targets])
        return cls([*xs, *ys])


def _wait_for_tap(touch):
    """Collect raw samples for one contact; return their median."""
    samples = []
    while True:
        for kind, rx, ry in touch.poll():
            if kind in ("down", "move"):
                samples.append((rx, ry))
            elif kind == "up" and samples:
                return tuple(np.median(np.array(samples), axis=0))
        time.sleep(0.02)


def calibrate(display, fonts):
    """Full-screen 3-tap calibration. Returns a Calibration."""
    surf = pygame.Surface((T.W, T.H))
    title, small = fonts("cond_bold", 18), fonts("cond", 15)
    while True:
        raws = []
        for i, (tx, ty) in enumerate(CAL_TARGETS):
            surf.fill(T.BG)
            for (x0, y0, x1, y1) in ((tx - 16, ty, tx - 5, ty), (tx + 5, ty, tx + 16, ty),
                                     (tx, ty - 16, tx, ty - 5), (tx, ty + 5, tx, ty + 16)):
                pygame.draw.line(surf, T.ACCENT, (x0, y0), (x1, y1), 2)
            pygame.draw.circle(surf, T.ACCENT, (tx, ty), 3)
            text_mid(surf, title, "TOUCH CALIBRATION", T.TEXT, T.W // 2, 140, "center", spacing=1.4)
            text_mid(surf, small, f"Tap the centre of the cross firmly ({i + 1}/3)", T.TEXT_SOFT,
                     T.W // 2, 166, "center")
            display.present(surf)
            raws.append(_wait_for_tap(display.touch))
            time.sleep(0.25)
        try:
            return Calibration.solve(CAL_TARGETS, raws)
        except ValueError as e:
            surf.fill(T.BG)
            text_mid(surf, title, f"Calibration failed: {e}", T.ACCENT, T.W // 2, 160, "center")
            display.present(surf)
            time.sleep(1.5)

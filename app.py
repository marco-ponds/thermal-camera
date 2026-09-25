"""Screen state machine (LIVE | SETTINGS | INFO), tap handling, settings, hold and snapshots."""

import datetime
import os
import subprocess
import time

import numpy as np
import pygame

from ui import theme as T
from ui.info import InfoScreen
from ui.live import SAVED_S, LiveScreen
from ui.settings import SettingsScreen

UI_HZ = 20
DEBOUNCE_S = 0.15
TAP_SLOP = 12            # px a resistive tap may wander and still count for its button
MIN_AUTO_SPAN = 0.5      # degC; stops a uniform wall dividing by ~zero
SNAP_DIR = os.path.expanduser("~/thermalcam/snapshots")


def clock_trusted():
    """No RTC on a Pi 2: only trust the clock once NTP has synced (non-systemd hosts: assume yes)."""
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return True
    return out.stdout.strip() == "yes"


def snapshot_base(directory, trusted=None):
    os.makedirs(directory, exist_ok=True)
    if trusted if trusted is not None else clock_trusted():
        base = os.path.join(directory, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        n, candidate = 2, base
        while os.path.exists(candidate + ".png"):
            candidate, n = f"{base}-{n}", n + 1
        return candidate
    n = 1
    while os.path.exists(os.path.join(directory, f"snap-{n:04d}.png")):
        n += 1
    return os.path.join(directory, f"snap-{n:04d}")


class App:
    def __init__(self, cfg, worker, display, fonts, snap_dir=SNAP_DIR):
        self.cfg, self.worker, self.display, self.fonts = cfg, worker, display, fonts
        self.snap_dir = snap_dir
        self.canvas = pygame.Surface((T.W, T.H))
        self.now = time.monotonic()

        self.frame = None            # latest live frame, oriented for display (degC)
        self.frame_id = -1
        self.hold = False
        self.held = None
        self.shown_version = 0       # bumps whenever the displayed frame changes
        self.saved_until = 0.0

        self.screens = {"live": LiveScreen(self), "settings": SettingsScreen(self), "info": InfoScreen(self)}
        self.screen_name = "live"
        self.dirty = True
        self._contact = None         # raw samples of the current touch
        self._pressed = None         # (id, rect, action) under the finger at touch-down
        self._last_up = -1.0
        self._last_status = None
        self._next_info = 0.0

    # ------------------------------------------------------------------ state helpers
    @property
    def screen(self):
        return self.screens[self.screen_name]

    @property
    def shown(self):
        return self.held if self.hold else self.frame

    def go(self, name):
        self.screen_name = name
        self.dirty = True

    def set(self, **changes):
        self.cfg.update(**changes)
        sensor_side = {k: v for k, v in changes.items() if k in ("refresh_hz", "emissivity")}
        if sensor_side:
            self.worker.configure(**sensor_side)
        self.dirty = True

    def set_range_mode(self, mode):
        if mode == "lock":
            frame = self.shown
            if frame is None:
                return                   # nothing to lock to yet
            lo, hi = self.auto_range(frame)
            self.set(range_mode="lock", locked_min=lo, locked_max=hi)
        else:
            self.set(range_mode="auto")

    def toggle_hold(self):
        self.hold = not self.hold
        self.held = self.frame if self.hold else None
        self.saved_until = 0.0
        self.shown_version += 1
        self.dirty = True

    def save_snapshot(self):
        frame = self.shown
        if frame is None:
            return
        base = snapshot_base(self.snap_dir)
        self.draw()                      # the PNG is the screen exactly as shown
        pygame.image.save(self.canvas, base + ".png")
        np.savetxt(base + "-raw.csv", frame, fmt="%.2f", delimiter=",")
        self.saved_until = time.monotonic() + SAVED_S
        self.dirty = True
        return base

    # ------------------------------------------------------------------ temperatures
    @staticmethod
    def auto_range(frame):
        lo, hi = float(frame.min()), float(frame.max())
        if hi - lo < MIN_AUTO_SPAN:
            mid = (lo + hi) / 2
            lo, hi = mid - MIN_AUTO_SPAN / 2, mid + MIN_AUTO_SPAN / 2
        return lo, hi

    def scale_range(self, frame):
        cfg = self.cfg
        if cfg["range_mode"] == "lock" and cfg["locked_min"] is not None:
            return cfg["locked_min"], cfg["locked_max"]
        return self.auto_range(frame)

    def to_units(self, c):
        return c * 9 / 5 + 32 if self.cfg["units"] == "F" else c

    def fmt_temp(self, c, digits=1, unit=None, spaced=False):
        """unit=None -> "24.6°", unit=True -> "24.6°C", unit=False -> "24.6", spaced -> "24.6 °C"."""
        s = f"{self.to_units(c):.{digits}f}"
        letter = "°" + self.cfg["units"]
        if spaced:
            return f"{s} {letter}"
        if unit is None:
            return s + "°"
        return s + letter if unit else s

    # ------------------------------------------------------------------ input
    def _hit(self, pos):
        for target in self.screen.targets():
            if target[1].collidepoint(pos):
                return target
        return None

    def on_event(self, ev):
        kind = ev[0]
        if kind == "quit":
            raise SystemExit(0)
        if kind == "key":
            return self._on_key(ev[1])
        pos = (ev[1], ev[2])
        if kind == "down":
            if self.now - self._last_up < DEBOUNCE_S:
                self._contact = None     # bounce: ignore this whole contact
                return
            self._contact = [pos]
            self._pressed = self._hit(pos)
            self.dirty = True
        elif kind == "move" and self._contact is not None:
            self._contact.append(pos)
        elif kind == "up" and self._contact is not None:
            self._contact.append(pos)
            tap = tuple(int(v) for v in np.median(np.array(self._contact), axis=0))
            pressed, self._pressed, self._contact = self._pressed, None, None
            self._last_up = self.now
            self.dirty = True
            if pressed and pressed[1].inflate(2 * TAP_SLOP, 2 * TAP_SLOP).collidepoint(tap):
                pressed[2](tap)

    def _on_key(self, key):
        """Keyboard shortcuts for --windowed development."""
        name = self.screen_name
        if key == pygame.K_q:
            raise SystemExit(0)
        if key == pygame.K_ESCAPE:
            if name == "live":
                raise SystemExit(0)
            self.go("settings" if name == "info" else "live")
        elif key == pygame.K_h and name == "live":
            self.toggle_hold()
        elif key == pygame.K_s and name == "live" and self.hold:
            self.save_snapshot()
        elif key == pygame.K_m:
            self.go("settings")
        elif key == pygame.K_i:
            self.go("info")

    # ------------------------------------------------------------------ loop
    def _poll_sensor(self):
        fid, raw = self.worker.latest()
        if raw is not None and fid != self.frame_id:
            f = raw
            if self.cfg["flip_h"]:
                f = f[:, ::-1]
            if self.cfg["flip_v"]:
                f = f[::-1, :]
            self.frame, self.frame_id = f, fid
            if not self.hold:
                self.shown_version += 1
                if self.screen_name == "live":
                    self.dirty = True
        status = self.worker.status
        if status != self._last_status:
            self._last_status = status
            self.dirty = True

    def _tick(self):
        if self.screen_name == "info" and self.now >= self._next_info:
            self._next_info = self.now + InfoScreen.REFRESH_S
            self.dirty = True
        if self.saved_until and self.now >= self.saved_until:
            self.saved_until = 0.0
            self.dirty = True

    def draw(self):
        pressed = None
        if self._pressed is not None and self._contact:
            if self._pressed[1].inflate(2 * TAP_SLOP, 2 * TAP_SLOP).collidepoint(self._contact[-1]):
                pressed = self._pressed[0]
        self.screen.draw(self.canvas, pressed)

    def run(self, exit_after=0.0, screenshot=None):
        deadline = time.monotonic() + exit_after if exit_after else None
        period = 1.0 / UI_HZ
        while True:
            self.now = time.monotonic()
            for ev in self.display.poll():
                self.on_event(ev)
            self._poll_sensor()
            self._tick()
            if self.dirty:
                self.dirty = False
                self.draw()
                self.display.present(self.canvas)
            if deadline and self.now > deadline:
                if screenshot:
                    self.draw()
                    pygame.image.save(self.canvas, screenshot)
                return
            time.sleep(max(0.0, period - (time.monotonic() - self.now)))

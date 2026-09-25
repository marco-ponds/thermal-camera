"""Synthetic sensor for laptop development: the design mockup's scene, gently animated."""

import math
import time

import numpy as np

from .base import SENSOR_H, SENSOR_W


def _scene(t):
    """Port of sceneT() from design-source/Main.dc.html (a person, a cold window corner, a hot mug)."""
    y, x = np.mgrid[0:SENSOR_H, 0:SENSOR_W].astype(np.float64)
    temp = 21.0 + y * 0.05 + x * 0.04 + ((((x * 7 + y * 13) % 5) - 2) * 0.07)
    temp = np.where((x < 7) & (y < 9), 17.4 + (x + y) * 0.12, temp)
    hd = ((x - 15.5) / 4.6) ** 2 + ((y - 8.5) / 5.6) ** 2
    temp = np.where(hd < 1, np.maximum(temp, 35.9 - hd * 3.0 - np.where(y < 5, 2.2, 0.0)), temp)
    temp = np.where((x >= 13) & (x <= 18) & (y >= 13) & (y <= 16), np.maximum(temp, 33.8), temp)
    sd = ((x - 15.5) / 12) ** 2 + ((y - 26) / 10) ** 2
    temp = np.where(sd < 1, np.maximum(temp, 29.4 - sd * 3.2), temp)
    mx = 27 + 0.8 * math.sin(t * 0.5)            # the mug drifts a little
    md = ((x - mx) / 2.2) ** 2 + ((y - 19) / 2.6) ** 2
    return np.where(md < 1, np.maximum(temp, 58.3 - md * 16), temp)


class FakeSensor:
    def __init__(self, noise=0.08):
        self._hz = 8
        self._emissivity = 0.95
        self._noise = noise
        self._rng = np.random.default_rng()
        self._next = time.monotonic()
        self._t0 = time.monotonic()

    def close(self):
        pass

    def set_refresh_hz(self, hz):
        self._hz = hz

    def set_emissivity(self, e):
        self._emissivity = float(e)

    def read_frame(self):
        self._next = max(self._next + 2.0 / self._hz, time.monotonic() - 1)   # full frames = hz / 2
        time.sleep(max(0.0, self._next - time.monotonic()))
        t = time.monotonic() - self._t0
        scene = _scene(t) + self._rng.normal(0, self._noise, (SENSOR_H, SENSOR_W))
        # Pretend emissivity matters: lower e reads warmer surfaces as slightly cooler.
        scene = 24.6 + (scene - 24.6) * (self._emissivity / 0.95) ** 0.25
        # The real sensor sees the scene mirrored; flip_h (default on) undoes it.
        return scene[:, ::-1].astype(np.float32)

    def ambient_c(self):
        return 24.6 + 0.1 * math.sin((time.monotonic() - self._t0) / 30)

    def vdd(self):
        return 3.29

    def info(self):
        return {"serial": "FAKE·0000·0001", "address": 0x33, "bus_hz": 400_000, "bad_pixels": 0,
                "adc_bits": 18, "pattern": "Chess", "subpage_hz": self._hz}

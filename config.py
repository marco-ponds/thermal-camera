"""Persistent settings (SPEC section 7): ~/.config/thermalcam/config.json."""

import json
import os
import sys

DEFAULT_PATH = os.path.expanduser("~/.config/thermalcam/config.json")

DEFAULTS = {
    "palette": "iron",              # iron | rainbow | grey
    "range_mode": "auto",           # auto | lock
    "locked_min": None,             # degC, used when range_mode == "lock"
    "locked_max": None,
    "refresh_hz": 8,                # subpage rate: 2 | 4 | 8 | 16 (full frames = half)
    "units": "C",                   # C | F
    "emissivity": 0.95,
    "smoothing": True,
    "spot": [16, 11],               # sensor pixel (x, y)
    "flip_h": True,                 # mirror so the image matches what you see
    "flip_v": False,
    "touch_calibration": None,      # [a, b, c, d, e, f]: x = a*rx + b*ry + c, y = d*rx + e*ry + f
    "touch_min_pressure": 0,        # ignore lighter contacts (0 = off)
    "sensor_model": "MLX90640BAB",  # BAB = 55x35 deg (Pimoroni standard), BAA = 110x75 deg (wide)
    "i2c_address": 0x33,
    "fonts": {},                    # optional overrides: {"cond": path, "cond_bold": ..., "mono": ..., "mono_bold": ...}
}


class Config:
    def __init__(self, path, data):
        self.path = path
        self.data = data

    @classmethod
    def load(cls, path=DEFAULT_PATH):
        data = dict(DEFAULTS)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data.update(json.load(f))
            except (OSError, ValueError) as e:
                # A corrupt file must not stop the camera booting: keep it aside and start fresh.
                os.replace(path, path + ".bad")
                print(f"config: {path} unreadable ({e}); moved to .bad, using defaults", file=sys.stderr)
        return cls(path, data)

    def __getitem__(self, key):
        return self.data[key]

    def update(self, **changes):
        self.data.update(changes)
        self.save()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)   # atomic: a power cut never leaves a half-written file

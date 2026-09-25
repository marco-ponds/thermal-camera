"""Colour palettes (SPEC section 5): 256-entry uint8 LUTs built from palettes.json."""

import json
import os

import numpy as np

NAMES = ["iron", "rainbow", "grey"]


def _lut(stops):
    xs = np.array([s[0] for s in stops], dtype=np.float64)
    cols = np.array([s[1] for s in stops], dtype=np.float64)
    t = np.linspace(0.0, 1.0, 256)
    return np.stack([np.round(np.interp(t, xs, cols[:, c])) for c in range(3)], axis=1).astype(np.uint8)


with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "palettes.json")) as _f:
    LUTS = {name: _lut(stops) for name, stops in json.load(_f).items()}

missing = set(NAMES) - set(LUTS)
if missing:
    raise SystemExit(f"palettes.json is missing {sorted(missing)}")

"""MLX90640 backend on adafruit-circuitpython-mlx90640 (pure Python, via Blinka).

The library's getFrame() computes the die temperature (Ta) and supply voltage
(Vdd) and then throws them away, and it has no way to pass emissivity in.
read_frame() therefore repeats getFrame's short body with the same helpers.
Those helpers are private, so the library version is pinned in
requirements.txt and check_library() fails loudly at startup if they vanish.

To go faster later (SPEC section 2), write another class with the same
methods on top of pimoroni/mlx90640-library (the C++ Melexis driver).
"""

import re

import numpy as np

from .base import REFRESH_HZ, SENSOR_H, SENSOR_W

_PRIVATE = ("_GetFrameData", "_GetTa", "_GetVdd", "_CalculateTo", "_I2CReadWords")
CONTROL_REGISTER = 0x800D


def check_library():
    import board  # noqa: F401  (fails here, loudly, if Blinka isn't set up)
    import busio  # noqa: F401
    import adafruit_mlx90640 as lib
    missing = [m for m in _PRIVATE if not hasattr(lib.MLX90640, m)]
    if missing:
        raise SystemExit(f"adafruit_mlx90640 {lib.__version__} lacks {missing}; "
                         "install the version pinned in requirements.txt")


def i2c_bus_hz(bus=1):
    """The I2C clock actually in use: device tree first, then config.txt. Blinka ignores `frequency=`."""
    try:
        with open(f"/sys/bus/i2c/devices/i2c-{bus}/of_node/clock-frequency", "rb") as f:
            return int.from_bytes(f.read(4), "big")
    except OSError:
        pass
    for path in ("/boot/firmware/config.txt", "/boot/config.txt"):
        try:
            with open(path) as f:
                m = re.search(r"^\s*dtparam=.*i2c_arm_baudrate=(\d+)", f.read(), re.M)
        except OSError:
            continue
        if m:
            return int(m.group(1))
    return None


def _neighbours(bad):
    """4-neighbours of each bad pixel that are themselves good."""
    out = {}
    for p in bad:
        r, c = divmod(p, SENSOR_W)
        nb = [rr * SENSOR_W + cc for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
              if 0 <= rr < SENSOR_H and 0 <= cc < SENSOR_W and rr * SENSOR_W + cc not in bad]
        out[p] = nb
    return out


class AdafruitSensor:
    def __init__(self, address=0x33):
        import board
        import busio
        import adafruit_mlx90640 as lib

        self._lib = lib
        # Library bug: the bad-pixel lists are class attributes that grow on
        # every construction. Reset them so re-opening after an unplug works.
        lib.MLX90640.brokenPixels = []
        lib.MLX90640.outlierPixels = []
        self._i2c = busio.I2C(board.SCL, board.SDA)
        self._mlx = lib.MLX90640(self._i2c, address=address)

        bad = set(self._mlx.brokenPixels) | set(self._mlx.outlierPixels)
        self._neigh = _neighbours(bad)
        self._address = address
        self._bus_hz = i2c_bus_hz()
        self._serial = "·".join(f"{w:04X}" for w in self._mlx.serial_number)  # EEPROM 0x2407-0x2409
        self._emissivity = 0.95
        self._ta = self._vdd = None
        self._buf = [0.0] * (SENSOR_W * SENSOR_H)
        self._raw = [0] * 834          # 832 RAM words + control register + subpage number
        ctrl = [0]
        self._mlx._I2CReadWords(CONTROL_REGISTER, ctrl)
        self._ctrl = ctrl[0]

    def close(self):
        self._i2c.deinit()

    def set_refresh_hz(self, hz):
        self._mlx.refresh_rate = REFRESH_HZ.index(hz)

    def set_emissivity(self, e):
        self._emissivity = float(e)

    def read_frame(self):
        mlx, raw = self._mlx, self._raw
        for _ in range(2):   # one full frame = two subpages
            if mlx._GetFrameData(raw) < 0:
                raise RuntimeError("frame data error")
            ta = mlx._GetTa(raw)
            vdd = mlx._GetVdd(raw)
            # Reflected temperature = Ta - 8 (Melexis' open-air recommendation)
            mlx._CalculateTo(raw, self._emissivity, ta - self._lib.OPENAIR_TA_SHIFT, self._buf)
        self._ta, self._vdd, self._ctrl = ta, vdd, raw[832]
        f = np.array(self._buf, dtype=np.float32)
        for p, nb in self._neigh.items():
            if nb:
                f[p] = f[nb].mean()
        return f.reshape(SENSOR_H, SENSOR_W)

    def ambient_c(self):
        return self._ta

    def vdd(self):
        return self._vdd

    def info(self):
        ctrl = self._ctrl
        return {
            "serial": self._serial,
            "address": self._address,
            "bus_hz": self._bus_hz,
            "bad_pixels": len(self._neigh),
            "adc_bits": 16 + ((ctrl >> 10) & 0x3),
            "pattern": "Chess" if ctrl & 0x1000 else "Interleaved",
            "subpage_hz": REFRESH_HZ[(ctrl >> 7) & 0x7],
        }

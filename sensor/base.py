"""ThermalSensor interface (SPEC section 6) and the background reader thread."""

import threading
import time
from collections import deque
from typing import Optional, Protocol

import numpy as np

SENSOR_W, SENSOR_H = 32, 24
REFRESH_HZ = [0.5, 1, 2, 4, 8, 16, 32, 64]   # index = value of control register 0x800D bits 7-9


class ThermalSensor(Protocol):
    def set_refresh_hz(self, hz: int) -> None: ...
    def set_emissivity(self, e: float) -> None: ...
    def read_frame(self) -> np.ndarray: ...        # (24, 32) float degC; blocks until a full frame is ready
    def ambient_c(self) -> Optional[float]: ...    # Ta (sensor die temperature)
    def vdd(self) -> Optional[float]: ...
    def info(self) -> dict: ...                    # serial, address, bus_hz, bad_pixels, adc_bits, pattern, subpage_hz
    def close(self) -> None: ...


# Read failures worth retrying: torn frames (ValueError/RuntimeError from the
# driver) and I2C errors (OSError: loose wire, sensor unplugged).
TRANSIENT = (OSError, ValueError, RuntimeError)


class SensorWorker(threading.Thread):
    """Reads frames continuously into a single "latest frame" slot.

    - Opening is retried every 2 s, so a missing sensor is a status, not a crash.
    - A failed read counts as "dropped" and the last good frame stays current.
    - After FAILS_BEFORE_MISSING failures in a row the sensor is treated as
      unplugged: it is closed and re-opened (re-applying settings) when it returns.
    - Settings from the UI are queued and applied between reads, so the I2C bus
      is only ever touched from this thread.
    """

    FAILS_BEFORE_MISSING = 5
    REOPEN_EVERY_S = 2.0

    def __init__(self, open_sensor, refresh_hz, emissivity):
        super().__init__(daemon=True)
        self._open_sensor = open_sensor
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wanted = {"refresh_hz": refresh_hz, "emissivity": emissivity}
        self._pending = dict(self._wanted)
        self._frame = None
        self._frame_id = 0
        self._times = deque(maxlen=9)    # rolling window for the frame rate
        self.status = "opening"          # opening | ok | missing
        self.message = ""
        self.frames = 0
        self.dropped = 0
        self.fps = None
        self.ta = None
        self.vdd = None
        self.info = {}

    def configure(self, **settings):
        with self._lock:
            self._wanted.update(settings)
            self._pending.update(settings)

    def latest(self):
        with self._lock:
            return self._frame_id, self._frame

    def stop(self):
        self._stop.set()

    def run(self):
        sensor = None
        fails = 0
        while not self._stop.is_set():
            if sensor is None:
                try:
                    sensor = self._open_sensor()
                except TRANSIENT as e:
                    self.status, self.message = "missing", str(e)
                    self._stop.wait(self.REOPEN_EVERY_S)
                    continue
                with self._lock:
                    self._pending = dict(self._wanted)
                self.info = sensor.info()
                self.status, fails = "ok", 0

            with self._lock:
                pending, self._pending = self._pending, {}
            try:
                if "refresh_hz" in pending:
                    sensor.set_refresh_hz(pending["refresh_hz"])
                if "emissivity" in pending:
                    sensor.set_emissivity(pending["emissivity"])
                frame = sensor.read_frame()
            except TRANSIENT as e:
                self.dropped += 1
                fails += 1
                self.message = f"{type(e).__name__}: {e}"
                with self._lock:
                    self._pending = {**pending, **self._pending}   # retry unapplied settings
                if fails >= self.FAILS_BEFORE_MISSING:
                    self.status = "missing"
                    self.fps = None
                    self._times.clear()
                    try:
                        sensor.close()
                    except TRANSIENT:
                        pass
                    sensor = None
                else:
                    time.sleep(0.05)
                continue

            fails = 0
            now = time.monotonic()
            self._times.append(now)
            if len(self._times) >= 2:
                self.fps = (len(self._times) - 1) / (self._times[-1] - self._times[0])
            self.ta, self.vdd, self.info = sensor.ambient_c(), sensor.vdd(), sensor.info()
            with self._lock:
                self._frame = frame
                self._frame_id += 1
                self.frames += 1
                self.status = "ok"

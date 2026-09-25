"""Off-device tests for the thermal camera. Run: python -m pytest tests/

They use the fake sensor, fake evdev devices and a regular file as the
"framebuffer", so they run on a laptop without any hardware.
"""

import json
import os
import sys
import threading
import time
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pygame  # noqa: E402
import pytest  # noqa: E402

import app as app_mod  # noqa: E402
from app import App, snapshot_base  # noqa: E402
from config import DEFAULTS, Config  # noqa: E402
from display import FramebufferDisplay  # noqa: E402
from sensor import adafruit  # noqa: E402
from sensor.base import SensorWorker  # noqa: E402
from sensor.fake import FakeSensor  # noqa: E402
from touch import CAL_TARGETS, Calibration, TouchInput, calibrate  # noqa: E402
from ui import live  # noqa: E402
from ui.theme import Fonts  # noqa: E402

pygame.font.init()
FONTS = Fonts()


class ListDisplay:
    """Display double: records presents, replays queued events."""

    def __init__(self):
        self.events, self.presented = [], 0

    def present(self, surface):
        self.presented += 1

    def poll(self):
        out, self.events = self.events, []
        return out


class StubWorker:
    def __init__(self):
        self.status, self.fps, self.ta, self.vdd = "ok", 3.9, 24.6, 3.29
        self.frames, self.dropped, self.info = 10, 1, {"serial": "X", "address": 0x33}
        self.configured = {}
        self.frame_id, self.frame = 1, np.linspace(15, 40, 768, dtype=np.float32).reshape(24, 32)

    def configure(self, **kw):
        self.configured.update(kw)

    def latest(self):
        return self.frame_id, self.frame


@pytest.fixture
def make_app(tmp_path):
    def _make(worker=None):
        cfg = Config.load(str(tmp_path / "config.json"))
        a = App(cfg, worker or StubWorker(), ListDisplay(), FONTS, str(tmp_path / "snaps"))
        a.now = time.monotonic()
        a._poll_sensor()
        return a
    return _make


def tap(a, x, y):
    """A clean tap, spaced past the 150 ms debounce on the app's clock."""
    a.now += 0.3
    a.on_event(("down", x, y))
    a.on_event(("up", x, y))


def centre_of(a, target_id):
    return next(t[1].center for t in a.screen.targets() if t[0] == target_id)


# ---------------------------------------------------------------- taps

def test_tap_acts_on_release_not_press(make_app):
    a = make_app()
    x, y = live.HOLD_BTN.center
    a.on_event(("down", x, y))
    assert not a.hold
    a.on_event(("up", x, y))
    assert a.hold


def test_sliding_off_a_button_cancels(make_app):
    a = make_app()
    x, y = live.HOLD_BTN.center
    a.on_event(("down", x, y))
    a.on_event(("move", 100, 100))
    a.on_event(("move", 100, 100))
    a.on_event(("move", 100, 100))
    a.on_event(("up", 100, 100))
    assert not a.hold


def test_bounce_within_150ms_is_ignored(make_app):
    a = make_app()
    x, y = live.HOLD_BTN.center
    a.now = 100.0
    a.on_event(("down", x, y)); a.on_event(("up", x, y))
    a.now = 100.1
    a.on_event(("down", x, y)); a.on_event(("up", x, y))
    assert a.hold                     # second contact ignored
    a.now = 100.4
    a.on_event(("down", x, y)); a.on_event(("up", x, y))
    assert not a.hold


def test_pressed_state_is_drawn_while_finger_down(make_app):
    a = make_app()
    x, y = live.MENU_BTN.center
    a.on_event(("down", x, y))
    a.draw()
    down_px = a.canvas.get_at((live.MENU_BTN.x + 4, live.MENU_BTN.y + 26))
    a.on_event(("up", 5, 5))
    a.draw()
    up_px = a.canvas.get_at((live.MENU_BTN.x + 4, live.MENU_BTN.y + 26))
    assert sum(down_px[:3]) > sum(up_px[:3])


def test_image_tap_moves_spot_to_sensor_pixel(make_app, tmp_path):
    a = make_app()
    tap(a, 5 * 12 + 7, 20 * 12 + 2)
    assert a.cfg["spot"] == [5, 20]
    assert json.load(open(tmp_path / "config.json"))["spot"] == [5, 20]


# ---------------------------------------------------------------- settings

def test_settings_apply_immediately_and_persist(make_app, tmp_path):
    a = make_app()
    tap(a, *live.MENU_BTN.center)
    assert a.screen_name == "settings"
    tap(a, *centre_of(a, ("palette", 1)))
    tap(a, *centre_of(a, ("refresh_hz", 3)))
    tap(a, *centre_of(a, ("units", 1)))
    tap(a, *centre_of(a, ("smoothing", 0)))
    tap(a, *centre_of(a, ("emissivity", "minus")))
    assert a.worker.configured == {"refresh_hz": 16, "emissivity": 0.94}
    reloaded = Config.load(str(tmp_path / "config.json"))
    assert (reloaded["palette"], reloaded["refresh_hz"], reloaded["units"], reloaded["smoothing"],
            reloaded["emissivity"]) == ("rainbow", 16, "F", False, 0.94)
    a.go("live")
    assert a.fmt_temp(100) == "212.0°"


def test_emissivity_clamps(make_app):
    a = make_app()
    a.go("settings")
    for _ in range(10):
        tap(a, *centre_of(a, ("emissivity", "plus")))
    assert a.cfg["emissivity"] == 1.0
    a.set(emissivity=0.11)
    tap(a, *centre_of(a, ("emissivity", "minus")))
    tap(a, *centre_of(a, ("emissivity", "minus")))
    assert a.cfg["emissivity"] == 0.10


def test_lock_freezes_current_range(make_app):
    a = make_app()
    a.go("settings")
    tap(a, *centre_of(a, ("range_mode", 1)))
    assert a.cfg["range_mode"] == "lock"
    assert (a.cfg["locked_min"], a.cfg["locked_max"]) == pytest.approx((15.0, 40.0))
    a.worker.frame = a.worker.frame + 10
    a.worker.frame_id += 1
    a._poll_sensor()
    assert a.scale_range(a.frame) == pytest.approx((15.0, 40.0))
    tap(a, *centre_of(a, ("range_mode", 0)))
    assert a.scale_range(a.frame) == pytest.approx((25.0, 50.0))


def test_navigation(make_app):
    a = make_app()
    tap(a, *live.MENU_BTN.center)
    tap(a, *centre_of(a, "right"))
    assert a.screen_name == "info"
    tap(a, *centre_of(a, "left"))
    assert a.screen_name == "settings"
    tap(a, *centre_of(a, "left"))
    assert a.screen_name == "live"


# ---------------------------------------------------------------- hold / save

def test_hold_freezes_and_save_writes_png_and_csv(make_app, tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "clock_trusted", lambda: True)
    a = make_app()
    tap(a, *live.HOLD_BTN.center)
    held = a.shown.copy()
    a.worker.frame = a.worker.frame + 5
    a.worker.frame_id += 1
    a._poll_sensor()
    assert np.array_equal(a.shown, held)
    assert a.screen._save_label() == "SAVE PNG"
    tap(a, *centre_of(a, "save"))
    files = os.listdir(tmp_path / "snaps")
    png = [f for f in files if f.endswith(".png")]
    assert len(files) == 2 and len(png) == 1 and png[0][:-4] + "-raw.csv" in files
    csv = np.loadtxt(tmp_path / "snaps" / (png[0][:-4] + "-raw.csv"), delimiter=",")
    assert csv.shape == (24, 32) and np.allclose(csv, held, atol=0.01)
    assert a.screen._save_label() == "SAVED"
    tap(a, *live.HOLD_BTN.center)
    assert not a.hold and np.array_equal(a.shown, a.frame)


def test_snapshot_names_fall_back_to_counter_without_ntp(tmp_path):
    d = str(tmp_path)
    assert os.path.basename(snapshot_base(d, trusted=False)) == "snap-0001"
    open(os.path.join(d, "snap-0001.png"), "w").close()
    assert os.path.basename(snapshot_base(d, trusted=False)) == "snap-0002"
    assert len(os.path.basename(snapshot_base(d, trusted=True))) == len("20260925-153000")


# ---------------------------------------------------------------- sensor worker

class FlakySensor(FakeSensor):
    """Works, then 'unplugs' (OSError) while `unplugged` is set."""
    unplugged = threading.Event()

    def read_frame(self):
        if self.unplugged.is_set():
            raise OSError(121, "Remote I/O error")
        return super().read_frame()


def test_unplug_shows_missing_then_recovers():
    FlakySensor.unplugged.clear()
    opened = []

    def open_sensor():
        if FlakySensor.unplugged.is_set():
            raise ValueError("No I2C device at address: 0x33")
        s = FlakySensor(); opened.append(s); return s

    w = SensorWorker(open_sensor, 16, 0.9)
    SensorWorker.REOPEN_EVERY_S = 0.1
    w.start()
    time.sleep(0.5)
    assert w.status == "ok" and w.frames > 0
    assert opened[0]._hz == 16 and opened[0]._emissivity == 0.9
    FlakySensor.unplugged.set()
    time.sleep(0.8)
    assert w.status == "missing" and w.dropped >= SensorWorker.FAILS_BEFORE_MISSING
    last_id, last = w.latest()
    assert last is not None               # last good frame is kept
    FlakySensor.unplugged.clear()
    time.sleep(0.6)
    assert w.status == "ok" and len(opened) == 2 and w.latest()[0] > last_id
    assert opened[1]._hz == 16            # settings re-applied after reconnect
    w.stop()


def test_missing_sensor_message_on_live_view(make_app):
    wk = StubWorker()
    wk.status = "missing"
    a = make_app(wk)
    a.draw()        # must not raise; message drawn over the dimmed last frame
    assert a.canvas.get_at(live.IMG.center)[:3] != (0, 0, 0)


# ---------------------------------------------------------------- touch

E = lambda t, c, v: types.SimpleNamespace(type=t, code=c, value=v)  # noqa: E731


class FakeEvdev:
    def __init__(self, batches):
        self.batches = list(batches)

    def read(self):
        if not self.batches:
            raise BlockingIOError
        return iter(self.batches.pop(0))


def contact(rx, ry, pressure=None, moves=()):
    down = [E(1, 330, 1), E(3, 0, rx), E(3, 1, ry)] + ([E(3, 24, pressure)] if pressure is not None else [])
    batches = [down + [E(0, 0, 0)]]
    batches += [[E(3, 0, mx), E(3, 1, my), E(0, 0, 0)] for mx, my in moves]
    batches.append([E(1, 330, 0), E(0, 0, 0)])
    return batches


def drain(t):
    out = []
    for _ in range(20):
        out += t.poll()
    return out


def test_touch_parser_and_pressure_filter():
    t = TouchInput(FakeEvdev(contact(100, 200, moves=[(110, 205)])))
    assert drain(t) == [("down", 100, 200), ("move", 110, 205), ("up", 110, 205)]
    t = TouchInput(FakeEvdev(contact(100, 200, pressure=5)), min_pressure=20)
    assert drain(t) == []
    t = TouchInput(FakeEvdev(contact(100, 200, pressure=50)), min_pressure=20)
    assert [e[0] for e in drain(t)] == ["down", "up"]


def raw_of(x, y):
    """A rotated, inverted, slightly skewed panel."""
    return (4000 - y * 11.2 + x * 0.3, 180 + x * 7.6 + y * 0.2)


def test_affine_calibration_handles_swap_invert_skew():
    cal = Calibration.solve(CAL_TARGETS, [raw_of(*p) for p in CAL_TARGETS])
    for p in [(0, 0), (479, 319), (240, 160), (12, 300)]:
        m = cal.map(*raw_of(*p))
        assert abs(m[0] - p[0]) <= 1 and abs(m[1] - p[1]) <= 1
    with pytest.raises(ValueError):
        Calibration.solve(CAL_TARGETS, [(10, 10), (20, 20), (30, 30)])


def test_calibration_screen(tmp_path):
    batches = []
    for p in CAL_TARGETS:
        batches += contact(*[int(v) for v in raw_of(*p)])
    fb = str(tmp_path / "fb")
    open(fb, "wb").write(b"\0" * 480 * 320 * 2)
    display = FramebufferDisplay(fb, (480, 320), 16, 960, 0, TouchInput(FakeEvdev(batches)))
    cal = calibrate(display, FONTS)
    m = cal.map(*raw_of(240, 160))
    assert abs(m[0] - 240) <= 2 and abs(m[1] - 160) <= 2


# ---------------------------------------------------------------- framebuffer

def test_framebuffer_encoding(tmp_path):
    fb = str(tmp_path / "fb")
    open(fb, "wb").write(b"\0" * 480 * 320 * 4 * 2)
    s = pygame.Surface((480, 320))
    s.fill((255, 0, 0))
    s.fill((0, 0, 255), (0, 0, 1, 1))
    d = np.frombuffer(FramebufferDisplay(fb, (480, 320), 16, 960, 0, None).encode(s), np.uint16).reshape(320, 480)
    assert d[0, 0] == 0x001F and d[5, 5] == 0xF800
    b = FramebufferDisplay(fb, (480, 320), 32, 480 * 4 + 64, 0, None).encode(s)
    assert len(b) == 320 * (480 * 4 + 64) and b[20:24] == bytes([0, 0, 255, 255])
    FramebufferDisplay(fb, (320, 480), 16, 640, 90, None).present(s)
    with pytest.raises(SystemExit):
        FramebufferDisplay(fb, (320, 480), 16, 640, 0, None)


# ---------------------------------------------------------------- adafruit backend

class FakeMLX:
    """Mimics the private helpers read_frame uses; subpage 0 then 1."""

    def __init__(self):
        self.sub = 0

    def _GetFrameData(self, raw):
        raw[832] = (0b11 << 10) | 0x1000 | (0b100 << 7)   # 19-bit, chess, 8 Hz
        raw[833] = self.sub
        self.sub ^= 1
        return raw[833]

    def _GetTa(self, raw):
        return 31.5

    def _GetVdd(self, raw):
        return 3.28

    def _CalculateTo(self, raw, emissivity, tr, buf):
        assert tr == 31.5 - 8
        for i in range(768):
            buf[i] = 20.0 + emissivity
        buf[33] = 999.0   # a dead pixel


def test_adafruit_backend_bad_pixel_interpolation_and_register_decode():
    s = adafruit.AdafruitSensor.__new__(adafruit.AdafruitSensor)
    s._lib = types.SimpleNamespace(OPENAIR_TA_SHIFT=8)
    s._mlx = FakeMLX()
    s._neigh = adafruit._neighbours({33, 34})
    s._emissivity, s._buf, s._raw, s._ctrl = 0.9, [0.0] * 768, [0] * 834, 0
    s._serial, s._address, s._bus_hz = "1234·5678·9ABC", 0x33, 400_000
    f = s.read_frame()
    assert f.shape == (24, 32) and f[1, 1] == pytest.approx(20.9)
    assert (s.ambient_c(), s.vdd()) == (31.5, 3.28)
    info = s.info()
    assert (info["adc_bits"], info["pattern"], info["subpage_hz"], info["bad_pixels"]) == (19, "Chess", 8, 2)


def test_check_library_finds_private_helpers(monkeypatch):
    for name in ("board", "busio"):
        mod = types.ModuleType(name)
        mod.I2C = object
        monkeypatch.setitem(sys.modules, name, mod)
    lib = pytest.importorskip("adafruit_mlx90640")
    adafruit.check_library()
    assert lib.__version__ == "1.3.9"


# ---------------------------------------------------------------- config / perf

def test_corrupt_config_is_set_aside(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{not json")
    cfg = Config.load(str(p))
    assert cfg.data == DEFAULTS and (tmp_path / "config.json.bad").exists()


def test_redraw_is_fast(make_app):
    a = make_app()
    for name in ("live", "settings", "info"):
        a.go(name)
        a.draw()
        t = time.perf_counter()
        for _ in range(10):
            a.draw()
        assert (time.perf_counter() - t) / 10 < 0.05, name

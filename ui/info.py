"""Sensor info (SPEC 4.3): hardware and live key/value columns, refreshed about once a second."""

from . import theme as T
from .widgets import HEADER_H, header, header_rects, text_mid, value_row

COL_X = (14, 248)
COL_W = 218
HEADING_Y = HEADER_H + 10
ROWS_Y = HEADING_Y + 21
ROW_H = 27
FOV = {"MLX90640BAA": "110° × 75°", "MLX90640BAB": "55° × 35°"}
DASH = "—"


def _read_cpu_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000
    except OSError:
        return None


def _bus(hz):
    if not hz:
        return DASH
    return f"{hz / 1e6:g} MHz" if hz >= 1_000_000 else f"{hz / 1000:g} kHz"


def _group(n):
    return f"{n:,}".replace(",", " ")


class InfoScreen:
    REFRESH_S = 1.0

    def __init__(self, app):
        self.app = app
        self._back, self._live = header_rects(app.fonts, "BACK", "LIVE")

    def targets(self):
        app = self.app
        return [("left", self._back, lambda pos: app.go("settings")),
                ("right", self._live, lambda pos: app.go("live"))]

    def rows(self):
        app, w = self.app, self.app.worker
        info = w.info or {}
        model = app.cfg["sensor_model"]
        lo, hi = app.fmt_temp(-40, digits=0, unit=False), app.fmt_temp(300, digits=0, unit=True)
        hardware = [
            ("Model", model),
            ("Field of view", FOV.get(model, DASH)),
            ("Array", "32 × 24"),
            ("Object range", f"{lo.replace('-', '−')}…{hi}"),
            ("I²C address", f"0x{info.get('address', app.cfg['i2c_address']):02X}"),
            ("Bus speed", _bus(info.get("bus_hz"))),
            ("Device ID", info.get("serial", DASH)),
            ("Bad pixels", f"{info['bad_pixels']} / 768" if "bad_pixels" in info else DASH),
        ]
        cpu = _read_cpu_c()
        live = [
            ("Die temp (Ta)", app.fmt_temp(w.ta, spaced=True) if w.ta is not None else DASH),
            ("Supply (Vdd)", f"{w.vdd:.2f} V" if w.vdd is not None else DASH),
            ("ADC resolution", f"{info['adc_bits']}-bit" if "adc_bits" in info else DASH),
            ("Readout pattern", info.get("pattern", DASH)),
            ("Subpage rate", f"{info['subpage_hz']:g} Hz" if "subpage_hz" in info else DASH),
            ("Frame rate", f"{w.fps:.1f} fps" if w.fps else DASH),
            ("Frames / dropped", f"{_group(w.frames)} / {_group(w.dropped)}"),
            ("Pi CPU temp", app.fmt_temp(cpu, spaced=True) if cpu is not None else DASH),
        ]
        return hardware, live

    def draw(self, c, pressed):
        fonts = self.app.fonts
        c.fill(T.BG)
        header(c, fonts, "SENSOR INFO", "BACK", "LIVE", "camera", pressed)
        heading = fonts("cond_bold", 14)
        for x, title, rows in zip(COL_X, ("HARDWARE", "LIVE"), self.rows()):
            text_mid(c, heading, title, T.ACCENT, x, HEADING_Y + 8, spacing=1.4)
            for i, (k, v) in enumerate(rows):
                value_row(c, fonts, x, ROWS_Y + i * ROW_H, COL_W, k, v)

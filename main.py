#!/usr/bin/env python3
"""Thermal camera: MLX90640 on a Raspberry Pi 2 with an Adafruit PiTFT 3.5".

On the Pi:        python3 main.py                 (what thermalcam.service runs)
Recalibrate:      python3 main.py --calibrate
On a laptop:      python3 main.py --windowed --fake-sensor
"""

import argparse
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import SNAP_DIR, App  # noqa: E402
from config import DEFAULT_PATH, Config  # noqa: E402
from sensor.base import SensorWorker  # noqa: E402
from ui.theme import Fonts  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--windowed", action="store_true", help="desktop window instead of the PiTFT framebuffer")
    p.add_argument("--fake-sensor", "--demo", action="store_true", help="synthetic scene, no sensor needed")
    p.add_argument("--calibrate", action="store_true", help="run the 3-point touch calibration first")
    p.add_argument("--scale", type=int, default=2, help="window scale with --windowed (default 2)")
    p.add_argument("--config", default=DEFAULT_PATH, help=f"config file (default {DEFAULT_PATH})")
    p.add_argument("--snap-dir", default=SNAP_DIR, help=f"snapshot folder (default {SNAP_DIR})")
    p.add_argument("--fb", help="framebuffer device (default: auto-detect the 480x320 one)")
    p.add_argument("--rotate", type=int, choices=[0, 90, 180, 270],
                   help="rotate output on the framebuffer (default: 0, or 90 if it is portrait)")
    p.add_argument("--touch-device", help="evdev touchscreen (default: auto-detect)")
    # development / docs helpers
    p.add_argument("--screen", choices=["live", "settings", "info"], default="live", help=argparse.SUPPRESS)
    p.add_argument("--hold-after", type=float, default=0, help=argparse.SUPPRESS)
    p.add_argument("--exit-after", type=float, default=0, help=argparse.SUPPRESS)
    p.add_argument("--screenshot", help=argparse.SUPPRESS)
    return p.parse_args(argv)


def make_display(args, cfg, fonts):
    if args.windowed:
        if args.calibrate:
            raise SystemExit("--calibrate needs the touchscreen; drop --windowed")
        from display import WindowDisplay
        return WindowDisplay(args.scale)
    from display import FramebufferDisplay
    from touch import Calibration, calibrate
    display = FramebufferDisplay.open(args.fb, args.rotate, args.touch_device, cfg["touch_min_pressure"])
    if display.touch is not None:
        if args.calibrate or not cfg["touch_calibration"]:
            cfg.update(touch_calibration=calibrate(display, fonts).coeffs)
        display.calibration = Calibration(cfg["touch_calibration"])
    elif args.calibrate:
        raise SystemExit("--calibrate: no touchscreen found")
    return display


def main(argv=None):
    args = parse_args(argv)
    cfg = Config.load(args.config)

    if args.fake_sensor:
        from sensor.fake import FakeSensor
        open_sensor = FakeSensor
    else:
        from sensor import adafruit
        adafruit.check_library()     # a broken install is a setup bug: fail now, loudly
        open_sensor = lambda: adafruit.AdafruitSensor(cfg["i2c_address"])  # noqa: E731

    pygame.font.init()
    fonts = Fonts(cfg["fonts"])
    display = make_display(args, cfg, fonts)

    worker = SensorWorker(open_sensor, cfg["refresh_hz"], cfg["emissivity"])
    worker.start()
    app = App(cfg, worker, display, fonts, args.snap_dir)
    app.go(args.screen)
    try:
        if args.hold_after:
            app.run(exit_after=args.hold_after)
            app.toggle_hold()
        app.run(exit_after=args.exit_after, screenshot=args.screenshot)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        worker.stop()
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())

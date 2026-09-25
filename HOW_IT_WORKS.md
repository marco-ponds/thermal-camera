# How it works

This is the internals companion to [README.md](README.md), which covers setup and use.
The UI implements `thermal-cam-ui/SPEC.md`; the places where it departs from the spec are listed at the end.

## The big picture

```
                 ┌──────────── sensor thread ────────────┐        ┌────────────── UI loop (20 Hz) ──────────────┐
 MLX90640 ──I²C──▶ AdafruitSensor.read_frame()           │        │ display.poll() ─▶ tap recogniser ─▶ screen  │
  (0x33)         │   2 subpages → 32×24 °C               │ latest │                                   targets   │
                 │   bad pixels interpolated             ├─frame─▶│ _poll_sensor(): flip, new frame?            │
                 │   Ta, Vdd, control register kept      │  slot  │ draw() → 480×320 pygame Surface             │
                 │ SensorWorker: retry, dropped, fps     │ (lock) │ display.present() ─▶ /dev/fbN  (or window)  │
                 └───────────────────────────────────────┘        └──────────────────────────────────────────────┘
                              ▲ settings queue (refresh Hz, emissivity)          │ config.json (atomic writes)
                              └──────────────────────────────────────────────────┘
```

Two threads share one "latest frame" slot guarded by a lock. Old frames are dropped, never queued. The UI
never touches I²C, and the sensor thread never touches pygame.

| File | Role |
|---|---|
| `main.py` | Arguments; wires config, fonts, display, sensor worker and app together |
| `app.py` | Screen state machine (LIVE / SETTINGS / INFO), tap recogniser, hold, snapshots, units |
| `display.py` | `FramebufferDisplay` (the Pi) and `WindowDisplay` (a laptop). Both take a Surface and return pointer events. |
| `touch.py` | evdev touchscreen reader, 3-point affine calibration, calibration screen |
| `sensor/base.py` | `ThermalSensor` interface and the `SensorWorker` thread |
| `sensor/adafruit.py` | Real backend on `adafruit-circuitpython-mlx90640` |
| `sensor/fake.py` | Synthetic scene (ported from the mockup's `sceneT()`) for development |
| `ui/theme.py` | Design tokens (SPEC §3) and font loading |
| `ui/widgets.py` | Letter-spaced text, icons, Button, Segmented, Stepper, ValueRow, header |
| `ui/live.py`, `ui/settings.py`, `ui/info.py` | The three screens |
| `palettes.py` + `palettes.json` | 256-entry colour lookup tables |
| `config.py` | `~/.config/thermalcam/config.json` |
| `thermalcam.service`, `setup.sh` | Boot service and one-shot install |
| `tests/` | 21 off-device tests (`python -m pytest tests/`) |

## Boot sequence

1. The Pi boots Raspberry Pi OS Lite to `multi-user.target`. No desktop is installed.
2. systemd starts `thermalcam.service` as your user, with the `video` (framebuffer), `input` (touch)
   and `i2c` groups. It doesn't wait for the network.
3. `main.py` loads the config and fonts, finds the PiTFT framebuffer and the touchscreen, and runs the calibration
   screen if no calibration is saved. Then it starts the sensor thread and the UI loop.
4. If the framebuffer isn't there yet (the SPI driver can be a little late), the app exits with an error and
   systemd starts it again 3 s later (`Restart=always`, `StartLimitIntervalSec=0`).
5. If the sensor is missing, the app still starts. The Live view shows "SENSOR NOT FOUND — RETRYING"
   until the sensor answers.

## Display

Adafruit's `adafruit-pitft.py` has several install modes. The design assumed the PiTFT could mirror HDMI,
but on current Pi OS Lite (Bookworm and later) the installer **refuses mirror mode**. Mirroring uses
`rpi-fbcp`, which copies from the legacy DispmanX display stack, and that stack no longer exists. So
`setup.sh` uses `--install-type=drivers`, which:
- loads the PiTFT's DRM driver (`dtoverlay=pitft35-resistive,rotate=90,...,drm`). The kernel exposes it as a
  normal framebuffer, `/dev/fbN`.
- applies the touch axis swap/invert for that rotation in the device tree
- keeps the text console off the PiTFT, so nothing else draws on it

Recent SDL2 (pygame 2) can't render to a framebuffer any more, so pygame renders **off-screen only**, into
a 480×320 `Surface`. `FramebufferDisplay.present()` then:
1. rotates the surface if the framebuffer is portrait (320×480)
2. converts it with numpy to the framebuffer's pixel format: RGB565 for 16 bpp, XRGB8888 for 32 bpp
3. pads each row to the framebuffer's `stride`
4. writes the bytes to `/dev/fbN` with a single `pwrite`

The framebuffer is auto-detected as the one whose `/sys/class/graphics/fbN/virtual_size` is 480×320
(override with `--fb`). On a laptop, `WindowDisplay` shows the same surface in a window, which is why the
development view and the device look identical.

## Touch

**Reading.** `touch.TouchInput` reads the STMPE610 through evdev. It tracks `ABS_X`, `ABS_Y`,
`ABS_PRESSURE` and `BTN_TOUCH`, and on each `SYN_REPORT` it emits `down`, `move` or `up` in raw units. Contacts
lighter than `touch_min_pressure` are ignored.

**Calibration.** The screen shows three crosses at (40,40), (440,60) and (240,280). Each tap is the
**median** of all raw samples during the contact, because resistive readings are noisy at touch-down and
lift-off. The three pairs solve an **affine** map:
```
x = a·rx + b·ry + c
y = d·rx + e·ry + f
```
Six unknowns and six equations, solved with `numpy.linalg.solve`. This covers swapped, inverted and slightly
skewed axes, so it doesn't matter which rotation the driver was installed with. The coefficients are saved
in the config.

**Tap rules (SPEC §3).** These live in `App.on_event`:
- **Act on release:** the target under the finger at touch-down is highlighted (pressed state). It only
  fires if the median position of the whole contact is still inside it, with 12 px of slop.
  Sliding off cancels.
- **Debounce:** a new contact within 150 ms of the last release is ignored completely.
- **One touch at a time:** no swipes, long presses or multi-touch.
- **Feedback:** touch-down redraws immediately, so it doesn't wait for the next sensor frame.

## Sensor pipeline

**Frames.** The MLX90640 reads out in two halves (subpages, in a chess pattern). The "refresh rate"
register is the subpage rate, so one 32×24 image takes two subpages. `AdafruitSensor.read_frame()` runs the
library's private helpers itself instead of calling `getFrame()`, because it wants three things `getFrame()`
doesn't give:
1. **Ta and Vdd.** `_GetTa()` and `_GetVdd()` are computed for each subpage and kept, for the Info screen and
   the strip.
2. **Emissivity.** It's passed into `_CalculateTo(raw, emissivity, Ta − 8, out)`, where Ta − 8 is Melexis'
   reflected-temperature rule for open air. `getFrame()` hard-codes 0.95.
3. **The control register.** Word 832 of the frame data is register `0x800D`. Its bits 10–11 give the ADC
   resolution (16–19 bit), bit 12 the readout pattern (chess or interleaved), and bits 7–9 the subpage rate.
   So these Info fields are live.

These helpers are private, so the library is **pinned to 1.3.9**, and `check_library()` stops the app with
a clear message at startup if they're missing.

**Bad pixels.** The EEPROM lists broken and outlier pixels (up to 4 is within spec). Each one is replaced by
the mean of its good 4-neighbours before display.

**Library workaround.** The library keeps its bad-pixel lists as *class* attributes, which grow every time
it's constructed. They're reset before each (re)open, otherwise reconnecting after an unplug would fail with
"More than 4 broken pixels".

**The worker (`SensorWorker`).**
- **Opening:** retried every 2 s. Until the sensor answers, the status is `missing`.
- **Read errors:** torn frames (`ValueError`/`RuntimeError`) and I²C errors (`OSError`) count as **dropped**.
  The last good frame stays current.
- **Unplug:** 5 failures in a row mark the sensor as unplugged. It's closed and reopened when it comes back,
  and all current settings are re-applied.
- **Settings:** refresh rate and emissivity from the UI are queued and applied between reads. Only this
  thread uses the I²C bus.
- **Frame rate:** a rolling average over the last 8 frame intervals.

**Speed.** The Adafruit driver is pure Python, and on a Pi 2 the per-pixel maths is the bottleneck: expect
about 1–4 fps, whatever the sensor rate is set to. The UI copes by only redrawing when something changes. To go
faster, add a backend with the same methods on top of the C++ `pimoroni/mlx90640-library`. Nothing else
needs to change.

## From temperatures to pixels (Live view)

1. The frame is flipped (`flip_h`/`flip_v`) so the image behaves like a camera.
2. **Range.** In AUTO, the frame's min maps to 0 and its max to 1 (with a 0.5 °C minimum span, so a blank
   wall doesn't turn to noise). In LOCK, the saved `locked_min`/`locked_max` are used instead. These are set
   when you tap LOCK, and they persist.
3. **Colour.** The value is scaled to 0–255, looked up in the palette's 256-entry LUT, and becomes a (24, 32, 3)
   array.
4. **Scaling up.**
   - Smoothing **off**: nearest-neighbour ×12 to 384×288 (the 32×24 blocks).
   - Smoothing **on**: the mockup blurs the 12 px cells by 6 px. To match cheaply, the image is upsampled ×3
     to 96×72, given a separable Gaussian blur (σ = 1.5 px, which is 6 px at full size), then scaled up
     bilinearly to 384×288. That's under 1 ms on a laptop and a few ms on a Pi 2.
5. The scaled image is cached, keyed on (frame, range, palette, smoothing). Overlays (markers, spot, pills,
   strip, column) are redrawn on top from cached text surfaces.
6. **Units** are converted only for display. Everything internal, including the CSV, stays in °C.

## What redraws, and when

The UI loop wakes 20 times a second but only draws when something is "dirty":
- a new frame arrives on the Live view (unless it's held)
- a touch goes down or up
- the sensor status changes
- the Sensor info screen's 1 Hz refresh comes round
- the SAVED label expires

A full redraw plus the framebuffer write is the heavy part. Doing it only when needed leaves the CPU free for
the pure-Python sensor maths.

## Persistence

- **Config:** `~/.config/thermalcam/config.json` is written after every setting change, by writing a temporary
  file, `fsync`, then an atomic rename. Pulling the power can't leave half a file. If the file is unreadable
  anyway, it's renamed to `config.json.bad` and defaults are used, so the camera still boots.
- **Snapshots:** saved to `~/thermalcam/snapshots/`. The PNG is the full screen as shown, and the CSV is the
  displayed frame in °C. Files are only named by date and time once `timedatectl` reports NTP sync, because
  the Pi 2 has no RTC. Before that, they're numbered `snap-NNNN`.

## Where this departs from SPEC.md

| Spec | This implementation | Why |
|---|---|---|
| §2: set the PiTFT up as a framebuffer or console, "follow the current Adafruit guide" | `--install-type=drivers` plus direct framebuffer writes | Mirror mode is refused on Bookworm Lite, and console mode would put the text console on the panel |
| §2: I²C at 1 MHz | 400 kHz by default; `I2C_BAUD=1000000 ./setup.sh` to change it | Your wiring goes through a GPIO multiplexing board with jumper wires; 1 MHz is less forgiving. The pure-Python maths is the bottleneck anyway. |
| §4.3: `MLX90640BAA` = 55°, `BAB` = 110° | `BAA` = **110°×75°**, `BAB` = **55°×35°**; the default is `BAB` | The spec has them swapped (Melexis part numbers: BAA is the wide lens). Pimoroni's standard breakout is 55°. |
| §3: fonts | DejaVu Sans Condensed and Mono, bundled in `fonts/` (Bitstream Vera licence) as well as from apt | So the laptop view matches the device exactly |
| §6: bad-pixel correction "using the driver's correction" | Mean of good 4-neighbours | The Python driver has no correction step; this is the same idea as Melexis' `BadPixelsCorrection` |
| Not in the spec | 3-point calibration runs automatically on first boot | There's no other way to calibrate a device without a keyboard |
| Not in the spec | No power-off control | The design has no place for one. See README "Switching off". |

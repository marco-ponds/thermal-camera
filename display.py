"""Where the finished 480x320 surface goes: the PiTFT framebuffer, or a desktop window.

Both displays deliver pointer events in screen coordinates:
    ("down", x, y)  ("move", x, y)  ("up", x, y)  ("key", pygame_key)  ("quit",)
"""

import glob
import os
import sys

import numpy as np
import pygame

from ui.theme import H, W

_tobytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring


class WindowDisplay:
    """Development: a desktop window, mouse stands in for the touchscreen."""

    touch = None

    def __init__(self, scale=2):
        pygame.display.init()
        self.scale = scale
        self.screen = pygame.display.set_mode((W * scale, H * scale))
        pygame.display.set_caption("Thermal camera")

    def present(self, surface):
        if self.scale == 1:
            self.screen.blit(surface, (0, 0))
        else:
            pygame.transform.scale(surface, self.screen.get_size(), self.screen)
        pygame.display.flip()

    def poll(self):
        out, s = [], self.scale
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                out.append(("quit",))
            elif e.type == pygame.KEYDOWN:
                out.append(("key", e.key))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                out.append(("down", e.pos[0] // s, e.pos[1] // s))
            elif e.type == pygame.MOUSEMOTION and e.buttons[0]:
                out.append(("move", e.pos[0] // s, e.pos[1] // s))
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                out.append(("up", e.pos[0] // s, e.pos[1] // s))
        return out


def _read_sys(path):
    with open(path) as f:
        return f.read().strip()


def find_framebuffer(explicit=None):
    """(dev_path, (w, h), bpp, stride) of the 480x320 framebuffer (or the one named)."""
    found = []
    for d in sorted(glob.glob("/sys/class/graphics/fb[0-9]*")):
        w, h = (int(v) for v in _read_sys(f"{d}/virtual_size").split(","))
        found.append((f"/dev/{os.path.basename(d)}", (w, h), int(_read_sys(f"{d}/bits_per_pixel")),
                      int(_read_sys(f"{d}/stride")), _read_sys(f"{d}/name")))
    for dev, size, bpp, stride, _name in found:
        if dev == explicit or (explicit is None and sorted(size) == [H, W]):
            return dev, size, bpp, stride
    have = ", ".join(f"{d} {n} {s[0]}x{s[1]}" for d, s, _, _, n in found) or "none"
    raise SystemExit(f"No {W}x{H} framebuffer found (have: {have}). "
                     "Did the PiTFT driver install run? Off-device, use --windowed.")


class FramebufferDisplay:
    """The Pi: convert the surface to the framebuffer's pixel format and write it to /dev/fbN.

    Recent SDL2 can't draw to a framebuffer any more, so pygame only renders
    off-screen and this class does the last step with numpy.
    """

    def __init__(self, path, size, bpp, stride, rotate, touch):
        if bpp not in (16, 32):
            raise SystemExit(f"{path}: unsupported {bpp} bits per pixel")
        expected = (H, W) if rotate in (90, 270) else (W, H)
        if size != expected:
            raise SystemExit(f"{path} is {size[0]}x{size[1]}; try --rotate {90 if rotate in (0, 180) else 0}")
        self.path, self.size, self.bpp, self.stride, self.rotate = path, size, bpp, stride, rotate
        self.fd = os.open(path, os.O_RDWR)
        self.touch = touch
        self.calibration = None

    @classmethod
    def open(cls, fb=None, rotate=None, touch_device=None, min_pressure=0):
        from touch import TouchInput
        path, size, bpp, stride = find_framebuffer(fb)
        if rotate is None:
            rotate = 90 if size == (H, W) else 0
        touch = TouchInput.open(touch_device, min_pressure)
        print(f"display: {path} {size[0]}x{size[1]} {bpp}bpp rotate={rotate}", file=sys.stderr)
        return cls(path, size, bpp, stride, rotate, touch)

    def encode(self, surface):
        surf = pygame.transform.rotate(surface, self.rotate) if self.rotate else surface
        w, h = self.size
        rgb = np.frombuffer(_tobytes(surf, "RGB"), np.uint8).reshape(h, w, 3)
        if self.bpp == 16:   # RGB565, little endian
            r, g, b = (rgb[..., i].astype(np.uint16) for i in range(3))
            px = (((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)).view(np.uint8).reshape(h, w * 2)
        else:                # XRGB8888, little endian: B G R X in memory
            px = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0],
                            np.full((h, w), 255, np.uint8)]).reshape(h, w * 4)
        if px.shape[1] != self.stride:
            padded = np.zeros((h, self.stride), np.uint8)
            padded[:, :px.shape[1]] = px
            px = padded
        return px.tobytes()

    def present(self, surface):
        os.pwrite(self.fd, self.encode(surface), 0)

    def poll(self):
        if self.touch is None or self.calibration is None:
            return []
        return [(kind, *self.calibration.map(rx, ry)) for kind, rx, ry in self.touch.poll()]

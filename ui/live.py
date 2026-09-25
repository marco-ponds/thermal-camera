"""Live view (SPEC 4.1): thermal image, overlays, bottom strip, right column."""

import numpy as np
import pygame

from palettes import LUTS
from sensor.base import SENSOR_H, SENSOR_W

from . import theme as T
from .widgets import alpha_rect, button, gradient_bar, icon, render, text_mid, text_width, triangle

IMG = pygame.Rect(0, 0, 384, 288)          # 32x24 sensor x 12
CELL = 12
STRIP = pygame.Rect(0, 288, 384, 32)
COL = pygame.Rect(384, 0, 96, 320)
COL_X, COL_W = 391, 83                     # inside 1 px border + 6 px padding
MAX_BLOCK_Y, SCALE_Y, SCALE_H, MIN_BLOCK_Y = 6, 52, 100, 158
HOLD_BTN = pygame.Rect(COL_X, 204, COL_W, 52)
MENU_BTN = pygame.Rect(COL_X, 262, COL_W, 52)
PILL_W, PILL_H = 72, 39
SAVED_S = 1.5


_KERNEL = np.exp(-0.5 * (np.arange(-4, 5) / 1.5) ** 2)
_KERNEL /= _KERNEL.sum()


def _blur3x(rgb):
    """Upsample 3x (nearest) and Gaussian-blur (sigma 1.5 px = 6 px at full size), edges clamped."""
    up = np.repeat(np.repeat(rgb.astype(np.float32), 3, axis=0), 3, axis=1)
    for axis in (0, 1):
        pad = [(4, 4) if a == axis else (0, 0) for a in range(3)]
        padded = np.pad(up, pad, mode="edge")
        n = up.shape[axis]
        up = sum(k * np.take(padded, range(i, i + n), axis=axis) for i, k in enumerate(_KERNEL))
    return np.clip(up + 0.5, 0, 255).astype(np.uint8)


class LiveScreen:
    def __init__(self, app):
        self.app = app
        self._img = None
        self._img_key = None
        self._bar_key = None
        self._bar = None
        self._pill = pygame.Surface((PILL_W, PILL_H), pygame.SRCALPHA)
        pygame.draw.rect(self._pill, T.SPOT_PILL, self._pill.get_rect(), border_radius=4)
        self._dim = pygame.Surface(IMG.size, pygame.SRCALPHA)
        self._dim.fill((0, 0, 0, 150))

    # ------------------------------------------------------------------ input
    def _save_label(self):
        return "SAVED" if self.app.saved_until > self.app.now else "SAVE PNG"

    def save_rect(self):
        tw = text_width(self.app.fonts("cond_bold", 17), self._save_label(), 17 * 0.06)
        w = 14 + 18 + 8 + tw + 14
        return pygame.Rect(IMG.right - 8 - w, 8, w, 44)

    def targets(self):
        app = self.app
        t = []
        if app.hold:
            t.append(("save", self.save_rect(), lambda pos: app.save_snapshot()))
        t += [("image", IMG, self._place_spot),
              ("hold", HOLD_BTN, lambda pos: app.toggle_hold()),
              ("menu", MENU_BTN, lambda pos: app.go("settings"))]
        return t

    def _place_spot(self, pos):
        x = min(SENSOR_W - 1, max(0, pos[0] // CELL))
        y = min(SENSOR_H - 1, max(0, pos[1] // CELL))
        self.app.set(spot=[x, y])

    # ------------------------------------------------------------------ drawing
    def _thermal_image(self, frame, lo, hi):
        cfg = self.app.cfg
        key = (self.app.shown_version, lo, hi, cfg["palette"], cfg["smoothing"])
        if key != self._img_key:
            norm = (frame - lo) * (255.0 / (hi - lo))
            rgb = LUTS[cfg["palette"]][np.clip(norm, 0, 255).astype(np.uint8)]      # (24, 32, 3)
            if cfg["smoothing"]:
                # The mockup blurs the 12 px cells by 6 px. Doing that at 3x (96x72) and then
                # scaling up bilinearly looks the same and costs a few ms, even on a Pi 2.
                small = pygame.surfarray.make_surface(_blur3x(rgb).swapaxes(0, 1))
                self._img = pygame.transform.smoothscale(small, IMG.size)
            else:
                self._img = pygame.transform.scale(pygame.surfarray.make_surface(rgb.swapaxes(0, 1)), IMG.size)
            self._img_key = key
        return self._img

    def draw(self, c, pressed):
        app, fonts = self.app, self.app.fonts
        c.fill(T.BLACK, IMG)
        frame = app.shown
        if frame is not None:
            lo, hi = app.scale_range(frame)
            c.blit(self._thermal_image(frame, lo, hi), IMG)
            self._draw_markers(c, frame)
            self._draw_spot(c, frame)
            if app.hold:
                self._draw_hold_overlay(c, pressed == "save")

        status = app.worker.status
        if status != "ok" or frame is None:
            if frame is not None:
                c.blit(self._dim, IMG)
            msg = "SENSOR NOT FOUND — RETRYING" if status == "missing" else "STARTING SENSOR…"
            font = fonts("cond_bold", 16)
            w = text_width(font, msg, 16 * 0.06) + 28
            r = pygame.Rect(0, 0, w, 40)
            r.center = IMG.center
            pygame.draw.rect(c, T.PANEL, r, border_radius=8)
            pygame.draw.rect(c, T.BORDER, r, 1, border_radius=8)
            text_mid(c, font, msg, T.ACCENT if status == "missing" else T.TEXT, r.centerx, r.centery,
                     "center", spacing=16 * 0.06)

        self._draw_strip(c)
        self._draw_column(c, frame, pressed)

    def _marker_pos(self, idx):
        row, col = divmod(int(idx), SENSOR_W)
        x = min(IMG.right - 8, max(8, col * CELL + CELL // 2))
        y = min(IMG.bottom - 8, max(8, row * CELL + CELL // 2))
        return x, y

    def _draw_markers(self, c, frame):
        triangle(c, self._marker_pos(frame.argmax()), True, T.MAX_MARKER)
        triangle(c, self._marker_pos(frame.argmin()), False, T.MIN_MARKER)

    def _draw_spot(self, c, frame):
        app, fonts = self.app, self.app.fonts
        sx, sy = app.cfg["spot"]
        px, py = sx * CELL + CELL // 2, sy * CELL + CELL // 2
        bars = [(-15, -1, 10, 2), (5, -1, 10, 2), (-1, -15, 2, 10), (-1, 5, 2, 10)]
        for dx, dy, w, h in bars:
            pygame.draw.rect(c, (20, 20, 20), (px + dx - 1, py + dy - 1, w + 2, h + 2))
        for dx, dy, w, h in bars:
            pygame.draw.rect(c, T.WHITE, (px + dx, py + dy, w, h))
        lx = px - 86 if sx > 24 else px + 14
        ly = py - 50 if sy > 19 else py + 12
        c.blit(self._pill, (lx, ly))
        c.blit(render(fonts("cond_bold", 12), "SPOT", T.TEXT_SOFT, 12 * 0.08), (lx + 6, ly + 3))
        c.blit(render(fonts("mono_bold", 17), app.fmt_temp(float(frame[sy, sx])), T.WHITE), (lx + 6, ly + 17))

    def _draw_hold_overlay(self, c, save_pressed):
        fonts = self.app.fonts
        font = fonts("cond_bold", 14)
        tw = text_width(font, "HOLD", 1.4)
        badge = pygame.Rect(8, 8, tw + 16, 22)
        pygame.draw.rect(c, T.ACCENT, badge, border_radius=4)
        text_mid(c, font, "HOLD", T.ON_ACCENT, badge.x + 8, badge.centery, spacing=1.4)

        r = self.save_rect()
        alpha_rect(c, T.SAVE_BG if not save_pressed else (*T.lighten(T.PANEL), 240), r, radius=8)
        pygame.draw.rect(c, T.BORDER, r, 1, border_radius=8)
        icon(c, "save", (r.x + 14 + 9, r.centery), 18, T.TEXT)
        text_mid(c, fonts("cond_bold", 17), self._save_label(), T.TEXT, r.x + 14 + 18 + 8, r.centery,
                 spacing=17 * 0.06)

    def _draw_strip(self, c):
        app, fonts = self.app, self.app.fonts
        pygame.draw.rect(c, T.PANEL, STRIP)
        pygame.draw.line(c, T.CONTROL, STRIP.topleft, (STRIP.right - 1, STRIP.top))
        lab, val = fonts("cond_bold", 13), fonts("mono", 13)
        ls = 13 * 0.06
        ta = app.worker.ta
        items = [
            [("Ta", lab, T.TEXT_MUTED, ls), (app.fmt_temp(ta) if ta is not None else "—", val, T.TEXT, 0)],
            [("ε", lab, T.TEXT_MUTED, 0), (f"{app.cfg['emissivity']:.2f}", val, T.TEXT, 0)],
            [("RANGE", lab, T.TEXT_MUTED, ls), (app.cfg["range_mode"].upper(), val, T.TEXT, 0)],
            [("PAL", lab, T.TEXT_MUTED, ls), (app.cfg["palette"].upper(), val, T.TEXT, 0)],
        ]
        if app.hold:
            items.append([("FROZEN", val, T.ACCENT, 0)])
        else:
            fps = app.worker.fps
            items.append([(f"{fps:.1f}" if fps else "—", val, T.TEXT, 0), ("FPS", lab, T.TEXT_MUTED, ls)])

        widths = [sum(text_width(f, s, sp) for s, f, _, sp in it) + 5 * (len(it) - 1) for it in items]
        gap = (STRIP.width - 20 - sum(widths)) / (len(items) - 1)
        x, cy = STRIP.x + 10.0, STRIP.y + 16.5
        for it, w in zip(items, widths):
            xx = x
            for s, f, color, sp in it:
                r = text_mid(c, f, s, color, int(round(xx)), cy, spacing=sp)
                xx = r.right + 5
            x += w + gap

    def _draw_column(self, c, frame, pressed):
        app, fonts = self.app, self.app.fonts
        pygame.draw.rect(c, T.PANEL, COL)
        pygame.draw.line(c, T.CONTROL, COL.topleft, (COL.x, COL.bottom - 1))

        fmax = float(frame.max()) if frame is not None else None
        fmin = float(frame.min()) if frame is not None else None
        self._draw_extreme(c, MAX_BLOCK_Y, "MAX", True, T.MAX_MARKER, fmax)
        self._draw_extreme(c, MIN_BLOCK_Y, "MIN", False, T.MIN_MARKER, fmin)

        # colour scale: 16 px gradient with a 1 px border, 5 whole-number ticks
        bar = pygame.Rect(COL_X, SCALE_Y, 16, SCALE_H)
        if self._bar_key != app.cfg["palette"]:
            self._bar = gradient_bar(LUTS[app.cfg["palette"]], (bar.width - 2, bar.height - 2))
            self._bar_key = app.cfg["palette"]
        c.blit(self._bar, (bar.x + 1, bar.y + 1))
        pygame.draw.rect(c, T.BORDER, bar, 1, border_radius=3)
        if frame is not None:
            lo, hi = app.scale_range(frame)
            tick = fonts("mono", 12)
            th = tick.get_height()
            for i, k in enumerate((1.0, 0.75, 0.5, 0.25, 0.0)):
                y = SCALE_Y + i * (SCALE_H - th) / 4
                c.blit(render(tick, f"{app.to_units(lo + (hi - lo) * k):.0f}", T.TEXT_SOFT),
                       (bar.right + 6, int(round(y))))

        hold = app.hold
        button(c, fonts, HOLD_BTN, "HOLD", icon_name="pause", bg=T.ACCENT if hold else T.CONTROL,
               fg=T.ON_ACCENT if hold else T.TEXT, border=T.ACCENT if hold else T.BORDER,
               pressed=pressed == "hold")
        button(c, fonts, MENU_BTN, "MENU", icon_name="menu", pressed=pressed == "menu")

    def _draw_extreme(self, c, top, label, up, color, value):
        fonts = self.app.fonts
        y = top + 1.5                                # 37 px of content centred in the 40 px block
        triangle(c, (COL_X + 5, y + 8), up, color, w=10, h=9, outline=False)
        text_mid(c, fonts("cond_bold", 13), label, T.TEXT_MUTED, COL_X + 14, y + 8, spacing=13 * 0.08)
        text = self.app.fmt_temp(value) if value is not None else "—"
        text_mid(c, fonts("mono_bold", 19), text, T.TEXT, COL_X, y + 26.5)

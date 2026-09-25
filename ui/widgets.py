"""Drawing helpers: text with letter spacing, icons, Button, Segmented, Stepper, ValueRow, header."""

import numpy as np
import pygame

from . import theme as T

_cache = {}


def render(font, s, color, spacing=0.0):
    """Cached text surface. `spacing` is extra px between letters (CSS letter-spacing)."""
    key = (id(font), s, color, spacing)
    surf = _cache.get(key)
    if surf is None:
        if len(_cache) > 1000:
            _cache.clear()
        if not spacing or len(s) < 2:
            surf = font.render(s, True, color)
        else:
            advances = [font.size(ch)[0] for ch in s]
            surf = pygame.Surface((int(sum(advances) + spacing * (len(s) - 1)) + 1, font.get_height()),
                                  pygame.SRCALPHA)
            x = 0.0
            for ch, adv in zip(s, advances):
                surf.blit(font.render(ch, True, color), (int(round(x)), 0))
                x += adv + spacing
        _cache[key] = surf
    return surf


def text_mid(surf, font, s, color, x, cy, align="left", spacing=0.0):
    """Draw text so its cap height is centred on `cy` (what CSS flex centring looks like)."""
    img = render(font, s, color, spacing)
    top = int(round(cy - 0.607 * font.get_ascent()))   # DejaVu: cap centre = 0.607 x ascent
    left = {"left": x, "center": x - img.get_width() // 2, "right": x - img.get_width()}[align]
    surf.blit(img, (left, top))
    return pygame.Rect(left, top, img.get_width(), img.get_height())


def text_width(font, s, spacing=0.0):
    return render(font, s, T.WHITE, spacing).get_width()


def alpha_rect(surf, rgba, rect, radius=0):
    tmp = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(tmp, rgba, tmp.get_rect(), border_radius=radius)
    surf.blit(tmp, rect.topleft)


# --------------------------------------------------------------------------- icons

def icon(surf, name, center, size, color):
    """Icons from the mockups, drawn on a 24-unit grid scaled to `size` px."""
    s = size / 24.0
    ox, oy = center[0] - size / 2, center[1] - size / 2

    def p(x, y):
        return (ox + x * s, oy + y * s)

    def w(stroke):
        return max(1, int(round(stroke * s)))

    if name == "pause":
        for x in (6, 14):
            pygame.draw.rect(surf, color, pygame.Rect(round(ox + x * s), round(oy + 4 * s),
                                                      max(2, round(4 * s)), round(16 * s)))
    elif name == "menu":
        for y in (6, 12, 18):
            pygame.draw.line(surf, color, p(4, y), p(20, y), w(2.4))
    elif name == "chevron_left":
        pygame.draw.lines(surf, color, False, [p(15, 5), p(8, 12), p(15, 19)], w(2.6))
    elif name == "info":
        pygame.draw.circle(surf, color, p(12, 12), round(9 * s), w(2.2))
        pygame.draw.line(surf, color, p(12, 11), p(12, 17), w(2.2))
        pygame.draw.circle(surf, color, p(12, 7.6), max(1, w(2.2) // 2 + 0.5))
    elif name == "camera":
        pygame.draw.rect(surf, color, pygame.Rect(p(3, 6), (13 * s, 12 * s)), w(2.2), border_radius=round(2 * s))
        pygame.draw.lines(surf, color, False, [p(16, 10), p(21, 7), p(21, 17), p(16, 14)], w(2.2))
    elif name == "save":
        pygame.draw.polygon(surf, color, [p(5, 3), p(16, 3), p(19, 6), p(19, 21), p(5, 21)], w(2))
        pygame.draw.lines(surf, color, False, [p(8, 3), p(8, 9), p(16, 9), p(16, 3)], w(2))
        pygame.draw.rect(surf, color, pygame.Rect(p(8, 13), (8 * s, 5 * s)), w(2))
    elif name in ("minus", "plus"):
        pygame.draw.line(surf, color, p(5, 12), p(19, 12), w(2.6))
        if name == "plus":
            pygame.draw.line(surf, color, p(12, 5), p(12, 19), w(2.6))
    else:
        raise ValueError(name)


def triangle(surf, center, up, fill, w=14, h=12, outline=True):
    """Marker triangle (14x12 viewBox from the mockup) centred on `center`."""
    sx, sy = w / 14, h / 12
    pts = [(7, 1), (13, 11), (1, 11)] if up else [(1, 1), (13, 1), (7, 11)]
    pts = [(center[0] - w / 2 + x * sx, center[1] - h / 2 + y * sy) for x, y in pts]
    pygame.draw.polygon(surf, fill, pts)
    if outline:
        pygame.draw.polygon(surf, T.BLACK, pts, 1)


# --------------------------------------------------------------------------- controls

def button(surf, fonts, rect, label, *, icon_name=None, icon_right=False, icon_size=16, bg=T.CONTROL,
           fg=T.TEXT, border=T.BORDER, radius=8, size=17, spacing_em=0.03, gap=6, justify="center",
           pad_l=0, pad_r=0, pressed=False):
    pygame.draw.rect(surf, T.lighten(bg) if pressed else bg, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, 1, border_radius=radius)
    font = fonts("cond_bold", size)
    spacing = size * spacing_em
    tw = text_width(font, label, spacing)
    iw, g = (icon_size, gap) if icon_name else (0, 0)
    total = tw + iw + g
    x = {"center": rect.centerx - total / 2, "left": rect.x + pad_l, "right": rect.right - pad_r - total}[justify]
    cy = rect.centery
    if icon_name and not icon_right:
        icon(surf, icon_name, (x + iw / 2, cy), iw, fg)
        x += iw + g
    text_mid(surf, font, label, fg, int(round(x)), cy, spacing=spacing)
    if icon_name and icon_right:
        icon(surf, icon_name, (x + tw + g + iw / 2, cy), iw, fg)


def segment_rects(rect, n, pad=3, gap=3):
    inner = rect.inflate(-2 * (pad + 1), -2 * (pad + 1))   # 1 px border + padding
    w = (inner.width - gap * (n - 1)) / n
    return [pygame.Rect(round(inner.x + i * (w + gap)), inner.y, round(w), inner.height) for i in range(n)]


def segmented(surf, fonts, rect, labels, selected, font_kind, size, pressed=None):
    pygame.draw.rect(surf, T.PANEL, rect, border_radius=9)
    pygame.draw.rect(surf, T.CONTROL_2, rect, 1, border_radius=9)
    font = fonts(font_kind, size)
    for i, (r, label) in enumerate(zip(segment_rects(rect, len(labels)), labels)):
        on = i == selected
        bg = T.ACCENT if on else None
        if pressed == i:
            bg = T.lighten(bg) if bg else T.CONTROL
        if bg:
            pygame.draw.rect(surf, bg, r, border_radius=6)
        text_mid(surf, font, label, T.ON_ACCENT if on else T.SEGMENT_TEXT, r.centerx, r.centery, "center")


def stepper_rects(rect):
    inner = rect.inflate(-8, -8)
    minus = pygame.Rect(inner.x, inner.centery - 20, 56, 40)
    plus = pygame.Rect(inner.right - 56, inner.centery - 20, 56, 40)
    return minus, plus


def stepper(surf, fonts, rect, value_text, pressed=None):
    pygame.draw.rect(surf, T.PANEL, rect, border_radius=9)
    pygame.draw.rect(surf, T.CONTROL_2, rect, 1, border_radius=9)
    for which, r in zip(("minus", "plus"), stepper_rects(rect)):
        pygame.draw.rect(surf, T.lighten(T.CONTROL_2) if pressed == which else T.CONTROL_2, r, border_radius=6)
        icon(surf, which, r.center, 18, T.TEXT)
    text_mid(surf, fonts("mono_bold", 19), value_text, T.TEXT, rect.centerx, rect.centery, "center")


def value_row(surf, fonts, x, y, w, key, value):
    """Sensor-info key/value row: 27 px tall with a 1 px divider."""
    cy = y + 13
    text_mid(surf, fonts("cond", 15), key, T.TEXT_MUTED, x, cy)
    text_mid(surf, fonts("mono", 13), value, T.TEXT, x + w, cy, "right")
    pygame.draw.line(surf, T.DIVIDER, (x, y + 26), (x + w - 1, y + 26))


# --------------------------------------------------------------------------- header

HEADER_H = 52


def header_rects(fonts, left_label, right_label):
    f = fonts("cond_bold", 18)
    sp = 18 * 0.04
    lw = max(88, 6 + 18 + 4 + text_width(f, left_label, sp) + 10)
    rw = max(88, 10 + text_width(f, right_label, sp) + 6 + 18 + 8)
    return pygame.Rect(6, 4, lw, 44), pygame.Rect(T.W - 6 - rw, 4, rw, 44)


def header(surf, fonts, title, left_label, right_label, right_icon, pressed=None):
    pygame.draw.rect(surf, T.PANEL, (0, 0, T.W, HEADER_H))
    pygame.draw.line(surf, T.CONTROL, (0, HEADER_H - 1), (T.W, HEADER_H - 1))
    left, right = header_rects(fonts, left_label, right_label)
    common = dict(bg=T.CONTROL, border=None, size=18, spacing_em=0.04, icon_size=18)
    button(surf, fonts, left, left_label, icon_name="chevron_left", gap=4, justify="left", pad_l=6,
           pressed=pressed == "left", **common)
    button(surf, fonts, right, right_label, icon_name=right_icon, icon_right=True, gap=6, justify="right",
           pad_r=8, pressed=pressed == "right", **common)
    text_mid(surf, fonts("cond_bold", 22), title, T.TEXT, T.W // 2, HEADER_H // 2, "center", spacing=22 * 0.06)


def gradient_bar(lut, size):
    """Vertical palette gradient, hot at the top."""
    column = lut[::-1][np.newaxis, :, :]               # (1, 256, 3) as (x, y, rgb)
    return pygame.transform.smoothscale(pygame.surfarray.make_surface(column), size)

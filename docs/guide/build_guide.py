#!/usr/bin/env python3
"""Builds docs/Thermal_Camera_Wiring_and_Setup_Guide.pdf (A4, greyscale-friendly for e-ink).

    python3 docs/guide/build_guide.py          # needs: pip install reportlab pillow

Screenshots come from docs/*.png (regenerate those with main.py --screenshot).
Edit the text here, not the PDF.
"""

import datetime
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (CondPageBreak, Flowable, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
OUT = os.path.join(DOCS, "Thermal_Camera_Wiring_and_Setup_Guide.pdf")
REPO = "github.com/marco-ponds/thermal-camera"
UPDATED = "26 September 2026"

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
FRAME_W = PAGE_W - 2 * MARGIN

BLACK = colors.black
INK = colors.HexColor("#222222")
MID = colors.HexColor("#666666")
SOFT = colors.HexColor("#999999")
RULE = colors.HexColor("#CCCCCC")
TINT = colors.HexColor("#EEEEEE")
WHITE = colors.white

# ------------------------------------------------------------------ styles

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK, spaceAfter=5)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=11, textColor=MID)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11.5, spaceAfter=0)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Helvetica-Bold")
HEAD = ParagraphStyle("head", parent=CELL, textColor=MID)
TITLE = ParagraphStyle("title", fontName="Helvetica", fontSize=28, leading=32, textColor=BLACK, spaceAfter=4)
SUB = ParagraphStyle("sub", parent=BODY, fontSize=11.5, leading=15, textColor=MID, spaceAfter=10)
H1 = ParagraphStyle("h1", fontName="Helvetica", fontSize=17, leading=21, textColor=BLACK, spaceBefore=10,
                    spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="Helvetica", fontSize=12.5, leading=16, textColor=BLACK, spaceBefore=8,
                    spaceAfter=4, keepWithNext=1)
STEP = ParagraphStyle("step", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=BLACK)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8.3, leading=11, textColor=BLACK)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=10, bulletIndent=0, spaceAfter=3)


def p(text, style=BODY):
    return Paragraph(text, style)


def bullets(items):
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def code(text):
    t = Table([[Preformatted(text.strip("\n"), CODE)]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def callout(text):
    t = Table([[Paragraph(text, CELL)]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, BLACK),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def table(rows, widths, header=True, bold_first=False, mono_cols=()):
    """rows: list of lists of str (or flowables). widths: fractions of the frame width."""
    data = []
    for i, row in enumerate(rows):
        body = not (header and i == 0)
        cells = []
        for j, c in enumerate(row):
            if isinstance(c, Flowable):
                cells.append(c)
                continue
            style = CELL_B if (bold_first and j == 0 and body) else (CELL if body else HEAD)
            if body and j in mono_cols:
                c = f"<font face='Courier' size='8'>{c}</font>"
            cells.append(Paragraph(c, style))
        data.append(cells)
    t = Table(data, colWidths=[w * FRAME_W for w in widths], repeatRows=1 if header else 0)
    cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        cmds.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, MID))
    t.setStyle(TableStyle(cmds))
    return t


def step(n, title):
    t = Table([[Paragraph(f"<font color='white'>{n}</font>", ParagraphStyle("n", parent=STEP, alignment=TA_CENTER)),
                Paragraph(title, STEP)]], colWidths=[7 * mm, FRAME_W - 7 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), BLACK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (0, 0), 0), ("RIGHTPADDING", (0, 0), (0, 0), 0),
                           ("LEFTPADDING", (1, 0), (1, 0), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# ------------------------------------------------------------------ drawings

class Drawing(Flowable):
    """Base: subclasses implement draw_at(c) with (0,0) at the bottom-left of the box."""

    def __init__(self, height, width=FRAME_W):
        super().__init__()
        self.width, self.height = width, height

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        self.draw_at(c)
        c.restoreState()


def box(c, x, y, w, h, title, sub=None, fill=INK, text=WHITE, radius=3):
    c.setFillColor(fill)
    c.setStrokeColor(fill)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
    c.setFillColor(text)
    c.setFont("Helvetica", 10)
    ty = y + h / 2 + (2 if sub else -3.5)
    c.drawCentredString(x + w / 2, ty, title)
    if sub:
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(x + w / 2, y + h / 2 - 9, sub)


WIRES = [  # (sensor pin, header label, pin number, wire name, dash pattern)
    ("2-6V", "3.3V", 1, "red", []),
    ("SDA", "SDA", 3, "blue", [5, 3]),
    ("SCL", "SCL", 5, "yellow", [1.2, 2.4]),
    ("GND", "GND", 9, "black", [6, 2.5, 1.2, 2.5]),
]


class StackDiagram(Drawing):
    """Section 2: what plugs onto what."""

    def __init__(self):
        super().__init__(62 * mm)

    def draw_at(self, c):
        w = FRAME_W
        box(c, 0, 4 * mm, 92 * mm, 13 * mm, "Raspberry Pi 2 Model B", "40-pin GPIO header", fill=INK)
        box(c, 12 * mm, 22 * mm, 68 * mm, 11 * mm, "Easy Multiplexing Board", "4 identical copies of the header",
            fill=MID)
        box(c, 0, 42 * mm, 62 * mm, 14 * mm, "Adafruit PiTFT 3.5\"", "plugs onto one block (all 40 pins)", fill=INK)
        box(c, w - 58 * mm, 42 * mm, 58 * mm, 14 * mm, "Pimoroni MLX90640", "thermal camera breakout", fill=INK)
        c.setStrokeColor(MID)
        c.setDash([2, 2])
        c.line(31 * mm, 42 * mm, 31 * mm, 33 * mm)
        c.line(46 * mm, 22 * mm, 46 * mm, 17 * mm)
        c.setDash([])
        # four wires from the sensor down to the rightmost block
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        for i, (_s, _l, _n, _name, dash) in enumerate(WIRES):
            c.setDash(dash)
            x0 = w - 50 * mm + i * 4 * mm
            y1 = 30.5 * mm - i * 2 * mm
            c.line(x0, 42 * mm, x0, y1)
            c.line(x0, y1, 78 * mm, y1)
        c.setDash([])
        c.setFillColor(INK)
        c.setFont("Helvetica", 8.5)
        c.drawString(97 * mm, 19 * mm, "Rightmost block: 4 jumper wires")
        c.setFillColor(MID)
        c.setFont("Helvetica", 7.5)
        c.drawString(97 * mm, 14.5 * mm, "pins 1, 3, 5, 9 = power, I2C data, I2C clock, ground")


class WiringDiagram(Drawing):
    """Section 3: sensor pins to the labelled column of the rightmost block."""

    ROW = 9 * mm

    def __init__(self):
        super().__init__(66 * mm)

    def draw_at(self, c):
        top = self.height - 14 * mm
        # sensor breakout
        sx, sw = 0, 34 * mm
        sensor_pins = ["2-6V", "SDA", "SCL", "INT", "GND"]
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(sx, self.height - 6 * mm, "Pimoroni MLX90640 (pins as printed)")
        c.setStrokeColor(INK)
        c.setLineWidth(1)
        c.roundRect(sx, top - 4 * self.ROW - 7 * mm, sw, 4 * self.ROW + 12 * mm, 3, fill=0, stroke=1)
        c.circle(sx + 10 * mm, top - 2 * self.ROW, 5 * mm, fill=0, stroke=1)
        c.setFont("Helvetica", 6.5)
        c.drawCentredString(sx + 10 * mm, top - 2 * self.ROW - 8.5 * mm, "sensor")
        pin_y = {}
        for i, name in enumerate(sensor_pins):
            y = top - i * self.ROW
            pin_y[name] = y
            c.setFillColor(INK)
            c.circle(sx + sw - 4 * mm, y, 1.6 * mm, fill=1, stroke=0)
            c.setFont("Helvetica", 8)
            c.drawRightString(sx + sw - 7 * mm, y - 3, name)

        # rightmost block of the multiplexing board: labels | odd column | even column
        bx = FRAME_W - 44 * mm
        labels = ["3.3V", "SDA", "SCL", "GCLK", "GND"]
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bx - 20 * mm, self.height - 6 * mm, "Multiplexing board, rightmost block")
        c.setStrokeColor(RULE)
        c.roundRect(bx - 1.5 * mm, top - 4 * self.ROW - 7 * mm, 17 * mm, 4 * self.ROW + 12 * mm, 2, fill=0, stroke=1)
        target = {}
        for i, lab in enumerate(labels):
            y = top - i * self.ROW
            odd = 2 * i + 1
            target[lab] = (bx + 3 * mm, y)
            c.setFillColor(BLACK if lab != "GCLK" else WHITE)
            c.setStrokeColor(BLACK)
            c.circle(bx + 3 * mm, y, 2.2 * mm, fill=1, stroke=1)
            c.setFillColor(WHITE if lab != "GCLK" else BLACK)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(bx + 3 * mm, y - 2.2, str(odd))
            c.setFillColor(WHITE)
            c.setStrokeColor(SOFT)
            c.circle(bx + 11 * mm, y, 2.2 * mm, fill=1, stroke=1)
            c.setFillColor(SOFT)
            c.setFont("Helvetica", 6.5)
            c.drawCentredString(bx + 11 * mm, y - 2.2, str(odd + 1))
        c.setFillColor(MID)
        c.setFont("Helvetica", 7)
        c.drawCentredString(bx + 7 * mm, top - 4 * self.ROW - 11 * mm, "top of the board = pin 1")
        c.drawString(bx + 17 * mm, top + 1.5 * mm, "even pins")
        c.drawString(bx + 17 * mm, top - 2 * mm, "(5V, GND...)")
        c.drawString(bx + 17 * mm, top - 5.5 * mm, "don't use")

        # wires first, then the printed labels on top of them (as on the board)
        c.setLineWidth(1.2)
        for sensor_pin, lab, n, name, dash in WIRES:
            x0, y0 = sx + sw - 4 * mm, pin_y[sensor_pin]
            x1, y1 = target[lab]
            c.setStrokeColor(BLACK)
            c.setDash(dash)
            c.line(x0, y0, x1 - 2.2 * mm, y1)
            c.setDash([])
            c.setFillColor(INK)
            c.setFont("Helvetica", 7.5)
            c.drawString(x0 + 5 * mm, y0 + 2.2 * mm, f"{name} wire: {sensor_pin} to {lab} (pin {n})")
        c.setFillColor(MID)
        c.setFont("Helvetica", 7.5)
        c.drawString(sx + sw + 1 * mm, pin_y["INT"] + 2.2 * mm, "INT: leave unconnected")
        for i, lab in enumerate(labels):
            y = top - i * self.ROW
            c.setFillColor(WHITE)
            c.rect(bx - 12.5 * mm, y - 2.3 * mm, 10 * mm, 4.6 * mm, fill=1, stroke=0)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawRightString(bx - 3 * mm, y - 2.6, lab)


PIN_LABELS = [
    ("3V3", "5V"), ("GPIO2 SDA", "5V"), ("GPIO3 SCL", "GND"), ("GPIO4", "GPIO14 TXD"), ("GND", "GPIO15 RXD"),
    ("GPIO17", "GPIO18"), ("GPIO27", "GND"), ("GPIO22", "GPIO23"), ("3V3", "GPIO24"), ("GPIO10 MOSI", "GND"),
    ("GPIO9 MISO", "GPIO25"), ("GPIO11 SCLK", "GPIO8 CE0"), ("GND", "GPIO7 CE1"), ("ID_SD", "ID_SC"),
    ("GPIO5", "GND"), ("GPIO6", "GPIO12"), ("GPIO13", "GND"), ("GPIO19", "GPIO16"), ("GPIO26", "GPIO20"),
    ("GND", "GPIO21"),
]
USED_BY = {1: "Camera 2-6V (red wire)", 3: "Camera SDA (blue wire)", 5: "Camera SCL (yellow wire)",
           9: "Camera GND (black wire)", 2: "PiTFT power", 4: "PiTFT power", 17: "PiTFT power",
           19: "PiTFT SPI data out", 21: "PiTFT SPI data in", 23: "PiTFT SPI clock", 18: "PiTFT touch interrupt",
           22: "PiTFT data/command", 24: "PiTFT display select", 26: "PiTFT touch select",
           12: "PiTFT backlight (optional)"}
CAMERA = {1, 3, 5, 9}
PITFT = {18, 19, 21, 22, 23, 24, 26, 12}


class HeaderMap(Drawing):
    ROW = 5.6 * mm

    def __init__(self):
        super().__init__(20 * 5.6 * mm + 18 * mm)

    def pin_style(self, n, label):
        if "3V3" in label:
            return colors.HexColor("#BBBBBB"), BLACK
        if label == "5V":
            return colors.HexColor("#555555"), WHITE
        if label == "GND":
            return BLACK, WHITE
        if n in (3, 5):
            return WHITE, BLACK
        if n in PITFT:
            return colors.HexColor("#DDDDDD"), BLACK
        return WHITE, SOFT

    def draw_at(self, c):
        cx = FRAME_W / 2
        top = self.height - 12 * mm
        c.setFillColor(MID)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(cx, self.height - 5 * mm, "Odd pins in the left column, even pins in the right, pin 1 at the top")
        for r, (left, right) in enumerate(PIN_LABELS):
            y = top - r * self.ROW
            for n, label, x, side in ((2 * r + 1, left, cx - 3.2 * mm, -1), (2 * r + 2, right, cx + 3.2 * mm, 1)):
                fill, ink = self.pin_style(n, label)
                c.setStrokeColor(BLACK if fill != WHITE or n in (3, 5) else SOFT)
                c.setFillColor(fill)
                c.setLineWidth(0.8)
                c.circle(x, y, 2.3 * mm, fill=1, stroke=1)
                if n in CAMERA:
                    c.setStrokeColor(BLACK)
                    c.setLineWidth(1)
                    c.circle(x, y, 3.1 * mm, fill=0, stroke=1)
                c.setFillColor(ink)
                c.setFont("Helvetica-Bold" if ink != SOFT else "Helvetica", 6)
                c.drawCentredString(x, y - 2.1, str(n))
                c.setFillColor(INK)
                c.setFont("Helvetica", 7.5)
                if side < 0:
                    c.drawRightString(x - 5.5 * mm, y - 2.6, label)
                    if n in USED_BY:
                        c.setFillColor(MID)
                        c.drawRightString(x - 30 * mm, y - 2.6, USED_BY[n])
                else:
                    c.drawString(x + 5.5 * mm, y - 2.6, label)
                    if n in USED_BY:
                        c.setFillColor(MID)
                        c.drawString(x + 30 * mm, y - 2.6, USED_BY[n])
        # legend
        y = 3 * mm
        items = [(colors.HexColor("#BBBBBB"), "3.3V"), (colors.HexColor("#555555"), "5V"), (BLACK, "Ground"),
                 (WHITE, "I2C (camera)"), (colors.HexColor("#DDDDDD"), "PiTFT signals"), (None, "Ring = camera wire")]
        x = 4 * mm
        for fill, text in items:
            c.setStrokeColor(BLACK)
            c.setLineWidth(0.8)
            if fill is None:
                c.circle(x, y + 1.5 * mm, 1.6 * mm, fill=0, stroke=1)
                c.circle(x, y + 1.5 * mm, 2.4 * mm, fill=0, stroke=1)
            else:
                c.setFillColor(fill)
                c.circle(x, y + 1.5 * mm, 2 * mm, fill=1, stroke=1)
            c.setFillColor(INK)
            c.setFont("Helvetica", 7.5)
            c.drawString(x + 4 * mm, y + 0.3 * mm, text)
            x += 30 * mm


class Screenshot(Drawing):
    """A 480x320 app screenshot with numbered callouts at (x, y) in screen pixels."""

    def __init__(self, path, width, callouts=()):
        super().__init__(width * 320 / 480, width)
        self.path, self.callouts = path, callouts

    def draw_at(self, c):
        c.drawImage(self.path, 0, 0, self.width, self.height)
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.6)
        c.rect(0, 0, self.width, self.height, fill=0, stroke=1)
        s = self.width / 480
        for n, (x, y) in self.callouts:
            px, py = x * s, self.height - y * s
            c.setFillColor(WHITE)
            c.setStrokeColor(BLACK)
            c.setLineWidth(1)
            c.circle(px, py, 3.4 * mm, fill=1, stroke=1)
            c.setFillColor(BLACK)
            c.setFont("Helvetica-Bold", 9)
            c.drawCentredString(px, py - 3.2, str(n))


def shot(name):
    return os.path.join(DOCS, name)


# ------------------------------------------------------------------ content

def story():
    s = []
    s += [p("Thermal Camera", TITLE),
          p("Wiring and setup guide for a Pimoroni MLX90640, a Raspberry Pi 2 Model B and an Adafruit PiTFT 3.5\" "
            "touchscreen. The camera app starts by itself at every boot.", SUB),
          p(f"Updated {UPDATED}, after the first build on real hardware. Matches the code at <b>{REPO}</b>.", SMALL)]

    # 1. Parts
    s += [p("1. Parts", H1), table([
        ["Part", "Job", "How it connects"],
        ["Raspberry Pi 2 Model B", "Runs the camera app", "Power bank via micro-USB"],
        ["Easy Multiplexing Board (52Pi)", "Four identical copies of the 40-pin header", "Stacks on the Pi's header"],
        ["Adafruit PiTFT 3.5\" (480x320, resistive touch)", "Screen and touch input",
         "Plugs onto one block of the multiplexing board (SPI)"],
        ["Pimoroni MLX90640 breakout", "32x24 pixel thermal camera", "4 jumper wires to the rightmost block (I2C)"],
        ["4 female-female jumper wires", "Sensor wiring", "Sensor pins to the multiplexing board"],
        ["SanDisk 32GB microSD", "Operating system and app", "Pi's microSD slot"],
        ["USB Wi-Fi dongle", "Network for setup, SSH and copying snapshots", "Any USB port"],
        ["Power bank + short micro-USB cable", "Power: 5 V from a port rated 2 A or more (section 9)",
         "Pi's micro-USB power socket"],
    ], [0.34, 0.33, 0.33])]

    # 2. How it fits together
    s += [p("2. How it fits together", H1),
          p("The screen and the camera use different buses, so they never compete for pins. The PiTFT uses SPI plus "
            "two control pins; the camera uses I2C on pins 3 and 5, which the PiTFT leaves free. The multiplexing "
            "board repeats the whole header four times, so every block has the same pins in the same places."),
          StackDiagram(), Spacer(1, 4 * mm),
          callout("<b>Always wire with the power off.</b> Unplug the power bank before connecting or moving jumper "
                  "wires or the screen. A wire slipping onto a 5V pin while powered is the easiest way to damage the "
                  "sensor or the Pi.")]

    # 3. Wiring
    s += [PageBreak(), p("3. Wiring the camera", H1),
          p("Use the <b>rightmost block</b> of the multiplexing board. Its printed labels read, from the top, "
            "<b>3.3V, SDA, SCL, GCLK, GND</b>, and they belong to the column of pins right next to them (the odd "
            "pins 1, 3, 5, 7, 9). Wire the 1st, 2nd, 3rd and 5th pins of that column. Each wire is drawn with its "
            "own line style so the drawing still reads in greyscale; the colours are only suggestions."),
          WiringDiagram(), Spacer(1, 2 * mm),
          table([
              ["Sensor pin", "Board label", "Pi pin", "Wire (line)", "Notes"],
              ["2-6V", "3.3V", "1", "Red (solid)", "Always 3.3V, never 5V: with 5V the sensor's I2C lines would sit "
                                                   "at 5V, which can damage the Pi."],
              ["SDA", "SDA", "3", "Blue (dashed)", "GPIO2, I2C data"],
              ["SCL", "SCL", "5", "Yellow (dotted)", "GPIO3, I2C clock"],
              ["INT", "", "", "", "Not needed. Leave it unconnected."],
              ["GND", "GND", "9", "Black (dash-dot)", "Any GND pin works (6 and 9 are nearest). It must be a GND "
                                                      "pin: on the first build this wire was on a GPIO pin and the "
                                                      "sensor didn't show up at all."],
          ], [0.13, 0.13, 0.08, 0.17, 0.49]),
          p("Using a different block", H2),
          p("Every block carries the same pins, but the labels sit beside different columns:"),
          *bullets(["<b>Rightmost block:</b> the labelled column (next to 3.3V / SDA / SCL / GCLK / GND).",
                    "<b>Leftmost block:</b> the <b>outer, unlabelled</b> column. The labels printed beside it "
                    "(5V, 5V, GND, TXD0...) belong to its inner column, the even pins, which the sensor must not use.",
                    "<b>Middle blocks:</b> the column with 3.3V, IO2, IO3, IO4, GND next to it."]),
          p("If you're unsure, check with a multimeter before connecting the sensor: with the Pi on, the top pin of "
            "the right column reads about 3.3 V against a GND pin. 5 V means you're on the wrong column.", SMALL),
          p("Checklist before powering on", H2),
          *bullets(["The PiTFT covers a whole 2x20 block, the right way round, not shifted by a row.",
                    "The red wire is on 3.3V (pin 1), not on a 5V pin.",
                    "The black wire is on a pin labelled GND.",
                    "The pin names printed on your breakout match the table. If they differ, go by name "
                    "(2-6V, SDA, SCL, GND), not by position."]),
          p("Mounting the sensor", H2),
          p("The sensor sees a 4:3 landscape picture, like the screen. Mount it so that, holding the camera "
            "upright, the picture is upright. If you find yourself tilting the camera to see things the right way "
            "up, turn the sensor board on its mount by the same amount (on the first build that was 90° clockwise). "
            "The software can mirror the picture but not rotate it.")]

    # 4. Header map
    s += [CondPageBreak(215 * mm), p("4. Full header map", H1),
          p("Every pin of the 40-pin header, shaded by what uses it. The PiTFT plugs straight on, so you never wire "
            "its pins by hand; this map shows there's no overlap with the camera."),
          HeaderMap(), Spacer(1, 3 * mm),
          table([
              ["Pin(s)", "Signal", "Used by", "Purpose"],
              ["3, 5", "GPIO2 SDA, GPIO3 SCL", "Camera", "I2C bus (sensor address 0x33)"],
              ["19, 21, 23", "GPIO10 MOSI, GPIO9 MISO, GPIO11 SCLK", "PiTFT", "SPI bus for display and touch"],
              ["24 / 26", "GPIO8 CE0 / GPIO7 CE1", "PiTFT", "Display chip select / touch controller chip select"],
              ["22", "GPIO25", "PiTFT", "Display data/command line"],
              ["18", "GPIO24", "PiTFT", "Touch interrupt"],
              ["12", "GPIO18", "PiTFT (optional)", "Backlight dimming, only if you enable it"],
              ["1, 17 / 2, 4 / GND", "3.3V / 5V / ground", "Both", "Power pins are shared; that's normal"],
          ], [0.17, 0.33, 0.16, 0.34]),
          p("PiTFT pins are from Adafruit's published pinout for the 3.5\" resistive PiTFT.", SMALL)]

    # 5. Software setup
    s += [PageBreak(), p("5. Software setup", H1),
          p("You do this once. Steps 1 and 2 happen at the bench; the rest runs over SSH from your laptop. "
            "Replace &lt;user&gt; with the username you choose in step 1.")]
    s += [KeepTogether([step(1, "Flash the microSD card"), Spacer(1, 2 * mm),
          p("In Raspberry Pi Imager choose device <b>Raspberry Pi 2</b>, operating system <b>Raspberry Pi OS Lite "
            "(32-bit)</b> (under \"Raspberry Pi OS (other)\"), and your SD card. In OS customisation set:"),
          *bullets(["Hostname: <b>thermalcam</b>", "A username and password",
                    "Your Wi-Fi name and password, wireless country GB",
                    "Enable SSH with password authentication"])])]
    s += [KeepTogether([step(2, "Assemble and power on"), Spacer(1, 2 * mm),
          p("With everything unplugged: multiplexing board on the Pi, PiTFT on one block, camera wired to the "
            "rightmost block (section 3), Wi-Fi dongle and SD card in. Then connect the power bank."),
          *bullets(["The PiTFT stays <b>plain white</b> until its driver is installed in step 5. That's expected.",
                    "<b>First boot takes 2 to 5 minutes</b> and the Pi reboots itself once. Later boots take "
                    "30 to 60 seconds.",
                    "Red LED steady = power OK. Green LED flickering = reading the SD card; mostly dark = booted. "
                    "A regular repeating flash pattern is an error code (usually a bad SD card)."])])]
    s += [KeepTogether([step(3, "Connect over SSH"), Spacer(1, 2 * mm),
          p("From your laptop. The white screen tells you nothing, so check over the network:"),
          code("ping thermalcam.local          # Ctrl+C once it answers\nssh <user>@thermalcam.local"),
          p("If ping never answers after 5 minutes, it's usually the Wi-Fi details in Imager or the dongle. Your "
            "router's list of connected devices shows whether the Pi joined.", SMALL)])]
    s += [KeepTogether([step(4, "Get the code"), Spacer(1, 2 * mm), p("On the Pi:"),
          code("sudo apt-get update\nsudo apt-get install -y git\n"
               "git clone https://github.com/marco-ponds/thermal-camera.git\ncd thermal-camera")])]
    s += [KeepTogether([step(5, "Run the setup script"), Spacer(1, 2 * mm),
          code("./setup.sh"),
          p("Run it as your normal user (not with sudo); it asks for your password once. It takes 15 to 30 minutes "
            "on a Pi 2 and ends with \"Done. Reboot now\". It:"),
          *bullets(["installs pygame, numpy, evdev, i2c-tools and the DejaVu fonts",
                    "creates the Python environment with Blinka and the MLX90640 library",
                    "installs the <b>PiTFT screen driver</b> with Adafruit's installer "
                    "(<font face='Courier'>--display=35r --rotation=90 --install-type=drivers</font>)",
                    "loads the <b>touchscreen driver</b> (<font face='Courier'>stmpe_ts</font>) now and at every boot",
                    "turns on I2C at 400 kHz",
                    "installs the <b>thermalcam</b> service, which starts the app at boot and keeps the text console "
                    "off the screen"])])]
    s += [callout("<b>Why not HDMI mirror mode?</b> Older instructions (including an earlier version of this guide) "
                  "used <font face='Courier'>--install-type=mirror</font>. Adafruit's installer refuses that on "
                  "current Raspberry Pi OS Lite, so the driver is installed on its own and the app draws straight "
                  "onto the screen."), Spacer(1, 3 * mm)]
    s += [KeepTogether([step(6, "Reboot and calibrate the touchscreen"), Spacer(1, 2 * mm),
          code("sudo reboot"),
          p("After about a minute the PiTFT shows <b>three crosses, one at a time</b>. Tap the centre of each "
            "firmly with a fingernail or stylus. Then the Live view appears. From now on the app starts by itself "
            "at every boot.")])]
    s += [KeepTogether([step(7, "Check it works"), Spacer(1, 2 * mm), p("SSH back in and run:"),
          code("i2cdetect -y 1                      # the grid shows 33 = sensor found\n"
               "systemctl status thermalcam         # \"active (running)\"\n"
               "journalctl -u thermalcam -b | tail  # which screen and touchscreen it found\n"
               "vcgencmd get_throttled              # throttled=0x0 = power is fine"),
          p("If anything is off, see section 10.", SMALL)])]

    # 6. Using the camera
    s += [PageBreak(), p("6. Using the camera", H1), p("Live view", H2),
          Screenshot(shot("01-live-iron.png"), FRAME_W * 0.72,
                     [(1, (70, 250)), (2, (262, 150)), (3, (12, 30)), (4, (320, 236)), (5, (462, 70)),
                      (6, (398, 212)), (7, (398, 270)), (8, (250, 285))]),
          Spacer(1, 3 * mm),
          table([
              ["", "What it is"],
              ["1", "The thermal image. Tap anywhere on it to move the spot meter to that pixel (it's remembered)."],
              ["2", "Spot meter: crosshair and SPOT reading."],
              ["3 / 4", "Coldest point (down-pointing triangle) and hottest point (up-pointing triangle)."],
              ["5", "MAX and MIN of the whole frame, with the colour scale and 5 ticks in between."],
              ["6", "HOLD: freeze the picture. Tap again to go live."],
              ["7", "MENU: open Settings."],
              ["8", "Strip: Ta (sensor chip temperature), e (emissivity), RANGE (AUTO or LOCK), PAL (palette) and "
                    "frames per second."],
          ], [0.08, 0.92])]
    s += [CondPageBreak(95 * mm), p("Hold and save", H2),
          Table([[Screenshot(shot("02-live-hold.png"), FRAME_W * 0.5),
                  [p("While held, the image is frozen, a <b>HOLD</b> badge shows top-left, the strip reads "
                     "<b>FROZEN</b>, and a <b>SAVE PNG</b> button appears."),
                   p("SAVE writes two files to <font face='Courier'>~/thermalcam/snapshots/</font>:"),
                   *bullets(["<font face='Courier'>YYYYMMDD-HHMMSS.png</font>: the screen as shown",
                             "<font face='Courier'>...-raw.csv</font>: 24 rows x 32 columns of °C"]),
                   p("The Pi 2 has no clock battery, so until it has synced the time over Wi-Fi the files are "
                     "numbered <font face='Courier'>snap-0001</font>, <font face='Courier'>snap-0002</font>...",
                     SMALL)]]],
                colWidths=[FRAME_W * 0.53, FRAME_W * 0.47],
                style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])]
    s += [PageBreak(), p("Settings", H2),
          Screenshot(shot("05-settings.png"), FRAME_W * 0.62), Spacer(1, 3 * mm),
          p("Every change applies immediately and is kept after a reboot. <b>SENSOR</b> (top right) opens "
            "Sensor info; <b>LIVE</b> (top left) goes back."),
          table([
              ["Setting", "Options", "What it does"],
              ["Palette", "Iron / Rainbow / Grey", "The colour map. Grey reads best on e-ink screenshots."],
              ["Temperature range", "Auto / Lock", "Lock fixes the colour scale at the current min and max, so the "
                                                   "same colour means the same temperature in every room."],
              ["Sensor rate", "2 / 4 / 8 / 16 Hz", "The sensor's half-frame rate; full images arrive at half this "
                                                   "(shown as approx. N fps). A Pi 2 manages about 1 to 4 fps "
                                                   "whatever you pick."],
              ["Units", "°C / °F", "Every temperature on every screen."],
              ["Emissivity", "0.10 to 1.00", "0.95 suits paint, plaster, wood, fabric and skin."],
              ["Smoothing", "Off / On", "Raw 32x24 blocks, or a smooth blurred picture."],
          ], [0.2, 0.2, 0.6], bold_first=True)]
    s += [CondPageBreak(110 * mm), p("Sensor info", H2),
          Screenshot(shot("06-sensor-info.png"), FRAME_W * 0.62), Spacer(1, 3 * mm),
          p("Refreshed about once a second. <b>BACK</b> returns to Settings, <b>LIVE</b> to the camera. "
            "Anything that can't be read shows a dash."),
          table([
              ["Field", "Meaning"],
              ["Model / Field of view", "MLX90640BAB = 55° x 35° (Pimoroni's standard), BAA = 110° x 75° (wide). "
                                        "The sensor can't report its lens, so this comes from the config file."],
              ["Bus speed", "The I2C clock actually in use (400 kHz)."],
              ["Device ID", "The sensor's unique serial number."],
              ["Bad pixels", "Faulty pixels listed in the sensor's memory (up to 4 is within spec). They're filled "
                             "in from their neighbours."],
              ["Die temp (Ta)", "The sensor chip's own temperature. It sits above room temperature and isn't a "
                                "scene reading."],
              ["Supply (Vdd)", "The sensor's supply voltage. Close to 3.3 V is right."],
              ["ADC / Readout / Subpage", "Read live from the sensor: ADC resolution, readout pattern and "
                                          "half-frame rate."],
              ["Frames / dropped", "Frames read since the app started, and failed reads. A few dropped frames are "
                                   "normal; lots point to a loose wire."],
          ], [0.28, 0.72], bold_first=True)]

    # 7. Finding cold spots
    s += [PageBreak(), p("7. Finding cold spots", H1),
          *bullets(["<b>Pick a cold day.</b> You need about a 10 °C difference between inside and outside for "
                    "draughts and missing insulation to show clearly.",
                    "<b>Lock the range in a normal room first</b>, then walk around. With auto range every room "
                    "looks like it has a cold spot, because the colours stretch to fit whatever is in view.",
                    "<b>Check the usual suspects:</b> window and door frames, skirting boards, where walls meet the "
                    "ceiling, pipes and cables through walls, loft hatches, sockets on outside walls.",
                    "<b>Don't trust glass or shiny surfaces.</b> Windows, mirrors, tiles and metal reflect heat "
                    "from elsewhere (often you). Aim at the frame, not the pane.",
                    "<b>Get close.</b> With 32x24 pixels each pixel covers more wall the further away you stand. "
                    "Scan from 1 to 2 metres, and move the spot meter onto anything suspicious."])]

    # 8. Everyday commands
    s += [p("8. Everyday commands", H1), p("On the Pi over SSH (<font face='Courier'>ssh &lt;user&gt;@thermalcam.local"
                                           "</font>), unless noted."),
          table([
              ["To do this", "Run"],
              ["Shut down safely before unplugging", "sudo poweroff"],
              ["See the app's log", "journalctl -u thermalcam -f"],
              ["Stop / start / restart the app", "sudo systemctl stop | start | restart thermalcam"],
              ["Run it by hand (stop the service first)", "cd ~/thermal-camera && .venv/bin/python main.py"],
              ["Test the screen without the sensor", "add --fake-sensor to the command above"],
              ["Redo the touch calibration", "add --calibrate to the command above"],
              ["Update to the latest code", "cd ~/thermal-camera && git pull && SKIP_PITFT=1 ./setup.sh "
                                           "&& sudo reboot"],
              ["Copy snapshots to your laptop (on the laptop)", "scp '&lt;user&gt;@thermalcam.local:thermalcam/"
                                                              "snapshots/*' ."],
          ], [0.38, 0.62], mono_cols=(1,)),
          Spacer(1, 3 * mm),
          callout("<b>Shut down before unplugging the power bank</b> when you can. The settings file is written "
                  "safely, but cutting power while the Pi writes is the usual cause of a corrupted SD card. Wait "
                  "for the green light to stop flashing, then unplug."),
          p("The config file", H2),
          p("Most settings are on the Settings screen. A few live only in "
            "<font face='Courier'>~/.config/thermalcam/config.json</font>. After editing it, run "
            "<font face='Courier'>sudo systemctl restart thermalcam</font>."),
          table([
              ["Key", "Default", "Change it when"],
              ["flip_h / flip_v", "true / false", "The picture is mirrored left-right / upside down"],
              ["sensor_model", "\"MLX90640BAB\"", "You have the 110° wide-angle sensor (\"MLX90640BAA\")"],
              ["touch_min_pressure", "0", "Light brushes trigger taps (try 20 to 40)"],
              ["touch_calibration", "set on first boot", "Delete it, or run with --calibrate, to calibrate again"],
          ], [0.28, 0.22, 0.5], mono_cols=(0, 1))]

    # 9. Power
    s += [PageBreak(), p("9. Power", H1),
          p("Any USB power bank gives 5 V, which is what the Pi 2 takes through its micro-USB socket. What matters "
            "is the current: use a port rated <b>2 A or more</b>."),
          table([
              ["Part", "Typical draw at 5 V"],
              ["Pi 2 under load", "400 to 600 mA"], ["PiTFT (mostly the backlight)", "about 100 mA"],
              ["USB Wi-Fi dongle", "100 to 250 mA"], ["MLX90640", "about 20 mA"],
              ["<b>Total</b>", "<b>about 0.7 to 1 A, with short spikes higher</b>"],
          ], [0.5, 0.5]),
          Spacer(1, 3 * mm),
          *bullets(["<b>10,000 mAh</b> gives roughly 6 to 8 hours; 5,000 mAh about 3.",
                    "USB-C power banks are fine with a USB-C to micro-USB cable.",
                    "<b>The cable matters as much as the bank.</b> Thin or long cables drop voltage. Use a short "
                    "(50 cm or less), thick one.",
                    "Check with <font face='Courier'>vcgencmd get_throttled</font>: 0x0 is fine; anything else "
                    "means the voltage dipped."])]

    # 10. Troubleshooting
    s += [p("10. Troubleshooting", H1),
          table([
              ["Symptom", "Likely cause and fix"],
              ["Screen stays plain white", "The screen driver isn't installed yet. Run ./setup.sh and reboot (step 5). "
                                           "If it's still white: check the PiTFT covers a whole block the right way "
                                           "round, and that cat /sys/class/graphics/fb*/virtual_size shows 480,320."],
              ["\"SENSOR NOT FOUND - RETRYING\" and i2cdetect shows an empty grid",
               "Wiring. Check the <b>GND wire is on a GND pin</b> first (the cause on the first build), then that "
               "the wires are on the right column (section 3). About 3.3 V between the sensor's 2-6V and GND pins "
               "means it has power. The app reconnects by itself once the sensor answers."],
              ["No calibration crosses; taps do nothing",
               "The touchscreen driver isn't loaded. Current setup.sh loads it; on an older install run: "
               "sudo modprobe stmpe_ts, then echo stmpe_ts | sudo tee /etc/modules-load.d/stmpe-ts.conf, then "
               "sudo systemctl restart thermalcam."],
              ["Boot messages or terminal text cover the Live view",
               "An older install. cd ~/thermal-camera && git pull && SKIP_PITFT=1 ./setup.sh && sudo reboot."],
              ["Taps land in the wrong place", "Stop the service and run main.py --calibrate (section 8)."],
              ["You have to tilt the camera to see things upright", "Rotate the sensor on its mount (section 3)."],
              ["Picture mirrored or upside down", "Set flip_h or flip_v in the config file. For the whole screen "
                                                   "upside down: PITFT_ROTATION=270 ./setup.sh, then reboot."],
              ["Many dropped frames on Sensor info", "A loose or long jumper. Reseat the wires, keep them short, or "
                                                     "choose a lower sensor rate."],
              ["Random reboots, or get_throttled isn't 0x0", "Not enough power: a 2 A port and a short, thick cable "
                                                             "(section 9)."],
              ["Everything looks about the same temperature", "Not enough difference indoors. Try a colder day, and "
                                                              "use LOCK so small differences stay visible."],
          ], [0.33, 0.67], bold_first=True)]
    return s


def footer(c, doc):
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN, 13 * mm, PAGE_W - MARGIN, 13 * mm)
    c.setFillColor(MID)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 9 * mm, "Thermal camera: MLX90640 + Raspberry Pi 2 Model B + PiTFT 3.5\"")
    c.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
    c.restoreState()


def main():
    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm,
                            bottomMargin=20 * mm, title="Thermal Camera: Wiring and Setup Guide",
                            author="Thermal camera project", subject=f"Updated {UPDATED}")
    doc.build(story(), onFirstPage=footer, onLaterPages=footer)
    print(f"wrote {OUT} ({datetime.date.today()})")


if __name__ == "__main__":
    main()

"""Crayon-style stage backdrops, drawn in code so every story has scenery with no AI at all.

Run `python -m doodle_theater.backdrops` to (re)draw them into static/backdrops/. Hand-drawn
crayon suits the children's own drawings better than generated art would.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .config import STATIC

W, H = 1280, 720
GROUND = int(H * 0.86)  # where the puppets' feet stand (the TV puts feet at 0.86-0.9)


class Crayon:
    """Wobbly, layered strokes on paper, like a child's crayon box."""

    def __init__(self, seed: int, paper=(255, 248, 231)):
        self.rng = random.Random(seed)
        self.img = Image.new("RGB", (W, H), paper)
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def _jit(self, v: float, amt: float) -> float:
        return v + self.rng.uniform(-amt, amt)

    def line(self, pts, color, width=6, passes=3, wobble=2.5):
        for _ in range(passes):
            p = [(self._jit(x, wobble), self._jit(y, wobble)) for x, y in pts]
            self.d.line(p, fill=(*color, 150), width=max(1, int(width * self.rng.uniform(0.6, 1.1))), joint="curve")

    def fill(self, poly, color, density=7, angle=None):
        """Scribble-fill a polygon with hatching, then outline it."""
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        x0, x1, y0, y1 = min(xs) - 40, max(xs) + 40, min(ys) - 40, max(ys) + 40
        a = math.radians(angle if angle is not None else self.rng.uniform(25, 65))
        dx, dy = math.cos(a), math.sin(a)
        span = int(math.hypot(x1 - x0, y1 - y0))
        for k in range(-span, span, density):
            cx, cy = (x0 + x1) / 2 - dy * k, (y0 + y1) / 2 + dx * k
            p0 = (cx - dx * span, cy - dy * span)
            p1 = (cx + dx * span, cy + dy * span)
            ld.line([(self._jit(p0[0], 3), self._jit(p0[1], 3)), (self._jit(p1[0], 3), self._jit(p1[1], 3))],
                    fill=(*color, self.rng.randint(150, 220)), width=self.rng.randint(4, 7))
        self.img.paste(layer, (0, 0), Image.fromarray(np.minimum(np.asarray(layer)[..., 3], np.asarray(mask))))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.line(list(poly) + [poly[0]], tuple(max(0, c - 60) for c in color), width=4, passes=2)

    def blob(self, cx, cy, rx, ry, color, n=28, **kw):
        poly = [(cx + rx * math.cos(t) * self.rng.uniform(0.93, 1.05),
                 cy + ry * math.sin(t) * self.rng.uniform(0.93, 1.05))
                for t in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        self.fill(poly, color, **kw)

    def rect(self, x0, y0, x1, y1, color, **kw):
        self.fill([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, **kw)

    def sky(self, top, bottom):
        arr = np.asarray(self.img).astype(np.float32)
        t = np.linspace(0, 1, H)[:, None, None]
        grad = np.array(top)[None, None] * (1 - t) + np.array(bottom)[None, None] * t
        sky = np.where(np.arange(H)[:, None, None] < GROUND, grad, arr)
        noise = np.random.default_rng(self.rng.randint(0, 9999)).normal(0, 6, (H, W, 1))
        self.img = Image.fromarray(np.clip(sky * 0.88 + arr * 0.12 + noise, 0, 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def ground(self, color, wavy=8):
        pts = [(x, GROUND + math.sin(x / 90) * wavy + self.rng.uniform(-3, 3)) for x in range(-20, W + 40, 40)]
        self.fill(pts + [(W + 20, H + 20), (-20, H + 20)], color, angle=10)
        self.line(pts, tuple(max(0, c - 70) for c in color), width=7)

    def star(self, cx, cy, r, color=(255, 214, 64)):
        pts = []
        for i in range(10):
            rr = r if i % 2 == 0 else r * 0.45
            t = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
        self.fill(pts, color, density=5)

    def tree(self, x, h, trunk=(120, 78, 40), leaves=(52, 150, 70)):
        self.rect(x - 14, GROUND - h * 0.45, x + 14, GROUND + 6, trunk, angle=80)
        self.blob(x, GROUND - h * 0.65, h * 0.33, h * 0.3, leaves)

    def palm(self, x, h):
        self.line([(x, GROUND), (x + 18, GROUND - h * 0.5), (x + 10, GROUND - h)], (120, 78, 40), width=18)
        for a in (-150, -110, -60, -20, 200):
            r = math.radians(a)
            self.line([(x + 10, GROUND - h), (x + 10 + math.cos(r) * 110, GROUND - h + math.sin(r) * 50 + 40)],
                      (40, 140, 60), width=16)

    def mountain(self, x, w, h, color, snow=True):
        peak = (x, GROUND - h)
        self.fill([(x - w / 2, GROUND), peak, (x + w / 2, GROUND)], color, angle=70)
        if snow:
            self.fill([(x - w * 0.12, GROUND - h * 0.76), peak, (x + w * 0.12, GROUND - h * 0.76),
                       (x + w * 0.04, GROUND - h * 0.7), (x - w * 0.05, GROUND - h * 0.74)], (250, 250, 255), density=5)

    def save(self, name: str):
        out = STATIC / "backdrops"
        out.mkdir(parents=True, exist_ok=True)
        self.img.filter(ImageFilter.SMOOTH).save(out / f"{name}.jpg", quality=86, optimize=True)


# One function per backdrop. Keep the bottom 14% (the stage floor) calm: puppets stand there.

def space_station(c: Crayon):
    c.sky((22, 24, 70), (60, 50, 120)); c.ground((150, 150, 175))
    for _ in range(40):
        c.star(c.rng.uniform(0, W), c.rng.uniform(20, GROUND - 260), c.rng.uniform(5, 12))
    c.blob(1080, 160, 90, 90, (230, 120, 80)); c.blob(1080, 160, 150, 20, (250, 200, 90), density=5)
    c.rect(180, GROUND - 360, 520, GROUND - 120, (190, 200, 215)); c.blob(350, GROUND - 240, 80, 70, (120, 200, 240))
    c.rect(600, GROUND - 210, 640, GROUND, (170, 170, 190)); c.blob(620, GROUND - 230, 40, 40, (255, 90, 90))


def moon(c: Crayon):
    c.sky((10, 12, 40), (40, 40, 90)); c.ground((200, 200, 205), wavy=14)
    for _ in range(50):
        c.star(c.rng.uniform(0, W), c.rng.uniform(20, GROUND - 200), c.rng.uniform(4, 10))
    c.blob(260, 170, 110, 110, (80, 150, 230)); c.blob(230, 150, 40, 30, (70, 170, 90))
    for x in (500, 860, 1120):
        c.blob(x, GROUND + 40, 70, 18, (160, 160, 170))


def comet(c: Crayon):
    c.sky((30, 20, 70), (90, 50, 120)); c.ground((170, 140, 190))
    for _ in range(35):
        c.star(c.rng.uniform(0, W), c.rng.uniform(20, GROUND - 200), c.rng.uniform(4, 10))
    c.fill([(980, 180), (300, 80), (320, 150), (260, 230), (980, 230)], (255, 190, 120), density=6, angle=-8)
    c.blob(1000, 205, 60, 55, (255, 240, 200))


def jungle_path(c: Crayon):
    c.sky((150, 210, 240), (210, 240, 210)); c.ground((120, 170, 80))
    for x, h in ((80, 380), (300, 300), (980, 420), (1200, 340)):
        c.palm(x, h)
    c.fill([(560, H), (640, GROUND), (720, GROUND), (820, H)], (190, 150, 90), angle=80)
    c.blob(1050, 120, 70, 70, (255, 220, 80))


def river(c: Crayon):
    c.sky((160, 215, 245), (220, 245, 220)); c.ground((110, 165, 80))
    c.fill([(0, GROUND - 120), (W, GROUND - 60), (W, GROUND - 10), (0, GROUND - 50)], (70, 150, 220), angle=5)
    for x in (200, 420, 640, 900):
        c.blob(x, GROUND - 70, 45, 16, (150, 140, 130))
    c.tree(1150, 380); c.palm(90, 360)


def temple(c: Crayon):
    c.sky((170, 220, 240), (230, 240, 210)); c.ground((120, 160, 85))
    for i, (w, h) in enumerate(((620, 90), (500, 90), (380, 90), (260, 90))):
        y1 = GROUND - i * 90
        c.rect(640 - w / 2, y1 - h, 640 + w / 2, y1, (170, 160, 130), angle=80)
    c.rect(600, GROUND - 120, 680, GROUND, (60, 50, 40)); c.palm(120, 380); c.palm(1160, 360)


def reef(c: Crayon):
    c.sky((60, 170, 220), (20, 90, 160)); c.ground((230, 210, 150))
    for x, col in ((150, (250, 110, 120)), (420, (255, 170, 60)), (900, (200, 100, 220)), (1150, (250, 120, 160))):
        for k in range(3):
            c.line([(x + k * 30 - 30, GROUND), (x + k * 30 - 40, GROUND - 140 - 40 * k)], col, width=22)
    for _ in range(12):
        x, y = c.rng.uniform(0, W), c.rng.uniform(60, GROUND - 200)
        c.d.ellipse([x, y, x + 18, y + 18], outline=(220, 240, 255, 200), width=3)
    c.blob(700, 250, 50, 26, (255, 200, 40)); c.fill([(745, 250), (790, 225), (790, 275)], (255, 160, 40))


def shipwreck(c: Crayon):
    c.sky((40, 140, 200), (15, 70, 130)); c.ground((220, 200, 140))
    c.fill([(380, GROUND - 40), (900, GROUND - 100), (860, GROUND + 10), (420, GROUND + 10)], (120, 80, 50), angle=80)
    c.line([(640, GROUND - 70), (600, GROUND - 400)], (100, 70, 40), width=16)
    c.fill([(600, GROUND - 390), (760, GROUND - 330), (610, GROUND - 260)], (230, 230, 220))
    c.rect(950, GROUND - 60, 1070, GROUND + 4, (170, 120, 50)); c.blob(1010, GROUND - 62, 60, 20, (250, 210, 60))


def kelp_forest(c: Crayon):
    c.sky((40, 150, 190), (20, 90, 140)); c.ground((210, 195, 140))
    for x in range(60, W, 110):
        pts = [(x + math.sin(y / 50) * 18, y) for y in range(GROUND, int(GROUND - c.rng.uniform(300, 520)), -20)]
        c.line(pts, (60, 150, 80), width=24)
    c.blob(1100, 180, 60, 34, (90, 190, 120)); c.blob(1100, 180, 28, 16, (60, 140, 90))


def castle_gate(c: Crayon):
    c.sky((150, 200, 250), (230, 220, 250)); c.ground((110, 170, 90))
    for x in (300, 980):
        c.rect(x - 90, GROUND - 420, x + 90, GROUND, (190, 185, 200), angle=80)
        c.fill([(x - 110, GROUND - 420), (x, GROUND - 540), (x + 110, GROUND - 420)], (200, 80, 90))
    c.rect(390, GROUND - 300, 890, GROUND, (175, 170, 190), angle=80)
    c.fill([(560, GROUND), (560, GROUND - 170), (640, GROUND - 230), (720, GROUND - 170), (720, GROUND)], (110, 70, 40))
    c.blob(1150, 110, 60, 60, (255, 215, 80))


def throne_room(c: Crayon):
    c.sky((150, 70, 90), (190, 110, 120)); c.ground((170, 40, 60), wavy=2)
    for x in (140, 1140):
        c.rect(x - 40, 80, x + 40, GROUND, (210, 190, 160), angle=80)
    c.rect(560, GROUND - 330, 720, GROUND, (230, 180, 60)); c.rect(590, GROUND - 260, 690, GROUND - 120, (190, 40, 70))
    c.fill([(560, GROUND - 330), (600, GROUND - 400), (640, GROUND - 340), (680, GROUND - 400), (720, GROUND - 330)],
           (240, 200, 70))


def dragon_cave(c: Crayon):
    c.sky((70, 50, 60), (110, 80, 80)); c.ground((90, 70, 60))
    c.fill([(0, 0), (W, 0), (W, 160), (1000, 120), (800, 180), (500, 110), (250, 170), (0, 120)], (60, 45, 50))
    c.blob(950, GROUND - 120, 220, 110, (90, 170, 100)); c.blob(1120, GROUND - 230, 70, 60, (90, 170, 100))
    c.blob(1135, GROUND - 245, 12, 12, (255, 255, 255)); c.blob(600, GROUND - 40, 120, 30, (230, 120, 60))


def snowy_village(c: Crayon):
    c.sky((160, 190, 230), (225, 235, 250)); c.ground((245, 248, 255))
    for x, col in ((200, (200, 90, 80)), (520, (90, 130, 200)), (1040, (230, 170, 70))):
        c.rect(x - 110, GROUND - 200, x + 110, GROUND, col, angle=80)
        c.fill([(x - 140, GROUND - 200), (x, GROUND - 320), (x + 140, GROUND - 200)], (245, 248, 255))
        c.rect(x - 30, GROUND - 100, x + 30, GROUND, (110, 70, 40))
    for _ in range(70):
        x, y = c.rng.uniform(0, W), c.rng.uniform(0, GROUND)
        c.d.ellipse([x, y, x + 8, y + 8], fill=(255, 255, 255, 230))


def ice_cave(c: Crayon):
    c.sky((120, 190, 230), (180, 225, 245)); c.ground((220, 240, 250))
    for x in range(40, W, 120):
        c.fill([(x - 30, 0), (x + 30, 0), (x, c.rng.uniform(120, 260))], (200, 235, 250), density=5)
    c.blob(640, GROUND - 200, 260, 150, (150, 210, 240))


def mountain_top(c: Crayon):
    c.sky((130, 180, 240), (220, 235, 255)); c.mountain(300, 700, 420, (150, 150, 180)); c.mountain(1000, 800, 520, (130, 140, 170))
    c.ground((245, 248, 255)); c.blob(1150, 110, 55, 55, (255, 220, 90))


def dino_valley(c: Crayon):
    c.sky((250, 200, 140), (250, 230, 180)); c.mountain(1050, 600, 300, (170, 120, 90), snow=False)
    c.ground((140, 170, 70)); c.palm(150, 380); c.palm(420, 300)
    c.blob(900, GROUND - 60, 120, 50, (100, 160, 80)); c.line([(1000, GROUND - 80), (1080, GROUND - 230)], (100, 160, 80), width=30)


def volcano(c: Crayon):
    c.sky((240, 160, 110), (250, 210, 160)); c.ground((120, 140, 70))
    c.fill([(400, GROUND), (590, GROUND - 400), (690, GROUND - 400), (880, GROUND)], (120, 90, 80), angle=75)
    c.fill([(590, GROUND - 400), (640, GROUND - 330), (690, GROUND - 400)], (250, 100, 40))
    for k in range(4):
        c.blob(640 + k * 30, GROUND - 470 - k * 60, 60 + k * 10, 40 + k * 8, (180, 180, 185))


def nest(c: Crayon):
    c.sky((250, 210, 150), (250, 235, 190)); c.ground((150, 170, 80))
    c.blob(640, GROUND - 20, 300, 70, (160, 110, 60), angle=15)
    for x in (520, 610, 700, 780):
        c.blob(x, GROUND - 80, 42, 54, (245, 240, 220))
    c.palm(120, 360); c.palm(1160, 380)


ALL = {f.__name__: f for f in (space_station, moon, comet, jungle_path, river, temple, reef, shipwreck, kelp_forest,
                                castle_gate, throne_room, dragon_cave, snowy_village, ice_cave, mountain_top,
                                dino_valley, volcano, nest)}


def draw_all() -> None:
    for i, (name, fn) in enumerate(ALL.items()):
        c = Crayon(seed=1000 + i)
        fn(c)
        c.save(name)
        print("drew", name)


if __name__ == "__main__":
    draw_all()

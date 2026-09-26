"""The map's ground as one picture: flagstones, the torn crimson carpet the monsters walk, the walls,
the hell portal they come out of and the sanctuary gate they are headed for.

Drawn in 2-D with Pillow and NumPy at the art density. Things that stand up and must hide what walks
behind them (the arches, pillars and towers) are sprites, not part of this picture. The painted version
of this picture (:func:`ground`) replaces it when ``hellward/assets/painted/ground-<location>.png`` exists.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from hellward.art.rig import DENSITY, TILE
from hellward.sim.level import Level, Tile

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted"
PX = TILE * DENSITY          # pixels per tile in the picture

FLOOR = np.array((70, 64, 62), dtype=np.float32)
PATH_STONE = np.array((92, 84, 78), dtype=np.float32)
CARPET = (118, 18, 24)
CARPET_DARK = (78, 10, 16)
TRIM = (170, 128, 52)
WALL_TOP = (48, 44, 48)
WALL_FACE = (74, 68, 70)


def _noise(width: int, height: int, scale: int, seed: int) -> np.ndarray:
    """Smooth value noise in [0, 1], upsampled from a coarse random grid."""
    rng = np.random.default_rng(seed)
    coarse = rng.random((height // scale + 2, width // scale + 2)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8)).resize((width + scale * 2, height + scale * 2), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32)[:height, :width] / 255.0


def _stone(level: Level, seed: int) -> Image.Image:
    w, h = level.width * PX, level.height * PX
    grain = 0.6 * _noise(w, h, 6, seed) + 0.4 * _noise(w, h, 40, seed + 1)
    rng = random.Random(seed)
    base = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(level.height):
        for x in range(level.width):
            tile = level.tile(x, y)
            color = PATH_STONE if tile in (Tile.PATH, Tile.DOOR) else FLOOR
            tint = rng.uniform(0.86, 1.1)
            warm = rng.uniform(-4, 6)
            base[y * PX:(y + 1) * PX, x * PX:(x + 1) * PX] = color * tint + np.array((warm, 0, -warm * 0.5))
    base *= (0.78 + 0.4 * grain)[..., None]
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    # Mortar: every floor tile is two flagstones, laid in a running bond.
    for y in range(level.height):
        for x in range(level.width):
            x0, y0 = x * PX, y * PX
            draw.rectangle((x0, y0, x0 + PX - 1, y0 + PX - 1), outline=(38, 34, 34), width=2)
            if (x + y) % 2:
                draw.line((x0 + PX // 2, y0, x0 + PX // 2, y0 + PX), fill=(44, 40, 40), width=2)
            else:
                draw.line((x0, y0 + PX // 2, x0 + PX, y0 + PX // 2), fill=(44, 40, 40), width=2)
    for _ in range(90):   # cracks
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        points = [(x, y)]
        a = rng.uniform(0, 2 * math.pi)
        for _ in range(rng.randint(3, 7)):
            a += rng.uniform(-0.9, 0.9)
            x, y = x + math.cos(a) * rng.uniform(8, 22), y + math.sin(a) * rng.uniform(8, 22)
            points.append((x, y))
        draw.line(points, fill=(30, 26, 28), width=2)
    return image


def _carpet(image: Image.Image, level: Level, seed: int) -> None:
    rng = random.Random(seed)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    points = [((x + 0.5) * PX, (y + 0.5) * PX) for x, y in level.waypoints]
    half = PX * 0.31
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        box = (min(x0, x1) - half, min(y0, y1) - half, max(x0, x1) + half, max(y0, y1) + half)
        draw.rectangle(box, fill=TRIM + (255,))
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        inner = half - 5
        box = (min(x0, x1) - inner, min(y0, y1) - inner, max(x0, x1) + inner, max(y0, y1) + inner)
        draw.rectangle(box, fill=CARPET + (255,))
    for (x0, y0), (x1, y1) in zip(points, points[1:]):   # a dark woven border inside the gold
        inner = half - 12
        box = (min(x0, x1) - inner, min(y0, y1) - inner, max(x0, x1) + inner, max(y0, y1) + inner)
        draw.rectangle(box, outline=CARPET_DARK + (255,), width=3)
    alpha = np.asarray(layer)[..., 3].astype(np.float32)
    wear = _noise(image.width, image.height, 10, seed + 5)
    torn = (wear < 0.22).astype(np.float32)
    rgba = np.asarray(layer).astype(np.float32)
    rgba[..., :3] *= (0.7 + 0.5 * wear)[..., None]
    rgba[..., 3] = alpha * (1 - torn)
    carpet = Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")
    image.paste(carpet, (0, 0), carpet)
    draw = ImageDraw.Draw(image)
    for _ in range(26):   # dark stains trodden into the carpet
        s = rng.uniform(0, level.length)
        px, py = level.point(s)
        r = rng.uniform(6, 16)
        draw.ellipse((px * PX - r, py * PX - r * 0.7, px * PX + r, py * PX + r * 0.7), fill=(58, 8, 12))


def _walls(image: Image.Image, level: Level, seed: int) -> None:
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image)
    for y in range(level.height):
        for x in range(level.width):
            if level.tile(x, y) is not Tile.WALL:
                continue
            x0, y0 = x * PX, y * PX
            below = level.tile(x, y + 1)
            draw.rectangle((x0, y0, x0 + PX - 1, y0 + PX - 1), fill=WALL_TOP)
            for i in range(3):   # coursed masonry on the tops
                yy = y0 + (i + 1) * PX // 4
                draw.line((x0, yy, x0 + PX, yy), fill=(38, 34, 38), width=2)
            if below is not Tile.WALL and y + 1 < level.height:
                face = PX * 0.55   # the wall's face, seen from the front, over the lower part of its tile
                draw.rectangle((x0, y0 + PX - face, x0 + PX - 1, y0 + PX - 1), fill=WALL_FACE)
                for i in range(3):
                    yy = y0 + PX - face + i * face / 3
                    draw.line((x0, yy, x0 + PX, yy), fill=(52, 48, 50), width=2)
                    off = (i % 2) * PX // 4
                    for xx in range(x0 + off, x0 + PX, PX // 2):
                        draw.line((xx, yy, xx, yy + face / 3), fill=(52, 48, 50), width=2)
                if y == 0 and x % 3 == 1:   # a lancet window glowing with the fires beyond
                    cx = x0 + PX / 2
                    top = y0 + PX - face + 8
                    draw.rectangle((cx - 10, top + 12, cx + 10, y0 + PX - 10), fill=(150, 36, 20))
                    draw.pieslice((cx - 10, top, cx + 10, top + 24), 180, 360, fill=(150, 36, 20))
                    draw.line((cx, top + 2, cx, y0 + PX - 10), fill=(40, 30, 30), width=2)
            draw.line((x0, y0 + PX - 1, x0 + PX, y0 + PX - 1), fill=(24, 20, 22), width=3)
    # Rubble at the foot of the walls.
    for _ in range(70):
        x, y = rng.randrange(level.width), rng.randrange(level.height)
        if level.tile(x, y) is not Tile.FLOOR:
            continue
        near = any(level.tile(x + dx, y + dy) is Tile.WALL for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)))
        if not near:
            continue
        for _ in range(rng.randint(2, 5)):
            px, py = (x + rng.uniform(0.1, 0.9)) * PX, (y + rng.uniform(0.1, 0.9)) * PX
            r = rng.uniform(3, 8)
            draw.polygon([(px + r * math.cos(a), py + r * 0.8 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 6)[:-1] + rng.uniform(0, 1)],
                         fill=(rng.randint(60, 80),) * 3)


def _gore(image: Image.Image, level: Level, seed: int) -> None:
    rng = random.Random(seed)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for _ in range(40):   # old blood on the flagstones
        x, y = rng.randrange(level.width), rng.randrange(level.height)
        if level.tile(x, y) is Tile.WALL:
            continue
        cx, cy = (x + rng.random()) * PX, (y + rng.random()) * PX
        for _ in range(rng.randint(3, 8)):
            r = rng.uniform(3, 14)
            ox, oy = rng.gauss(0, 10), rng.gauss(0, 7)
            draw.ellipse((cx + ox - r, cy + oy - r * 0.7, cx + ox + r, cy + oy + r * 0.7), fill=(90, 10, 12, rng.randint(90, 170)))
    for _ in range(26):   # bones and skulls
        x, y = rng.randrange(level.width), rng.randrange(level.height)
        if level.tile(x, y) is not Tile.FLOOR:
            continue
        cx, cy = (x + rng.uniform(0.2, 0.8)) * PX, (y + rng.uniform(0.2, 0.8)) * PX
        if rng.random() < 0.4:
            draw.ellipse((cx - 7, cy - 6, cx + 7, cy + 6), fill=(200, 192, 168, 255))
            draw.ellipse((cx - 4, cy - 2, cx - 1, cy + 1), fill=(30, 24, 24, 255))
            draw.ellipse((cx + 1, cy - 2, cx + 4, cy + 1), fill=(30, 24, 24, 255))
        else:
            a = rng.uniform(0, math.pi)
            dx, dy = math.cos(a) * 11, math.sin(a) * 6
            draw.line((cx - dx, cy - dy, cx + dx, cy + dy), fill=(196, 188, 164, 255), width=4)
            for sx, sy in ((cx - dx, cy - dy), (cx + dx, cy + dy)):
                draw.ellipse((sx - 3, sy - 3, sx + 3, sy + 3), fill=(206, 198, 174, 255))
    image.paste(layer, (0, 0), layer)


def _portal(image: Image.Image, level: Level) -> None:
    """The hell portal the path starts from, and the sanctuary gate it ends at."""
    x, y = level.waypoints[0]
    cx, cy = (x + 0.5) * PX, (y + 0.5) * PX
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    for i in range(14, 0, -1):
        r = PX * 0.12 * i
        draw.ellipse((cx - r * 0.55, cy - r, cx + r * 0.55, cy + r), fill=(255, 60 + i * 6, 20, 18))
    draw.ellipse((cx - PX * 0.42, cy - PX * 0.72, cx + PX * 0.42, cy + PX * 0.72), fill=(40, 4, 6, 255))
    for i in range(3):
        r = PX * (0.62 - i * 0.16)
        draw.arc((cx - r * 0.6, cy - r, cx + r * 0.6, cy + r), 20 + i * 90, 280 + i * 90, fill=(255, 120 - i * 30, 30, 255), width=5)
    image.paste(glow, (0, 0), glow)
    x, y = level.waypoints[-1]
    cx, cy = (x + 0.5) * PX, (y + 0.5) * PX
    holy = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(holy)
    for i in range(12, 0, -1):
        r = PX * 0.13 * i
        draw.ellipse((cx - r * 0.6, cy - r, cx + r * 0.6, cy + r), fill=(255, 220, 140, 14))
    draw.rectangle((cx - PX * 0.36, cy - PX * 0.6, cx + PX * 0.36, cy + PX * 0.5), fill=(250, 226, 160, 255))
    draw.pieslice((cx - PX * 0.36, cy - PX * 0.95, cx + PX * 0.36, cy - PX * 0.25), 180, 360, fill=(250, 226, 160, 255))
    draw.rectangle((cx - PX * 0.36, cy - PX * 0.6, cx + PX * 0.36, cy + PX * 0.5), outline=(206, 164, 72, 255), width=5)
    draw.line((cx, cy - PX * 0.5, cx, cy + PX * 0.2), fill=(206, 164, 72, 255), width=6)
    draw.line((cx - PX * 0.18, cy - PX * 0.25, cx + PX * 0.18, cy - PX * 0.25), fill=(206, 164, 72, 255), width=6)
    image.paste(holy, (0, 0), holy)


def stand_in(level: Level, seed: int = 11) -> Image.Image:
    image = _stone(level, seed)
    _gore(image, level, seed + 1)
    _carpet(image, level, seed + 2)
    _walls(image, level, seed + 3)
    _portal(image, level)
    vignette = _noise(image.width, image.height, 120, seed + 9)
    array = np.asarray(image).astype(np.float32) * (0.85 + 0.25 * vignette)[..., None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.SMOOTH)


def painted(key: str) -> Path:
    """Where a location's painted floor lives, when it has one."""
    return PAINTED / f"ground-{key}.png"


def ground(key: str, level: Level) -> Image.Image:
    """A location's floor: its painting when there is one, else the stand-in."""
    if painted(key).exists():
        image = Image.open(painted(key)).convert("RGB")
        return image.resize((level.width * PX, level.height * PX), Image.LANCZOS)
    return stand_in(level)

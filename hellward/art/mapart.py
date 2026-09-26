"""A location's ground as one picture: its floor, the way the monsters walk, the walls, the pits, the
hell portal they come out of and the sanctuary gate they are headed for.

Each location has a :class:`Theme`: the cathedral's flagstones and torn crimson carpet, the village's mud
and dirt road, the graveyard's turf and flagged path, the catacombs' bone halls, the caves' rock and lava,
hell's brimstone. Drawn in 2-D with Pillow and NumPy at the art density. Things that stand up and must hide
what walks behind them (the arches, the cathedral's pillars, the towers) are sprites, not part of this
picture; elsewhere the obstacles lie flat in it (headstones, bone heaps, boulders). The painted version of
this picture (:func:`ground`) replaces it when ``hellward/assets/painted/ground-<location>.png`` exists.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from dataclasses import dataclass

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


@dataclass(frozen=True)
class Theme:
    floor: tuple[int, int, int]
    path: tuple[int, int, int]
    wall_top: tuple[int, int, int]
    wall_face: tuple[int, int, int]
    pool: str            # "grave", "lava" or "pit": what a pit tile holds
    prop: str            # the flat obstacle: "cart", "headstone", "bones", "boulder", "spire"
    pillars: bool        # obstacles stand up as pillar sprites (the cathedral)
    flagstones: bool     # a floor of laid stones, or of earth and rock
    lights: str          # what lights it besides the way: "torches", "fires", "moon" or "lava"
    words: str           # how the painter should see it


THEMES: dict[str, Theme] = {
    "cathedral": Theme((70, 64, 62), (92, 84, 78), WALL_TOP, WALL_FACE, "pit", "bones", True, True, "torches",
                       "a desecrated gothic cathedral floor: worn grey flagstones with cracks, moss and old blood; a long torn "
                       "crimson carpet with gold trim along the path; the north wall of dark stone with tall lancet windows "
                       "glowing red; scattered bones, skulls and candle stubs"),
    "village": Theme((58, 60, 40), (92, 72, 50), (46, 36, 30), (72, 56, 42), "grave", "cart", False, False, "fires",
                     "a burning medieval village square at night seen from above: trampled grass and mud, a rutted dirt road "
                     "along the path with scattered cobbles, the edges walled by the dark timber and stone of houses, burning "
                     "thatch and embers, broken carts, barrels and a stone well"),
    "graveyard": Theme((46, 56, 42), (86, 84, 80), (60, 60, 62), (84, 84, 86), "grave", "headstone", False, False, "moon",
                       "a haunted churchyard at night seen from above: dark wet turf and mist, a path of old grey flagstones "
                       "along the path, a low mossy stone wall around the edges, crooked headstones and crosses, open graves "
                       "with heaped earth, dead leaves, crypt arches of carved stone"),
    "catacombs": Theme((54, 48, 44), (96, 88, 74), (40, 36, 34), (70, 64, 58), "pit", "bones", False, True, "torches",
                       "the catacombs under a cathedral seen from above: narrow halls of dark worn stone, a corridor of pale "
                       "flagstones along the path, walls lined with niches of stacked skulls and bones, bone heaps, open "
                       "ossuary pits, cobwebs, a few candle stubs"),
    "caves": Theme((62, 50, 42), (98, 78, 58), (44, 34, 30), (70, 54, 44), "lava", "boulder", False, False, "lava",
                   "a deep cave seen from above: rough brown and grey rock floor, a trodden dirt trail along the path, jagged "
                   "rock walls around the edges, a lake of glowing molten lava with a black crust at the edges, boulders, "
                   "stalagmite stumps, scattered bones of the goatmen's prey"),
    "hell": Theme((50, 30, 28), (38, 30, 32), (30, 18, 18), (58, 30, 26), "lava", "spire", False, True, "lava",
                  "the gate of hell seen from above: cracked black obsidian and brimstone ground veined with glowing lava, a "
                  "road of black basalt flagstones along the path stained with blood, walls of jagged obsidian lit red from "
                  "below, pools and rivers of lava, skull piles and brimstone spires"),
}


def _noise(width: int, height: int, scale: int, seed: int) -> np.ndarray:
    """Smooth value noise in [0, 1], upsampled from a coarse random grid."""
    rng = np.random.default_rng(seed)
    coarse = rng.random((height // scale + 2, width // scale + 2)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8)).resize((width + scale * 2, height + scale * 2), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32)[:height, :width] / 255.0


def _stone(level: Level, seed: int, theme: Theme) -> Image.Image:
    w, h = level.width * PX, level.height * PX
    grain = 0.6 * _noise(w, h, 6, seed) + 0.4 * _noise(w, h, 40, seed + 1)
    rng = random.Random(seed)
    base = np.zeros((h, w, 3), dtype=np.float32)
    floor, path = np.array(theme.floor, dtype=np.float32), np.array(theme.path, dtype=np.float32)
    for y in range(level.height):
        for x in range(level.width):
            tile = level.tile(x, y)
            color = path if tile in (Tile.PATH, Tile.DOOR) else floor
            tint = rng.uniform(0.86, 1.1)
            warm = rng.uniform(-4, 6)
            base[y * PX:(y + 1) * PX, x * PX:(x + 1) * PX] = color * tint + np.array((warm, 0, -warm * 0.5))
    base *= (0.78 + 0.4 * grain)[..., None]
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    mortar = tuple(int(c * 0.55) for c in theme.floor)
    for y in range(level.height):
        for x in range(level.width):
            x0, y0 = x * PX, y * PX
            if theme.flagstones:   # every floor tile is two flagstones, laid in a running bond
                draw.rectangle((x0, y0, x0 + PX - 1, y0 + PX - 1), outline=(38, 34, 34), width=2)
                if (x + y) % 2:
                    draw.line((x0 + PX // 2, y0, x0 + PX // 2, y0 + PX), fill=(44, 40, 40), width=2)
                else:
                    draw.line((x0, y0 + PX // 2, x0 + PX, y0 + PX // 2), fill=(44, 40, 40), width=2)
            else:   # earth and rock: only a faint grid, so a tower's place still reads
                draw.rectangle((x0, y0, x0 + PX - 1, y0 + PX - 1), outline=mortar, width=1)
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


def _walls(image: Image.Image, level: Level, seed: int, theme: Theme = THEMES["cathedral"]) -> None:
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image)
    for y in range(level.height):
        for x in range(level.width):
            if level.tile(x, y) is not Tile.WALL:
                continue
            x0, y0 = x * PX, y * PX
            below = level.tile(x, y + 1)
            draw.rectangle((x0, y0, x0 + PX - 1, y0 + PX - 1), fill=theme.wall_top)
            for i in range(3):   # coursed masonry on the tops
                yy = y0 + (i + 1) * PX // 4
                draw.line((x0, yy, x0 + PX, yy), fill=(38, 34, 38), width=2)
            if below is not Tile.WALL and y + 1 < level.height:
                face = PX * 0.55   # the wall's face, seen from the front, over the lower part of its tile
                draw.rectangle((x0, y0 + PX - face, x0 + PX - 1, y0 + PX - 1), fill=theme.wall_face)
                for i in range(3):
                    yy = y0 + PX - face + i * face / 3
                    draw.line((x0, yy, x0 + PX, yy), fill=(52, 48, 50), width=2)
                    off = (i % 2) * PX // 4
                    for xx in range(x0 + off, x0 + PX, PX // 2):
                        draw.line((xx, yy, xx, yy + face / 3), fill=(52, 48, 50), width=2)
                if y == 0 and x % 3 == 1 and theme.pillars:   # a lancet window glowing with the fires beyond
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


def _road(image: Image.Image, level: Level, seed: int, theme: Theme) -> None:
    """The way the monsters walk, where there is no carpet: worn ground or flags, darker at the edges."""
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image)
    points = [((x + 0.5) * PX, (y + 0.5) * PX) for x, y in level.waypoints]
    half = PX * 0.36
    edge = tuple(int(c * 0.6) for c in theme.path)
    for width, color in ((half + 5, edge), (half, theme.path)):
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            draw.rectangle((min(x0, x1) - width, min(y0, y1) - width, max(x0, x1) + width, max(y0, y1) + width), fill=color)
    for _ in range(int(level.length * 5)):   # stones, ruts and stains along it
        s = rng.uniform(0, level.length)
        px, py = level.point(s)
        ox, oy = rng.uniform(-0.3, 0.3) * PX, rng.uniform(-0.3, 0.3) * PX
        r = rng.uniform(3, 8)
        shade = rng.uniform(0.7, 1.25)
        draw.ellipse((px * PX + ox - r, py * PX + oy - r * 0.7, px * PX + ox + r, py * PX + oy + r * 0.7),
                     fill=tuple(int(min(255, c * shade)) for c in theme.path))


def _pits(image: Image.Image, level: Level, seed: int, theme: Theme) -> None:
    """The pits nothing stands on: lava, open graves, bone pits."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x, y in sorted(level.pools):
        x0, y0 = x * PX, y * PX
        if theme.pool == "lava":
            draw.rounded_rectangle((x0 - 6, y0 - 6, x0 + PX + 6, y0 + PX + 6), radius=PX // 3, fill=(40, 20, 16, 255))
            draw.rounded_rectangle((x0 + 4, y0 + 4, x0 + PX - 4, y0 + PX - 4), radius=PX // 4, fill=(230, 90, 20, 255))
            for _ in range(6):
                cx, cy, r = x0 + rng.uniform(10, PX - 10), y0 + rng.uniform(10, PX - 10), rng.uniform(4, 10)
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 200, 70, 255))
        elif theme.pool == "grave":
            draw.rectangle((x0 + PX * 0.3, y0 + PX * 0.1, x0 + PX * 0.7, y0 + PX * 0.9), fill=(18, 14, 12, 255))
            draw.ellipse((x0 + PX * 0.66, y0 + PX * 0.1, x0 + PX * 0.98, y0 + PX * 0.9), fill=(70, 54, 40, 255))
        else:
            draw.ellipse((x0 + 6, y0 + 6, x0 + PX - 6, y0 + PX - 6), fill=(14, 10, 10, 255))
            for _ in range(8):
                cx, cy = x0 + rng.uniform(14, PX - 14), y0 + rng.uniform(14, PX - 14)
                draw.ellipse((cx - 4, cy - 3, cx + 4, cy + 3), fill=(190, 182, 160, 255))
    image.paste(layer, (0, 0), layer.filter(ImageFilter.GaussianBlur(1.5)))


def _props(image: Image.Image, level: Level, seed: int, theme: Theme) -> None:
    """The obstacles, lying flat in the floor where no pillar stands up."""
    rng = random.Random(seed)
    draw = ImageDraw.Draw(image)
    for x, y in sorted(level.obstacles):
        cx, cy = (x + 0.5) * PX, (y + 0.5) * PX
        if theme.prop == "headstone":
            draw.ellipse((cx - PX * 0.32, cy - PX * 0.1, cx + PX * 0.32, cy + PX * 0.38), fill=(52, 44, 34))
            draw.rounded_rectangle((cx - PX * 0.2, cy - PX * 0.38, cx + PX * 0.2, cy + PX * 0.12), radius=PX // 5, fill=(118, 116, 112),
                                   outline=(60, 58, 56), width=3)
        elif theme.prop == "cart":
            draw.rectangle((cx - PX * 0.38, cy - PX * 0.24, cx + PX * 0.38, cy + PX * 0.24), fill=(84, 60, 36), outline=(40, 28, 18), width=3)
            for wx in (cx - PX * 0.3, cx + PX * 0.3):
                draw.ellipse((wx - 7, cy + PX * 0.18, wx + 7, cy + PX * 0.34), fill=(40, 28, 18))
        elif theme.prop == "boulder":
            draw.ellipse((cx - PX * 0.4, cy - PX * 0.3, cx + PX * 0.4, cy + PX * 0.36), fill=(78, 70, 64), outline=(38, 32, 30), width=3)
            draw.ellipse((cx - PX * 0.2, cy - PX * 0.24, cx + PX * 0.05, cy - PX * 0.05), fill=(108, 98, 90))
        elif theme.prop == "spire":
            draw.polygon([(cx - PX * 0.3, cy + PX * 0.3), (cx, cy - PX * 0.4), (cx + PX * 0.3, cy + PX * 0.3)], fill=(34, 20, 20),
                         outline=(200, 70, 20))
        else:   # a heap of bones and skulls
            for _ in range(9):
                bx, by = cx + rng.uniform(-PX * 0.3, PX * 0.3), cy + rng.uniform(-PX * 0.25, PX * 0.25)
                draw.ellipse((bx - 7, by - 6, bx + 7, by + 6), fill=(206, 196, 170), outline=(90, 84, 70))


def stand_in(level: Level, theme: Theme = THEMES["cathedral"], seed: int = 11) -> Image.Image:
    image = _stone(level, seed, theme)
    _gore(image, level, seed + 1)
    if theme is THEMES["cathedral"]:
        _carpet(image, level, seed + 2)
    else:
        _road(image, level, seed + 2, theme)
        _pits(image, level, seed + 4, theme)
        _props(image, level, seed + 5, theme)
    _walls(image, level, seed + 3, theme)
    _portal(image, level)
    vignette = _noise(image.width, image.height, 120, seed + 9)
    array = np.asarray(image).astype(np.float32) * (0.85 + 0.25 * vignette)[..., None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.SMOOTH)


def painted(key: str) -> Path:
    """Where a location's painted floor lives, when it has one."""
    return PAINTED / f"ground-{key}.png"


def ground(key: str, level: Level, theme: Theme) -> Image.Image:
    """A location's floor: its painting when there is one, else the stand-in."""
    if painted(key).exists():
        image = Image.open(painted(key)).convert("RGB")
        return image.resize((level.width * PX, level.height * PX), Image.LANCZOS)
    return stand_in(level, theme)

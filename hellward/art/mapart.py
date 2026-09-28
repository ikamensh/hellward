"""A location's ground as one picture: its build ground, bounded monster halls, walls, pits, the
hell portal they come out of and the sanctuary gate they are headed for.

Each location has a :class:`Theme`: the cathedral's flagstones and torn crimson carpet, the village's mud
and dirt road, the graveyard's turf and flagged path, the catacombs' bone halls, the caves' rock and lava,
hell's brimstone. Drawn in 2-D with Pillow and NumPy at the art density. Things that stand up and must hide
what walks behind them (the arches, the cathedral's pillars, the towers) are sprites, not part of this
picture; elsewhere the obstacles lie flat in it (headstones, bone heaps, boulders). The painted version of
this picture (:func:`ground`) replaces it when ``hellward/assets/painted/ground-<location>.png`` exists.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import warnings
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from dataclasses import dataclass

from hellward.art.rig import DENSITY, TILE
from hellward.sim.level import Level, Route, Tile

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted"
TERRAIN = Path(__file__).resolve().parent.parent / "assets" / "terrain"
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
    pool: str            # "grave", "lava", "pit", "water", "web" or "brazier": what a pit tile holds
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
    "docks": Theme((32, 28, 26), (56, 48, 44), (24, 20, 20), (48, 40, 36), "water", "bones", False, False, "fires",
                   "Kurast's rotting docks at night: black water and dark wooden planks, a path of weathered boards over the "
                   "piers, walls of crumbling warehouses with lantern light, scattered crates, rope coils and barnacled posts"),
    "spider_forest": Theme((28, 36, 26), (48, 56, 44), (20, 28, 20), (40, 48, 36), "web", "boulder", False, False, "moon",
                           "the spider forest's canopy floor: dark green moss and black loam, a winding path of root and stone, "
                           "ancient oaks with silver bark forming a druid ring, webs strung between trunks, fallen leaves"),
    "jungle": Theme((24, 40, 22), (44, 60, 40), (18, 28, 18), (36, 48, 32), "water", "boulder", False, False, "fires",
                    "the flayer jungle's dense floor: deep green moss and black earth, two long straight roads of packed dirt, "
                    "walls of massive buttress roots and lianas, torchlight from zealot shrines, scattered bones and fetishes"),
    "drowned_city": Theme((26, 28, 36), (40, 44, 56), (18, 20, 24), (32, 36, 48), "water", "bones", False, True, "moon",
                          "Kurast's drowned streets: black water canals reflecting moonlight, flagstone paths along the canals, "
                          "walls of water-stained masonry with green moss, bone pits in the plazas, lanterns on drowned arches"),
    "travincal": Theme((48, 44, 32), (72, 64, 48), (36, 32, 24), (56, 52, 38), "brazier", "spire", True, True, "torches",
                       "the High Council's terrace: gilt-edged marble flagstones, a wide carpet of crimson and gold, "
                       "pillared arches along the way, braziers burning with pale flame, the mother lamp's light above"),
    "temple": Theme((42, 38, 32), (60, 56, 48), (30, 26, 22), (50, 46, 40), "brazier", "bones", True, True, "torches",
                    "the Temple of Light's nave: worn marble flagstones veined with gold, a dim crimson carpet to the altar, "
                    "tall pillars with bone niches, torch sconces guttering, the mother lamp hanging dim, scattered skulls"),
}

MATERIALS = {
    "village": "village", "graveyard": "graveyard", "cathedral": "stone",
    "catacombs": "stone", "caves": "cavern", "hell": "brimstone",
    "docks": "docks", "spider_forest": "forest", "jungle": "forest",
    "drowned_city": "stone", "travincal": "stone", "temple": "stone",
}


def _visible_routes(level: Level) -> tuple[Route, ...]:
    """Direct routes leave a worn trace within the broader monster halls."""
    return tuple(route for route in level.routes if route.key != "meander" and not route.key.endswith("_detour"))


def _noise(width: int, height: int, scale: int, seed: int) -> np.ndarray:
    """Smooth value noise in [0, 1], upsampled from a coarse random grid."""
    rng = np.random.default_rng(seed)
    coarse = rng.random((height // scale + 2, width // scale + 2)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8)).resize((width + scale * 2, height + scale * 2), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32)[:height, :width] / 255.0


def _material(level: Level, theme: Theme) -> Image.Image:
    """Repeat image-generated ground with mirrored joins, then match a location's palette."""
    key = next((name for name, value in THEMES.items() if value is theme), "cathedral")
    with Image.open(TERRAIN / f"{MATERIALS[key]}.webp") as painting:
        source = painting.convert("RGB")
    size = (round(source.width * 0.65), round(source.height * 0.65))
    source = source.resize(size, Image.Resampling.LANCZOS)
    tile = Image.new("RGB", (size[0] * 2, size[1] * 2))
    tile.paste(source, (0, 0))
    tile.paste(ImageOps.mirror(source), (size[0], 0))
    tile.paste(ImageOps.flip(source), (0, size[1]))
    tile.paste(ImageOps.flip(ImageOps.mirror(source)), size)
    w, h = level.width * PX, level.height * PX
    canvas = Image.new("RGB", (w, h))
    for y in range(0, h, tile.height):
        for x in range(0, w, tile.width):
            canvas.paste(tile, (x, y))
    pixels = np.asarray(canvas, dtype=np.float32)
    current = np.asarray(source, dtype=np.float32).mean(axis=(0, 1))
    target = np.asarray(theme.floor, dtype=np.float32) * 1.2
    pixels = np.clip(pixels * target / current, 0, 255)
    return Image.fromarray(pixels.astype(np.uint8), "RGB")


def _build_ground(level: Level, theme: Theme) -> Image.Image:
    image = _material(level, theme)
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
    return image


def _halls(image: Image.Image, level: Level, theme: Theme) -> None:
    """Give every monster tile one readable surface, including space between route centrelines."""
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    for x, y in level.walkable_tiles:
        draw.rectangle((x * PX, y * PX, (x + 1) * PX - 1, (y + 1) * PX - 1), fill=255)
    floor = np.asarray(image, dtype=np.float32)
    ratio = np.maximum(1.25, np.asarray(theme.path, dtype=np.float32)
                       / np.maximum(np.asarray(theme.floor, dtype=np.float32), 1))
    hall = Image.fromarray(np.clip(floor * ratio, 0, 255).astype(np.uint8), "RGB")
    image.paste(hall, (0, 0), mask)
    rim = tuple(round(c * 0.38) for c in theme.path)
    glint = tuple(min(255, round(c * 1.38)) for c in theme.path)
    edge = ImageDraw.Draw(image)
    for x, y in level.walkable_tiles:
        x0, y0 = x * PX, y * PX
        for dx, dy, segment in (
            (-1, 0, (x0, y0, x0, y0 + PX - 1)),
            (1, 0, (x0 + PX - 1, y0, x0 + PX - 1, y0 + PX - 1)),
            (0, -1, (x0, y0, x0 + PX - 1, y0)),
            (0, 1, (x0, y0 + PX - 1, x0 + PX - 1, y0 + PX - 1)),
        ):
            if (x + dx, y + dy) not in level.walkable_tiles:
                edge.line(segment, fill=rim, width=5)
                edge.line(segment, fill=glint, width=1)


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
    """Open entrances, visibly sealed optional breach entrances, and the sanctuary."""
    entrances = dict.fromkeys(route.entrance for route in _visible_routes(level) if not route.key.startswith("breach"))
    for x, y in entrances:
        cx, cy = (x + 0.5) * PX, (y + 0.5) * PX
        glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)
        for i in range(14, 0, -1):
            r = PX * 0.12 * i
            draw.ellipse((cx - r * 0.55, cy - r, cx + r * 0.55, cy + r), fill=(255, 60 + i * 6, 20, 18))
        draw.ellipse((cx - PX * 0.42, cy - PX * 0.72, cx + PX * 0.42, cy + PX * 0.72), fill=(40, 4, 6, 255))
        for i in range(3):
            r = PX * (0.62 - i * 0.16)
            draw.arc((cx - r * 0.6, cy - r, cx + r * 0.6, cy + r), 20 + i * 90, 280 + i * 90,
                     fill=(255, 120 - i * 30, 30, 255), width=5)
        image.paste(glow, (0, 0), glow)
    for x, y in dict.fromkeys(route.entrance for route in level.routes if route.key.startswith("breach")):
        cx, cy = (x + 0.5) * PX, (y + 0.5) * PX
        seal = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(seal)
        draw.ellipse((cx - PX * 0.38, cy - PX * 0.65, cx + PX * 0.38, cy + PX * 0.65),
                     fill=(25, 13, 34, 255), outline=(158, 88, 188, 255), width=6)
        draw.arc((cx - PX * 0.31, cy - PX * 0.56, cx + PX * 0.31, cy + PX * 0.56),
                 35, 325, fill=(214, 160, 227, 255), width=3)
        for offset in (-0.22, 0, 0.22):
            xx = cx + offset * PX
            draw.line((xx, cy - PX * 0.47, xx, cy + PX * 0.47), fill=(110, 95, 106, 255), width=6)
        draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(178, 133, 72, 255),
                     outline=(238, 197, 121, 255), width=2)
        image.paste(seal, (0, 0), seal)
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
    """A worn trace shows the shorter committed roads within the wider walkable halls."""
    rng = random.Random(seed)
    wear = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    for route in _visible_routes(level):
        half = PX * (0.36 if route.key == "main" else 0.24 if not route.key.startswith("breach") else 0.17)
        path = theme.path if not route.key.startswith("breach") else tuple(int(c * 0.72) for c in theme.path)
        edge = tuple(int(c * 0.6) for c in path)
        points = [((x + 0.5) * PX, (y + 0.5) * PX) for x, y in route.waypoints]
        for width, color, alpha in ((half + 5, edge, 110), (half, path, 145)):
            stroke = round(width * 2)
            draw.line(points, fill=color + (alpha,), width=stroke, joint="curve")
            for x, y in points:
                draw.ellipse((x - width, y - width, x + width, y + width), fill=color + (alpha,))
        for _ in range(int(route.length * (5 if route.key == "main" else 3))):
            s = rng.uniform(0, route.length)
            px, py = route.point(s)
            ox, oy = rng.uniform(-0.3, 0.3) * PX, rng.uniform(-0.3, 0.3) * PX
            r = rng.uniform(3, 8)
            shade = rng.uniform(0.7, 1.25)
            draw.ellipse((px * PX + ox - r, py * PX + oy - r * 0.7, px * PX + ox + r, py * PX + oy + r * 0.7),
                         fill=tuple(int(min(255, c * shade)) for c in path) + (75,))
    image.paste(wear, (0, 0), wear)


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
        elif theme.pool == "water":   # black water: neighbouring tiles run together into canals and pools
            draw.rounded_rectangle((x0 - 4, y0 - 4, x0 + PX + 4, y0 + PX + 4), radius=PX // 5, fill=(10, 18, 24, 255))
            for _ in range(3):
                cx, cy, r = x0 + rng.uniform(12, PX - 12), y0 + rng.uniform(12, PX - 12), rng.uniform(8, 16)
                draw.arc((cx - r, cy - r * 0.4, cx + r, cy + r * 0.4), 200, 340, fill=(40, 60, 70, 255), width=2)
        elif theme.pool == "web":
            draw.ellipse((x0 + 4, y0 + 4, x0 + PX - 4, y0 + PX - 4), fill=(30, 34, 28, 255))
            cx, cy = x0 + PX / 2, y0 + PX / 2
            for k in range(8):
                a = k * math.pi / 4
                draw.line((cx, cy, cx + math.cos(a) * PX * 0.46, cy + math.sin(a) * PX * 0.46), fill=(170, 170, 160, 255), width=2)
            for r in (PX * 0.14, PX * 0.26, PX * 0.38):
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 150, 140, 255), width=2)
        elif theme.pool == "brazier":
            draw.ellipse((x0 + 8, y0 + 8, x0 + PX - 8, y0 + PX - 8), fill=(60, 48, 30, 255), outline=(150, 120, 60, 255), width=4)
            draw.ellipse((x0 + 18, y0 + 18, x0 + PX - 18, y0 + PX - 18), fill=(240, 150, 40, 255))
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
    image = _build_ground(level, theme)
    _gore(image, level, seed + 1)
    _halls(image, level, theme)
    _road(image, level, seed + 2, theme)
    if theme is THEMES["cathedral"]:
        _carpet(image, level, seed + 2)
    else:
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


def layout_fingerprint(level: Level) -> str:
    """Identity of everything that fixes a floor's paths, portals, and unbuildable tiles."""
    layout = {
        "version": 2,
        "size": (level.width, level.height),
        "routes": [(route.key, route.waypoints) for route in level.routes],
        "walkable": sorted(level.walkable_tiles),
        "doors": sorted(level.doors),
        "obstacles": sorted(level.obstacles),
        "pools": sorted(level.pools),
    }
    data = json.dumps(layout, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


def painted_layout(key: str) -> Path:
    """The geometry recorded when a painted floor was installed."""
    return PAINTED / f"ground-{key}.layout.json"


def painted_matches(key: str, level: Level) -> bool:
    """A floor without a layout stamp is old art, even if its dimensions match."""
    stamp = painted_layout(key)
    if not painted(key).exists() or not stamp.exists():
        return False
    return json.loads(stamp.read_text(encoding="utf-8"))["fingerprint"] == layout_fingerprint(level)


def record_painted_layout(key: str, level: Level) -> None:
    """Mark a newly installed floor as matching the current authored geometry."""
    if not painted(key).exists():
        raise FileNotFoundError(painted(key))
    painted_layout(key).write_text(json.dumps({"fingerprint": layout_fingerprint(level)}) + "\n", encoding="utf-8")


def ground(key: str, level: Level, theme: Theme) -> Image.Image:
    """A location's floor: use its painting only when it matches the authored map."""
    if painted_matches(key, level):
        image = Image.open(painted(key)).convert("RGB")
        return image.resize((level.width * PX, level.height * PX), Image.LANCZOS)
    if painted(key).exists():
        warnings.warn(f"painted floor for {key} has old geometry; drawing the current stand-in", stacklevel=2)
    return stand_in(level, theme)

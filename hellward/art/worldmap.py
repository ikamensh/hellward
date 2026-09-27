"""The world map: a cut-away of the ground under Tristram, the six locations at fixed places on it, and the
trail the lantern walks down from one to the next.

The picture is drawn here as a stand-in (sky, the village, the churchyard and the church on the surface; the
cathedral's labyrinth, the catacombs, the caves and hell's gate as chambers ever deeper in the rock, joined by
tunnels). A painting of it (``assets/painted/worldmap.jpg``) replaces it when there is one; it was painted over
this stand-in, so the chambers stay where :data:`ANCHORS` says. Places are in the 1280 × 800 screen's pixels.

Act I: the descent under Tristram. Act II: a jungle coast seen from above — docks on the left shore,
forest and jungle inland, drowned city in a swamp, Travincal and the temple on a hill on the right.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from hellward.art.rig import DENSITY

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted" / "worldmap.jpg"
PAINTED_II = Path(__file__).resolve().parent.parent / "assets" / "painted" / "worldmap-2.jpg"
WIDTH, HEIGHT = 1280, 800
SURFACE = 182          # where the ground begins (Act I)

# Act I: the descent under Tristram
ANCHORS_I: dict[str, tuple[float, float]] = {
    "tristram": (230, 158),
    "graveyard": (640, 166),
    "cathedral": (990, 330),
    "catacombs": (380, 450),
    "caves": (900, 560),
    "hells_gate": (610, 668),
}

#: The trail between consecutive locations, as the points it bends at (both ends included).
TRAIL_I: dict[tuple[str, str], tuple[tuple[float, float], ...]] = {
    ("tristram", "graveyard"): ((230, 158), (330, 176), (450, 170), (560, 178), (640, 166)),
    ("graveyard", "cathedral"): ((640, 166), (760, 176), (900, 172), (975, 196), (1000, 240), (990, 330)),
    ("cathedral", "catacombs"): ((990, 330), (900, 356), (760, 372), (600, 400), (470, 420), (380, 450)),
    ("catacombs", "caves"): ((380, 450), (470, 500), (600, 520), (760, 530), (900, 560)),
    ("caves", "hells_gate"): ((900, 560), (840, 610), (740, 640), (610, 668)),
}

CHAMBERS_I: dict[str, tuple[tuple[int, int, int], float, float]] = {   # glow colour, half width, half height
    "cathedral": ((150, 70, 190), 118, 64),
    "catacombs": ((200, 190, 160), 124, 62),
    "caves": ((255, 110, 30), 132, 70),
    "hells_gate": ((255, 60, 20), 150, 76),
}

# Act II: a jungle coast seen from above
ANCHORS_II: dict[str, tuple[float, float]] = {
    "docks": (180, 400),
    "spider_forest": (380, 280),
    "jungle": (520, 420),
    "drowned_city": (350, 600),
    "travincal": (850, 300),
    "temple": (950, 450),
}

TRAIL_II: dict[tuple[str, str], tuple[tuple[float, float], ...]] = {
    ("docks", "spider_forest"): ((180, 400), (220, 360), (280, 330), (340, 300), (380, 280)),
    ("spider_forest", "jungle"): ((380, 280), (420, 310), (470, 350), (500, 390), (520, 420)),
    ("jungle", "drowned_city"): ((520, 420), (480, 480), (430, 530), (380, 570), (350, 600)),
    ("drowned_city", "travincal"): ((350, 600), (450, 540), (580, 460), (720, 380), (850, 300)),
    ("travincal", "temple"): ((850, 300), (880, 340), (910, 380), (930, 420), (950, 450)),
}

CHAMBERS_II: dict[str, tuple[tuple[int, int, int], float, float]] = {   # glow colour, half width, half height
    "docks": ((60, 120, 180), 100, 50),           # cold blue water glow
    "spider_forest": ((100, 180, 80), 110, 55),   # forest green glow
    "jungle": ((80, 150, 60), 120, 60),           # jungle green glow
    "drowned_city": ((40, 100, 140), 130, 65),    # swamp water glow
    "travincal": ((220, 180, 60), 115, 55),       # gold glow
    "temple": ((255, 220, 80), 125, 60),          # bright gold glow
}

# Keyed by act (1 or 2)
ANCHORS = {1: ANCHORS_I, 2: ANCHORS_II}
TRAIL = {1: TRAIL_I, 2: TRAIL_II}
CHAMBERS = {1: CHAMBERS_I, 2: CHAMBERS_II}


def trail(a: str, b: str, act: int = 1) -> tuple[tuple[float, float], ...]:
    """The trail from one location to another, in either direction along the descent."""
    t = TRAIL[act]
    if (a, b) in t:
        return t[(a, b)]
    return tuple(reversed(t[(b, a)]))


def _noise(width: int, height: int, scale: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coarse = rng.random((height // scale + 2, width // scale + 2)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8)).resize((width + scale * 2, height + scale * 2), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32)[:height, :width] / 255.0


def stand_in(seed: int = 3, act: int = 1) -> Image.Image:
    """Render the world map stand-in for the given act (1 or 2)."""
    if act == 1:
        return _stand_in_act1(seed)
    return _stand_in_act2(seed)


def _stand_in_act1(seed: int = 3) -> Image.Image:
    d = DENSITY
    w, h = WIDTH * d, HEIGHT * d
    rng = random.Random(seed)
    y = np.arange(h, dtype=np.float32)[:, None] / d
    grain = 0.55 * _noise(w, h, 5 * d, seed) + 0.45 * _noise(w, h, 60 * d, seed + 1)
    # The rock: brown-grey under the surface, reddening and darkening towards hell.
    depth = np.clip((y - SURFACE) / (HEIGHT - SURFACE), 0, 1)
    rock = np.dstack([58 + 30 * depth, 48 - 26 * depth, 44 - 30 * depth]) * (0.6 + 0.6 * grain)[..., None]
    strata = 0.85 + 0.15 * np.sin((y + 18 * _noise(w, h, 90 * d, seed + 2) * 10) / 9.0)
    rock *= strata[..., None] if strata.ndim == 2 else strata
    # The night sky over the surface, glowing red at the horizon.
    sky_t = np.clip(y / SURFACE, 0, 1)
    sky = np.dstack([8 + 70 * sky_t ** 3, 6 + 12 * sky_t ** 3, 14 + 6 * sky_t]) * np.ones((1, w, 1))
    ground_line = SURFACE + 7 * np.sin(np.arange(w) / d / 53.0) + 4 * np.sin(np.arange(w) / d / 17.0 + 1)
    below = (y >= ground_line[None, :])
    rgb = np.where(below[..., None], rock, sky)
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image)
    for _ in range(140):   # stars and drifting embers
        sx, sy = rng.uniform(0, w), rng.uniform(0, (SURFACE - 40) * d)
        r = rng.uniform(0.6, 1.8) * d
        warm = rng.random() < 0.3
        draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 150, 80, 200) if warm else (220, 210, 230, 160))
    mx, my = 1150 * d, 62 * d
    for i in range(10, 0, -1):   # the red moon
        r = (26 + i * 5) * d
        draw.ellipse((mx - r, my - r, mx + r, my + r), fill=(200, 40, 30, 10))
    draw.ellipse((mx - 26 * d, my - 26 * d, mx + 26 * d, my + 26 * d), fill=(170, 40, 34, 255))
    # The turf along the surface.
    for x in range(0, w, 2):
        top = ground_line[x]
        draw.line((x, top * d - 1, x, top * d + 5 * d), fill=(34, 40, 26, 255), width=2)
    _village(draw, rng, d)
    _churchyard(draw, rng, d)
    _church(draw, d)
    _tunnels(draw, d, act=1)
    for key, (color, rx, ry) in CHAMBERS[1].items():
        _chamber(image, ANCHORS[1][key], color, rx, ry, d, rng)
    image = image.filter(ImageFilter.GaussianBlur(0.6 * d))
    vignette = _noise(w, h, 200 * d, seed + 7)
    array = np.asarray(image.convert("RGB")).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.clip(1.25 - np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) * 0.55, 0.45, 1)
    array *= (edge * (0.9 + 0.2 * vignette))[..., None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _stand_in_act2(seed: int = 3) -> Image.Image:
    """Act II: a jungle coast seen from above — black sea left, dense jungle inland, swamp center, gold temple hill right."""
    d = DENSITY
    w, h = WIDTH * d, HEIGHT * d
    rng = random.Random(seed + 100)
    # Base coordinate grids
    y = np.arange(h, dtype=np.float32)[:, None] / d
    x = np.arange(w, dtype=np.float32)[None, :] / d
    # Noise layers
    grain_fine = _noise(w, h, 4 * d, seed)
    grain_med = _noise(w, h, 30 * d, seed + 1)
    grain_coarse = _noise(w, h, 80 * d, seed + 2)
    grain = 0.5 * grain_fine + 0.3 * grain_med + 0.2 * grain_coarse
    # Region masks
    sea_mask = x < 280                    # black sea left
    coast_mask = (x >= 280) & (x < 420)   # shore/harbour
    jungle_mask = (x >= 420) & (x < 750)  # dense jungle inland
    swamp_mask = (x >= 750) & (x < 920) & (y > 450)  # swamp lower-center
    hill_mask = (x >= 880) & (y < 400)    # temple hill top-right
    # Base colors
    sea_color = np.dstack([3 + 5 * grain, 3 + 5 * grain, 8 + 10 * grain])
    coast_color = np.dstack([12 + 10 * grain, 25 + 15 * grain, 8 + 10 * grain])
    jungle_color = np.dstack([8 + 20 * grain, 35 + 30 * grain, 8 + 15 * grain])
    swamp_color = np.dstack([5 + 8 * grain, 10 + 10 * grain, 5 + 8 * grain])
    hill_color = np.dstack([35 + 20 * grain, 55 + 25 * grain, 20 + 15 * grain])
    # Combine
    rgb = np.where(sea_mask[..., None], sea_color,
           np.where(coast_mask[..., None], coast_color,
           np.where(jungle_mask[..., None], jungle_color,
           np.where(swamp_mask[..., None], swamp_color,
           np.where(hill_mask[..., None], hill_color, jungle_color)))))
    # Add texture variation
    variation = 0.25 * _noise(w, h, 25 * d, seed + 5)
    rgb = rgb * (0.88 + 0.24 * variation)[..., None]
    # Subtle ridges in jungle
    ridges = 0.15 * _noise(w, h, 12 * d, seed + 10) * np.sin(y / 15.0 + x / 20.0)
    rgb = np.where(jungle_mask[..., None], rgb * (1 + ridges)[..., None], rgb)
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image)
    # Coast line with small piers for docks
    for xi in range(0, w, 2):
        xp = xi / d
        coast_y = 420 + 35 * math.sin(xp / 35.0) + 20 * math.sin(xp / 12.0 + 0.7)
        if 0 <= coast_y <= HEIGHT:
            draw.line((xi, max(0, int(coast_y * d - 2)), xi, min(h, int(coast_y * d + 2))), fill=(8, 6, 5, 255), width=2)
    # Docks: short piers into the sea
    for px in (160, 190, 220, 250):
        draw.line((int(px * d), int(380 * d), int(px * d), int(460 * d)), fill=(40, 35, 30, 255), width=max(1, d // 2))
    # Swamp water channels
    for i in range(12):
        cx = 780 + 40 * math.sin(i * 0.5)
        cy = 520 + 30 * math.cos(i * 0.7)
        r = 15 + 8 * grain_coarse[int(cy * d) % h, int(cx * d) % w]
        draw.ellipse((int((cx - r) * d), int((cy - r) * d), int((cx + r) * d), int((cy + r) * d)), fill=(2, 2, 4, 200))
    # Hill contours
    for level in range(4):
        for xi in range(int(880 * d), w, 4):
            xp = xi / d
            hy = 380 - level * 25 + 12 * math.sin(xp / 30.0 + level)
            if 0 <= hy <= HEIGHT:
                draw.line((xi, int(hy * d), xi + 2, int(hy * d)), fill=(60, 50, 30, 180), width=1)
    # Draw chambers (glowing locations)
    for key, (color, rx, ry) in CHAMBERS[2].items():
        _chamber(image, ANCHORS[2][key], color, rx, ry, d, rng)
    # Draw trails
    _tunnels(draw, d, act=2)
    # Gold glows for Travincal and Temple
    for key in ("travincal", "temple"):
        cx, cy = ANCHORS[2][key]
        cx, cy = int(cx * d), int(cy * d)
        for i in range(6):
            r = (10 + i * 4) * d
            draw.ellipse((cx - r, cy - r, cx + r, cx + r), fill=(255, 210, 60, 35 - i * 5))
    # Stars over sea
    for _ in range(80):
        sx = rng.uniform(0, 280 * d)
        sy = rng.uniform(0, 400 * d)
        r = rng.uniform(0.5, 1.5) * d
        draw.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(220, 210, 230, 180))
    image = image.filter(ImageFilter.GaussianBlur(0.5 * d))
    vignette = _noise(w, h, 200 * d, seed + 7)
    array = np.asarray(image.convert("RGB")).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.clip(1.25 - np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) * 0.55, 0.45, 1)
    array *= (edge * (0.9 + 0.2 * vignette))[..., None]
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB")


def _village(draw: ImageDraw.ImageDraw, rng: random.Random, d: int) -> None:
    """Tristram: a huddle of roofs, some burning."""
    for i, x in enumerate((120, 165, 205, 250, 292, 335)):
        base = SURFACE + 2
        width, height = rng.uniform(30, 44), rng.uniform(22, 34)
        draw.rectangle(((x - width / 2) * d, (base - height) * d, (x + width / 2) * d, base * d), fill=(26, 20, 22, 255))
        draw.polygon([((x - width / 2 - 5) * d, (base - height) * d), (x * d, (base - height - 22) * d),
                      ((x + width / 2 + 5) * d, (base - height) * d)], fill=(20, 15, 17, 255))
        draw.rectangle(((x - 4) * d, (base - height + 8) * d, (x + 4) * d, (base - height + 16) * d), fill=(255, 170, 70, 255))
        if i % 2 == 0:   # on fire
            for k in range(6):
                fx = x + rng.uniform(-width / 2, width / 2)
                fy = base - height - rng.uniform(0, 30)
                r = rng.uniform(4, 10)
                draw.ellipse(((fx - r) * d, (fy - r * 1.4) * d, (fx + r) * d, (fy + r) * d), fill=(255, 110 + k * 12, 30, 190))


def _churchyard(draw: ImageDraw.ImageDraw, rng: random.Random, d: int) -> None:
    """The graveyard: crosses and headstones, and a crypt's mouth in the ground."""
    for x in range(560, 730, 17):
        base = SURFACE + 2 + rng.uniform(-2, 2)
        if rng.random() < 0.5:
            draw.rectangle(((x - 1.5) * d, (base - 20) * d, (x + 1.5) * d, base * d), fill=(60, 56, 58, 255))
            draw.rectangle(((x - 6) * d, (base - 15) * d, (x + 6) * d, (base - 12) * d), fill=(60, 56, 58, 255))
        else:
            draw.rounded_rectangle(((x - 5) * d, (base - 14) * d, (x + 5) * d, base * d), radius=4 * d, fill=(70, 66, 66, 255))
    draw.ellipse((620 * d, (SURFACE - 4) * d, 662 * d, (SURFACE + 18) * d), fill=(8, 6, 8, 255))


def _church(draw: ImageDraw.ImageDraw, d: int) -> None:
    """The cathedral on the hill: nave, tower and spire, windows red with the fire inside."""
    base = SURFACE + 3
    draw.rectangle((930 * d, (base - 70) * d, 1070 * d, base * d), fill=(22, 18, 22, 255))
    draw.polygon([(922 * d, (base - 70) * d), (1000 * d, (base - 112) * d), (1078 * d, (base - 70) * d)], fill=(18, 14, 18, 255))
    draw.rectangle((1040 * d, (base - 140) * d, 1066 * d, (base - 60) * d), fill=(20, 16, 20, 255))
    draw.polygon([(1036 * d, (base - 140) * d), (1053 * d, (base - 196) * d), (1070 * d, (base - 140) * d)], fill=(16, 12, 16, 255))
    for x in range(944, 1030, 20):
        draw.rectangle((x * d, (base - 56) * d, (x + 8) * d, (base - 30) * d), fill=(170, 40, 24, 255))
        draw.pieslice((x * d, (base - 62) * d, (x + 8) * d, (base - 50) * d), 180, 360, fill=(170, 40, 24, 255))
    draw.rectangle((990 * d, (base - 26) * d, 1010 * d, base * d), fill=(60, 14, 10, 255))


def _tunnels(draw: ImageDraw.ImageDraw, d: int, act: int = 1) -> None:
    t = TRAIL[act]
    for (a, b), points in t.items():
        if act == 1 and b in ("graveyard",):
            continue   # the surface road needs no tunnel
        start = 3 if act == 1 and (a, b) == ("graveyard", "cathedral") else 0
        path = [(x * d, y * d) for x, y in points[start:]]
        draw.line(path, fill=(14, 10, 10, 255), width=16 * d, joint="curve")
        draw.line(path, fill=(30, 22, 20, 255), width=9 * d, joint="curve")


def _chamber(image: Image.Image, at: tuple[float, float], color: tuple[int, int, int], rx: float, ry: float, d: int,
             rng: random.Random) -> None:
    """A cavity in the rock with its light inside."""
    cx, cy = at[0] * d, at[1] * d
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    points = []
    for k in range(28):
        a = 2 * math.pi * k / 28
        wobble = 1 + rng.uniform(-0.12, 0.12)
        points.append((cx + rx * d * wobble * math.cos(a), cy + ry * d * wobble * math.sin(a)))
    draw.polygon(points, fill=(10, 7, 8, 255))
    for i in range(12, 0, -1):
        r = i / 12
        draw.ellipse((cx - rx * d * r * 0.9, cy + ry * d * (0.5 - r * 0.8), cx + rx * d * r * 0.9, cy + ry * d * (0.5 + r * 0.4)),
                     fill=color + (int(28 * (1 - r) + 6),))
    draw.line([(cx - rx * d * 0.8, cy + ry * d * 0.62), (cx + rx * d * 0.8, cy + ry * d * 0.62)], fill=color + (120,), width=3 * d)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(2 * d)))


def picture(act: int = 1) -> Image.Image:
    """The map as the game shows it: the painting when there is one, else the stand-in."""
    if act == 1:
        if PAINTED.exists():
            return Image.open(PAINTED).convert("RGB").resize((WIDTH * DENSITY, HEIGHT * DENSITY), Image.LANCZOS)
    else:
        if PAINTED_II.exists():
            return Image.open(PAINTED_II).convert("RGB").resize((WIDTH * DENSITY, HEIGHT * DENSITY), Image.LANCZOS)
    return stand_in(act=act)

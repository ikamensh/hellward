"""The world map: a cut-away of the ground under Tristram, the six locations at fixed places on it, and the
trail the lantern walks down from one to the next.

The picture is drawn here as a stand-in (sky, the village, the churchyard and the church on the surface; the
cathedral's labyrinth, the catacombs, the caves and hell's gate as chambers ever deeper in the rock, joined by
tunnels). A painting of it (``assets/painted/worldmap.jpg``) replaces it when there is one; it was painted over
this stand-in, so the chambers stay where :data:`ANCHORS` says. Places are in the 1280 × 800 screen's pixels.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from hellward.art.rig import DENSITY

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted" / "worldmap.jpg"
WIDTH, HEIGHT = 1280, 800
SURFACE = 182          # where the ground begins

ANCHORS: dict[str, tuple[float, float]] = {
    "tristram": (230, 158),
    "graveyard": (640, 166),
    "cathedral": (990, 330),
    "catacombs": (380, 450),
    "caves": (900, 560),
    "hells_gate": (610, 668),
}

#: The trail between consecutive locations, as the points it bends at (both ends included).
TRAIL: dict[tuple[str, str], tuple[tuple[float, float], ...]] = {
    ("tristram", "graveyard"): ((230, 158), (330, 176), (450, 170), (560, 178), (640, 166)),
    ("graveyard", "cathedral"): ((640, 166), (760, 176), (900, 172), (975, 196), (1000, 240), (990, 330)),
    ("cathedral", "catacombs"): ((990, 330), (900, 356), (760, 372), (600, 400), (470, 420), (380, 450)),
    ("catacombs", "caves"): ((380, 450), (470, 500), (600, 520), (760, 530), (900, 560)),
    ("caves", "hells_gate"): ((900, 560), (840, 610), (740, 640), (610, 668)),
}

CHAMBERS: dict[str, tuple[tuple[int, int, int], float, float]] = {   # glow colour, half width, half height
    "cathedral": ((150, 70, 190), 118, 64),
    "catacombs": ((200, 190, 160), 124, 62),
    "caves": ((255, 110, 30), 132, 70),
    "hells_gate": ((255, 60, 20), 150, 76),
}


def trail(a: str, b: str) -> tuple[tuple[float, float], ...]:
    """The trail from one location to another, in either direction along the descent."""
    if (a, b) in TRAIL:
        return TRAIL[(a, b)]
    return tuple(reversed(TRAIL[(b, a)]))


def _noise(width: int, height: int, scale: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coarse = rng.random((height // scale + 2, width // scale + 2)).astype(np.float32)
    image = Image.fromarray((coarse * 255).astype(np.uint8)).resize((width + scale * 2, height + scale * 2), Image.BICUBIC)
    return np.asarray(image, dtype=np.float32)[:height, :width] / 255.0


def stand_in(seed: int = 3) -> Image.Image:
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
    _tunnels(draw, d)
    for key, (color, rx, ry) in CHAMBERS.items():
        _chamber(image, ANCHORS[key], color, rx, ry, d, rng)
    image = image.filter(ImageFilter.GaussianBlur(0.6 * d))
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


def _tunnels(draw: ImageDraw.ImageDraw, d: int) -> None:
    for (a, b), points in TRAIL.items():
        if b in ("graveyard",):
            continue   # the surface road needs no tunnel
        start = 3 if (a, b) == ("graveyard", "cathedral") else 0
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


def picture() -> Image.Image:
    """The map as the game shows it: the painting when there is one, else the stand-in."""
    if PAINTED.exists():
        return Image.open(PAINTED).convert("RGB").resize((WIDTH * DENSITY, HEIGHT * DENSITY), Image.LANCZOS)
    return stand_in()

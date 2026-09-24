"""Procedural textures for light and magic: soft glows, sparks, rings, shards, smoke, sigils and shadows,
and the two glass orbs of the interface.

Everything is drawn once at the art density and registered under ``fx/<name>``. The glows are white-hot
in the middle and fade to the element's colour at the edge, so layered over the dark map they read as light.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from saga2d import Game

from hellward.art.rig import DENSITY

ELEMENT_COLORS = {
    "fire": (255, 120, 32),
    "lightning": (130, 190, 255),
    "cold": (150, 220, 255),
    "poison": (120, 230, 60),
    "curse": (190, 40, 230),
    "holy": (255, 220, 130),
    "blood": (220, 20, 30),
    "ember": (255, 70, 20),
}


def _radial(size: int) -> np.ndarray:
    c = (size - 1) / 2
    y, x = np.mgrid[0:size, 0:size]
    return np.sqrt((x - c) ** 2 + (y - c) ** 2) / c


def glow(color: tuple[int, int, int], size: int = 64, falloff: float = 2.2, core: float = 0.35) -> Image.Image:
    r = _radial(size)
    alpha = np.clip(1 - r, 0, 1) ** falloff
    white = np.clip(1 - r / core, 0, 1) ** 1.5 if core > 0 else np.zeros_like(r)
    rgb = np.array(color, dtype=np.float32)[None, None, :] * (1 - white[..., None]) + 255 * white[..., None]
    rgba = np.dstack([rgb, alpha * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def ring(color: tuple[int, int, int], size: int = 160, width: float = 0.12) -> Image.Image:
    r = _radial(size)
    alpha = np.clip(1 - np.abs(r - (1 - width)) / width, 0, 1) ** 1.5
    inner = np.clip(1 - r, 0, 1) * 0.18 * (r < 1)
    rgb = np.array(color, dtype=np.float32)[None, None, :] * np.ones_like(r)[..., None]
    rgb = rgb * 0.7 + 255 * 0.3 * alpha[..., None]
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha + inner, 0, 1) * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def shard(color: tuple[int, int, int], size: int = 20) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon([(size / 2, 0), (size * 0.68, size * 0.55), (size / 2, size), (size * 0.32, size * 0.55)], fill=color + (240,))
    draw.line([(size / 2, 1), (size / 2, size - 2)], fill=(255, 255, 255, 220), width=1)
    return image


def smoke(color: tuple[int, int, int], size: int = 48, seed: int = 0) -> Image.Image:
    rng = np.random.default_rng(seed)
    r = _radial(size)
    noise = Image.fromarray((rng.random((6, 6)) * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    n = np.asarray(noise, dtype=np.float32) / 255
    alpha = np.clip(1 - r, 0, 1) ** 1.4 * (0.55 + 0.45 * n)
    rgb = np.array(color, dtype=np.float32)[None, None, :] * (0.8 + 0.3 * n[..., None])
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 200]).astype(np.uint8), "RGBA")


def shadow(width: int = 64, height: int = 24) -> Image.Image:
    y, x = np.mgrid[0:height, 0:width]
    d = np.sqrt(((x - (width - 1) / 2) / (width / 2)) ** 2 + ((y - (height - 1) / 2) / (height / 2)) ** 2)
    alpha = np.clip(1 - d, 0, 1) ** 1.2 * 150
    return Image.fromarray(np.dstack([np.zeros((height, width, 3)), alpha]).astype(np.uint8), "RGBA")


def sigil(color: tuple[int, int, int], size: int = 96, seed: int = 3) -> Image.Image:
    """A curse's rune circle: two rings, a triangle and scratched runes between them."""
    ss = 3
    big = size * ss
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c = big / 2
    rgba = color + (255,)
    for r, w in ((0.47, 5), (0.36, 4)):
        draw.ellipse((c - r * big, c - r * big, c + r * big, c + r * big), outline=rgba, width=w * ss // 2)
    tri = [(c + 0.36 * big * math.cos(a), c + 0.36 * big * math.sin(a)) for a in (-math.pi / 2, math.pi / 6, 5 * math.pi / 6)]
    draw.polygon(tri, outline=rgba, width=4)
    rng = random.Random(seed)
    for i in range(9):
        a = 2 * math.pi * i / 9
        cx, cy = c + 0.415 * big * math.cos(a), c + 0.415 * big * math.sin(a)
        for _ in range(3):
            dx, dy = rng.uniform(-9, 9), rng.uniform(-9, 9)
            draw.line((cx, cy, cx + dx, cy + dy), fill=rgba, width=5)
    image = image.resize((size, size), Image.LANCZOS)
    blur = image.filter(ImageFilter.GaussianBlur(2.5))
    out = Image.alpha_composite(blur, image)
    return out


def bolt_trail(color: tuple[int, int, int], length: int = 48, width: int = 14) -> Image.Image:
    """An elongated glow, bright at its head (the right end)."""
    y, x = np.mgrid[0:width, 0:length]
    along = x / (length - 1)
    across = np.abs(y - (width - 1) / 2) / (width / 2)
    alpha = np.clip(1 - across, 0, 1) ** 1.6 * along ** 1.4
    white = np.clip((along - 0.75) / 0.25, 0, 1) * np.clip(1 - across * 1.6, 0, 1)
    rgb = np.array(color, dtype=np.float32)[None, None, :] * (1 - white[..., None]) + 255 * white[..., None]
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def orb(liquid: tuple[int, int, int], fill: float, size: int = 116) -> Image.Image:
    """A Diablo-style glass orb, filled to *fill* with swirling liquid, in a dark iron socket."""
    ss = 2
    big = size * ss
    r = _radial(big)
    y, x = np.mgrid[0:big, 0:big]
    level = 1 - fill   # the liquid's surface, as a share of the height from the top
    inside = r < 0.86
    wet = inside & (y / big > level * 0.86 + 0.07)
    swirl = 0.5 + 0.5 * np.sin(x / big * 9 + y / big * 5 + np.sin(y / big * 11) * 2)
    base = np.zeros((big, big, 4), dtype=np.float32)
    color = np.array(liquid, dtype=np.float32)
    shade = (0.55 + 0.45 * (1 - r)) * (0.75 + 0.35 * swirl)
    base[wet, :3] = color * shade[wet, None]
    base[wet, 3] = 255
    dry = inside & ~wet
    base[dry, :3] = np.array((18, 14, 16)) + 20 * (1 - r[dry, None])
    base[dry, 3] = 255
    rim = (r >= 0.86) & (r < 1.0)
    base[rim, :3] = np.array((70, 62, 58)) * (0.6 + 0.8 * (1 - np.abs(r[rim, None] - 0.93) / 0.07))
    base[rim, 3] = 255
    image = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    shine = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shine)
    draw.ellipse((big * 0.26, big * 0.14, big * 0.52, big * 0.34), fill=(255, 255, 255, 70))
    draw.ellipse((big * 0.3, big * 0.17, big * 0.42, big * 0.25), fill=(255, 255, 255, 110))
    image = Image.alpha_composite(image, shine.filter(ImageFilter.GaussianBlur(6)))
    return image.resize((size, size), Image.LANCZOS)


ORB_LEVELS = 40


def register(game: Game) -> None:
    assets = game.assets
    d = DENSITY
    for name, color in ELEMENT_COLORS.items():
        assets.image_from_pil(f"fx/glow/{name}", glow(color, 64 * d))
        assets.image_from_pil(f"fx/soft/{name}", glow(color, 64 * d, falloff=1.4, core=0.0))
        assets.image_from_pil(f"fx/ring/{name}", ring(color, 160 * d))
        assets.image_from_pil(f"fx/trail/{name}", bolt_trail(color, 48 * d, 14 * d))
        assets.image_from_pil(f"fx/sigil/{name}", sigil(color, 96 * d))
    assets.image_from_pil("fx/spark", glow((255, 230, 180), 12 * d, falloff=1.5, core=0.5))
    assets.image_from_pil("fx/shard", shard((190, 235, 255), 20 * d))
    for i in range(3):
        assets.image_from_pil(f"fx/smoke/{i}", smoke((70, 64, 64), 48 * d, seed=i))
        assets.image_from_pil(f"fx/venom/{i}", smoke((90, 170, 40), 48 * d, seed=10 + i))
        assets.image_from_pil(f"fx/miasma/{i}", smoke((110, 30, 140), 48 * d, seed=20 + i))
    assets.image_from_pil("fx/shadow", shadow(64 * d, 24 * d))
    assets.image_from_pil("fx/blood", _splat((110, 8, 12), 40 * d, 1))
    assets.image_from_pil("fx/ichor", _splat((60, 90, 30), 40 * d, 2))
    assets.image_from_pil("fx/dust", _splat((150, 144, 130), 40 * d, 3))
    for i in range(ORB_LEVELS + 1):
        assets.image_from_pil(f"ui/orb/life/{i}", orb((190, 14, 20), i / ORB_LEVELS, 116 * d))
        assets.image_from_pil(f"ui/orb/mana/{i}", orb((30, 60, 210), i / ORB_LEVELS, 116 * d))


def _splat(color: tuple[int, int, int], size: int, seed: int) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    c = size / 2
    for _ in range(14):
        r = rng.uniform(size * 0.05, size * 0.2)
        ox, oy = rng.gauss(0, size * 0.14), rng.gauss(0, size * 0.1)
        draw.ellipse((c + ox - r, c + oy - r * 0.7, c + ox + r, c + oy + r * 0.7), fill=color + (rng.randint(150, 230),))
    return image.filter(ImageFilter.GaussianBlur(1))


def panel(width: int, height: int, seed: int = 7) -> Image.Image:
    """The bottom panel: dark worked stone between two gilded rails, with a riveted iron trim."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:height, 0:width]
    coarse = Image.fromarray((rng.random((height // 16 + 2, width // 16 + 2)) * 255).astype(np.uint8)).resize(
        (width + 32, height + 32), Image.BICUBIC)
    n = np.asarray(coarse, dtype=np.float32)[:height, :width] / 255
    fine = rng.random((height, width)).astype(np.float32)
    shade = 0.75 + 0.35 * n + 0.08 * fine - 0.25 * (y / height)
    rgb = np.dstack([34 * shade, 29 * shade, 30 * shade])
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    draw = ImageDraw.Draw(image)
    s = height / 128
    for yy, color, w in ((2 * s, (120, 92, 48), 3 * s), (7 * s, (60, 46, 30), 2 * s), (height - 3 * s, (70, 54, 34), 3 * s)):
        draw.line((0, yy, width, yy), fill=color + (255,), width=max(1, int(w)))
    for xx in range(int(20 * s), width, int(64 * s)):
        draw.ellipse((xx - 3 * s, 3 * s, xx + 3 * s, 9 * s), fill=(150, 120, 70, 255))
    return image


def slot(size: int, lit: bool) -> Image.Image:
    """A bevelled stone socket for a build or spell icon."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    edge = (150, 118, 64) if lit else (86, 70, 50)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 10, fill=(18, 14, 16, 255), outline=edge + (255,), width=max(2, size // 28))
    inner = size // 14
    draw.rounded_rectangle((inner, inner, size - 1 - inner, size - 1 - inner), radius=size // 12, outline=(50, 40, 34, 255), width=max(1, size // 40))
    if lit:
        glow_layer = Image.fromarray((np.clip(1 - _radial(size), 0, 1) ** 2 * 90).astype(np.uint8))
        warm = Image.new("RGBA", (size, size), (255, 170, 80, 0))
        warm.putalpha(glow_layer)
        image = Image.alpha_composite(image, warm)
    return image


def register_ui(game: Game) -> None:
    game.assets.image_from_pil("ui/panel", panel(1280 * DENSITY, 128 * DENSITY))
    game.assets.image_from_pil("ui/slot", slot(68 * DENSITY, False))
    game.assets.image_from_pil("ui/slot_lit", slot(68 * DENSITY, True))

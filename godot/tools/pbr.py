"""Turn Codex's tileable paintings into the game's material maps.

    python3 tools/pbr.py            # every painted tile
    python3 tools/pbr.py cobbles    # one, with a 2x2 preview in the scratch dir given by --preview

A painting is cropped to its opaque interior, quilted with itself across both wraps (a minimum-error
cut through the overlap, as in Efros-Freeman quilting) so it tiles, and flattened at large scale so
no blotch repeats. Height comes from luminance at the scale of the pattern; the normal map (OpenGL,
green up, as Godot reads it) and roughness come from height. Outputs:
game/assets/textures/<name>_{albedo,normal,rough,height}.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paint import OUT as PAINTED, TEXTURES  # noqa: E402

GAME = Path(__file__).resolve().parent.parent / "game" / "assets" / "textures"
SIZE = 1024

# name: (normal strength, base roughness, roughness spread, height detail blur px)
LOOK = {
    "cobbles": (5.0, 0.80, 0.15, 24),
    "flagstones": (4.0, 0.82, 0.12, 30),
    "earth": (2.5, 0.92, 0.06, 12),
    "grass": (2.0, 0.90, 0.08, 8),
    "plaster": (1.6, 0.92, 0.05, 16),
    "timber": (3.0, 0.78, 0.12, 10),
    "planks": (3.0, 0.80, 0.10, 14),
    "thatch": (3.5, 0.95, 0.04, 10),
    "stone": (4.0, 0.85, 0.10, 28),
    "slate": (3.0, 0.60, 0.20, 20),
    "iron": (2.0, 0.55, 0.30, 10),
    "demon_skin": (2.5, 0.55, 0.20, 10),
    "corpse_skin": (2.5, 0.60, 0.20, 10),
    "bone": (1.5, 0.50, 0.20, 12),
    "cloth": (2.0, 0.95, 0.04, 8),
    "basalt": (2.0, 0.35, 0.25, 16),
}


def opaque_square(img: Image.Image) -> np.ndarray:
    """The largest centred square whose pixels are all opaque, as float RGB in 0..1."""
    a = np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0
    h, w = a.shape[:2]
    side = min(h, w)
    y0, x0 = (h - side) // 2, (w - side) // 2
    a = a[y0:y0 + side, x0:x0 + side]
    m = 0
    while m < side // 3 and a[m:side - m, m:side - m, 3].min() < 0.9:
        m += 4
    if m:
        m += 8   # the soft rim inside the alpha edge
    return a[m:side - m, m:side - m, :3]


def _cut_mask(err: np.ndarray) -> np.ndarray:
    """A mask over an (h, o) overlap: 1 left of the vertical path of least error, 0 right of it."""
    h, o = err.shape
    cost = err.copy()
    for y in range(1, h):
        prev = cost[y - 1]
        left = np.concatenate([[np.inf], prev[:-1]])
        right = np.concatenate([prev[1:], [np.inf]])
        cost[y] += np.minimum(np.minimum(left, prev), right)
    path = np.empty(h, dtype=int)
    path[-1] = int(np.argmin(cost[-1]))
    for y in range(h - 2, -1, -1):
        x = path[y + 1]
        lo, hi = max(0, x - 1), min(o, x + 2)
        path[y] = lo + int(np.argmin(cost[y, lo:hi]))
    cols = np.arange(o)[None, :]
    return (cols < path[:, None]).astype(np.float32)


def wrap_x(img: np.ndarray, overlap: int) -> np.ndarray:
    """Make the left and right edges meet: the tile's first columns cut from the image's last ones."""
    n = img.shape[1]
    left, right = img[:, :overlap], img[:, n - overlap:]
    err = ((left - right) ** 2).sum(axis=2)
    mask = _cut_mask(err)
    feather = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)),
                         dtype=np.float32)[..., None] / 255.0
    seam = feather * right + (1 - feather) * left
    return np.concatenate([seam, img[:, overlap:n - overlap]], axis=1)


def tileable(img: np.ndarray) -> np.ndarray:
    overlap = img.shape[0] // 6
    img = wrap_x(img, overlap)
    img = wrap_x(img.transpose(1, 0, 2), overlap).transpose(1, 0, 2)
    return img


def blur(a: np.ndarray, radius: float) -> np.ndarray:
    """Gaussian blur that wraps, so maps stay tileable."""
    sigma = (radius, radius) + (0,) * (a.ndim - 2)
    return ndimage.gaussian_filter(a, sigma, mode="wrap")


def lum(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def material(name: str) -> dict[str, Image.Image]:
    strength, rough, spread, detail = LOOK[name]
    rgb = tileable(opaque_square(Image.open(PAINTED / f"{name}.png")))
    rgb = np.asarray(Image.fromarray((rgb * 255).clip(0, 255).astype(np.uint8)).resize((SIZE, SIZE), Image.LANCZOS),
                     dtype=np.float32) / 255.0
    # flatten blotches larger than a quarter tile, so the repeat does not show
    y = lum(rgb)
    low = blur(y, SIZE / 8)
    rgb = (rgb * (y.mean() / np.maximum(low, 0.02))[..., None]).clip(0, 1)
    y = lum(rgb)
    height = y - blur(y, detail * SIZE / 1024)
    height = blur(height, 1.2)
    height = (height - height.min()) / max(1e-6, height.max() - height.min())
    gy, gx = np.gradient(height)
    nx, ny = -gx * strength * SIZE / 64, gy * strength * SIZE / 64
    nz = np.ones_like(nx)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / norm, ny / norm, nz / norm], axis=2) * 0.5 + 0.5
    roughness = (rough + spread * (0.5 - height)).clip(0.05, 1.0)
    cavity = (blur(height, 6) - height).clip(0, 1)
    albedo = rgb * (1 - 0.6 * cavity / max(1e-6, cavity.max()))[..., None]

    def img(a: np.ndarray) -> Image.Image:
        return Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))

    return {"albedo": img(albedo), "normal": img(normal), "rough": img(roughness), "height": img(height)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*")
    parser.add_argument("--preview", type=Path, help="write a 2x2 tiling of each albedo here")
    args = parser.parse_args()
    names = args.names or [n for n in TEXTURES if (PAINTED / f"{n}.png").exists()]
    GAME.mkdir(parents=True, exist_ok=True)
    for name in names:
        maps = material(name)
        for kind, im in maps.items():
            im.save(GAME / f"{name}_{kind}.png")
        if args.preview:
            args.preview.mkdir(parents=True, exist_ok=True)
            a = maps["albedo"]
            sheet = Image.new("RGB", (SIZE * 2, SIZE * 2))
            for x in (0, SIZE):
                for yy in (0, SIZE):
                    sheet.paste(a, (x, yy))
            sheet.resize((SIZE, SIZE)).save(args.preview / f"{name}.png")
        print(f"material {name}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

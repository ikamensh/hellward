"""Turn Codex's effect paintings (art/painted/) into the game's effect sprites (game/assets/fx/).

    uv run python tools/fxsprites.py

Additive sprites (fire, rune circle, portal swirl) keep their black backgrounds, which add nothing.
Blended ones get alpha: smoke and blood from their brightness over black, the scorch from its darkness over white.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "art" / "painted", ROOT / "game" / "assets" / "fx"


def load(name: str) -> np.ndarray:
    return np.asarray(Image.open(SRC / f"{name}.png").convert("RGB"), dtype=np.float32) / 255.0


def save(name: str, a: np.ndarray, size: int) -> None:
    mode = "RGBA" if a.shape[2] == 4 else "RGB"
    Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8), mode).resize((size, size), Image.LANCZOS).save(OUT / f"{name}.png")
    print(f"fx {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("fire_sheet", "portal_swirl"):
        rgb = load(name)
        rgb[rgb.max(axis=2) < 0.04] = 0.0     # the painter's near-black is not quite black
        save(name, rgb, 1024)
    rune = load("rune_circle")                # a decal: its glow needs alpha to cut the black square out
    alpha = ((rune.max(axis=2) - 0.06) / 0.35).clip(0, 1)
    save("rune_circle", np.dstack([rune / np.maximum(rune.max(axis=2, keepdims=True), 0.05), alpha]), 1024)
    smoke = load("smoke_sheet")
    lum = smoke.mean(axis=2)
    alpha = ((lum - 0.03) / 0.6).clip(0, 1)
    save("smoke_sheet", np.dstack([np.full_like(smoke, 0.82), alpha]), 1024)
    blood = load("blood_decal")
    alpha = ((blood.max(axis=2) - 0.05) / 0.25).clip(0, 1)
    save("blood_decal", np.dstack([blood / np.maximum(blood.max(axis=2, keepdims=True), 0.05) * 0.35, alpha]), 512)
    scorch = load("scorch_decal")
    alpha = ((0.92 - scorch.mean(axis=2)) / 0.7).clip(0, 1)
    save("scorch_decal", np.dstack([scorch * 0.6, alpha]), 512)


if __name__ == "__main__":
    main()

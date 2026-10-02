"""Turn Codex's effect paintings (art/painted/) into the game's effect sprites (game/assets/fx/) and HUD pieces
(game/assets/ui/).

    uv run python tools/fxsprites.py

Additive sprites (fire, portal swirl) keep their black backgrounds, which add nothing. Blended ones get alpha:
smoke, blood and the rune circle from their brightness over black; the scorch from a filled, blurred mask of the
painted disc times its darkness (with matte ORM and cooling-ember maps beside it).
HUD pieces were painted on flat green, which is keyed out.
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT, UI = ROOT / "art" / "painted", ROOT / "game" / "assets" / "fx", ROOT / "game" / "assets" / "ui"
HOLE = 0.40   # an orb frame's opening, as a fraction of the frame image's half-size (hud.gd: Hud.FRAME_HOLE)


def load(name: str) -> np.ndarray:
    return np.asarray(Image.open(SRC / f"{name}.png").convert("RGB"), dtype=np.float32) / 255.0


def save(name: str, a: np.ndarray, size: int) -> None:
    mode = "RGBA" if a.shape[2] == 4 else "RGB"
    Image.fromarray((a.clip(0, 1) * 255).astype(np.uint8), mode).resize((size, size), Image.LANCZOS).save(OUT / f"{name}.png")
    print(f"fx {name}")


def keyed(name: str) -> np.ndarray:
    """A painting on flat green as RGBA: alpha from how green each pixel is, the colour unmixed from the green."""
    rgba = np.asarray(Image.open(SRC / f"{name}.png").convert("RGBA"), dtype=np.float32) / 255.0
    rgb = rgba[..., :3]
    if rgba[..., 3].min() < 0.5:     # Codex sometimes hands back a cut-out: its colours are not mixed with green
        alpha, fg = rgba[..., 3].copy(), rgb.copy()
    else:
        green = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
        alpha = (1.0 - (green - 0.06) / 0.86).clip(0, 1)
        a = np.maximum(alpha, 0.05)[..., None]
        fg = ((rgb - (1.0 - a) * np.array([0.0, 1.0, 0.0])) / a).clip(0, 1)
    fg[..., 1] = np.minimum(fg[..., 1], np.maximum(fg[..., 0], fg[..., 2]) + 0.04)   # what green still spills
    alpha[alpha < 0.04] = 0.0
    return np.dstack([fg, alpha])


def ui_icon(name: str, size: int) -> None:
    """An icon cropped square to its painted object."""
    a = keyed(name)
    ys, xs = np.nonzero(a[..., 3] > 0.5)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    half = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2 + 4
    _save_ui(name, a, cx, cy, half, size)


def ui_frame(name: str, size: int) -> None:
    """An orb's frame, centred on the ring's opening, which spans HOLE of the half-size."""
    a = keyed(name)
    solid = a[..., 3] > 0.5
    hole, _ = ndimage.label(~solid)
    h, w = solid.shape
    inside = hole == hole[h // 2, w // 2]
    if inside[0, 0]:
        raise ValueError(f"{name}: the ring's opening runs into the background")
    ys, xs = np.nonzero(inside)
    cx, cy = xs.mean(), ys.mean()
    r = np.sqrt(inside.sum() / np.pi)
    half = r / HOLE
    oy, ox = np.nonzero(solid)
    reach = max(np.abs(ox - cx).max(), np.abs(oy - cy).max())
    if reach > half:
        raise ValueError(f"{name}: the frame reaches {reach / r:.2f} openings out, more than 1/HOLE")
    _save_ui(name, a, cx, cy, half, size)


def ui() -> None:
    UI.mkdir(parents=True, exist_ok=True)
    for name in ("orb_life_frame", "orb_mana_frame"):
        ui_frame(name, 768)
    for name in ("coin", "cleanse", "smite", "meteor", "orb"):
        ui_icon(name, 256)
    Image.open(SRC / "icon.png").convert("RGB").resize((1024, 1024), Image.LANCZOS).save(UI / "icon.png")
    print("ui icon")


def _save_ui(name: str, a: np.ndarray, cx: float, cy: float, half: float, size: int) -> None:
    img = Image.fromarray((a * 255).astype(np.uint8), "RGBA")
    box = (round(cx - half), round(cy - half), round(cx + half), round(cy + half))
    img.crop(box).resize((size, size), Image.LANCZOS).save(UI / f"{name}.png")
    print(f"ui {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("fire_sheet", "portal_swirl"):
        rgb = load(name)
        rgb[rgb.max(axis=2) < 0.04] = 0.0     # the painter's near-black is not quite black
        save(name, rgb, 1024)
    rune = load("rune_circle")                # a decal: its lines get alpha, its haze none, so it stays crisp
    alpha = ((rune.max(axis=2) - 0.2) / 0.45).clip(0, 1) ** 1.5
    save("rune_circle", np.dstack([rune, alpha]), 1024)
    smoke = load("smoke_sheet")
    lum = smoke.mean(axis=2)
    alpha = ((lum - 0.03) / 0.6).clip(0, 1)
    save("smoke_sheet", np.dstack([np.full_like(smoke, 0.82), alpha]), 1024)
    blood = load("blood_decal")
    alpha = ((blood.max(axis=2) - 0.05) / 0.25).clip(0, 1)
    save("blood_decal", np.dstack([blood / np.maximum(blood.max(axis=2, keepdims=True), 0.05) * 0.35, alpha]), 512)
    scorch = load("scorch_decal")             # a pale ash ring round a charred core, painted over black
    disc = ndimage.binary_fill_holes(ndimage.binary_closing(scorch.max(axis=2) > 0.035, iterations=6))
    disc = ndimage.gaussian_filter(ndimage.binary_erosion(disc, iterations=5).astype(np.float32), 3)
    dark = ((0.9 - scorch.mean(axis=2)) / 0.7).clip(0, 1) ** 1.3
    alpha = disc * (0.1 + 0.9 * dark)
    save("scorch_decal", np.dstack([scorch * 0.45, alpha]), 512)
    # and its ORM: soot is matte and swallows the sky's light, so the stone's sheen goes too
    save("scorch_orm", np.dstack([1.0 - 0.6 * dark, np.ones_like(dark), np.zeros_like(dark), alpha]), 512)
    # and its embers alone, for a glow that cools: orange specks, not the grey ash
    r, g, b = scorch[..., 0], scorch[..., 1], scorch[..., 2]
    ember = ((r - 0.9 * g - 0.3 * b - 0.08) / 0.3).clip(0, 1)
    save("scorch_glow", scorch * (ember * disc)[..., None], 512)
    ui()


if __name__ == "__main__":
    main()

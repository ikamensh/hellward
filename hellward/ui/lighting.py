"""Darkness with pools of light, the Diablo way: one small picture stretched over the map every frame.

Each cell of the picture covers six logical pixels. Where no light reaches, it is near-black at
:data:`DARK` opacity; where light falls, it thins out and takes on the light's colour a little. The
picture is drawn above the monsters and towers and below the effects, so a firebolt stays white-hot
while the corridor around it is lit orange. Bilinear filtering makes the cells soft.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from saga2d import RenderLayer, Scene, Sprite, SpriteAnchor

CELL = 6          # logical pixels per light cell
DARK = 0.5        # opacity of unlit ground
TINT = 0.16       # how strongly a light colours what it lights


@dataclass
class Light:
    x: float          # world logical pixels
    y: float
    radius: float     # logical pixels
    color: tuple[int, int, int]
    intensity: float = 1.0


class Lighting:
    def __init__(self, scene: Scene, origin: tuple[float, float], size: tuple[int, int]) -> None:
        self.origin = origin
        self.cols, self.rows = size[0] // CELL, size[1] // CELL
        ys, xs = np.mgrid[0:self.rows, 0:self.cols]
        self.xs = (xs + 0.5) * CELL + origin[0]
        self.ys = (ys + 0.5) * CELL + origin[1]
        scene.game.assets.image_from_pil("light", Image.new("RGBA", (self.cols, self.rows), (0, 0, 0, int(DARK * 255))))
        self.sprite = scene.add_sprite(Sprite(
            "light", position=origin, size=size, anchor=SpriteAnchor.TOP_LEFT, layer=RenderLayer.UNITS,
            y_sort=True, ground=-60_000))   # sorted after every standing thing, still below the effects layer
        self.scene = scene
        self.ambient = 0.0

    def render(self, lights: list[Light]) -> None:
        total = np.zeros((self.rows, self.cols), dtype=np.float32)
        color = np.zeros((self.rows, self.cols, 3), dtype=np.float32)
        for light in lights:
            r = light.radius
            c0 = max(0, int((light.x - r - self.origin[0]) / CELL))
            c1 = min(self.cols, int((light.x + r - self.origin[0]) / CELL) + 1)
            r0 = max(0, int((light.y - r - self.origin[1]) / CELL))
            r1 = min(self.rows, int((light.y + r - self.origin[1]) / CELL) + 1)
            if c0 >= c1 or r0 >= r1:
                continue
            dx = self.xs[r0:r1, c0:c1] - light.x
            dy = self.ys[r0:r1, c0:c1] - light.y
            f = np.clip(1.0 - (dx * dx + dy * dy) / (r * r), 0.0, 1.0)
            f = f * f * light.intensity
            total[r0:r1, c0:c1] += f
            color[r0:r1, c0:c1] += f[..., None] * np.array(light.color, dtype=np.float32)
        lit = np.clip(total + self.ambient, 0.0, 1.0)
        hue = color / np.maximum(total, 1e-4)[..., None]
        alpha = DARK * (1.0 - lit) + TINT * lit
        rgb = hue * lit[..., None]
        rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
        self.scene.game.assets.update_image("light", Image.fromarray(rgba, "RGBA"))

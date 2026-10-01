"""Draw an articulated painted creature using Saga2D's retained sprite batch."""

from __future__ import annotations

import math

from saga2d import RenderLayer, Scene, Sprite
from saga2d.rendering.layers import Y_SORT_STEP

from hellward.art import puppet


class PuppetBody:
    def __init__(self, scene: Scene, kind: str, facing: str) -> None:
        self.kind = kind
        self.last_pose = puppet.live_pose(kind, facing, 0)
        self.death_start: puppet.Endpoints | None = None
        self.order = puppet.rig(kind, facing).order
        self.sprites = [scene.add_sprite(Sprite(f"puppet/{kind}/{facing}/{name}",
                        layer=RenderLayer.UNITS, y_sort=True))
                        for name in puppet.rig(kind, facing).order]

    def draw(self, facing: str, pose: puppet.Endpoints, x: float, y: float, *,
             tint: tuple[float, float, float] = (1.0, 1.0, 1.0), opacity: int = 255) -> None:
        # Use the middle of the root's sorting interval. Floating point cancellation
        # at an exact boundary could otherwise send body pieces into different groups.
        sorting_y = math.floor(y / Y_SORT_STEP) * Y_SORT_STEP + Y_SORT_STEP * 0.5
        for sprite, name in zip(self.sprites, self.order):
            a, b = pose[name]
            transform = puppet.transform(self.kind, facing, name, a, b)
            image = f"puppet/{self.kind}/{facing}/{name}"
            if sprite.image != image:
                sprite.image = image
            if any(abs(a - b) > 1e-6 for a, b in zip(sprite.size, transform.size)):
                sprite.size = transform.size
            sprite.position = (x + transform.center[0], y + transform.center[1])
            sprite.rotation = transform.rotation
            sprite.ground = sprite.position[1] + sprite.height * 0.5 - sorting_y
            sprite.tint = tint
            sprite.opacity = opacity

    def walk(self, facing: str, distance: float, x: float, y: float) -> None:
        self.update(facing, distance, x, y)

    def update(self, facing: str, distance: float, x: float, y: float, *,
               hit: float = -1.0, attack: float = -1.0, death: float = -1.0,
               fall: int = 1, tint: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> None:
        opacity = 255
        if death >= 0:
            if self.death_start is None:
                self.death_start = self.last_pose
            pose = puppet.death_pose(self.kind, facing, self.death_start, death, fall)
            opacity = round(255 * min(1.0, max(0.0, (puppet.DEATH_LIFE[self.kind] - death) / 0.35)))
        else:
            pose = puppet.live_pose(self.kind, facing, distance, hit=hit, attack=attack)
            self.last_pose = pose
            self.order = puppet.rig(self.kind, facing).order
            if attack >= 0:
                arms = ("r_upper_arm", "r_forearm", "l_upper_arm", "l_forearm") if self.kind == "zombie" else ("r_upper_arm", "r_forearm")
                self.order = tuple(name for name in self.order if name not in arms) + arms
        self.draw(facing, pose, x, y, tint=tint, opacity=opacity)

    def remove(self) -> None:
        for sprite in self.sprites:
            sprite.remove()

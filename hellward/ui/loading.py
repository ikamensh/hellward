"""The frame to look at while the game gets ready: its textures and sounds on a first launch, and the compiled
simulation when its sources changed. It imports nothing from the simulation, which may not be activated yet."""

from __future__ import annotations

from saga2d import Scene

from hellward.ui import style


class LoadingScene(Scene):
    background_color = (6, 4, 6, 255)

    def __init__(self, message: str = "Preparing the cathedral...") -> None:
        self.message = message

    def draw(self) -> None:
        self.draw_text("HELLWARD", 640, 360, style="banner", anchor_x="center", anchor_y="center")
        self.draw_text(self.message, 640, 410, font_size=16, color=style.DIM, anchor_x="center", anchor_y="center")

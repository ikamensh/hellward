"""The title screen and the reckoning at the end of a defence."""

from __future__ import annotations

import math
from typing import Callable

from saga2d import Anchor, Button, Column, Scene

from hellward.sim.content import START_LIVES
from hellward.sim.model import World
from hellward.ui import style


class TitleScene(Scene):
    background_color = (6, 4, 6, 255)

    def __init__(self, begin: Callable[[bool], None], quit: Callable[[], None]) -> None:
        self.begin = begin
        self.quit = quit
        self.clock = 0.0

    def on_enter(self) -> None:
        menu = Column(anchor=Anchor.CENTER, margin=(0, 150), spacing=12, children=[
            Button("Descend", shortcut="Enter", on_click=lambda: self.begin(False), width=320),
            Button("Watch the leaders at work", shortcut="D", on_click=lambda: self.begin(True), width=320),
            Button("Leave", shortcut="Esc", on_click=self.quit, width=320),
        ])
        self.ui.add(menu)

    def update(self, dt: float) -> None:
        self.clock += dt

    def draw(self) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.clock * 1.3)
        self.draw_image("ground", 0, 0, 1280, 800, opacity=0.35)
        self.draw_rect(0, 0, 1280, 800, (0, 0, 0, 150))
        for i in range(8):
            r = 260 - i * 28
            self.draw_circle(640, 230, r, (140, 20, 10, int(10 + 6 * pulse)))
        self.draw_text("HELLWARD", 643, 213, style="title", color=(0, 0, 0, 220), anchor_x="center", anchor_y="center")
        self.draw_text("HELLWARD", 640, 210, style="title", anchor_x="center", anchor_y="center")
        self.draw_text("The demons have leaders now. They watch your towers, and they choose.", 640, 290,
                       font_size=19, color=style.BONE, anchor_x="center", anchor_y="center")
        self.draw_text("Each curse is picked by playing the fight ahead, again and again, before it is cast.", 640, 320,
                       font_size=15, color=style.DIM, anchor_x="center", anchor_y="center")


class ReckoningScene(Scene):
    transparent = True
    background_color = None

    def __init__(self, world: World, again: Callable[[], None], title: Callable[[], None]) -> None:
        self.world = world
        self.again = again
        self.title = title
        self.curses = 0

    def on_enter(self) -> None:
        self.ui.add(Column(anchor=Anchor.CENTER, margin=(0, 150), spacing=10, children=[
            Button("Defend again", shortcut="Enter", on_click=self.again, width=280),
            Button("To the title", shortcut="Esc", on_click=self.title, width=280),
        ]))

    def draw(self) -> None:
        world = self.world
        won = world.outcome == "victory"
        self.draw_rect(0, 0, 1280, 800, (0, 0, 0, 185))
        title = "The Sanctuary Holds" if won else "The Sanctuary Has Fallen"
        self.draw_text(title, 640, 230, style="title", color=style.GOLD if won else style.BLOOD, anchor_x="center", anchor_y="center")
        lines = [
            f"Waves withstood: {world.wave + (1 if won else 0)} of {len(world.waves)}",
            f"Monsters slain: {world.kills}",
            f"Life kept: {world.lives} of {START_LIVES}",
        ]
        for i, line in enumerate(lines):
            self.draw_text(line, 640, 310 + i * 30, font_size=19, color=style.BONE, anchor_x="center", anchor_y="center")

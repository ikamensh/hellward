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
        self.art = self.game.assets.has_image("title")
        menu = Column(
            Button("Descend", shortcut="Enter", on_click=lambda: self.begin(False), width=320),
            Button("Watch the leaders at work", shortcut="D", on_click=lambda: self.begin(True), width=320),
            Button("Leave", shortcut="Esc", on_click=self.quit, width=320),
            anchor=Anchor.BOTTOM, margin=(0, 70), spacing=12)
        self.ui.add(menu)

    def update(self, dt: float) -> None:
        self.clock += dt

    def draw(self) -> None:
        pulse = 0.5 + 0.5 * math.sin(self.clock * 1.3)
        if self.art:
            self.draw_image("title", 0, 0, 1280, 800)
        else:
            self.draw_image("ground", 0, 0, 1280, 800, opacity=0.35)
        for i in range(10):   # the dark vault the title hangs in, breathing
            self.draw_rect(0, i * 26, 1280, 26, (0, 0, 0, int((150 + 20 * pulse) * (1 - i / 10))))
        for i in range(8):
            self.draw_rect(0, 800 - (i + 1) * 30, 1280, 30, (0, 0, 0, int(140 * (1 - i / 8))))
        self.draw_text("HELLWARD", 643, 103, style="title", color=(0, 0, 0, 230), anchor_x="center", anchor_y="center")
        self.draw_text("HELLWARD", 640, 100, style="title", color=(230 + int(20 * pulse), 186, 100, 255), anchor_x="center", anchor_y="center")
        self.draw_text("The demons have leaders now. They watch your towers, and they choose.", 641, 169,
                       font_size=19, color=(0, 0, 0, 220), anchor_x="center", anchor_y="center")
        self.draw_text("The demons have leaders now. They watch your towers, and they choose.", 640, 168,
                       font_size=19, color=style.BONE, anchor_x="center", anchor_y="center")
        self.draw_text("Each curse is picked by playing the fight ahead, again and again, before it is cast.", 640, 198,
                       font_size=15, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")


class ReckoningScene(Scene):
    transparent = True
    background_color = None

    def __init__(self, world: World, again: Callable[[], None], title: Callable[[], None]) -> None:
        self.world = world
        self.again = again
        self.title = title
        self.curses = 0

    def on_enter(self) -> None:
        self.ui.add(Column(
            Button("Defend again", shortcut="Enter", on_click=self.again, width=280),
            Button("To the title", shortcut="Esc", on_click=self.title, width=280),
            anchor=Anchor.BOTTOM, margin=(0, 190), spacing=10))

    def draw(self) -> None:
        world = self.world
        won = world.outcome == "victory"
        self.draw_rect(0, 0, 1280, 800, (0, 0, 0, 185))
        title = "The Sanctuary Holds" if won else "The Sanctuary Has Fallen"
        self.draw_text(title, 643, 213, style="title", color=(0, 0, 0, 230), anchor_x="center", anchor_y="center")
        self.draw_text(title, 640, 210, style="title", color=style.GOLD if won else style.BLOOD, anchor_x="center", anchor_y="center")
        lines = [
            f"Waves withstood: {world.wave + (1 if won else 0)} of {len(world.waves)}",
            f"Monsters slain: {world.kills}",
            f"Life kept: {world.lives} of {START_LIVES}",
            f"Curses the leaders laid on your towers: {world.curses_landed}, and you cleansed {world.cleanses}",
        ]
        for i, line in enumerate(lines):
            self.draw_text(line, 640, 300 + i * 32, font_size=19, color=style.BONE, anchor_x="center", anchor_y="center")

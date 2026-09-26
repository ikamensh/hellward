"""The title screen and the reckoning at the end of a defence."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Column, Row, Scene

from hellward.sim.campaign import ORDER, LOCATIONS, sigils
from hellward.sim.content import START_LIVES
from hellward.sim.model import World
from hellward.ui import style, widgets
from hellward.ui.menus import SettingsScene, settings

if TYPE_CHECKING:
    from hellward.ui.flow import Flow


class TitleScene(Scene):
    background_color = (6, 4, 6, 255)

    controls = {"s": "open_settings"}

    def __init__(self, flow: Flow) -> None:
        self.flow = flow
        self.clock = 0.0

    def open_settings(self) -> None:
        self.game.push(SettingsScene(settings(self.game)))

    def on_enter(self) -> None:
        self.art = self.game.assets.has_image("title")
        menu = Column(
            Button("Descend", shortcut="Enter", on_click=self.flow.descend, width=320),
            Button("Chronicle", shortcut="C", on_click=self.flow.chronicle, width=320),
            Button("Watch the leaders at work", shortcut="D", on_click=self.flow.demo, width=320),
            Button("Settings", hotkey="S", on_click=self.open_settings, width=320),
            Button("Leave", shortcut="Q", on_click=self.game.quit, width=320),
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
    """The end of a defence: how it went, the sigils it won (lit one by one), and where the way goes now."""

    transparent = True
    background_color = None

    def __init__(self, flow: Flow, world: World, gained: int) -> None:
        self.flow = flow
        self.world = world
        self.gained = gained
        self.earned = sigils(world.outcome, world.lives)
        self.clock = 0.0
        self.lit = 0
        key = world.location.key
        index = ORDER.index(key)
        after = LOCATIONS[ORDER[index + 1]] if index + 1 < len(ORDER) else None
        self.opened = after if after is not None and gained and flow.progress.best(key) == self.earned and \
            flow.progress.opened(after) and not flow.progress.held(after.key) else None

    def on_enter(self) -> None:
        self.ui.add(Row(Button("Again", shortcut="Enter", on_click=lambda: self.flow.leave_reckoning(self.world, again=True),
                               width=220),
                        Button("To the map", shortcut="Esc", on_click=lambda: self.flow.leave_reckoning(self.world, again=False),
                               width=220),
                        anchor=Anchor.BOTTOM, margin=(0, 150), spacing=16))

    def update(self, dt: float) -> None:
        self.clock += dt
        due = min(self.earned, int((self.clock - 0.6) / 0.45) + 1) if self.clock > 0.6 else 0
        while self.lit < due:
            self.lit += 1
            self.flow.sound.play("upgrade")

    def draw(self) -> None:
        world = self.world
        won = world.outcome == "victory"
        self.draw_rect(0, 0, 1280, 800, (0, 0, 0, 190))
        title = "The Sanctuary Holds" if won else "The Sanctuary Has Fallen"
        self.draw_text(title, 643, 153, style="title", color=(0, 0, 0, 230), anchor_x="center", anchor_y="center")
        self.draw_text(title, 640, 150, style="title", color=style.GOLD if won else style.BLOOD, anchor_x="center", anchor_y="center")
        self.draw_text(world.location.name, 640, 200, style="heading", color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        lines = [
            f"Waves withstood: {world.wave + (1 if won else 0)} of {len(world.waves)}",
            f"Monsters slain: {world.kills}",
            f"Life kept: {world.lives} of {START_LIVES}",
            f"Curses the leaders laid on your towers: {world.curses_landed}. You cleansed {world.cleanses} "
            f"and broke {world.chants_broken} before they landed.",
        ]
        for i, line in enumerate(lines):
            self.draw_text(line, 640, 250 + i * 30, font_size=18, color=style.BONE, anchor_x="center", anchor_y="center")
        widgets.sigil_pips(self, 640, 410, self.lit, size=16, gap=48)
        if won:
            note = (f"{self.gained} new sigil{'s' if self.gained > 1 else ''}: spend {'them' if self.gained > 1 else 'it'} on skills."
                    if self.gained else "No new sigils: you have held this place as well before.")
        else:
            note = "No sigils for a fallen sanctuary. Reshape your skills and try again."
        self.draw_text(note, 640, 450, font_size=16, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        if self.opened is not None:
            self.draw_text(f"The way down to {self.opened.called} is open.", 640, 482, font_size=17, color=style.HOLY,
                           anchor_x="center", anchor_y="center")

"""The title screen and the reckoning at the end of a defence."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Column, Label, Layout, Panel, Row, Scene
from saga2d.input import InputEvent

from hellward.sim.campaign import ORDER, LOCATIONS, sigils
from hellward.sim.content import START_LIVES
from hellward.sim.model import World
from hellward.ui import style, widgets
from hellward.ui.menus import PANEL, QUIET_BUTTON, SettingsScene, settings
from hellward.ui.progress import campaign_profiles

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

    def open_profiles(self) -> None:
        self.game.push(ProfileScene(self.flow))

    def on_enter(self) -> None:
        self.art = self.game.assets.has_image("title")
        menu = Column(
            Button("Descend", shortcut="Enter", on_click=self.flow.descend, width=320),
            Button("Campaign profiles", shortcut="P", on_click=self.open_profiles, width=320),
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
        self.draw_text(f"Campaign profile: {self.flow.progress.profile}", 640, 236,
                       font_size=16, color=style.BONE, anchor_x="center", anchor_y="center")


class ProfileScene(Scene):
    """Choose an existing campaign or name a new one before descending."""

    transparent = True
    pause_below = True
    pop_on_cancel = True
    PAGE_SIZE = 5

    def __init__(self, flow: Flow) -> None:
        self.flow = flow
        self.names: tuple[str, ...] = ()
        self.page = 0
        self.creating = False
        self.name = ""
        self.error = ""

    def on_enter(self) -> None:
        self.names = campaign_profiles(self.game)
        current = self.flow.progress.profile
        if current not in self.names:  # a command-line profile may not have been saved yet
            self.names = (*self.names, current)
        self.page = self.names.index(current) // self.PAGE_SIZE
        self.panel = Panel(layout=Layout.VERTICAL, spacing=10, anchor=Anchor.CENTER, style=PANEL)
        self.ui.add(self.panel)
        self.show_list()

    def show_list(self) -> None:
        self.creating = False
        self.panel.clear()
        self.panel.add(Label("Campaign profiles", text_style="banner", width=420, align="center"))
        self.panel.add(Label("Each profile saves its own progress.",
                             text_style="small", width=420, align="center", wrap=True))
        first = self.page * self.PAGE_SIZE
        for index, name in enumerate(self.names[first:first + self.PAGE_SIZE], 1):
            current = name == self.flow.progress.profile
            self.panel.add(Button(f"{name}{'  •  current' if current else ''}", shortcut=str(index),
                                  on_click=lambda chosen=name: self.select(chosen), width=420,
                                  style=None if current else QUIET_BUTTON))
        pages = (len(self.names) - 1) // self.PAGE_SIZE + 1
        if pages > 1:
            self.panel.add(Row(
                Button("Previous", on_click=lambda: self.turn_page(-1), width=150,
                       enabled=self.page > 0, style=QUIET_BUTTON),
                Label(f"{self.page + 1} / {pages}", text_style="small", width=100, align="center"),
                Button("Next", on_click=lambda: self.turn_page(1), width=150,
                       enabled=self.page + 1 < pages, style=QUIET_BUTTON), spacing=10))
        self.panel.add(Button("New campaign profile", shortcut="N", on_click=self.show_new, width=420))
        self.panel.add(Button("Back", shortcut="Esc", on_click=self.game.pop, width=420, style=QUIET_BUTTON))

    def turn_page(self, direction: int) -> None:
        self.page += direction
        self.show_list()

    def select(self, name: str) -> None:
        self.flow.switch_profile(name)
        self.game.pop()

    def show_new(self) -> None:
        self.creating = True
        self.name = ""
        self.error = ""
        self.panel.clear()
        self.panel.add(Label("New campaign", text_style="banner", width=420, align="center"))
        self.panel.add(Label("Use letters, digits or _. Start with a letter or _.",
                             text_style="small", width=420, align="center", wrap=True))
        field = Panel(layout=Layout.VERTICAL, style=QUIET_BUTTON)
        field.add(Label(lambda: f"{self.name}|" if self.name else "Name your campaign", text_style="heading",
                        width=410, align="center"))
        self.panel.add(field)
        self.panel.add(Label(lambda: self.error or "Backspace edits the name.", text_style="small", width=420,
                             align="center", text_color=style.PALE_GOLD))
        self.panel.add(Row(Button("Create", shortcut="Enter", on_click=self.create, width=205),
                           Button("Back", shortcut="Esc", on_click=self.show_list, width=205, style=QUIET_BUTTON),
                           spacing=10))

    def create(self) -> None:
        if not self.name.isidentifier() or not self.name.isascii():
            self.error = "Start with a letter or _; use only letters, digits and underscores."
        elif self.name.casefold() in {name.casefold() for name in self.names}:
            self.error = "That profile exists. Choose it from the list."
        else:
            self.flow.create_profile(self.name)
            self.game.pop()

    def handle_input(self, event: InputEvent) -> bool:
        if not self.creating or event.type != "key_press" or event.key is None:
            return False
        if event.key == "backspace":
            self.name = self.name[:-1]
            self.error = ""
            return True
        if event.ctrl or event.alt or event.meta:
            return False
        key = event.key
        char = "_" if key == "underscore" or (key == "minus" and event.shift) else key
        if len(char) != 1 or not char.isascii() or not (char.isalnum() or char == "_"):
            return False
        if len(self.name) >= 24:
            self.error = "Names can be at most 24 characters."
        elif not self.name and char.isdigit():
            self.error = "Start with a letter or underscore."
        else:
            self.name += char.lower()
            self.error = ""
        return True

    def draw(self) -> None:
        self.draw_rect(0, 0, 1280, 800, (0, 0, 0, 175))


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
        reward = self.flow.reward
        if reward.salvage:
            self.draw_text(f"+{reward.salvage} salvage banked for the tower forge.", 640, 518,
                           font_size=16, color=style.GOLD, anchor_x="center", anchor_y="center")
        if reward.trophy:
            self.draw_text(f"The {world.breach_spec.name} trophy is yours. Rare patterns need trophies.", 640, 546,
                           font_size=16, color=style.UNIQUE, anchor_x="center", anchor_y="center")
        elif world.breach_cleared and world.breach_mode == "cash":
            self.draw_text("The side cache paid gold during the defence; this site yields no trophy.", 640, 546,
                           font_size=15, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")

"""A location's intro: who comes, the curses their leaders cast and how to answer them, what the player may use
there, and the sigils won so far. The Bone Priest, who has watched this fight before, says a word first.

Defend (Enter) begins; Skills (K) opens the tree over this screen and returns to it; Esc goes back to the map.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Row, Scene

from hellward.art import sprites
from hellward.sim.campaign import DIFFICULTIES, ORDER, SIGIL_LIVES, Location, LOCATIONS, idle, offers
from hellward.sim.content import CURSES, MONSTERS, SPELLS, START_LIVES, TOWERS, Curse
from hellward.sim.skills import SKILLS
from hellward.ui import style, widgets
from hellward.ui.hud import monster_notes

if TYPE_CHECKING:
    from hellward.ui.flow import Flow

ARSENAL = ("pyre", "storm", "frost", "plague", "gate", "cleanse", "smite", "meteor", "orb")


class BriefingScene(Scene):
    background_color = (6, 4, 6, 255)

    def __init__(self, flow: Flow, location: Location) -> None:
        self.flow = flow
        self.location = location
        self.clock = 0.0
        self.spots: list[widgets.Hotspot] = []

    def on_enter(self) -> None:
        self.floor = sprites.ground(self.game, self.location)
        self.ui.add(Row(Button("Defend", shortcut="Enter", on_click=lambda: self.flow.defend(self.location), width=220),
                        Button("Skills", shortcut="K", on_click=lambda: self.flow.skills(self.location), width=170),
                        Button("Back to the map", shortcut="Esc", on_click=self.flow.world_map, width=220),
                        anchor=Anchor.BOTTOM, margin=(0, 16), spacing=14))

    def update(self, dt: float) -> None:
        self.clock += dt

    # -- Drawing ----------------------------------------------------------------------------------

    def draw(self) -> None:
        location = self.location
        progress = self.flow.progress
        difficulty = DIFFICULTIES[progress.difficulty]
        self.spots = []
        self.draw_image(self.floor, 0, 0, 1280, 800, opacity=0.6)   # layer 0, under the veil
        with self.screen_layer(1):
            self.draw_rect(0, 0, 1280, 800, (6, 3, 5, 205))
        with self.screen_layer(2):
            index = ORDER.index(location.key)
            self.draw_text(location.name, 642, 46, font_size=50, color=(0, 0, 0, 220), font=style.TITLE_FONT, anchor_x="center",
                           anchor_y="center")
            self.draw_text(location.name, 640, 44, font_size=50, color=style.GOLD, font=style.TITLE_FONT, anchor_x="center",
                           anchor_y="center")
            self.draw_text(f"The descent, {index + 1} of {len(ORDER)}  ·  {difficulty.name}  ·  {len(location.waves)} waves", 640, 94,
                           font_size=15, color=style.DIM, anchor_x="center", anchor_y="center")
            widgets.centred(self, location.blurb, 640, 108, 1040, font_size=17, color=style.BONE)
            self._taunt(160)
            self._host(242)
            self._curses(496)
            self._arsenal(636)
            self._sigils(636)
        mouse = self.game.mouse_position
        if mouse is not None:
            spot = widgets.hit(self.spots, *mouse)
            if spot is not None and spot.tip:
                with self.screen_layer(5):
                    widgets.tooltip(self, spot.tip, mouse, mouse[1] - 20)

    def _heading(self, text: str, y: float) -> None:
        self.draw_text(text, 90, y, style="heading", anchor_y="center")
        self.draw_line(90, y + 16, 1190, y + 16, (92, 76, 58, 200), 1.2)

    def _taunt(self, y: float) -> None:
        cell = self.flow.art.monster["priest"]
        h = 58
        w = h * cell.size[0] / cell.size[1]
        self.draw_image("mon/priest/front/chant", 150 - w / 2, y - 8, w, h)
        glow = 0.75 + 0.25 * math.sin(self.clock * 2)
        height = self.draw_paragraph(f"“{self.location.taunt}”", 200, y + 4, 960, font_size=16,
                                     color=style.CURSE[:3] + (int(255 * glow),), max_lines=2)
        self.draw_text("— the Bone Priest", 1160, y + 4 + height + 10, font_size=12, color=style.DIM, anchor_x="right",
                       anchor_y="center")

    def _host(self, y: float) -> None:
        """A card per monster kind: its figure, life on this difficulty, pace, and what it resists."""
        self._heading("The host", y)
        kinds = self.location.monsters
        width = min(150, (1100 - 10 * (len(kinds) - 1)) / len(kinds))
        x = 640 - (len(kinds) * width + (len(kinds) - 1) * 10) / 2
        difficulty = DIFFICULTIES[self.flow.progress.difficulty]
        for key in kinds:
            kind = MONSTERS[key]
            first = next(w for w in self.location.waves if any(g.kind == key for g in w.groups))
            life = kind.hp * first.hp * self.location.life * difficulty.factor(self.location.key)
            top = y + 26
            leader = kind.leader is not None
            self.draw_rect(x, top, width, 214, (18, 12, 14, 230), border_color=style.CURSE if leader else style.PANEL_EDGE,
                           border_width=1.5, radius=6)
            cell = self.flow.art.monster[key]
            h = min(96, 60 + 40 * kind.size)
            w = h * cell.size[0] / cell.size[1]
            frame = "chant" if leader else "walk1"
            self.draw_image(f"mon/{key}/front/{frame}", x + width / 2 - w / 2, top + 100 - h, w, h)
            size = 14 if len(kind.name) < 13 else 12
            name = self.fit_text(kind.name, width - 8, font_size=size, font=style.TITLE_FONT)
            self.draw_text(name, x + width / 2, top + 116, font_size=size, color=style.UNIQUE if leader else style.GOLD,
                           font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
            pace = "fast" if kind.speed >= 1.3 else "steady" if kind.speed >= 0.9 else "slow"
            cost = f", {kind.lives} lives" if kind.lives > 1 else ""
            line = self.fit_text(f"{life:.0f} life, {pace}{cost}", width - 8, font_size=12)
            self.draw_text(line, x + width / 2, top + 136, font_size=12, color=style.BONE, anchor_x="center", anchor_y="center")
            notes = monster_notes(kind)
            if leader:
                notes.append("Curses: " + ", ".join(CURSES[c].name for c in kind.leader.curses))
            widgets.centred(self, ", ".join(notes) or "No resistances", x + width / 2, top + 148, width - 12, font_size=11,
                            color=style.PALE_GOLD, max_lines=4)
            x += width + 10

    def _curses(self, y: float) -> None:
        """A card per curse the leaders here cast: how long, what it does, and the answer."""
        curses: list[Curse] = []
        for key in self.location.monsters:
            spec = MONSTERS[key].leader
            if spec is not None:
                curses += [c for c in spec.curses if c not in curses]
        self._heading("Their curses", y)
        answers = []
        if offers(self.location, "smite"):
            answers.append("Smite (Q) the leader while it ponders or chants")
        if offers(self.location, "orb"):
            answers.append("freeze it with the Frozen Orb")
        answers.append("Cleanse (C) lifts a curse that has landed")
        answer = "; ".join(answers) + "."
        width = min(270, (1100 - 12 * (len(curses) - 1)) / len(curses))
        x = 640 - (len(curses) * width + (len(curses) - 1) * 12) / 2
        for curse in curses:
            spec = CURSES[curse]
            self.draw_rect(x, y + 24, width, 84, (26, 10, 30, 230), border_color=(150, 70, 190, 255), border_width=1.5, radius=6)
            self.draw_text(f"{spec.name}, {spec.duration:g} s", x + 12, y + 42, font_size=17, color=style.CURSE,
                           font=style.TITLE_FONT, anchor_y="center")
            self.draw_paragraph(f"The tower {spec.blurb}.", x + 12, y + 58, width - 24, font_size=12, color=style.BONE, max_lines=2)
            self.spots.append(widgets.Hotspot(f"curse:{curse.value}", (x, y + 24, width, 84), True, f"{spec.name}\n{answer}"))
            x += width + 12
        widgets.centred(self, f"The answer: {answer}", 640, y + 112, 1100, font_size=13, color=style.HOLY)

    def _arsenal(self, y: float) -> None:
        """What the player may use here, with what is new since the last location marked."""
        self._heading("Your arsenal", y)
        index = ORDER.index(self.location.key)
        before = LOCATIONS[ORDER[index - 1]] if index > 0 else None
        x = 96
        for thing in ARSENAL:
            if not offers(self.location, thing):
                continue
            new = before is not None and not offers(before, thing)
            self.draw_rect(x, y + 26, 56, 56, (18, 12, 14, 230), border_color=style.GOLD if new else style.PANEL_EDGE,
                           border_width=2 if new else 1.2, radius=5)
            if thing in TOWERS:
                self.draw_image(f"tower/{thing}/0", x + 10, y + 14, 36, 36 * 150 / 72)
                name, tip = TOWERS[thing].name, TOWERS[thing].blurb
            elif thing == "gate":
                self.draw_image("gate/intact", x + 8, y + 30, 40, 40 * 80 / 60)
                name, tip = "Warded Gate", "Bars an arch: walkers must break it; flyers pass over."
            else:
                self.draw_image(f"ui/spell/{thing}", x + 6, y + 32, 44, 44)
                name, tip = SPELLS[thing].name, SPELLS[thing].blurb
            if new:
                self.draw_text("New", x + 28, y + 94, font_size=12, color=style.GOLD, anchor_x="center", anchor_y="center")
            self.spots.append(widgets.Hotspot(thing, (x, y + 26, 56, 56), True, f"{name}\n{tip}"))
            x += 64

    def _sigils(self, y: float) -> None:
        progress = self.flow.progress
        won = progress.best(self.location.key)
        x = 1040
        self.draw_text("Sigils here", x, y + 40, font_size=15, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        widgets.sigil_pips(self, x, y + 66, won, size=9, gap=26)
        if won < 3:
            need = SIGIL_LIVES[won]
            text = "Hold the sanctuary to win the first." if won == 0 else f"The next: keep {need} of {START_LIVES} lives."
            self.draw_text(text, x, y + 86, font_size=12, color=style.DIM, anchor_x="center", anchor_y="center")
        wasted = sum(SKILLS[key].cost for key in progress.learned if idle(self.location, SKILLS[key].needs))
        if wasted:
            what = "1 sigil sits in a skill that does" if wasted == 1 else f"{wasted} sigils sit in skills that do"
            self.draw_text(f"{what} nothing here.", x, y + 20, font_size=12, color=style.BLOOD, anchor_x="center",
                           anchor_y="center")

"""The world map: the cut-away of the ground under Tristram, the six locations on it, the lit trail between them,
and the lantern that walks down it.

Choosing an open location sends the lantern along the trail (a click skips the walk) and opens its intro. The
first descent walks straight to Tristram. The bottom bar holds the skill tree, the way back, and act tabs.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Row, Scene

from hellward.art import worldmap
from hellward.sim.campaign import ACTS, ACT_ENDS, LOCATIONS

from hellward.ui import style, widgets
from hellward.ui.story import INPUT_GUARD

if TYPE_CHECKING:
    from hellward.ui.flow import Flow

PACE = 340.0              # pixels a second the lantern walks
FIRST_STEP = 1.2          # seconds the map shows before a first descent walks on by itself


class MapScene(Scene):
    background_color = (6, 4, 6, 255)
    controls = {"k": "open_skills", "escape": "to_title", "1": "tab_act1", "2": "tab_act2"}

    def __init__(self, flow: Flow, act: int | None = None, *, first: bool = False) -> None:
        self.flow = flow
        self.progress = flow.progress
        self.spots: list[widgets.Hotspot] = []
        self.clock = 0.0
        self.walk: list[tuple[float, float]] = []   # the points still ahead of the lantern
        self.going: str | None = None
        self.act = act if act is not None else LOCATIONS[self.progress.at].act
        self.first = first   # a first Descend from the title walks on by itself
        # Initialize lantern position
        if LOCATIONS[self.progress.at].act == self.act:
            self.lantern = worldmap.ANCHORS[self.act][self.progress.at]
        else:
            self.lantern = worldmap.ANCHORS[self.act][ACTS[self.act][0]]

    def on_enter(self) -> None:
        act2_locked = not self.progress.held(ACT_ENDS[1])
        bar = Row(
            Button("Act I", shortcut="1", on_click=self.tab_act1, width=140),
            Button("Act II", shortcut="2", on_click=self.tab_act2, width=140, enabled=not act2_locked,
                   tooltip="Hold Hell's Gate to cross the sea" if act2_locked else ""),
            Button("Skills", shortcut="K", on_click=self.open_skills, width=200),
            Button("The title", shortcut="Esc", on_click=self.to_title, width=170),
            anchor=Anchor.BOTTOM, margin=(0, 14), spacing=12)
        self.ui.add(bar)

    # -- Commands ---------------------------------------------------------------------------------

    def open_skills(self) -> None:
        self.flow.skills()

    def to_title(self) -> None:
        if self.clock < INPUT_GUARD:   # a key held through a story page must not skip the map unread
            return
        self.flow.title()

    def tab_act1(self) -> None:
        if self.act != 1:
            self.act = 1
            self._reset_for_act()

    def tab_act2(self) -> None:
        if self.progress.held(ACT_ENDS[1]) and self.act != 2:
            self.act = 2
            self._reset_for_act()
        elif not self.progress.held(ACT_ENDS[1]):
            self.flow.sound.play("refuse")

    def _reset_for_act(self) -> None:
        """Reset lantern position and walk when switching acts."""
        self.walk = []
        self.going = None
        # Lantern stays on its act's map; the other act shows no lantern
        if LOCATIONS[self.progress.at].act == self.act:
            self.lantern = worldmap.ANCHORS[self.act][self.progress.at]
        else:
            # Lantern is on the other act; start from the first location of this act if first walk
            first_loc = ACTS[self.act][0]
            self.lantern = worldmap.ANCHORS[self.act][first_loc]

    def go(self, key: str) -> None:
        """Walk the lantern to a location, then open its intro."""
        if self.going is not None:
            return
        if LOCATIONS[key].act != self.act:
            return
        path = self._route(self._lantern_start_location(), key)
        self.going = key
        self.walk = list(path[1:])
        self.flow.sound.play("click")

    def _lantern_start_location(self) -> str:
        """The location the lantern is currently at on this act's map."""
        if LOCATIONS[self.progress.at].act == self.act:
            return self.progress.at
        return ACTS[self.act][0]

    def _route(self, start: str, end: str) -> list[tuple[float, float]]:
        act_locs = ACTS[self.act]
        a, b = act_locs.index(start), act_locs.index(end)
        step = 1 if b >= a else -1
        points = [worldmap.ANCHORS[self.act][start]]
        for i in range(a, b, step):
            points += list(worldmap.trail(act_locs[i], act_locs[i + step], act=self.act)[1:])
        return points

    def handle_input(self, event) -> bool:
        if event.type != "click":
            return False
        if self.clock < INPUT_GUARD:
            return True
        if self.going is not None:   # a click skips the walk
            self._arrive()
            return True
        spot = widgets.hit(self.spots, event.x, event.y)
        if spot is not None:
            if spot.enabled:
                self.go(spot.name)
            else:
                self.flow.sound.play("refuse")
            return True
        return False

    # -- The clock --------------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.clock += dt
        if self.first and self.going is None and self.clock > FIRST_STEP:
            self.first = False
            nearest = self.progress.next_location(self.act)
            if nearest is not None:
                self.go(nearest.key)
        step = PACE * dt
        while self.walk and step > 0:
            tx, ty = self.walk[0]
            x, y = self.lantern
            d = math.hypot(tx - x, ty - y)
            if d <= step:
                self.lantern = (tx, ty)
                self.walk.pop(0)
                step -= d
            else:
                self.lantern = (x + (tx - x) * step / d, y + (ty - y) * step / d)
                step = 0
        if self.going is not None and not self.walk:
            self._arrive()

    def _arrive(self) -> None:
        key, self.going, self.walk = self.going, None, []
        self.lantern = worldmap.ANCHORS[self.act][key]
        if self.progress.opened(LOCATIONS[key]):
            self.flow.intro(LOCATIONS[key])

    # -- Drawing ----------------------------------------------------------------------------------

    def draw(self) -> None:
        progress = self.progress
        # Draw the map picture for the current act
        if self.act == 1:
            self.draw_image("worldmap", 0, 0, 1280, 800)
        else:
            self.draw_image("worldmap-2", 0, 0, 1280, 800)
        self.spots = []
        mouse = self.game.mouse_position
        with self.screen_layer(1):
            self.draw_rect(0, 740, 1280, 60, (0, 0, 0, 150))
            act_locs = ACTS[self.act]
            for a, b in zip(act_locs, act_locs[1:]):
                self._trail(worldmap.trail(a, b, act=self.act), lit=progress.held(a))
        for key in act_locs:
            self._place(key, mouse)
        with self.screen_layer(4):
            # Only draw lantern if it's on this act
            if LOCATIONS[progress.at].act == self.act or self.going is not None:
                self._lantern()
            act_name = "The Descent" if self.act == 1 else "The Drowned Temples"
            self.draw_text(act_name, 640, 34, style="banner", anchor_x="center", anchor_y="center")
            won = sum(progress.best(key) for key in ACTS[self.act])
            total = 3 * len(ACTS[self.act])
            self.draw_text(f"Act {self.act}: {won} of {total} sigils won. {progress.free} to spend on skills.",
                           640, 66, font_size=15, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
        if mouse is not None:
            spot = widgets.hit(self.spots, *mouse)
            if spot is not None and spot.tip:
                with self.screen_layer(5):
                    widgets.tooltip(self, spot.tip, mouse, mouse[1] - 24)

    def _trail(self, points, *, lit: bool) -> None:
        """Dots along the trail: gold where the way is open, dark where it is not yet."""
        color = (240, 196, 110, 230) if lit else (60, 48, 40, 200)
        carry = 0.0
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            t = carry
            while t < length:
                x, y = x0 + (x1 - x0) * t / length, y0 + (y1 - y0) * t / length
                self.draw_circle(x, y, 3.2 if lit else 2.6, (0, 0, 0, 160))
                self.draw_circle(x, y, 2.4 if lit else 2.0, color)
                t += 13
            carry = t - length

    def _place(self, key: str, mouse) -> None:
        progress = self.progress
        location = LOCATIONS[key]
        x, y = worldmap.ANCHORS[self.act][key]
        opened = progress.opened(location)
        won = progress.best(key)
        over = mouse is not None and math.hypot(mouse[0] - x, mouse[1] - y) < 34 and opened
        pulse = 0.5 + 0.5 * math.sin(self.clock * 3)
        nearest = progress.next_location(self.act)
        if nearest is not None and nearest.key == key:   # where the descent goes on
            with self.screen_layer(2):
                self.draw_image("fx/glow/holy", x - 46 - 8 * pulse, y - 46 - 8 * pulse, 92 + 16 * pulse, 92 + 16 * pulse, opacity=0.7)
        with self.screen_layer(3):
            self._medallion(key, location, x, y, opened, won, over)
        self._spot(key, location, x, y, opened, won)

    def _medallion(self, key: str, location, x: float, y: float, opened: bool, won: int, over: bool) -> None:
        act_locs = ACTS[self.act]
        ring = (230, 190, 100, 255) if opened else (80, 66, 54, 255)
        self.draw_circle(x, y, 24 if over else 21, (0, 0, 0, 200))
        self.draw_circle(x, y, 20 if over else 17, ring)
        self.draw_circle(x, y, 15 if over else 13, (40, 18, 14, 255) if opened else (24, 20, 20, 255))
        self.draw_text(str(act_locs.index(key) + 1), x, y, font_size=16, color=style.PALE_GOLD if opened else style.DIM,
                       font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
        label_y = y - 44 if key in ("tristram", "graveyard", "docks", "spider_forest") else y + 42
        width = 190
        self.draw_rect(x - width / 2, label_y - 14, width, 28, (10, 6, 8, 210), border_color=ring, border_width=1.2, radius=5)
        self.draw_text(location.name, x, label_y, font_size=16, color=style.GOLD if opened else style.DIM, font=style.TITLE_FONT,
                       anchor_x="center", anchor_y="center")
        if opened:
            widgets.sigil_pips(self, x, label_y + 26 if label_y > y else label_y - 26, won, size=6, gap=16)

    def _spot(self, key: str, location, x: float, y: float, opened: bool, won: int) -> None:
        need = LOCATIONS[location.requires[0]].called if location.requires else ""
        tip = (f"{location.name}\n{location.blurb}\nSigils won here: {won} of 3." if opened
               else f"{location.name}\nThe way opens when {need} holds." if need else location.name)
        self.spots.append(widgets.Hotspot(key, (x - 34, y - 34, 68, 68), opened, tip))

    def _lantern(self) -> None:
        x, y = self.lantern
        flicker = 0.85 + 0.15 * math.sin(self.clock * 13) * math.sin(self.clock * 7.1)
        size = 64 * flicker
        self.draw_image("fx/glow/fire", x - size / 2, y - 24 - size / 2, size, size)
        with self.screen_layer(5):
            self.draw_line(x, y - 42, x, y - 34, (200, 160, 80, 255), 2)
            self.draw_rect(x - 7, y - 34, 14, 18, (60, 44, 24, 255), border_color=(220, 180, 90, 255), border_width=1.5, radius=2)
            self.draw_circle(x, y - 25, 4.5, (255, 226, 150, 255))
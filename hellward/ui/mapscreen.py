"""The world map: the cut-away of the ground under Tristram, the six locations on it, the lit trail between them,
and the lantern that walks down it.

Choosing an open location sends the lantern along the trail (a click skips the walk) and opens its intro. The
first descent walks straight to Tristram. The bottom bar holds the difficulty, the skill tree and the way back.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from saga2d import Anchor, Button, Row, Scene

from hellward.art import worldmap
from hellward.sim.campaign import DIFFICULTIES, LOCATIONS, ORDER
from hellward.ui import style, widgets

if TYPE_CHECKING:
    from hellward.ui.flow import Flow

PACE = 340.0              # pixels a second the lantern walks
FIRST_STEP = 1.2          # seconds the map shows before a first descent walks on by itself


class MapScene(Scene):
    background_color = (6, 4, 6, 255)
    controls = {"k": "open_skills", "escape": "to_title"}

    def __init__(self, flow: Flow) -> None:
        self.flow = flow
        self.progress = flow.progress
        self.spots: list[widgets.Hotspot] = []
        self.clock = 0.0
        self.walk: list[tuple[float, float]] = []   # the points still ahead of the lantern
        self.going: str | None = None
        here = worldmap.ANCHORS[self.progress.at]
        self.lantern = here
        self.first = self.progress.sigils == 0 and not any(self.progress.won[d] for d in DIFFICULTIES)

    def on_enter(self) -> None:
        bar = Row(Button("Skills", shortcut="K", on_click=self.open_skills, width=200),
                  *(Button(lambda d=d: self._difficulty_label(d), on_click=lambda d=d: self.choose(d), width=170)
                    for d in DIFFICULTIES),
                  Button("The title", shortcut="Esc", on_click=self.to_title, width=170),
                  anchor=Anchor.BOTTOM, margin=(0, 14), spacing=12)
        self.ui.add(bar)

    def _difficulty_label(self, key: str) -> str:
        difficulty = DIFFICULTIES[key]
        if not self.progress.difficulty_opened(difficulty):
            return f"{difficulty.name} (locked)"
        return f"» {difficulty.name} «" if key == self.progress.difficulty else difficulty.name

    # -- Commands ---------------------------------------------------------------------------------

    def open_skills(self) -> None:
        self.flow.skills()

    def to_title(self) -> None:
        self.flow.title()

    def choose(self, key: str) -> None:
        difficulty = DIFFICULTIES[key]
        if not self.progress.difficulty_opened(difficulty):
            self.flow.sound.play("refuse")
            return
        self.progress.choose(key)
        self.flow.sound.play("click")

    def go(self, key: str) -> None:
        """Walk the lantern to a location, then open its intro."""
        if self.going is not None:
            return
        path = self._route(self.progress.at, key)
        self.going = key
        self.walk = list(path[1:])
        self.flow.sound.play("click")

    def _route(self, start: str, end: str) -> list[tuple[float, float]]:
        a, b = ORDER.index(start), ORDER.index(end)
        step = 1 if b >= a else -1
        points = [worldmap.ANCHORS[start]]
        for i in range(a, b, step):
            points += list(worldmap.trail(ORDER[i], ORDER[i + step])[1:])
        return points

    def handle_input(self, event) -> bool:
        if event.type != "click":
            return False
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
            nearest = self.progress.next_location()
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
        self.lantern = worldmap.ANCHORS[key]
        self.flow.intro(LOCATIONS[key])

    # -- Drawing ----------------------------------------------------------------------------------

    def draw(self) -> None:
        progress = self.progress
        self.draw_image("worldmap", 0, 0, 1280, 800)   # layer 0; within a layer text covers images and images cover shapes
        self.spots = []
        mouse = self.game.mouse_position
        with self.screen_layer(1):
            self.draw_rect(0, 740, 1280, 60, (0, 0, 0, 150))
            for a, b in zip(ORDER, ORDER[1:]):
                self._trail(worldmap.trail(a, b), lit=progress.held(a))
        for key in ORDER:
            self._place(key, mouse)
        with self.screen_layer(4):
            self._lantern()
            difficulty = DIFFICULTIES[progress.difficulty]
            won = sum(progress.won[progress.difficulty].values())
            self.draw_text("The Descent", 640, 34, style="banner", anchor_x="center", anchor_y="center")
            self.draw_text(f"{difficulty.name}: {won} of {3 * len(ORDER)} sigils won. {progress.free} to spend on skills.", 640, 66,
                           font_size=15, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
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
        x, y = worldmap.ANCHORS[key]
        opened = progress.opened(location)
        won = progress.best(key)
        over = mouse is not None and math.hypot(mouse[0] - x, mouse[1] - y) < 34 and opened
        pulse = 0.5 + 0.5 * math.sin(self.clock * 3)
        nearest = progress.next_location()
        if nearest is not None and nearest.key == key:   # where the descent goes on
            with self.screen_layer(2):
                self.draw_image("fx/glow/holy", x - 46 - 8 * pulse, y - 46 - 8 * pulse, 92 + 16 * pulse, 92 + 16 * pulse, opacity=0.7)
        with self.screen_layer(3):
            self._medallion(key, location, x, y, opened, won, over)
        self._spot(key, location, x, y, opened, won)

    def _medallion(self, key: str, location, x: float, y: float, opened: bool, won: int, over: bool) -> None:
        ring = (230, 190, 100, 255) if opened else (80, 66, 54, 255)
        self.draw_circle(x, y, 24 if over else 21, (0, 0, 0, 200))
        self.draw_circle(x, y, 20 if over else 17, ring)
        self.draw_circle(x, y, 15 if over else 13, (40, 18, 14, 255) if opened else (24, 20, 20, 255))
        self.draw_text(str(ORDER.index(key) + 1), x, y, font_size=16, color=style.PALE_GOLD if opened else style.DIM,
                       font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
        label_y = y - 44 if key in ("tristram", "graveyard") else y + 42
        width = 190
        self.draw_rect(x - width / 2, label_y - 14, width, 28, (10, 6, 8, 210), border_color=ring, border_width=1.2, radius=5)
        self.draw_text(location.name, x, label_y, font_size=16, color=style.GOLD if opened else style.DIM, font=style.TITLE_FONT,
                       anchor_x="center", anchor_y="center")
        if opened:
            widgets.sigil_pips(self, x, label_y + 26 if label_y > y else label_y - 26, won, size=6, gap=16)

    def _spot(self, key: str, location, x: float, y: float, opened: bool, won: int) -> None:
        need = LOCATIONS[location.requires[0]].name if location.requires else ""
        tip = (f"{location.name}\n{location.blurb}\nSigils won here: {won} of 3." if opened
               else f"{location.name}\nThe way opens when {need} holds.")
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

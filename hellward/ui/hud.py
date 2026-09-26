"""The bottom panel and the words over the map: orbs, build slots, the wave, a selected tower's panel,
the monster under the pointer, the chronicle of what the leaders did, and the wave banners.

Everything is drawn immediately in screen space; :meth:`Hud.hit` says which control a click landed on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

from saga2d import Scene

from hellward.art.fx import ORB_LEVELS
from hellward.sim.campaign import first_offering, offers
from hellward.sim.content import CURSES, SELL_REFUND, SPELLS, START_LIVES, TOWERS, Element, MonsterKind
from hellward.sim.model import Monster, Tower, World
from hellward.ui import style, widgets

TOP = 672
SLOT = 68
BUILD = ("pyre", "storm", "frost", "plague", "gate")
SLOT_X = 146
SPELL_BAR = ("smite", "meteor", "orb")       # Cleanse is C, and the button on a selected tower
SPELL_KEYS = {"smite": "Q", "meteor": "W", "orb": "E"}
SPELL_X = 918
ELEMENT_NAMES = {Element.FIRE: "Fire", Element.LIGHTNING: "Lightning", Element.COLD: "Cold", Element.POISON: "Poison"}


def monster_notes(kind: MonsterKind) -> list[str]:
    """What a monster resists, in Diablo's words, and whether it flies."""
    notes = []
    for element in Element:
        r = kind.resist.get(element, 0.0)
        if r >= 1:
            notes.append(f"Immune to {ELEMENT_NAMES[element]}")
        elif r > 0:
            notes.append(f"Resists {ELEMENT_NAMES[element]}")
        elif r < 0:
            notes.append(f"Weak to {ELEMENT_NAMES[element]}")
    if kind.flying:
        notes.append("Flies over gates")
    return notes


@dataclass
class Control:
    name: str
    box: tuple[float, float, float, float]
    enabled: bool = True
    tip: str = ""


@dataclass
class Banner:
    title: str
    subtitle: str
    color: tuple[int, int, int, int]
    life: float = 3.2
    age: float = 0.0


@dataclass
class Hud:
    scene: Scene
    world: World
    controls: list[Control] = field(default_factory=list)
    log: list[tuple[float, str, tuple]] = field(default_factory=list)
    banners: list[Banner] = field(default_factory=list)
    clock: float = 0.0

    def note(self, text: str, color=style.BONE) -> None:
        self.log.append((self.clock, text, color))
        self.log = self.log[-6:]

    def banner(self, title: str, subtitle: str = "", color=style.GOLD, life: float = 3.2) -> None:
        self.banners = [Banner(title, subtitle, color, life)]

    def update(self, dt: float) -> None:
        self.clock += dt
        for b in list(self.banners):
            b.age += dt
            if b.age > b.life:
                self.banners.remove(b)

    def hit(self, x: float, y: float) -> Control | None:
        for control in self.controls:
            cx, cy, w, h = control.box
            if cx <= x <= cx + w and cy <= y <= cy + h:
                return control
        return None

    # -- Drawing ----------------------------------------------------------------------------------

    def draw(self, *, placing: str | None, selected: Tower | None, hovered: Monster | None, speed: float, paused: bool,
             mouse: tuple[float, float] | None, costs: Callable[[str], int]) -> None:
        scene = self.scene
        self.controls = []
        scene.draw_image("ui/panel", 0, TOP, 1280, 128)
        with scene.screen_layer(1):
            self._panel(placing, selected, costs)
            self._spells(placing, paused)
            self._corner(speed)
        with scene.screen_layer(3):
            if hovered is not None:
                self._monster_bar(hovered)
            self._chronicle()
            self._banners()
        if mouse is not None:
            control = self.hit(*mouse)
            if control is not None and control.tip:
                with scene.screen_layer(5):
                    self._tooltip(control.tip, mouse)

    def _panel(self, placing, selected, costs) -> None:
        scene = self.scene
        world = self.world
        scene.draw_rect(0, 0, 40, TOP, (14, 11, 12, 255))
        scene.draw_rect(1240, 0, 40, TOP, (14, 11, 12, 255))
        scene.draw_line(40, 0, 40, TOP, (90, 70, 44, 255), 2)
        scene.draw_line(1240, 0, 1240, TOP, (90, 70, 44, 255), 2)
        self._orb("life", 14, TOP + 8, world.lives / START_LIVES, f"{world.lives}", "Life")
        self._orb("mana", 1154, TOP + 8, world.mana / world.mana_max, f"{int(world.mana)}", "Mana")
        location = world.location
        for i, key in enumerate(BUILD):
            x = SLOT_X + i * (SLOT + 10)
            y = TOP + 16
            if key == "gate":
                name, tip = "Warded Gate", (f"Bar an arch on the path. Walkers must break it ({world.gate_life:.0f} life); flyers pass "
                                            "over. A broken gate lies in rubble until the wave is cleared.")
            else:
                kind = TOWERS[key]
                name, tip = kind.name, f"{ELEMENT_NAMES[kind.element]}. {kind.blurb}"
            offered = offers(location, key)
            cost = costs(key)
            affordable = offered and world.gold >= cost
            scene.draw_image("ui/slot_lit" if placing == key else "ui/slot", x, y, SLOT, SLOT)
            with scene.screen_layer(2):
                shown = 1.0 if affordable else 0.4 if offered else 0.12
                if key == "gate":
                    scene.draw_image("gate/intact", x + 12, y + 2, 44, 44 * 80 / 60, opacity=shown)
                else:
                    scene.draw_image(f"tower/{key}/0", x + 12, y - 16, 44, 44 * 150 / 72, opacity=shown)
                self._keycap(x, y, str(i + 1))
                if not offered:
                    self._padlock(x + SLOT / 2, y + SLOT / 2)
            if offered:
                scene.draw_text(f"{cost}", x + SLOT / 2, y + SLOT + 16, font_size=14, color=style.GOLD if affordable else style.DIM,
                                anchor_x="center", anchor_y="center")
                self.controls.append(Control(f"build:{key}", (x, y, SLOT, SLOT), affordable, f"{name} — {cost} gold\n{tip}"))
            else:
                self.controls.append(Control(f"build:{key}", (x, y, SLOT, SLOT), False,
                                             f"{name}\nNot here. It arrives in {first_offering(key).called}."))
        self._centre(selected)

    def _keycap(self, x: float, y: float, key: str) -> None:
        scene = self.scene
        scene.draw_rect(x + 3, y + 3, 17, 17, (0, 0, 0, 170), radius=3)
        scene.draw_text(key, x + 11.5, y + 12, font_size=12, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")

    def _padlock(self, cx: float, cy: float) -> None:
        """A small iron padlock over a slot the location does not offer."""
        scene = self.scene
        iron, dark = (150, 136, 116, 235), (30, 24, 22, 255)
        for i in range(10):   # the shackle, a half ring of short strokes
            a0, a1 = math.pi + math.pi * i / 10, math.pi + math.pi * (i + 1) / 10
            scene.draw_line(cx + 8 * math.cos(a0), cy - 2 + 9 * math.sin(a0), cx + 8 * math.cos(a1), cy - 2 + 9 * math.sin(a1), iron, 3.5)
        scene.draw_rect(cx - 12, cy - 2, 24, 18, iron, border_color=dark, border_width=1.5, radius=3)
        scene.draw_circle(cx, cy + 5, 3, dark)
        scene.draw_line(cx, cy + 5, cx, cy + 11, dark, 2.5)

    def _spells(self, placing: str | None, paused: bool) -> None:
        """Smite, Meteor and Frozen Orb, with the mana each costs under it."""
        scene = self.scene
        world = self.world
        for i, key in enumerate(SPELL_BAR):
            spec = SPELLS[key]
            x, y = SPELL_X + i * (SLOT + 9), TOP + 16
            offered = offers(world.location, key)
            cost = world.spell_cost(key)
            left = world.recharge.get(key, 0.0)
            ready = offered and world.mana >= cost and not paused and left <= 0
            scene.draw_image("ui/slot_lit" if placing == f"spell:{key}" else "ui/slot", x, y, SLOT, SLOT)
            with scene.screen_layer(2):
                scene.draw_image(f"ui/spell/{key}", x + 6, y + 6, SLOT - 12, SLOT - 12, opacity=1.0 if ready else 0.45 if offered else 0.12)
                self._keycap(x, y, SPELL_KEYS[key])
                if not offered:
                    self._padlock(x + SLOT / 2, y + SLOT / 2)
            if left > 0:   # still gathering itself: a veil that lifts from the top, and the seconds
                with scene.screen_layer(3):
                    share = left / spec.recharge
                    scene.draw_rect(x + 4, y + 4 + (SLOT - 8) * (1 - share), SLOT - 8, (SLOT - 8) * share, (0, 0, 0, 170), radius=4)
                    scene.draw_text(f"{math.ceil(left)}", x + SLOT / 2, y + SLOT / 2, font_size=20, color=style.PALE_GOLD,
                                    font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
            if offered:
                scene.draw_text(f"{cost:.0f}", x + SLOT / 2, y + SLOT + 16, font_size=14,
                                color=style.MANA if world.mana >= cost else style.DIM, anchor_x="center", anchor_y="center")
                how = ("Q with a leader pondering or chanting smites the one closest to cursing. " if key == "smite" else "")
                self.controls.append(Control(f"spell:{key}", (x, y, SLOT, SLOT), ready,
                                             f"{spec.name} — {cost:.0f} mana, then {spec.recharge:.0f} s to gather itself\n"
                                             f"{spec.blurb} {how}Not while paused."))
            else:
                self.controls.append(Control(f"spell:{key}", (x, y, SLOT, SLOT), False,
                                             f"{spec.name}\nNot yet yours. You learn it for {first_offering(key).called}."))

    def _corner(self, speed: float) -> None:
        """Pace and Menu, small, at the top right over the wall."""
        self._button("speed", 1104, 8, 70, 26, f"Pace {speed:.0f}x", tip="[F] Double the pace of the fight, or restore it.")
        self._button("menu", 1180, 8, 56, 26, "Menu", tip="[Esc] Pause, settings and volume, start again or leave.")

    def _orb(self, which: str, x: float, y: float, fill: float, value: str, label: str) -> None:
        scene = self.scene
        level = max(0, min(ORB_LEVELS, round(fill * ORB_LEVELS)))
        scene.draw_image(f"ui/orb/{which}/{level}", x, y, 112, 112)
        scene.draw_text(value, x + 57, y + 58, font_size=26, color=(0, 0, 0, 200), font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
        scene.draw_text(value, x + 56, y + 56, font_size=26, color=style.PALE_GOLD, font=style.TITLE_FONT, anchor_x="center", anchor_y="center")

    def _button(self, name: str, x: float, y: float, w: float, h: float, text: str, *, enabled: bool = True, tip: str = "",
                accent=style.GOLD) -> None:
        scene = self.scene
        mouse = self.scene.game.mouse_position
        over = mouse is not None and x <= mouse[0] <= x + w and y <= mouse[1] <= y + h and enabled
        scene.draw_rect(x, y, w, h, (60, 44, 34, 255) if over else (34, 26, 24, 255), border_color=accent if enabled else (70, 60, 50, 255),
                        border_width=1.5, radius=4)
        scene.draw_text(text, x + w / 2, y + h / 2, font_size=14, color=style.PALE_GOLD if enabled else style.DIM,
                        anchor_x="center", anchor_y="center")
        self.controls.append(Control(name, (x, y, w, h), enabled, tip))

    def _centre(self, selected: Tower | None) -> None:
        scene = self.scene
        world = self.world
        x0, y0 = 560, TOP + 14
        self._gold()
        if selected is not None:
            kind = selected.kind
            stats = selected.stats
            scene.draw_text(scene.fit_text(f"{kind.name} {'I' * (selected.level + 1)}", 250, style="heading"), x0, y0 + 14,
                            style="heading", anchor_y="center")
            parts = [f"{stats.damage * selected.damage_mult():.0f} {ELEMENT_NAMES[kind.element].lower()}",
                     f"{stats.rate * selected.rate_mult():.2f}/s", f"reach {selected.reach:.1f}"]
            if stats.splash:
                parts.append(f"blast {stats.splash:.1f}")
            if stats.chains:
                parts.append(f"{stats.chains} leaps")
            if stats.chill:
                parts.append(f"chills {stats.chill:.0%}")
            if stats.poison:
                parts.append(f"venom {stats.poison:.0f}/s")
            scene.draw_text("  ·  ".join(parts), x0, y0 + 38, font_size=13, color=style.BONE, anchor_y="center")
            if selected.curses:
                text = ", ".join(f"{CURSES[c].name} ({left:.0f}s): {CURSES[c].blurb}" for c, left in selected.curses.items())
                scene.draw_text(scene.fit_text(text, 340, font_size=13), x0, y0 + 58, font_size=13, color=style.CURSE, anchor_y="center")
            cost = world.upgrade_cost(selected)
            by = TOP + 86
            self._button("upgrade", x0, by, 112, 28, f"Upgrade {cost}" if cost else "Highest rank", enabled=bool(cost) and world.gold >= cost,
                         tip="[U] The next rank: more damage and reach, and a finer look.")
            self._button("sell", x0 + 118, by, 100, 28, f"Sell +{int(selected.spent * SELL_REFUND)}", tip="[S] Tear it down for most of its cost.")
            cleanse = world.spell_cost("cleanse")
            self._button("cleanse", x0 + 224, by, 116, 28, f"Cleanse {cleanse:.0f}", enabled=bool(selected.curses) and world.mana >= cleanse,
                         tip="[C] Burn every curse off this tower with holy light. Costs mana.", accent=style.HOLY)
            return
        names = world.location.wave_names
        title = world.location.name if world.wave < 0 else names[world.wave]
        scene.draw_text(scene.fit_text(title, 250, style="heading"), x0, y0 + 14, style="heading", anchor_y="center")
        if world.outcome is not None:
            status = "Victory." if world.outcome == "victory" else "The sanctuary has fallen."
        elif world.schedule or world.monsters:
            status = f"{len(world.monsters) + len(world.schedule)} monsters abroad"
            leaders = world.leaders()
            if leaders:
                status += f", {len(leaders)} leading"
        elif world.wave < 0:
            status = "Towers (1-4) beside the carpet, gates (5) in the arches."
        elif world.break_left is not None:
            status = f"the next comes in {world.break_left:.0f}s"
        else:
            status = ""
        if world.wave >= 0 and world.outcome is None:
            status = f"Wave {world.wave + 1} of {len(world.waves)}" + (f": {status}" if status else "")
        scene.draw_text(scene.fit_text(status, 340, font_size=14), x0, y0 + 40, font_size=14, color=style.BONE, anchor_y="center")
        if world.can_call_wave:
            bonus = int(world.break_left) if world.break_left is not None and world.wave >= 0 else 0
            label = "Summon the next wave" + (f"  +{bonus}" if bonus else "")
            self._button("call", x0, TOP + 86, 250, 28, label, tip="[Space] Call the next wave now; gold for every second you spare.")

    def _gold(self) -> None:
        scene = self.scene
        x = 896
        text = f"{self.world.gold}"
        scene.draw_text(text, x, TOP + 28, font_size=22, color=style.GOLD, font=style.TITLE_FONT, anchor_x="right", anchor_y="center")
        width, _ = scene.game.backend.measure_text(text, 22, style.TITLE_FONT)
        scene.draw_circle(x - width - 13, TOP + 29, 8, (200, 160, 60, 255))
        scene.draw_circle(x - width - 13, TOP + 29, 5, (240, 204, 110, 255))

    def _monster_bar(self, m: Monster) -> None:
        """Diablo's bar at the top of the screen: the name, the life left, and what it resists."""
        scene = self.scene
        kind = m.kind
        max_hp = m.max_hp
        w, x, y = 300, 640 - 150, 10
        color = style.BOSS if kind.key == "azazel" else style.UNIQUE if kind.leader else style.BONE
        scene.draw_rect(x, y, w, 24, (40, 6, 8, 230), border_color=(120, 30, 30, 255), border_width=1.5)
        scene.draw_rect(x + 2, y + 2, (w - 4) * max(0.0, m.hp / max_hp), 20, (150, 16, 20, 255))
        scene.draw_text(kind.name, 640, y + 12, font_size=16, color=color, font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
        notes = monster_notes(kind)
        if kind.leader:
            notes.append("Leader: curses " + " and ".join(CURSES[c].name for c in kind.leader.curses))
        if notes:
            scene.draw_text(", ".join(notes), 640, y + 38, font_size=13, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")

    def _chronicle(self) -> None:
        """The last few things the leaders did, top right, over the bare floor by the north wall."""
        scene = self.scene
        lines = [(self.clock - stamp, text, color) for stamp, text, color in self.log if self.clock - stamp <= 14]
        if not lines:
            return
        width, right = 470, 1232
        backing = min(1.0, (14 - min(age for age, _, _ in lines)) / 3)
        scene.draw_rect(right - width, 64, width, 18 * len(lines) + 8, (10, 6, 8, int(175 * backing)), radius=4)
        y = 77
        for age, text, color in lines:
            alpha = int(255 * min(1.0, (14 - age) / 3))
            text = scene.fit_text(text, width - 16, font_size=12)
            scene.draw_text(text, right - width + 9, y + 1, font_size=12, color=(0, 0, 0, alpha), anchor_y="center")
            scene.draw_text(text, right - width + 8, y, font_size=12, color=color[:3] + (alpha,), anchor_y="center")
            y += 18

    def _banners(self) -> None:
        scene = self.scene
        for b in self.banners:
            fade = min(1.0, b.age / 0.4, (b.life - b.age) / 0.8)
            alpha = int(255 * max(0.0, fade))
            scene.draw_rect(0, 250, 1280, 110, (0, 0, 0, int(alpha * 0.45)))
            scene.draw_text(b.title, 642, 292, style="banner", color=(0, 0, 0, alpha), anchor_x="center", anchor_y="center")
            scene.draw_text(b.title, 640, 290, style="banner", color=b.color[:3] + (alpha,), anchor_x="center", anchor_y="center")
            if b.subtitle:
                scene.draw_text(b.subtitle, 640, 334, font_size=17, color=style.BONE[:3] + (alpha,), anchor_x="center", anchor_y="center")

    def tower_tip(self, tower: Tower, mouse: tuple[float, float]) -> None:
        """What a tower on the map is, and what is cursing it."""
        lines = [f"{tower.kind.name} {'I' * (tower.level + 1)}  ({ELEMENT_NAMES[tower.kind.element]})"]
        for curse, left in sorted(tower.curses.items(), key=lambda kv: -kv[1]):
            lines.append(f"{CURSES[curse].name}, {left:.0f}s: {CURSES[curse].blurb}")
        if not tower.curses:
            lines.append("Click to upgrade, sell or cleanse it.")
        with self.scene.screen_layer(5):
            self._tooltip("\n".join(lines), mouse, above=mouse[1] - 30)

    def _tooltip(self, tip: str, mouse: tuple[float, float], above: float = TOP - 8) -> None:
        widgets.tooltip(self.scene, tip, mouse, above)

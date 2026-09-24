"""The bottom panel and the words over the map: orbs, build slots, the wave, a selected tower's panel,
the monster under the pointer, the chronicle of what the leaders did, and the wave banners.

Everything is drawn immediately in screen space; :meth:`Hud.hit` says which control a click landed on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from saga2d import Scene

from hellward.art.fx import ORB_LEVELS
from hellward.sim.content import CLEANSE_COST, CURSES, DOOR, MANA_MAX, MONSTERS, SELL_REFUND, START_LIVES, TOWERS, Element
from hellward.sim.model import Monster, Tower, World
from hellward.ui import style

TOP = 672
SLOT = 68
BUILD = ("pyre", "storm", "frost", "plague", "gate")
SLOT_X = 146
WAVE_NAMES = ("The Fallen Horde", "The Shaman's Warband", "The Restless Dead", "Rot and Fire", "Horns and Wings",
              "The Bone Priest", "The Blood Witch", "The Winged Siege", "The Council of Curses", "Azazel the Flayer")
ELEMENT_NAMES = {Element.FIRE: "Fire", Element.LIGHTNING: "Lightning", Element.COLD: "Cold", Element.POISON: "Poison"}


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
             thoughts: bool, mouse: tuple[float, float] | None, costs: Callable[[str], int]) -> None:
        scene = self.scene
        world = self.world
        self.controls = []
        scene.draw_image("ui/panel", 0, TOP, 1280, 128)
        with scene.screen_layer(1):
            self._panel(placing, selected, speed, paused, thoughts, costs)
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

    def _panel(self, placing, selected, speed, paused, thoughts, costs) -> None:
        scene = self.scene
        world = self.world
        scene.draw_rect(0, 0, 40, TOP, (14, 11, 12, 255))
        scene.draw_rect(1240, 0, 40, TOP, (14, 11, 12, 255))
        scene.draw_line(40, 0, 40, TOP, (90, 70, 44, 255), 2)
        scene.draw_line(1240, 0, 1240, TOP, (90, 70, 44, 255), 2)
        self._orb("life", 14, TOP + 8, world.lives / START_LIVES, f"{world.lives}", "Life")
        self._orb("mana", 1154, TOP + 8, world.mana / MANA_MAX, f"{int(world.mana)}", "Mana")
        for i, key in enumerate(BUILD):
            x = SLOT_X + i * (SLOT + 10)
            y = TOP + 16
            cost = costs(key)
            lit = placing == key
            affordable = world.gold >= cost
            scene.draw_image("ui/slot_lit" if lit else "ui/slot", x, y, SLOT, SLOT)
            with scene.screen_layer(2):
                if key == "gate":
                    scene.draw_image("gate/intact", x + 12, y + 2, 44, 44 * 80 / 60, opacity=1.0 if affordable else 0.4)
                else:
                    scene.draw_image(f"tower/{key}/0", x + 12, y - 16, 44, 44 * 150 / 72, opacity=1.0 if affordable else 0.4)
            if key == "gate":
                name, tip = "Warded Gate", f"Bar an arch on the path. Walkers must break it ({DOOR.hp:.0f} life); flyers pass over."
            else:
                kind = TOWERS[key]
                name, tip = kind.name, f"{ELEMENT_NAMES[kind.element]}. {kind.blurb}"
            with scene.screen_layer(2):
                scene.draw_rect(x + 3, y + 3, 17, 17, (0, 0, 0, 170), radius=3)
                scene.draw_text(str(i + 1), x + 11.5, y + 12, font_size=12, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")
            scene.draw_text(f"{cost}", x + SLOT / 2, y + SLOT + 16, font_size=14, color=style.GOLD if affordable else style.DIM,
                            anchor_x="center", anchor_y="center")
            self.controls.append(Control(f"build:{key}", (x, y, SLOT, SLOT), affordable, f"{name} — {cost} gold\n{tip}"))
        self._centre(selected)
        self._right(speed, paused, thoughts)

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
        if selected is not None:
            kind = selected.kind
            stats = selected.stats
            scene.draw_text(f"{kind.name} {'I' * (selected.level + 1)}", x0, y0 + 14, style="heading", anchor_y="center")
            parts = [f"{stats.damage * selected.multiplier('damage'):.0f} {ELEMENT_NAMES[kind.element].lower()}",
                     f"{stats.rate * selected.multiplier('rate'):.2f}/s", f"reach {selected.reach:.1f}"]
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
            self._button("cleanse", x0 + 224, by, 116, 28, f"Cleanse {CLEANSE_COST:.0f}", enabled=bool(selected.curses) and world.mana >= CLEANSE_COST,
                         tip="[C] Burn every curse off this tower with holy light. Costs mana.", accent=style.HOLY)
            return
        if world.wave < 0:
            title = "The cathedral waits"
        else:
            title = f"Wave {world.wave + 1} of {len(world.waves)}: {WAVE_NAMES[min(world.wave, len(WAVE_NAMES) - 1)]}"
        scene.draw_text(scene.fit_text(title, 340, style="heading"), x0, y0 + 14, style="heading", anchor_y="center")
        if world.outcome is not None:
            status = "Victory." if world.outcome == "victory" else "The sanctuary has fallen."
        elif world.schedule or world.monsters:
            status = f"{len(world.monsters) + len(world.schedule)} monsters abroad"
            leaders = world.leaders()
            if leaders:
                status += f", {len(leaders)} leader{'s' if len(leaders) > 1 else ''} among them"
        elif world.break_left is not None:
            status = f"The next wave comes in {world.break_left:.0f}s"
        else:
            status = ""
        scene.draw_text(status, x0, y0 + 40, font_size=14, color=style.BONE, anchor_y="center")
        if world.can_call_wave:
            bonus = int(world.break_left) if world.break_left is not None and world.wave >= 0 else 0
            label = "Summon the next wave" + (f"  +{bonus}" if bonus else "")
            self._button("call", x0, TOP + 86, 250, 28, label, tip="[Space] Call the next wave now; gold for every second you spare.")

    def _right(self, speed: float, paused: bool, thoughts: bool) -> None:
        scene = self.scene
        world = self.world
        x0 = 918
        scene.draw_circle(x0 + 10, TOP + 30, 9, (200, 160, 60, 255))
        scene.draw_circle(x0 + 10, TOP + 30, 6, (240, 204, 110, 255))
        scene.draw_text(f"{world.gold}", x0 + 26, TOP + 30, font_size=22, color=style.GOLD, font=style.TITLE_FONT, anchor_y="center")
        self._button("speed", x0, TOP + 52, 108, 26, f"Pace {speed:.0f}x", tip="[F] Double the pace of the fight, or restore it.")
        self._button("pause", x0 + 114, TOP + 52, 108, 26, "Resume" if paused else "Pause", tip="[P] Stop time while you think.")
        self._button("thoughts", x0, TOP + 86, 222, 28, "Leaders' minds: " + ("shown" if thoughts else "hidden"),
                     tip="[Tab] Show what each leader weighed before it cursed: the life each curse would save its pack.",
                     accent=style.CURSE)

    def _monster_bar(self, m: Monster) -> None:
        """Diablo's bar at the top of the screen: the name, the life left, and what it resists."""
        scene = self.scene
        kind = m.kind
        max_hp = kind.hp * self.world.waves[m.wave].hp
        w, x, y = 300, 640 - 150, 10
        color = style.BOSS if kind.key == "azazel" else style.UNIQUE if kind.leader else style.BONE
        scene.draw_rect(x, y, w, 24, (40, 6, 8, 230), border_color=(120, 30, 30, 255), border_width=1.5)
        scene.draw_rect(x + 2, y + 2, (w - 4) * max(0.0, m.hp / max_hp), 20, (150, 16, 20, 255))
        scene.draw_text(kind.name, 640, y + 12, font_size=16, color=color, font=style.TITLE_FONT, anchor_x="center", anchor_y="center")
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
        if kind.leader:
            notes.append("Leader: curses " + " and ".join(CURSES[c].name for c in kind.leader.curses))
        if notes:
            scene.draw_text(", ".join(notes), 640, y + 38, font_size=13, color=style.PALE_GOLD, anchor_x="center", anchor_y="center")

    def _chronicle(self) -> None:
        scene = self.scene
        lines = [(self.clock - stamp, text, color) for stamp, text, color in self.log if self.clock - stamp <= 14]
        if not lines:
            return
        width = max(scene.game.backend.measure_text(text, 13, style.TEXT_FONT)[0] for _, text, _ in lines) + 20
        backing = min(1.0, (14 - min(age for age, _, _ in lines)) / 3)
        scene.draw_rect(46, 6, width, 18 * len(lines) + 8, (10, 6, 8, int(170 * backing)), radius=4)
        y = 19
        for age, text, color in lines:
            alpha = int(255 * min(1.0, (14 - age) / 3))
            scene.draw_text(text, 57, y + 1, font_size=13, color=(0, 0, 0, alpha), anchor_y="center")
            scene.draw_text(text, 56, y, font_size=13, color=color[:3] + (alpha,), anchor_y="center")
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

    def _tooltip(self, tip: str, mouse: tuple[float, float]) -> None:
        scene = self.scene
        lines = tip.split("\n")
        width = 320
        layout = [scene.layout_text(line, width - 20, font_size=13) for line in lines]
        height = sum(l.height for l in layout) + 10 * len(layout) + 8
        x = min(max(mouse[0] - width / 2, 44), 1236 - width)
        y = TOP - height - 8
        scene.draw_rect(x, y, width, height, (16, 12, 12, 240), border_color=style.PANEL_EDGE, border_width=1.5, radius=4)
        yy = y + 8
        for i, line in enumerate(lines):
            yy += scene.draw_paragraph(line, x + 10, yy, width - 20, font_size=13, color=style.GOLD if i == 0 else style.BONE) + 8


def monster_title(m: Monster) -> str:
    return MONSTERS[m.kind.key].name

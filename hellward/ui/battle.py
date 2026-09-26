"""The defence itself: the map, the fight and the panel, stepped at the rules' fixed rate.

Input: a build slot (or 1–5) picks a tower or a gate to place, a click on the floor or on an arch places
it, a click on a tower selects it (U upgrades, S sells, C cleanses), right click or Esc lets go; Esc with
nothing to let go of opens the menu. Q, W and E pick Smite, Meteor and Frozen Orb, aimed with a click; Q with
a leader pondering or chanting smites the one closest to cursing at once. Spells wait while the fight is
paused. Space calls the next wave, F doubles the pace, P pauses, Tab shows or hides what the leaders were
thinking.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from saga2d import Camera, RenderLayer, Scene

from hellward.art.sprites import Art
from hellward.sim.campaign import CATHEDRAL, NORMAL, Difficulty, Location, first_offering, offers
from hellward.sim.content import CURSES, DOOR, MONSTERS, SPELLS
from hellward.sim.model import SIM_DT, Monster, Refused, Tower, World
from hellward.sim.players.hands import Hands, Player
from hellward.sim.skills import NO_PERKS, Perks
from hellward.ui import style
from hellward.ui.effects import Effects
from hellward.ui.hud import BUILD, Hud
from hellward.ui.lighting import Lighting
from hellward.ui.menus import PauseScene
from hellward.ui.view import MAP_X, MAP_Y, T, TOWER_SCALE, WorldView, px

WIDTH, HEIGHT = 1280, 800


class Silent:
    def play(self, cue: str, **_: Any) -> None:
        pass

    def music(self, mood: str) -> None:
        pass


class BattleScene(Scene):
    background_color = (8, 6, 8, 255)
    controls = {
        "1": "slot_1", "2": "slot_2", "3": "slot_3", "4": "slot_4", "5": "slot_5",
        "space": "call_wave", "f": "toggle_speed", "p": "toggle_pause", "tab": "toggle_thoughts",
        "u": "upgrade", "s": "sell", "c": "cleanse", "escape": "cancel",
        "q": "spell_smite", "w": "spell_meteor", "e": "spell_orb",
    }

    def __init__(self, art: Art, location: Location = CATHEDRAL, *, difficulty: Difficulty = NORMAL, perks: Perks = NO_PERKS,
                 seed: int = 0, planner: Callable | None = None, sound: Any = None,
                 autopilot: Player | None = None, on_end: Callable[[World], None] | None = None,
                 settings: Any = None, restart: Callable[[], None] | None = None,
                 to_title: Callable[[], None] | None = None, to_map: Callable[[], None] | None = None) -> None:
        self.art = art
        self.location = location
        self.difficulty = difficulty
        self.perks = perks
        self.settings = settings
        self.restart = restart
        self.to_title = to_title
        self.to_map = to_map
        self.seed = seed
        self.planner = planner
        self.sound = sound or Silent()
        self.autopilot = autopilot
        self.on_end = on_end
        self.placing: str | None = None
        self.selected: Tower | None = None
        self.speed = 1.0
        self.paused = False
        self.acc = 0.0
        self.ended = 0.0
        self.door_clock: dict[int, float] = {}
        self.last_hold_note = -10.0

    def on_enter(self) -> None:
        self.camera = Camera((WIDTH, HEIGHT))
        self.world = World(self.location, difficulty=self.difficulty, perks=self.perks, seed=self.seed, planner=self.planner)
        self.view = WorldView(self, self.world, self.art)
        self.fx = Effects(self, self.view, self.world)
        self.hud = Hud(self, self.world)
        self.lighting = Lighting(self, (MAP_X, MAP_Y), (self.world.level.width * T, self.world.level.height * T))
        self.hands = Hands(self.world, react=0.6)
        if self.settings is not None:
            self.fx.show_thoughts = self.settings["minds"]
        self.hud.banner(self.location.name, "Hold the sanctuary. The first wave comes soon.", life=4.5)
        self.sound.music("battle")

    def on_background(self) -> None:
        """A player who looks away comes back to the pause menu, whose Resume resumes."""
        if self.autopilot is None and self.game.scenes[-1] is self:
            self.open_menu()

    def on_reveal(self) -> None:
        self.paused = False   # closing the menu resumes, whatever paused the fight before it opened

    # -- The clock -------------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        world = self.world
        if not self.paused:
            self.acc += min(dt, 0.1) * self.speed
            while self.acc >= SIM_DT:
                self.acc -= SIM_DT
                if self.autopilot is not None:
                    self.autopilot.act(self.hands)
                self.view.before_step()
                world.step(SIM_DT)
                self.hands.observe(world.events)
                for event in world.events:
                    self._event(event)
                world.events.clear()
        if self.selected is not None and self.selected.id not in world.towers:
            self.selected = None
        self.fx.selected = self.selected.id if self.selected is not None else -1
        self.view.sync(self.acc / SIM_DT if not self.paused else 1.0, dt)
        self.fx.update(dt)
        self.hud.update(dt)
        self._door_blows(dt)
        self.lighting.render(self.view.lights() + self.fx.lights())
        if world.outcome is not None:
            self.ended += dt
            if self.ended > 3.0 and self.on_end is not None:
                self.hud.banners.clear()   # the reckoning is drawn over this scene
                callback, self.on_end = self.on_end, None
                callback(world)

    def _door_blows(self, dt: float) -> None:
        if self.paused:
            return
        for door in self.world.doors:
            if not door.built:
                continue
            batterers = sum(1 for m in self.world.monsters if m.door == door.index)
            if not batterers:
                continue
            left = self.door_clock.get(door.index, 0.0) - dt * self.speed
            if left <= 0:
                left = 0.55
                x, y = self.world.level.doors[door.index]
                self.sound.play("door_hit", volume=min(1.0, 0.5 + 0.1 * batterers))
                cx, cy = px(x + 0.5, y + 0.5)
                self.fx.burst("fx/dust", cx, cy - 18, 3, speed=(20, 60), size=(7, 7))
            self.door_clock[door.index] = left

    def _event(self, e: tuple) -> None:
        self.fx.event(e)
        kind = e[0]
        world = self.world
        sound = self.sound
        if kind == "wave":
            index = e[1]
            last = index == len(world.waves) - 1
            subtitle = "The last wave." if last else f"Wave {index + 1} of {len(world.waves)}"
            self.hud.banner(world.location.wave_names[index], subtitle, color=style.BLOOD if last else style.GOLD)
            sound.play("wave")
            if last and any(g.kind == "azazel" for g in world.waves[index].groups):
                sound.music("boss")
        elif kind == "cleared":
            if e[2]:
                mend = "" if not world.doors else " Gates mend fully." if world.perks.gate_mend >= 1 else " Gates mend by half."
                self.hud.banner("The wave is broken", f"+{e[2]} gold.{mend}", life=2.4)
            sound.play("cleared")
        elif kind == "bolt":
            sound.play("fire_cast" if e[1].kind == "pyre" else "venom_cast", volume=0.6)
        elif kind == "impact":
            bolt = e[1]
            sound.play(("fireball" if bolt.splash > 0 else "fire_hit") if bolt.kind == "pyre" else "venom_hit", volume=0.7)
        elif kind == "chain":
            sound.play("lightning", volume=0.7)
        elif kind == "nova":
            sound.play("frost", volume=0.7)
        elif kind == "death":
            sound.play(f"death_{e[2]}", volume=0.8)
            if e[5] >= 20:
                sound.play("gold")
        elif kind == "leak":
            sound.play("leak")
            self.hud.note(f"{MONSTERS[e[2]].name} reached the sanctuary. -{e[3]} life.", style.BLOOD)
        elif kind == "door_broken":
            sound.play("door_break")
            self.hud.note("A warded gate has been broken.", style.BLOOD)
        elif kind == "door_built":
            sound.play("door_build")
        elif kind == "built":
            sound.play("build")
        elif kind == "upgraded":
            sound.play("upgrade")
        elif kind == "sold":
            sound.play("sell")
        elif kind == "cleansed":
            sound.play("cleanse")
        elif kind == "chant":
            leader = world.monster(e[1])
            tower = world.towers.get(e[3])
            sound.play("chant")
            if leader is not None and tower is not None:
                self.hud.note(f"{leader.kind.name} chants {CURSES[e[2]].name} at the {tower.kind.name}.", style.CURSE)
        elif kind == "cursed":
            sound.play("curse")
        elif kind == "fizzle":
            sound.play("fizzle")
        elif kind == "smite":
            sound.play("smite")
        elif kind == "meteor_cast":
            sound.play("meteor_fall")
        elif kind == "meteor":
            sound.play("meteor")
        elif kind == "orb":
            sound.play("orb")
        elif kind == "broken":
            sound.play("broken")
            leader = world.monster(e[1])
            self.hud.note(f"{leader.kind.name if leader else 'The leader'} loses its curse.", style.HOLY)
        elif kind == "ward_holds":
            sound.play("ward")
            tower = world.towers.get(e[2])
            if tower is not None:
                self.hud.note(f"{CURSES[e[3]].name} breaks on the ward of the {tower.kind.name}.", style.HOLY)
        elif kind == "ponder":
            sound.play("ponder", volume=0.6)
        elif kind == "plan":
            decision = e[2]
            leader = world.monster(e[1])
            if leader is None:
                return
            if decision.cast is not None:
                tower = world.towers.get(decision.cast.tower)
                if tower is not None:
                    self.hud.note(f"{leader.kind.name} weighed {decision.considered}: {CURSES[decision.cast.curse].name} "
                                  f"on the {tower.kind.name}, +{decision.cast.gain:.0f} life", style.UNIQUE)
            elif decision.later is not None and self.hud.clock - self.last_hold_note > 6:
                self.last_hold_note = self.hud.clock
                self.hud.note(f"{leader.kind.name} waits: in {decision.later.delay:.0f}s its curse is worth more", style.DIM)
        elif kind == "victory":
            sound.play("victory")
            sound.music("title")
        elif kind == "defeat":
            sound.play("defeat")

    # -- Commands --------------------------------------------------------------------------------

    def cost(self, key: str) -> int:
        return DOOR.cost if key == "gate" else self.world.cost(key)

    def _try(self, action: Callable[[], Any]) -> bool:
        try:
            action()
            return True
        except Refused as refusal:
            self.hud.note(str(refusal), style.DIM)
            self.sound.play("refuse")
            return False

    def pick(self, key: str) -> None:
        if not offers(self.location, key):
            self._refuse(f"Not in {self.location.called}: it arrives in {first_offering(key).called}.")
            return
        self.selected = None
        self.placing = None if self.placing == key else key
        self.sound.play("click")

    def _refuse(self, why: str) -> None:
        self.hud.note(why, style.DIM)
        self.sound.play("refuse")

    # -- Spells ----------------------------------------------------------------------------------

    def spell(self, key: str) -> None:
        """Pick a spell to aim, as a tower is picked. Smite with a leader pondering or chanting strikes it at once."""
        if self.paused:
            self._refuse("Spells are cast in the fight's own time: resume it first (P).")
            return
        if not offers(self.location, key):
            self._refuse(f"{SPELLS[key].name} is not yet yours: you learn it for {first_offering(key).called}.")
            return
        cost = self.world.spell_cost(key)
        if self.world.mana < cost:
            self._refuse(f"{SPELLS[key].name} takes {cost:.0f} mana.")
            return
        if key == "smite":
            leader = self.threat()
            if leader is not None:
                if self._try(lambda: self.world.smite(leader.id)):
                    self.placing = None
                return
        self.selected = None
        self.placing = None if self.placing == f"spell:{key}" else f"spell:{key}"
        self.sound.play("click")

    def spell_smite(self) -> None:
        self.spell("smite")

    def spell_meteor(self) -> None:
        self.spell("meteor")

    def spell_orb(self) -> None:
        self.spell("orb")

    def threat(self) -> Monster | None:
        """The leader closest to cursing: the chant nearest its end, else the pondering nearest its end."""
        leaders = self.world.leaders()
        chanting = [m for m in leaders if m.chant_curse is not None]
        if chanting:
            return min(chanting, key=lambda m: (m.chant_left, m.id))
        pondering = [m for m in leaders if m.asking is not None]
        return min(pondering, key=lambda m: (m.ask_left, m.id)) if pondering else None

    def _cast_at(self, key: str, wx: float, wy: float) -> bool:
        if self.paused:
            self._refuse("Spells are cast in the fight's own time: resume it first (P).")
            return False
        world = self.world
        x, y = (wx - MAP_X) / T, (wy - MAP_Y) / T
        if key == "smite":
            target = self.monster_at(wx, wy) or self.nearest_monster(wx, wy, T)
            if target is None:
                self._refuse("Smite strikes a monster: click on one.")
                return False
            return self._try(lambda: world.smite(target.id))
        if key == "meteor":
            return self._try(lambda: world.meteor(x, y))
        return self._try(lambda: world.orb(x, y))

    def slot_1(self) -> None:
        self.pick(BUILD[0])

    def slot_2(self) -> None:
        self.pick(BUILD[1])

    def slot_3(self) -> None:
        self.pick(BUILD[2])

    def slot_4(self) -> None:
        self.pick(BUILD[3])

    def slot_5(self) -> None:
        self.pick(BUILD[4])

    def call_wave(self) -> None:
        if self.world.can_call_wave:
            self._try(self.world.call_wave)

    def toggle_speed(self) -> None:
        self.speed = 1.0 if self.speed > 1 else 2.0

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def toggle_thoughts(self) -> None:
        self.fx.show_thoughts = not self.fx.show_thoughts
        if self.settings is not None:
            self.settings["minds"] = self.fx.show_thoughts
            self.settings.save()

    def upgrade(self) -> None:
        if self.selected is not None:
            self._try(lambda: self.world.upgrade(self.selected.id))

    def sell(self) -> None:
        if self.selected is not None:
            tower, self.selected = self.selected, None
            self._try(lambda: self.world.sell(tower.id))

    def cleanse(self) -> None:
        if self.selected is not None:
            self._try(lambda: self.world.cleanse(self.selected.id))

    def cancel(self) -> None:
        """Escape lets go of what is held or selected; with nothing to let go of, it opens the menu."""
        if self.placing is not None or self.selected is not None:
            self.placing = None
            self.selected = None
        else:
            self.open_menu()

    def open_menu(self) -> None:
        if self.restart is None or self.to_title is None or self.to_map is None:
            self.paused = True   # a scene without a game around it (tests, clips) can only pause; P resumes
            return
        self.game.push(PauseScene(restart=self.restart, to_map=self.to_map, to_title=self.to_title, on_settings=self.settings_changed))

    def settings_changed(self) -> None:
        self.fx.show_thoughts = self.settings["minds"]

    # -- Pointer ---------------------------------------------------------------------------------

    def tile_at(self, wx: float, wy: float) -> tuple[int, int] | None:
        tx, ty = math.floor((wx - MAP_X) / T), math.floor((wy - MAP_Y) / T)
        level = self.world.level
        if 0 <= tx < level.width and 0 <= ty < level.height:
            return tx, ty
        return None

    def monster_at(self, wx: float, wy: float) -> Monster | None:
        best, best_d = None, 1e9
        for figure in self.view.figures.values():
            m = figure.monster
            cx, cy = self.view.chest(m)
            d = math.hypot(wx - cx, wy - cy)
            if d < m.kind.size * T * 0.7 and d < best_d:
                best, best_d = m, d
        return best

    def nearest_monster(self, wx: float, wy: float, within: float) -> Monster | None:
        """The monster nearest a point within ``within`` pixels, a leader before any other."""
        best, best_key = None, (True, within)
        for figure in self.view.figures.values():
            m = figure.monster
            cx, cy = self.view.chest(m)
            d = math.hypot(wx - cx, wy - cy)
            key = (m.kind.leader is None, d)
            if d <= within and key < best_key:
                best, best_key = m, key
        return best

    def door_at(self, tile: tuple[int, int] | None) -> int | None:
        if tile is None:
            return None
        for i, door in enumerate(self.world.level.doors):
            if abs(door[0] - tile[0]) + abs(door[1] - tile[1]) <= 1:
                return i
        return None

    def handle_input(self, event) -> bool:
        if event.type == "click":
            if event.button == "right":
                self.placing = None
                self.selected = None
                return True
            control = self.hud.hit(event.x, event.y)
            if control is not None:
                self._control(control.name, control.enabled)
                return True
            if event.y >= 672:
                return True
            if self.placing is not None and self.placing.startswith("spell:"):
                if self._cast_at(self.placing[6:], event.world_x, event.world_y) and not event.shift:
                    self.placing = None
                return True
            tile = self.tile_at(event.world_x, event.world_y)
            if self.placing == "gate":
                door = self.door_at(tile)
                if door is not None and self._try(lambda: self.world.build_door(door)):
                    self.placing = None
                return True
            if self.placing is not None and tile is not None:
                if self._try(lambda: self.world.build(self.placing, tile)):
                    if not event.shift:
                        self.placing = None
                return True
            tower = self.world.tower_at(tile) if tile is not None else None
            self.selected = tower
            if tower is not None:
                self.sound.play("click")
            return True
        return False

    def _control(self, name: str, enabled: bool) -> None:
        kind, _, key = name.partition(":")
        if kind == "spell":
            self.spell(key)   # it says why when it cannot
        elif kind == "build" and not offers(self.location, key):
            self.pick(key)    # it says where the slot's tower arrives
        elif not enabled:
            self.sound.play("refuse")
        elif kind == "build":
            self.pick(key)
        elif name == "call":
            self.call_wave()
        elif name == "speed":
            self.toggle_speed()
        elif name == "menu":
            self.open_menu()
        elif name in ("upgrade", "sell", "cleanse"):
            getattr(self, name)()

    # -- Drawing ---------------------------------------------------------------------------------

    def draw(self) -> None:
        world = self.world
        mouse = self.game.mouse_position
        hovered = None
        if mouse is not None and mouse[1] < 672:
            wx, wy = self.camera.screen_to_world(*mouse)
            hovered = self.monster_at(wx, wy)
            tile = self.tile_at(wx, wy)
            if self.placing == "gate":
                self._gate_sockets(self.door_at(tile))
            elif self.placing is not None and self.placing.startswith("spell:"):
                self._aim(self.placing[6:], wx, wy, hovered)
            elif self.placing is not None and tile is not None:
                self._ghost(self.placing, tile)
        if self.selected is not None:
            self._ring(self.selected.centre, self.selected.reach, (230, 190, 100, 220))
        self._bars()
        self.fx.draw()
        self.hud.draw(placing=self.placing, selected=self.selected, hovered=hovered, speed=self.speed, paused=self.paused,
                      mouse=mouse, costs=self.cost)
        if mouse is not None and mouse[1] < 672 and self.placing is None and hovered is None:
            tile = self.tile_at(*self.camera.screen_to_world(*mouse))
            tower = world.tower_at(tile) if tile is not None else None
            if tower is not None:
                self.hud.tower_tip(tower, mouse)
        if self.paused:
            with self.screen_layer(4):
                self.draw_text("Paused", 640, 330, style="banner", anchor_x="center", anchor_y="center")
                self.draw_text("P resumes", 640, 372, font_size=16, color=style.BONE, anchor_x="center", anchor_y="center")

    def _ring(self, centre: tuple[float, float], reach: float, color, fill: bool = True) -> None:
        cx, cy = px(*centre)
        r = reach * T
        if fill:
            self.draw_circle(cx, cy, r, color[:3] + (26,), space="world", layer=RenderLayer.EFFECTS)
        steps = 64
        for i in range(steps):
            a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
            self.draw_line(cx + r * math.cos(a0), cy + r * math.sin(a0), cx + r * math.cos(a1), cy + r * math.sin(a1), color, 1.6,
                           space="world", layer=RenderLayer.EFFECTS)

    def _aim(self, key: str, wx: float, wy: float, hovered: Monster | None) -> None:
        """Where a held spell would strike: its circle on the floor, or the monster Smite would hit."""
        ready = self.world.mana >= self.world.spell_cost(key) and not self.paused
        if key == "smite":
            target = hovered or self.nearest_monster(wx, wy, T)
            if target is not None:
                x, y = self.view.chest(target)
                r = target.kind.size * T * 0.7
                self._ring(((x - MAP_X) / T, (y - MAP_Y) / T), r / T, (255, 226, 140, 230) if ready else (160, 140, 120, 160))
            return
        color = {"meteor": (255, 140, 60, 220), "orb": (150, 210, 255, 220)}[key] if ready else (160, 140, 120, 160)
        self._ring(((wx - MAP_X) / T, (wy - MAP_Y) / T), SPELLS[key].radius, color)

    def _ghost(self, key: str, tile: tuple[int, int]) -> None:
        level = self.world.level
        ok = level.buildable(*tile) and self.world.tower_at(tile) is None and self.world.gold >= self.cost(key)
        cx, cy = px(tile[0] + 0.5, tile[1] + 0.5)
        cell, k = self.art.tower, TOWER_SCALE
        self.draw_image(f"tower/{key}/0", cx - cell.origin[0] * k, cy + 0.25 * T - cell.origin[1] * k, cell.size[0] * k,
                        cell.size[1] * k, opacity=0.6, space="world", layer=RenderLayer.EFFECTS)
        self.draw_rect(MAP_X + tile[0] * T + 2, MAP_Y + tile[1] * T + 2, T - 4, T - 4, (0, 0, 0, 0),
                       border_color=(120, 220, 120, 200) if ok else (230, 60, 60, 220), border_width=2, space="world",
                       layer=RenderLayer.EFFECTS)
        self._ring((tile[0] + 0.5, tile[1] + 0.5), self.world.tower_levels[key][0].range, (120, 220, 120, 200) if ok else (230, 60, 60, 200))

    def _gate_sockets(self, hovered: int | None) -> None:
        for i, (x, y) in enumerate(self.world.level.doors):
            door = self.world.doors[i]
            color = (255, 220, 120, 255) if i == hovered else (200, 160, 80, 160)
            if door.built:
                color = (120, 110, 100, 120)
            self.draw_rect(MAP_X + x * T + 1, MAP_Y + y * T + 1, T - 2, T - 2, (255, 220, 120, 40 if i == hovered else 0),
                           border_color=color, border_width=2.5, space="world", layer=RenderLayer.EFFECTS)

    def _bars(self) -> None:
        world = self.world
        for figure in self.view.figures.values():
            m = figure.monster
            max_hp = m.max_hp
            x, y = self.view.chest(m)
            top = y - m.kind.size * T * 0.75 - 8
            if m.hp < max_hp or m.kind.leader is not None:
                w = 18 + 16 * m.kind.size
                self.draw_rect(x - w / 2 - 1, top - 1, w + 2, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                color = (200, 170, 70, 255) if m.kind.leader is not None else (200, 28, 28, 255)
                self.draw_rect(x - w / 2, top, w * max(0.0, m.hp / max_hp), 3, color, space="world", layer=RenderLayer.UI_WORLD)
            if m.asking is not None:
                dots = "." * (1 + int(self.view.clock * 4) % 3)
                self.draw_text(dots, x, top - 6, font_size=18, color=(220, 150, 255, 255), anchor_x="center", space="world",
                               layer=RenderLayer.UI_WORLD)
        for door in world.doors:
            if door.built and door.hp < world.gate_life:
                x, y = world.level.doors[door.index]
                cx, cy = px(x + 0.5, y + 0.5)
                self.draw_rect(cx - 20, cy - 52, 40, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                self.draw_rect(cx - 19, cy - 51, 38 * door.hp / world.gate_life, 3, (230, 190, 90, 255), space="world", layer=RenderLayer.UI_WORLD)

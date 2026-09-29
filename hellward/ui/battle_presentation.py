"""Battle presentation: visuals, audio reactions, pointer geometry, and the rendered panel.

The scene owns the rules clock and commands. This module owns what one world step looks and
sounds like. ``route_events`` consumes events only after the scene has let the scripted player's
hands observe them; ``update`` interpolates the resulting world into a frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from saga2d import RenderLayer, Scene

from hellward.art.sprites import Art
from hellward.sim.content import CURSES, MONSTERS, SPELLS
from hellward.sim.model import Monster, Tower, World
from hellward.ui import style
from hellward.ui.effects import Effects
from hellward.ui.hud import Control, Hud, TOP
from hellward.ui.lighting import Lighting
from hellward.ui.view import MAP_X, MAP_Y, T, TOWER_SCALE, WorldView, px


@dataclass
class BattleState:
    placing: str | None
    selected: Tower | None
    speed: float
    paused: bool


class BattlePresentation:
    """All battle feedback behind event, frame, drawing and pointer operations."""

    def __init__(self, scene: Scene, world: World, art: Art, sound: Any, *, breach_claim: str | None,
                 show_thoughts: bool = True) -> None:
        self.scene = scene
        self.world = world
        self.art = art
        self.sound = sound
        self.view = WorldView(scene, world, art)
        self.fx = Effects(scene, self.view, world)
        self.hud = Hud(scene, world, breach_claim=breach_claim)
        self.lighting = Lighting(scene, (MAP_X, MAP_Y), (world.level.width * T, world.level.height * T))
        self.fx.show_thoughts = show_thoughts
        self.hud.banner(world.location.name, "Hold the sanctuary. The first wave comes soon.", life=4.5)
        self.door_clock: dict[int, float] = {}
        self.last_hold_note = -10.0

    @property
    def show_thoughts(self) -> bool:
        return self.fx.show_thoughts

    @show_thoughts.setter
    def show_thoughts(self, value: bool) -> None:
        self.fx.show_thoughts = value

    def before_step(self) -> None:
        self.view.before_step()

    def route_events(self) -> None:
        for event in self.world.events:
            self._event(event)
        self.world.events.clear()

    def update(self, dt: float, alpha: float, state: BattleState) -> None:
        self.fx.selected = state.selected.id if state.selected is not None else -1
        self.view.sync(alpha, dt, animation_dt=0.0 if state.paused else min(dt, 0.1) * state.speed)
        self.fx.update(dt)
        self.hud.update(dt)
        self._door_blows(dt, state)
        self.lighting.render(self.view.lights() + self.fx.lights())

    def refuse(self, why: str) -> None:
        self.hud.note(why, style.DIM)
        self.sound.play("refuse")

    def clear_banners(self) -> None:
        self.hud.banners.clear()

    def hit_control(self, x: float, y: float) -> Control | None:
        return self.hud.hit(x, y)

    def _cost(self, key: str) -> int:
        return self.world.door_cost if key == "gate" else self.world.cost(key)

    # -- Reaction to rules events -----------------------------------------------------------

    def _door_blows(self, dt: float, state: BattleState) -> None:
        if state.paused:
            return
        for door in self.world.doors:
            if not door.built:
                continue
            batterers = sum(1 for m in self.world.monsters if m.door == door.index)
            if not batterers:
                continue
            left = self.door_clock.get(door.index, 0.0) - dt * state.speed
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
            cue = {"arrow": "arrow_cast", "pyre": "fire_cast", "frost": "frost", "plague": "venom_cast"}[e[1].kind]
            sound.play(cue, volume=0.6)
        elif kind == "impact":
            bolt = e[1]
            cue = ("fireball" if bolt.splash > 0 else "fire_hit") if bolt.kind == "pyre" else (
                "arrow_hit" if bolt.kind == "arrow" else "frost" if bolt.kind == "frost" else "venom_hit")
            sound.play(cue, volume=0.7)
        elif kind == "chain":
            sound.play("lightning", volume=0.7)
        elif kind == "nova":
            sound.play("frost", volume=0.7)
        elif kind == "amplify":
            sound.play("curse", volume=0.7)
        elif kind == "twister":
            sound.play("frost", volume=0.6)
        elif kind == "corpse_explosion":
            sound.play("fire_hit", volume=0.8)
        elif kind == "death":
            sound.play(f"death_{e[2]}", volume=0.8)
            if e[5] >= 3:
                sound.play("gold")
        elif kind == "salvage":
            self.hud.note(f"Salvage recovered ({world.salvage_held}). Bank it after victory or sell during a break.", style.GOLD)
        elif kind == "salvage_sold":
            self.hud.note(f"Sold {e[1]} salvage for {e[2]} battle gold.", style.GOLD)
            sound.play("gold")
        elif kind == "breach_choice":
            if e[1] == "decline":
                self.hud.note("The side entrance stays sealed.", style.DIM)
            else:
                self.hud.note(f"The side entrance opens for {'a trophy' if e[1] == 'trophy' else 'a cash cache'}.", style.UNIQUE)
        elif kind == "breach_elite":
            self.hud.banner(e[2], "An elite comes from the side entrance.", color=style.UNIQUE)
        elif kind == "breach_cleared":
            reward = "Its trophy is yours after a victory." if e[1] == "trophy" else "Its cash cache pays now."
            self.hud.note(f"Side pack defeated. {reward}", style.HOLY)
        elif kind == "breach_failed":
            self.hud.note("A side monster escaped. Its cache is lost.", style.BLOOD)
        elif kind == "breach_cash":
            self.hud.note(f"Side cache: +{e[1]} gold.", style.GOLD)
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
            sound.play("chant")
            if leader is not None:
                self.hud.note(f"{leader.kind.name} chants {CURSES[e[2]].name} on the marked spot.", style.CURSE)
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
            self.hud.note(f"{leader.kind.name if leader else 'The leader'} loses its curse, and its next will not break.",
                          style.HOLY)
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
                self.hud.note(f"{leader.kind.name} weighed {decision.considered}: {CURSES[decision.cast.curse].name} "
                              f"on the marked spot, +{decision.cast.gain:.0f} life", style.UNIQUE)
            elif decision.later is not None and self.hud.clock - self.last_hold_note > 6:
                self.last_hold_note = self.hud.clock
                self.hud.note(f"{leader.kind.name} waits: in {decision.later.delay:.0f}s its curse is worth more", style.DIM)
        elif kind == "victory":
            sound.play("victory")
            sound.music("title")
        elif kind == "defeat":
            sound.play("defeat")

    # -- Pointer geometry -------------------------------------------------------------------

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

    # -- Drawing ---------------------------------------------------------------------------

    def draw(self, state: BattleState) -> None:
        world = self.world
        mouse = self.scene.game.mouse_position
        hovered = None
        if mouse is not None and mouse[1] < TOP:
            wx, wy = self.scene.camera.screen_to_world(*mouse)
            hovered = self.monster_at(wx, wy)
            tile = self.tile_at(wx, wy)
            if state.placing == "gate":
                self._gate_sockets(self.door_at(tile))
            elif state.placing is not None and state.placing.startswith("spell:"):
                self._aim(state.placing[6:], wx, wy, hovered, state)
            elif state.placing is not None and tile is not None:
                self._ghost(state.placing, tile)
        if state.selected is not None:
            # an aura is not a reach: Dim Vision does nothing to it, so the ring shows the aura's own radius
            reach = state.selected.stats.range if state.selected.kind.key == "grove" else state.selected.reach
            self._ring(state.selected.centre, reach, (230, 190, 100, 220))
        self._bars()
        self.fx.draw()
        self.hud.draw(placing=state.placing, selected=state.selected, hovered=hovered, speed=state.speed, paused=state.paused,
                      mouse=mouse, costs=self._cost)
        if mouse is not None and mouse[1] < TOP and state.placing is None and hovered is None:
            tile = self.tile_at(*self.scene.camera.screen_to_world(*mouse))
            tower = world.tower_at(tile) if tile is not None else None
            if tower is not None:
                self.hud.tower_tip(tower, mouse)
        if state.paused:
            with self.scene.screen_layer(4):
                self.scene.draw_text("Paused", 640, 330, style="banner", anchor_x="center", anchor_y="center")
                self.scene.draw_text("P resumes", 640, 372, font_size=16, color=style.BONE, anchor_x="center", anchor_y="center")

    def _ring(self, centre: tuple[float, float], reach: float, color, fill: bool = True) -> None:
        cx, cy = px(*centre)
        r = reach * T
        if fill:
            self.scene.draw_circle(cx, cy, r, color[:3] + (26,), space="world", layer=RenderLayer.EFFECTS)
        steps = 64
        for i in range(steps):
            a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
            self.scene.draw_line(cx + r * math.cos(a0), cy + r * math.sin(a0), cx + r * math.cos(a1), cy + r * math.sin(a1), color, 1.6,
                           space="world", layer=RenderLayer.EFFECTS)

    def _aim(self, key: str, wx: float, wy: float, hovered: Monster | None, state: BattleState) -> None:
        """Where a held spell would strike: its circle on the floor, or the monster Smite would hit."""
        ready = self.world.mana >= self.world.spell_cost(key) and not state.paused
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
        ok = level.buildable(*tile) and self.world.tower_at(tile) is None and self.world.gold >= self._cost(key)
        cx, cy = px(tile[0] + 0.5, tile[1] + 0.5)
        cell, k = self.art.tower, TOWER_SCALE
        if self.scene.game.assets.has_image(f"tower/{key}/0"):
            self.scene.draw_image(f"tower/{key}/0", cx - cell.origin[0] * k, cy + 0.25 * T - cell.origin[1] * k, cell.size[0] * k,
                            cell.size[1] * k, opacity=0.6, space="world", layer=RenderLayer.EFFECTS)
        else:   # no sprite for the kind yet: a coloured rune disc on its tile
            color = (214, 204, 176, 160) if key == "altar" else (120, 230, 60, 160)
            self.scene.draw_circle(cx, cy, T * 0.42, color, space="world", layer=RenderLayer.EFFECTS)
        self.scene.draw_rect(MAP_X + tile[0] * T + 2, MAP_Y + tile[1] * T + 2, T - 4, T - 4, (0, 0, 0, 0),
                       border_color=(120, 220, 120, 200) if ok else (230, 60, 60, 220), border_width=2, space="world",
                       layer=RenderLayer.EFFECTS)
        self._ring((tile[0] + 0.5, tile[1] + 0.5), self.world.tower_levels[key][0].range, (120, 220, 120, 200) if ok else (230, 60, 60, 200))

    def _gate_sockets(self, hovered: int | None) -> None:
        for i, (x, y) in enumerate(self.world.level.doors):
            door = self.world.doors[i]
            color = (255, 220, 120, 255) if i == hovered else (200, 160, 80, 160)
            if door.built:
                color = (120, 110, 100, 120)
            elif door.rubble:   # broken this wave: it takes a gate again once the wave is cleared
                color = (220, 70, 60, 220)
            self.scene.draw_rect(MAP_X + x * T + 1, MAP_Y + y * T + 1, T - 2, T - 2, (255, 220, 120, 40 if i == hovered else 0),
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
                self.scene.draw_rect(x - w / 2 - 1, top - 1, w + 2, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                color = (200, 170, 70, 255) if m.kind.leader is not None else (200, 28, 28, 255)
                self.scene.draw_rect(x - w / 2, top, w * max(0.0, m.hp / max_hp), 3, color, space="world", layer=RenderLayer.UI_WORLD)
            if m.asking is not None:
                dots = "." * (1 + int(self.view.clock * 4) % 3)
                self.scene.draw_text(dots, x, top - 6, font_size=18, color=(220, 150, 255, 255), anchor_x="center", space="world",
                               layer=RenderLayer.UI_WORLD)
        for door in world.doors:
            if door.built and door.hp < world.gate_life:
                x, y = world.level.doors[door.index]
                cx, cy = px(x + 0.5, y + 0.5)
                self.scene.draw_rect(cx - 20, cy - 52, 40, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                self.scene.draw_rect(cx - 19, cy - 51, 38 * door.hp / world.gate_life, 3, (230, 190, 90, 255), space="world", layer=RenderLayer.UI_WORLD)

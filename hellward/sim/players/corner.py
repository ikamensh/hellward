"""The corner player: Ilya's winning opening from the old Normal, now tested against area curses.

- Frost Shrine on a buildable tile at every path corner (tile diagonal to a waypoint turn, covering both legs)
- Other offered damage towers packed on free tiles closest to those frost shrines
- Spend every coin as it comes (build first, then upgrade where the tree allows)
- Gates in every arch when offered
- Smite on a chanting leader's sign when it has the mana
- Cleanse the most valuable cursed tower
- Skills: adept/master of cold and of each offered tower, in that order
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from hellward.sim.campaign import Location
from hellward.sim.content import DOOR, MONSTERS, SPELLS, TOWERS, Element, TowerKind
from hellward.sim.model import DOOR_STOP, JOSTLE, Refused, Tower, World
from hellward.sim.players.hands import Hands, ready
from hellward.sim.players.spacing import max_curse_radius, score_with_spacing
from hellward.sim.skills import SKILLS, can_learn, column_of
from hellward.sim.sums import float_sum, int_sum


def path_corners(level) -> list[tuple[int, int]]:
    """Tiles diagonal to a waypoint turn: corners where the path changes direction."""
    corners = []
    waypoints = level.waypoints
    for i in range(1, len(waypoints) - 1):
        x0, y0 = waypoints[i - 1]
        x1, y1 = waypoints[i]
        x2, y2 = waypoints[i + 1]
        dx1, dy1 = x1 - x0, y1 - y0
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 == 0 and dy2 == 0:
            cx, cy = x1 + (1 if dx2 > 0 else -1), y1 + (1 if dy1 > 0 else -1)
        elif dy1 == 0 and dx2 == 0:
            cx, cy = x1 + (1 if dx1 > 0 else -1), y1 + (1 if dy2 > 0 else -1)
        else:
            continue
        if level.buildable(cx, cy):
            corners.append((cx, cy))
    return corners


def tower_reach(kind: str, world: World) -> float:
    stats = world.tower_levels[kind][0]
    return stats.range


def tile_value_for_kind(location: Location, kind: str, tile: tuple[int, int], reach: float) -> float:
    spans = location.level.coverage(tile, reach)
    length = float_sum(b - a for a, b in spans)
    queues = 0.0
    for door in location.level.doors:
        ds = location.level.s_of(door)
        for a, b in spans:
            if a <= ds <= b:
                queues += 1.0
                break
    if kind == "frost":
        return 10.0 * queues + 0.5 * length
    if kind == "plague":
        return length + 3.0 * queues
    if kind == "altar":
        return length * 2.0 + 4.0 * queues
    if kind == "grove":
        return length * 1.5 + 3.0 * queues
    return length + 6.0 * queues


@dataclass
class Corner:
    name: str = "corner"
    reaction: tuple[float, float] = (0.5, 0.8)
    aim_gap: float = 0.5
    _planned: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    _frost_tiles: list[tuple[int, int]] = field(default_factory=list)
    _clock: float = 0.0
    _last_aim: float = -1e9
    THINK: float = 0.5

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        arsenal = location.arsenal
        kinds = (["frost"] if "frost" in arsenal.towers else []) + [k for k in arsenal.towers if k != "frost"]
        order = [key for kind in kinds for key in sorted((k for k, skill in SKILLS.items() if skill.column == column_of(kind)),
                                                         key=lambda k: SKILLS[k].tier)]
        if arsenal.gates:
            order += ["holy_shield", "salvation", "thorns"]
        order += ["warmth", "soul_harvest", "spell_mastery"]
        learned: frozenset[str] = frozenset()
        for key in [*order, *(k for k in SKILLS if k not in order)]:
            if can_learn(learned, key, sigils):
                learned |= {key}
        return learned

    def act(self, hands: Hands) -> None:
        world = hands.world
        if not self._planned:
            self._plan(world)
        if world.time < self._clock:
            return
        self._clock = world.time + self.THINK
        self._spells(hands)
        self._gates(world)
        self._spend(world)
        if world.can_call_wave and world.break_left is not None and world.break_left < 23.0:
            world.call_wave()

    def _plan(self, world: World) -> None:
        level = world.level
        arsenal = world.location.arsenal
        self._frost_tiles = path_corners(level)
        built: set[tuple[int, int]] = set()
        damage_kinds = [k for k in arsenal.towers if TOWERS[k].attack != "aura"]
        if "frost" in damage_kinds:
            damage_kinds.remove("frost")
        for tile in self._frost_tiles:
            if "frost" in arsenal.towers and tile not in built and world.level.buildable(*tile):
                self._planned.append(("frost", tile))
                built.add(tile)
        free_tiles = [(x, y) for y in range(level.height) for x in range(level.width)
                      if level.buildable(x, y) and (x, y) not in built]
        radius = max_curse_radius(world.location)
        for kind in damage_kinds:
            reach = tower_reach(kind, world)
            free_tiles.sort(key=lambda t: (min(math.hypot(t[0] - ft[0], t[1] - ft[1]) for ft in self._frost_tiles) if self._frost_tiles else 0.0,
                                           -score_with_spacing(tile_value_for_kind(world.location, kind, t, reach), list(built), t, world.location) if radius > 0 else -tile_value_for_kind(world.location, kind, t, reach)))
            for tile in free_tiles[:2]:
                if tile not in built:
                    self._planned.append((kind, tile))
                    built.add(tile)
            free_tiles = [t for t in free_tiles if t not in built]

    def _spells(self, hands: Hands) -> None:
        world = hands.world
        if "cleanse" in world.location.arsenal.spells:
            self._cleanse(hands)
        if world.time - self._last_aim < self.aim_gap - 1e-9:
            return
        if "smite" in world.location.arsenal.spells:
            threats = hands.threats()
            for sign in threats:
                if sign.kind == "chant" and world.mana >= world.spell_cost("smite"):
                    hands.smite(sign.leader)
                    self._last_aim = world.time
                    return

    def _cleanse(self, hands: Hands) -> None:
        world = hands.world
        if world.mana < world.spell_cost("cleanse"):
            return
        best, best_value = None, 0.0
        for t in world.towers.values():
            if not t.curses:
                continue
            left = max(t.curses.values())
            if left < 2.0:
                continue
            value = t.spent * left
            if value > best_value:
                best, best_value = t, value
        if best is not None:
            hands.cleanse(best.id)

    def _gates(self, world: World) -> None:
        if not world.location.arsenal.gates or world.gold < DOOR.cost:
            return
        for door in world.doors:
            if not door.built and not door.rubble:
                try:
                    world.build_door(door.index)
                except Refused:
                    pass

    def _spend(self, world: World) -> None:
        while True:
            built = {t.tile for t in world.towers.values()}
            todo = [(kind, tile) for kind, tile in self._planned if tile not in built]
            if todo:
                kind, tile = todo[0]
                if world.gold < world.cost(kind):
                    return
                try:
                    world.build(kind, tile)
                except Refused:
                    self._planned.pop(0)
                continue
            upgrades = [(t, c) for t in world.towers.values()
                        if (c := world.upgrade_cost(t)) is not None and world.rank_needs(t) is None]
            if not upgrades:
                return
            tower, cost = min(upgrades, key=lambda u: (u[0].level, u[0].id))
            if world.gold < cost:
                return
            world.upgrade(tower.id)


def _make_corner(seed: int) -> Corner:
    return Corner()


PLAYERS = {"corner": _make_corner}
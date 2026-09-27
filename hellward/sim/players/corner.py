"""The corner player: Ilya's winning opening from the old Normal, now tested against area curses.

- Frost Shrine on the inside of every bend of the path (the tile beside both legs)
- Other offered damage towers packed on free tiles closest to each shrine, bend by bend
- Spend every coin as it comes: build the plan, upgrade where the tree allows, then pack another round
- Gates in every arch when offered
- Smite on a chanting leader's sign when it has the mana
- Cleanse the most valuable cursed tower
- Skills: adept/master of cold and of each offered tower, in that order
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from hellward.sim.campaign import Location
from hellward.sim.content import DOOR, TOWERS
from hellward.sim.model import Refused, World
from hellward.sim.players.hands import Hands, ready
from hellward.sim.skills import SKILLS, can_learn, column_of
from hellward.sim.sums import float_sum


def path_corners(level) -> list[tuple[int, int]]:
    """The inside of every bend in the path: the tile beside both legs, where a frost nova covers the most of it."""
    corners = []
    waypoints = level.waypoints
    for (x0, y0), (x1, y1), (x2, y2) in zip(waypoints, waypoints[1:], waypoints[2:]):
        in_x, in_y = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
        out_x, out_y = (x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1)
        cx, cy = x1 - in_x + out_x, y1 - in_y + out_y
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
        if self._spend(world):   # the towers first; the gates only once the planned towers stand
            self._gates(world)
        if world.can_call_wave and world.break_left is not None and world.break_left < 23.0:
            world.call_wave()

    def _plan(self, world: World) -> None:
        """Bend by bend: the frost shrine on the inside, then one of each other damage tower packed round it."""
        self._frost_tiles = path_corners(world.level)
        for corner in self._frost_tiles:
            if "frost" in world.location.arsenal.towers:
                self._planned.append(("frost", corner))
            self._pack(world, [corner])

    def _pack(self, world: World, corners: list[tuple[int, int]]) -> bool:
        """One round: at each corner, one of each other offered damage tower on the free tile nearest the corner that
        sees the most path, so the gold goes out mixed. Whether it planned anything."""
        level = world.level
        damage_kinds = [k for k in world.location.arsenal.towers
                        if TOWERS[k].attack not in ("aura", "amplify") and k != "frost"]
        taken = {tile for _, tile in self._planned} | {t.tile for t in world.towers.values()}
        free = [(x, y) for y in range(level.height) for x in range(level.width)
                if level.buildable(x, y) and (x, y) not in taken]
        before = len(self._planned)
        for corner in corners:
            for kind in damage_kinds:
                if not free:
                    break
                reach = tower_reach(kind, world)
                nearest = min(math.hypot(t[0] - corner[0], t[1] - corner[1]) for t in free)
                near = [t for t in free if math.hypot(t[0] - corner[0], t[1] - corner[1]) <= nearest + 1.0]
                tile = max(near, key=lambda t: (tile_value_for_kind(world.location, kind, t, reach), -t[1], -t[0]))
                self._planned.append((kind, tile))
                free.remove(tile)
        return len(self._planned) > before

    def _spells(self, hands: Hands) -> None:
        world = hands.world
        if "cleanse" in world.location.arsenal.spells:
            self._cleanse(hands)
        if world.time - self._last_aim < self.aim_gap - 1e-9:
            return
        if "smite" in world.location.arsenal.spells:
            threats = hands.threats()
            for sign in threats:
                if sign.kind == "chant" and ready(world, "smite"):
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

    def _spend(self, world: World) -> bool:
        """Build the planned towers in order, then raise ranks, then plan another round, every coin as it comes.
        Whether every planned tower stands."""
        while True:
            built = {t.tile for t in world.towers.values()}
            todo = [(kind, tile) for kind, tile in self._planned if tile not in built]
            if todo:
                kind, tile = todo[0]
                if world.gold < world.cost(kind):
                    return False
                try:
                    world.build(kind, tile)
                except Refused:
                    self._planned.remove((kind, tile))
                continue
            upgrades = [(t, c) for t in world.towers.values()
                        if (c := world.upgrade_cost(t)) is not None and world.rank_needs(t) is None]
            if not upgrades:
                if self._pack(world, self._frost_tiles):
                    continue
                return True
            tower, cost = min(upgrades, key=lambda u: (u[0].level, u[0].id))
            if world.gold < cost:
                return True
            world.upgrade(tower.id)


def _make_corner(seed: int) -> Corner:
    return Corner()


PLAYERS = {"corner": _make_corner}
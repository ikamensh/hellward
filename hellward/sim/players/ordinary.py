"""The ordinary scripted defender: the tests, the clips and the balance tools' baseline.

It is deliberately ordinary: towers on the tiles that watch the most path (a door's queue counts
extra), elements in rotation, gates in the arches once it can afford them, upgrades with what is left,
and a Cleanse on the cursed tower that has work to do. It learns no skills and casts no other spell.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hellward.sim.campaign import Location
from hellward.sim.content import WAVE_BREAK
from hellward.sim.model import DOOR_STOP, JOSTLE, Refused, Tower, World
from hellward.sim.players.hands import Hands, REACT, AIM_GAP
from hellward.sim.sums import float_sum, int_sum

ROTATION = ("arrow", "pyre", "frost", "storm", "plague", "arrow", "pyre", "storm", "plague", "arrow")
DOOR_BONUS = 4.0     # path tiles a door queue in reach is worth when ranking a tile
THINK = 0.5          # seconds between the defender's decisions


def tile_scores(world: World, reach: float = 3.0) -> list[tuple[float, tuple[int, int]]]:
    level = world.level
    queues = [(route.key, s - DOOR_STOP - JOSTLE / 2)
              for route in level.routes for _, s in level.crossings(route.key)]
    scored = []
    for y in range(level.height):
        for x in range(level.width):
            if not level.buildable(x, y):
                continue
            score = 0.0
            for route in level.routes:
                spans = route.coverage((x, y), reach)
                score += float_sum(b - a for a, b in spans)
                score += DOOR_BONUS * int_sum(1 for key, q in queues
                                              if key == route.key and any(a <= q <= b for a, b in spans))
            scored.append((score, (x, y)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored


@dataclass
class Ordinary:
    name: str = "ordinary"
    reaction: tuple[float, float] = REACT
    aim_gap: float = AIM_GAP
    cleanse: bool = True
    doors: bool = True
    call_early: bool = True
    shift: int = 0        # where in the element rotation this defender starts: variety for the balance tools
    towers: int = 14
    planned: list[tuple[str, tuple[int, int]]] = field(default_factory=list)
    clock: float = 0.0

    def plan(self, world: World) -> None:
        tiles = [tile for _, tile in tile_scores(world)]
        rotation = [kind for kind in ROTATION if kind in world.location.arsenal.towers]
        self.planned = [(rotation[(i + self.shift) % len(rotation)], tile) for i, tile in enumerate(tiles[:self.towers])]

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        return frozenset()

    def act(self, hands: Hands) -> None:
        world = hands.world
        if world.time < self.clock:
            return
        self.clock = world.time + THINK
        if not self.planned:
            self.plan(world)
        if self.cleanse:
            self._cleanse(hands)
        if self.doors and world.location.arsenal.gates and world.wave >= 1:
            for door in world.doors:
                if not door.built and not door.rubble and world.gold >= world.door_cost + world.cost("arrow"):
                    try:
                        world.build_door(door.index)
                    except Refused:
                        pass
        self._spend(world)
        if (self.call_early and world.can_call_wave and world.break_left is not None and world.wave >= 0
                and world.break_left < WAVE_BREAK - 2):
            world.call_wave()

    def _spend(self, world: World) -> None:
        while True:
            built = {t.tile for t in world.towers.values()}
            todo = [(kind, tile) for kind, tile in self.planned if tile not in built]
            if todo:
                kind, tile = todo[0]
                if world.gold < world.cost(kind):
                    return
                world.build(kind, tile)
                continue
            upgrades = [(t, cost) for t in world.towers.values()
                        if (cost := world.upgrade_cost(t)) is not None and world.rank_needs(t) is None]
            if not upgrades:
                return
            tower, cost = min(upgrades, key=lambda u: (u[0].level, u[0].id))
            if world.gold < cost:
                return
            world.upgrade(tower.id)

    def _cleanse(self, hands: Hands) -> None:
        world = hands.world
        if world.mana < world.spell_cost("cleanse"):
            return
        busy: list[Tower] = []
        for t in world.towers.values():
            if t.curses and max(t.curses.values()) > 3.0:
                if any(world.in_reach(t, m.s, m.route) for m in world.monsters):
                    busy.append(t)
        if busy:
            hands.cleanse(max(busy, key=lambda t: (t.spent, -t.id)).id)

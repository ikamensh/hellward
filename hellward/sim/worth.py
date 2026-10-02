"""What a cell is worth to a tower: how much of each route it reaches.

A pure function of the level and the location's waves, computed per tower kind in the arsenal (each kind's
rank-I reach; the Knife Post's gate-queue bonus counts double, since it strikes standing monsters twice as
hard), with and without each gate. Boulder cells carry the worth they would have once cleared.
``tools/maps.py`` analyzes maps with the same reckoning.
"""

from __future__ import annotations

from hellward.sim import tuning
from hellward.sim.content import MONSTERS, TOWERS, Wave
from hellward.sim.level import Level

QUEUE_TILES = 1.0   # a gate's queue counts up to one more tile, weighted by the walkers' share
QUEUE_FRONT = tuning.number("battle.door_stop")
QUEUE_BACK = QUEUE_FRONT + tuning.number("battle.jostle")


def shares(level: Level, waves: tuple[Wave, ...]) -> tuple[dict[str, float], dict[str, float]]:
    """Each route's share of the waves' monsters: all of them, and those a gate stops (not flyers). A
    wanderer counts evenly on every route from its entrance, as the simulation chooses among them."""
    every = {route.key: 0.0 for route in level.routes}
    ground = dict(every)
    total = 0
    for wave in waves:
        for group in wave.groups:
            kind = MONSTERS[group.kind]
            routes = [group.route]
            if kind.movement == "wander":
                entrance = level.route(group.route).entrance
                routes = [route.key for route in level.routes if route.entrance == entrance]
            for key in routes:
                every[key] += group.count / len(routes)
                if not kind.flying:
                    ground[key] += group.count / len(routes)
            total += group.count
    if total == 0:
        return every, ground
    return {k: v / total for k, v in every.items()}, {k: v / total for k, v in ground.items()}


def cell(level: Level, every: dict[str, float], ground: dict[str, float], at: tuple[int, int], reach: float, *,
         knife: bool = False, built: frozenset[int] = frozenset()) -> float:
    """Tiles of the average monster's walk a tower on ``at`` reaches: each route's length in reach, weighted
    by the share of monsters walking it, plus the queues of the built gates it reaches, weighted by the share
    a gate stops."""
    worth = 0.0
    bonus = 2 * QUEUE_TILES if knife else QUEUE_TILES
    for route in level.routes:
        share, held = every[route.key], ground[route.key]
        if not share:
            continue
        spans = route.coverage(at, reach)
        for a, b in spans:
            worth += share * (b - a)
        if held:
            for door, crossing in level.crossings(route.key):
                if door not in built:
                    continue
                back, front = crossing - QUEUE_BACK, crossing - QUEUE_FRONT
                for a, b in spans:
                    worth += held * bonus * max(0.0, min(b, front) - max(a, back)) / (front - back)
    return worth


def worth_map(level: Level, waves: tuple[Wave, ...], kind: str, *,
              built: frozenset[int] = frozenset()) -> dict[tuple[int, int], float]:
    """Every buildable cell's worth to a tower kind, and every boulder's would-be worth once cleared."""
    every, ground = shares(level, waves)
    reach = TOWERS[kind].levels[0].range
    cells = [(x, y) for y in range(level.height) for x in range(level.width)
             if level.buildable(x, y) or (x, y) in level.boulders]
    return {at: cell(level, every, ground, at, reach, knife=kind == "knife", built=built) for at in cells}

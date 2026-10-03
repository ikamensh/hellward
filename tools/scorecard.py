"""Every measurable criterion of docs/design-criteria.md, with its number and whether it is met.

    uv run python tools/scorecard.py              # the checks that read the content tables
    uv run python tools/scorecard.py --json OUT   # the same, written as JSON for the evidence folder

A check reads the game's own tables (hellward/sim/data and the campaign), never a copy of their numbers. Criteria
that need bot runs are listed as not yet measured until their measurement exists.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim.balance import BALANCE  # noqa: E402
from hellward.sim.campaign import ACTS, LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import MAX_POISON_STACKS, MONSTERS, SPELLS, TOWERS, TowerKind, felt_hit  # noqa: E402
from hellward.sim.model import World  # noqa: E402
from tools.maps import (LEAST_CLUSTERED, LEAST_OCCUPIED, MOST_PRIME, REFERENCE_REACH, survey, traffic,  # noqa: E402
                        worth_map)

ATTACKS = ("bolt", "chain", "nova", "venom", "hook")   # tower attacks that deal damage; the others are mechanics towers


@dataclass(frozen=True)
class Result:
    id: str
    what: str
    value: str
    met: bool | None   # None: not measured yet


def spawns(location: Location) -> Iterator[tuple[str, float, int]]:
    """(monster kind, life, wave index) for every authored spawn of a location."""
    for index, wave in enumerate(location.waves):
        for group in wave.groups:
            life = MONSTERS[group.kind].hp
            for _ in range(group.count):
                yield group.kind, life, index


def is_boss(kind: str) -> bool:
    return MONSTERS[kind].boss


def bodies_per_wave() -> Result:
    most = max(sum(group.count for group in wave.groups) for location in LOCATIONS.values() for wave in location.waves)
    return Result("G2.1", "most monsters in one wave", str(most), most <= 30)


def three_ranks() -> Result:
    counts = sorted({len(kind.levels) for kind in TOWERS.values()})
    return Result("G2.3", "ranks per tower", ", ".join(map(str, counts)), counts == [3])


def number_scale() -> list[Result]:
    first = LOCATIONS[ORDER[0]]
    first_life = next(spawns(first))[1]
    first_hit = min(kind.levels[0].damage for kind in TOWERS.values() if kind.attack in ATTACKS)
    last = LOCATIONS[ORDER[-1]]
    ordinary = [life for kind, life, _ in spawns(last) if not is_boss(kind)]
    every = [(kind, life) for location in LOCATIONS.values() for kind, life, _ in spawns(location)]
    biggest = max(life for kind, life in every if not is_boss(kind))
    boss = max((life for kind, life in every if is_boss(kind)), default=0.0)
    top_hit = max(level.damage for kind in TOWERS.values() if kind.attack in ATTACKS for level in kind.levels)
    toughest = max(ordinary)
    return [
        Result("G2.4", "first monster's life", f"{first_life:.1f}", 8 <= first_life <= 12),
        Result("G2.4", "weakest first-rank hit", f"{first_hit:g}", 1 <= first_hit <= 2),
        Result("G2.4", "last location's toughest ordinary life", f"{toughest:.0f}", 60 <= toughest <= 100),
        Result("G2.4", "largest non-boss life", f"{biggest:.0f}", biggest <= 200),
        Result("G2.4", "largest boss life", f"{boss:.0f}", boss <= 1000),
        Result("G2.4", "largest tower hit (before bonuses)", f"{top_hit:g}", top_hit <= 30),
    ]


def felt_dps(kind: TowerKind, rank: int, location: Location) -> float:
    """A rank's damage per second as the location's host feels its hits (and its venom, as many stacks as its darts
    keep up), each monster kind weighed by its share of the life that comes: the location's armor and element mix."""
    level = kind.levels[rank]
    life: dict[str, float] = {}
    for monster, hp, _ in spawns(location):
        life[monster] = life.get(monster, 0.0) + hp
    total = sum(life.values())
    stacks = min(MAX_POISON_STACKS, level.rate * level.poison_time)
    return sum(hp / total * (level.rate * felt_hit(level.damage, kind.element, MONSTERS[monster])
                             + level.poison * stacks * MONSTERS[monster].taken(kind.element))
               for monster, hp in life.items())


def rank_economy() -> list[Result]:
    """Upgrading buys less damage per gold than a new rank-I tower, and more per cell, at every location that offers
    the tower, against that location's armor mix. The worst location's marginal damage per gold is shown. Not the Hook
    Tower: its ranks buy pulls, not damage."""
    out = []
    for key, kind in TOWERS.items():
        if kind.attack not in ATTACKS or kind.attack == "hook":
            continue
        cost = [level.cost for level in kind.levels]
        worst: tuple[float, str, list[float]] | None = None
        met = True
        for location in LOCATIONS.values():
            if key not in location.arsenal.towers:
                continue
            dps = [felt_dps(kind, rank, location) for rank in range(3)]
            per_gold = [dps[0] / cost[0]] + [(dps[r] - dps[r - 1]) / cost[r] for r in (1, 2)]
            cheaper = all(per_gold[r] < per_gold[0] for r in (1, 2))
            denser = all(dps[r] > dps[0] for r in (1, 2))
            met = met and cheaper and denser
            slack = per_gold[0] - max(per_gold[1], per_gold[2])
            if worst is None or slack < worst[0]:
                worst = (slack, location.key, per_gold)
        assert worst is not None
        out.append(Result("R3", f"{kind.name}: damage per gold by rank, at {worst[1]}",
                          " / ".join(f"{v:.3f}" for v in worst[2]), met))
    return out


def no_dispel() -> Result:
    """No spell lifts a curse (Cleanse, Salvation's ward) or breaks a chant (tests/test_spells.py plays them all)."""
    dispels = [name for name in ("cleanse",) if name in SPELLS or hasattr(World, name)]
    return Result("S1", "spells that lift a curse or break a chant", ", ".join(dispels) or "none", not dispels)


def tower_kinds() -> list[Result]:
    mechanics = [kind.name for kind in TOWERS.values() if kind.attack not in ATTACKS]
    share = len(mechanics) / len(TOWERS)
    return [Result("M4", "tower kinds", str(len(TOWERS)), len(TOWERS) >= 14),
            Result("M6", "share of mechanics towers", f"{share:.0%}", share >= 0.4)]


def real_estate() -> list[Result]:
    """Each map's scarce ground, by tools/maps.py: the worst map against each target."""
    maps = {key: survey(LOCATIONS[key]) for key in ORDER}
    occupied = min(maps, key=lambda key: maps[key].occupied_share)
    crowded = max(maps, key=lambda key: len(maps[key].prime))
    scattered = min(maps, key=lambda key: maps[key].clustered_share)
    return [
        Result("R1", "least occupied ground beside the halls", f"{maps[occupied].occupied_share:.0%} ({occupied})",
               maps[occupied].occupied_share >= LEAST_OCCUPIED),
        Result("R1", "most prime cells on a map", f"{len(maps[crowded].prime)} ({crowded})",
               len(maps[crowded].prime) <= MOST_PRIME),
        Result("R5", "fewest prime cells near another (maps only)",
               f"{maps[scattered].clustered_share:.0%} ({scattered})",
               maps[scattered].clustered_share >= LEAST_CLUSTERED),
    ]


def worth_and_cells() -> list[Result]:
    """R2: a battle's start carries every offered kind's per-cell coverage; R7: every frame's state carries
    each taken cell with its waves left, and each mark with its seconds."""
    from hellward.server.protocol import battle_start, state
    world = World(LOCATIONS["tristram"], seed=1)
    start = battle_start(world, demo=True, breach_claim=None)
    kinds = set(start["worth"]) == set(LOCATIONS["tristram"].arsenal.towers)
    bare = bool(start["worth"]["arrow"]["bare"])
    world.blighted[(3, 4)] = (2, "webbed")
    found = state(world)
    taken = found["blighted"] == [[3, 4, 2, "webbed"]] and isinstance(found["blight_marks"], list)
    return [Result("R2", "per-cell coverage in the battle's start", f"{len(start['worth'])} kinds",
                   kinds and bare),
            Result("R7", "a taken cell in the frame's state", str(found["blighted"]), taken)]


def blight_kinds() -> list[Result]:
    """R6's content half: a kind that takes empty cells walks each act's waves, its mark burning at least 1.5 s
    before it lands, its cells taken for two cleared waves (tests/test_blight.py plays the engine)."""
    blighters = {key for key, kind in MONSTERS.items() if kind.blight is not None}
    out = []
    for act, keys in ACTS.items():
        walked = {g.kind for key in keys for wave in LOCATIONS[key].waves for g in wave.groups}
        mine = sorted(blighters & walked)
        spec = all(MONSTERS[key].blight is not None and MONSTERS[key].blight.telegraph >= 1.5
                   and MONSTERS[key].blight.waves == 2 for key in mine)
        out.append(Result("R6", f"act {act}'s cell-takers", ", ".join(mine) or "none", bool(mine) and spec))
    return out


def power_table() -> list[Result]:
    """G3.4: at every location, the reference board's damage per second covers the last
    wave's life per second. The reference board is the best board the location's gold buys: at most 8 towers
    and not all rank III, each buy maximizing the worst walked route's supply over demand (Hooks buy pulls,
    not damage). Each route's demand is its monsters' life over their seconds inside the covered stretch;
    each tower's supply is its felt damage per second against the last wave's mix, weighed by life. Chains,
    splashes and venom beyond one stack are left out, so the board is weaker here than in a fight. The row
    says whether gold or cells bind."""
    out = []
    for key in ORDER:
        location = LOCATIONS[key]
        mix = _last_mix(location)
        total = sum(mix.values())
        shares = {kind: life / total for kind, life in mix.items()}
        gold = BALANCE.starting_gold() + sum(BALANCE.wave_income(i) for i in range(len(location.waves)))
        worth = worth_map(location.level, traffic(location))
        kinds = [k for k in location.arsenal.towers if TOWERS[k].attack in ATTACKS and TOWERS[k].attack != "hook"]
        routes = [r for r in location.level.routes
                  if any(g.route == r.key for g in location.waves[-1].groups)]
        cells: list = []
        for route in routes:
            top = sorted(worth, key=lambda c: (_cover_len(route, c, REFERENCE_REACH), worth[c]), reverse=True)
            cells += [c for c in top[:6] if _cover_len(route, c, REFERENCE_REACH) > 0]
        cells = list(dict.fromkeys(cells))
        board: dict = {}
        left = gold
        while True:
            offer = _best_buy(location, routes, board, cells, kinds, shares, left)
            if offer is None:
                break
            (cell, placed), price = offer
            board[cell] = placed
            left -= price
        binds = "gold" if left < min(TOWERS[k].levels[0].cost for k in kinds) else "cells"
        route, worst = min(_ratios(location, routes, board, shares).items(), key=lambda kv: kv[1])
        out.append(Result("G3.4", f"{key}: worst route's supply over demand ({route}; {binds} binds)",
                          f"{worst:.2f}", worst >= 1.0))
    return out


def _last_mix(location: Location) -> dict[str, float]:
    """The last wave's kinds with their life."""
    wave = location.waves[-1]
    mix: dict[str, float] = {}
    for group in wave.groups:
        life = MONSTERS[group.kind].hp * group.count
        mix[group.kind] = mix.get(group.kind, 0.0) + life
    return mix


def _felt_dps(kind: str, rank: int, shares: dict[str, float]) -> float:
    """A rank's damage per second against a kind mix: each hit as felt, weighed by the kind's life share."""
    tower, level = TOWERS[kind], TOWERS[kind].levels[rank]
    return sum(share * level.rate * felt_hit(level.damage, tower.element, MONSTERS[monster])
               for monster, share in shares.items())


def _best_buy(location: Location, routes: list, board: dict, cells: list, kinds: list[str],
              shares: dict[str, float], gold: int):
    """The buy that most raises the worst walked route's ratio: a new rank-I tower of the best damage per
    gold, or a rank up (at most 8 towers, at most seven at rank III); None when nothing affordable helps."""
    base = min(_ratios(location, routes, board, shares).values())
    new_kind = max(kinds, key=lambda k: _felt_dps(k, 0, shares) / TOWERS[k].levels[0].cost)
    tops = sum(1 for placed in board.values() if placed[1] == 2)
    best = None
    for cell in cells:
        if cell in board:
            kind, rank = board[cell]
            if rank == 2 or (rank == 1 and tops >= 7):
                continue
            price = TOWERS[kind].levels[rank + 1].cost
            if price > gold:
                continue
            trial = {**board, cell: (kind, rank + 1)}
        else:
            if len(board) >= 8:
                continue
            price = TOWERS[new_kind].levels[0].cost
            if price > gold:
                continue
            trial = {**board, cell: (new_kind, 0)}
        if base <= 0:
            key = _covered_key(location, routes, trial, shares)
            if best is None or key > best[0]:
                best = (key, price, (cell, trial[cell]))
            continue
        worst = min(_ratios(location, routes, trial, shares).values())
        if worst > base + 1e-9 and (best is None or (worst, -price) > (best[0], -best[1])):
            best = (worst, price, (cell, trial[cell]))
    if base <= 0:
        if best is None or best[0] <= _covered_key(location, routes, board, shares):
            return None
        return best[2], best[1]
    return None if best is None else (best[2], best[1])


def _covered_key(location: Location, routes: list, board: dict, shares: dict[str, float]) -> tuple:
    """How much of the walked routes a board reaches: routes covered, then tiles covered."""
    cover = _cover(location, routes, board, shares)
    return (sum(1 for supply, spans in cover.values() if spans > 0),
            round(sum(spans for supply, spans in cover.values()), 6))


def _ratios(location: Location, routes: list, board: dict, shares: dict[str, float]) -> dict[str, float]:
    """Each walked route's supply over demand: the towers covering it deal their felt damage per second;
    its monsters' life arrives over their seconds inside the covered stretch."""
    wave = location.waves[-1]
    cover = _cover(location, routes, board, shares)
    ratios = {}
    for route in routes:
        groups = [g for g in wave.groups if g.route == route.key]
        supply, covered = cover[route.key]
        demand = sum(MONSTERS[g.kind].hp * g.count
                      * MONSTERS[g.kind].speed / covered for g in groups) if covered else float("inf")
        ratios[route.key] = supply / demand if demand else 1.0
    return ratios or {"main": 0.0}


def _cover(location: Location, routes: list, board: dict, shares: dict[str, float]) -> dict[str, tuple]:
    """Each walked route's supply and covered tiles: the towers covering it, and the union they reach."""
    found: dict[str, tuple] = {}
    for route in routes:
        spans: list = []
        supply = 0.0
        for cell, (kind, rank) in board.items():
            reached = route.coverage(cell, TOWERS[kind].levels[rank].range)
            if reached:
                spans += reached
                supply += _felt_dps(kind, rank, shares)
        found[route.key] = (supply, _union_length(spans))
    return found


def _cover_len(route, cell: tuple[int, int], reach: float) -> float:
    return _union_length(route.coverage(cell, reach))


def _union_length(spans: list[tuple[float, float]]) -> float:
    total, end = 0.0, -1.0
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


CHECKS: tuple[Callable[[], Result | list[Result]], ...] = (
    bodies_per_wave, three_ranks, number_scale, rank_economy, no_dispel, tower_kinds, real_estate,
    worth_and_cells, blight_kinds, power_table,
)

NOT_YET = (
    "G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G2.2", "G2.5", "G2.6", "G3.1", "G3.2", "G3.3",
    "M1", "M2", "M3", "M5", "M7", "M9", "M10", "S2", "S3", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
    "R4", "T2", "T4",
)


def results() -> list[Result]:
    out: list[Result] = []
    for check in CHECKS:
        found = check()
        out.extend(found if isinstance(found, list) else [found])
    measured = {r.id for r in out}
    out.extend(Result(id, "not measured yet", "", None) for id in NOT_YET if id not in measured)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, help="also write the results here")
    args = parser.parse_args()
    rows = results()
    for r in rows:
        mark = {True: "MET ", False: "MISS", None: "    "}[r.met]
        print(f"{mark} {r.id:<6} {r.what:<48} {r.value}")
    met = sum(1 for r in rows if r.met)
    missed = sum(1 for r in rows if r.met is False)
    print(f"\n{met} met, {missed} missed, {sum(1 for r in rows if r.met is None)} not measured yet")
    if args.json:
        args.json.write_text(json.dumps([r.__dict__ for r in rows], indent=1))


if __name__ == "__main__":
    main()

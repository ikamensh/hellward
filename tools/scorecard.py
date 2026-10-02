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

from hellward.sim.campaign import LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import MAX_POISON_STACKS, MONSTERS, SPELLS, TOWERS, TowerKind, felt_hit  # noqa: E402
from hellward.sim.model import World  # noqa: E402

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
            life = MONSTERS[group.kind].hp * wave.hp * location.life
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
    median = statistics.median(ordinary)
    return [
        Result("G2.4", "first monster's life", f"{first_life:.1f}", 8 <= first_life <= 12),
        Result("G2.4", "weakest first-rank hit", f"{first_hit:g}", 1 <= first_hit <= 2),
        Result("G2.4", "last location's ordinary median life", f"{median:.0f}", 60 <= median <= 120),
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


CHECKS: tuple[Callable[[], Result | list[Result]], ...] = (
    bodies_per_wave, three_ranks, number_scale, rank_economy, no_dispel, tower_kinds,
)

NOT_YET = (
    "G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G2.2", "G2.5", "G2.6", "G3.1", "G3.2", "G3.3", "G3.4",
    "M1", "M2", "M3", "M5", "M7", "M9", "M10", "S2", "S3", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
    "R1", "R2", "R4", "R5", "R6", "R7", "T2", "T4",
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

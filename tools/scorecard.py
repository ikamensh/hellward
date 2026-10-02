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
from hellward.sim.content import MONSTERS, SPELLS, TOWERS  # noqa: E402
from tools.maps import LEAST_CLUSTERED, LEAST_OCCUPIED, MOST_PRIME, survey  # noqa: E402

ATTACKS = ("bolt", "chain", "nova", "venom")   # tower attacks that deal damage; the others are mechanics towers


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
    return MONSTERS[kind].lives >= 10


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


def rank_economy() -> list[Result]:
    """Upgrading buys less damage per gold than a new rank-I tower, and more per cell."""
    out = []
    for key, kind in TOWERS.items():
        if kind.attack not in ATTACKS:
            continue
        dps = [level.damage * level.rate for level in kind.levels]
        cost = [level.cost for level in kind.levels]
        per_gold = [dps[0] / cost[0]] + [(dps[r] - dps[r - 1]) / cost[r] for r in (1, 2)]
        cheaper = all(per_gold[r] < per_gold[0] for r in (1, 2))
        denser = all(dps[r] > dps[0] for r in (1, 2))
        out.append(Result("R3", f"{kind.name}: damage per gold by rank (marginal)",
                          " / ".join(f"{v:.3f}" for v in per_gold), cheaper and denser))
    return out


def no_dispel() -> Result:
    dispels = [spec.name for key, spec in SPELLS.items() if spec.aim == "tower" and key == "cleanse"]
    return Result("S1", "spells that lift a curse", ", ".join(dispels) or "none", not dispels)


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


CHECKS: tuple[Callable[[], Result | list[Result]], ...] = (
    bodies_per_wave, three_ranks, number_scale, rank_economy, no_dispel, tower_kinds, real_estate,
)

NOT_YET = (
    "G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G2.2", "G2.5", "G2.6", "G3.1", "G3.2", "G3.3", "G3.4",
    "M1", "M2", "M3", "M5", "M7", "M9", "M10", "S2", "S3", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
    "R2", "R4", "R6", "R7", "T2", "T4",
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

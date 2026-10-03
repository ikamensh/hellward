"""M9: a light build falls behind where armor walks.

    uv run python tools/armor.py                  # the light-vs-heavy duels below, seeds 0-5
    uv run python tools/armor.py --seeds 0,1      # a subset of seeds

Each duel pits two builds of exactly equal gold against each other: pure arrows against pure
ballistae, at 3:2 counts (three arrows-III cost what two ballistae-III do, at every rank). Both are
physical, both stand on the same tiles (the warden's draft, which follows the current maps), and both
are piloted by the planned player with the location's calls; only the hits differ (2 against 7). Armor
takes 2 off every hit at hells_gate, 3 at the temple; the caves, without armor, are the control.

Hells_gate fights capped at rank I (108 gold): ranks would let the arrows escape armor 2, and the
early economy cannot pay them anyway. The temple fights full builds to rank III (300 gold with its one
gate): armor 3 holds even ranked arrows (4 damage to 1), while ballistae-III shrug it (14 to 11). The
caves fight the same capped 108 gold as hells_gate: the light build holds there and dies there, so it
is the armor.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.content import TOWERS  # noqa: E402
from hellward.sim.model import DOOR  # noqa: E402
from hellward.sim.players.hands import defend, reference_kit  # noqa: E402
from hellward.sim.players.planned import Plan, Planned, load  # noqa: E402
from hellward.sim.players.warden import draft_build  # noqa: E402

LIGHT, HEAVY = "arrow", "ballista"
TILES = 20   # warden towers drafted for the shared tile pool


def tiles(location: str) -> list[tuple[int, int]]:
    """The duel's shared tiles: the warden's draft on the current map, both builds stand on its first."""
    steps = draft_build(LOCATIONS[location], frozenset({"unlock_ballista"}), towers=TILES)
    return [s.tile for s in steps if s.what == "build"]


def plan_cost(steps: list[tuple]) -> int:
    """The gold a build's steps cost: each rank step pays the rank it climbs to."""
    kinds: dict[tuple[int, int], str] = {}
    ranks: dict[tuple[int, int], int] = {}
    total = 0
    for step in steps:
        if step[0] == "build":
            kinds[step[2]] = step[1]
            total += TOWERS[step[1]].levels[0].cost
        elif step[0] == "rank":
            ranks[step[1]] = ranks.get(step[1], 0) + 1
            total += TOWERS[kinds[step[1]]].levels[ranks[step[1]]].cost
        elif step[0] == "gate":
            total += DOOR.cost
    return total


def capped(location: str, count: int) -> tuple[Plan, Plan]:
    """Two rank-I builds of exactly equal gold: ``count`` arrows against two thirds as many ballistae."""
    assert count % 3 == 0, count
    base = load(location)
    ground = tiles(location)
    assert len(ground) >= count, (location, len(ground), count)
    light = Plan(skills=[], steps=[("build", LIGHT, t) for t in ground[:count]], calls=list(base.calls))
    heavy = Plan(skills=["unlock_ballista"],
                 steps=[("build", HEAVY, t) for t in ground[:count * 2 // 3]], calls=list(base.calls))
    assert plan_cost(light.steps) == plan_cost(heavy.steps)
    return light, heavy


def full(location: str, count: int) -> tuple[Plan, Plan]:
    """Two builds to rank III of exactly equal gold, with the location's gates, skills and calls."""
    assert count % 3 == 0, count
    base = load(location)
    ground = tiles(location)
    assert len(ground) >= count, (location, len(ground), count)
    out = []
    for kind, n in ((LIGHT, count), (HEAVY, count * 2 // 3)):
        use = ground[:n]
        steps = [s for s in base.steps if s[0] == "gate"]
        steps += [("build", kind, t) for t in use]
        steps += [("rank", t) for t in use] + [("rank", t) for t in use]
        out.append(Plan(skills=list(base.skills), steps=steps, calls=list(base.calls), rebuild=base.rebuild,
                        smite_worth=base.smite_worth, meteor_worth=base.meteor_worth, orb_worth=base.orb_worth,
                        reserve=base.reserve))
    assert plan_cost(out[0].steps) == plan_cost(out[1].steps)
    return out[0], out[1]


def duel(location: str, make, count: int, seeds: list[int]) -> tuple[list[str], list[str], int]:
    """A location's duel: both builds' outcomes over ``seeds``, and the gold they cost."""
    plans = make(location, count)
    cost = plan_cost(plans[0].steps)
    outs = []
    for plan in plans:
        row = []
        for seed in seeds:
            learned = plan.learn(99, ORDER.index(location))
            world, record = defend(reference_kit(LOCATIONS[location], learned, seed), Planned(plan=plan),
                                   planner=planner.smart)
            row.append(f"{world.outcome[0]}{world.lives}")
        outs.append(row)
    return outs[0], outs[1], cost


DUELS = (("hells_gate", capped, 9), ("temple", full, 9), ("caves", capped, 9))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default=",".join(str(s) for s in range(6)))
    args = parser.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]
    for location, make, count in DUELS:
        light, heavy, cost = duel(location, make, count, seeds)
        print(f"{location:11s} {cost} gold  light {' '.join(light)}  heavy {' '.join(heavy)}")


if __name__ == "__main__":
    main()

"""How hard the defence is, and how much the leaders' choices matter.

    uv run python tools/balance.py                  # every leader policy against eight ordinary defenders
    uv run python tools/balance.py --policies none,smart --defenders 4 --location hells_gate

Each defender is the ordinary player with a different element rotation and tower count. For every leader
policy it prints the victories, the lives the defenders lost (mean and range) and the curses cast. The
leaders are worth something when ``smart`` costs the defenders clearly more lives than ``random``.

It runs the compiled simulation (:mod:`hellward.sim.fastsim`, built on first use), which plays as the source does;
``HELLWARD_INTERPRETED=1`` runs the source.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes, not as a library
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS  # noqa: E402
from hellward.sim.content import START_LIVES  # noqa: E402
from hellward.sim.model import SIM_DT, World  # noqa: E402
from hellward.sim.players.hands import Hands  # noqa: E402
from hellward.sim.players.ordinary import Ordinary  # noqa: E402

POLICIES = {"none": lambda: None, "random": lambda: planner.RandomLeaders(7), "nearest": lambda: planner.nearest,
            "greedy": lambda: planner.greedy, "smart": lambda: planner.smart}


def defenders(count: int) -> list[Ordinary]:
    return [Ordinary(shift=i % 5, towers=(13, 15)[i // 5 % 2]) for i in range(count)]


def match(policy: str, index: int, count: int, location: str) -> dict:
    defender = defenders(count)[index]
    world = World(LOCATIONS[location], seed=index, planner=POLICIES[policy]())
    world.lives = 10_000   # uncapped: count every life lost instead of stopping at a defeat
    hands = Hands(world, react=0.6)
    stats: Counter = Counter()
    leaks: Counter = Counter()
    while world.outcome is None and world.time < 1800:
        defender.act(hands)
        world.step(SIM_DT)
        hands.observe(world.events)
        for e in world.events:
            if e[0] in ("cursed", "fizzle", "cleansed", "door_broken"):
                stats[e[0]] += 1
            elif e[0] == "leak":
                leaks[world.wave] += e[3]
        world.events.clear()
    lost = 10_000 - world.lives
    return {"policy": policy, "outcome": "victory" if lost < START_LIVES else "defeat", "lost": lost, "wave": world.wave,
            "stats": stats, "leaks": leaks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--policies", default=",".join(POLICIES))
    parser.add_argument("--defenders", type=int, default=8)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--location", default="cathedral")
    args = parser.parse_args()
    policies = args.policies.split(",")
    jobs = [(p, i, args.defenders, args.location) for p in policies for i in range(args.defenders)]
    with ProcessPoolExecutor(args.jobs) as pool:
        results = list(pool.map(match, *zip(*jobs)))
    for policy in policies:
        rows = [r for r in results if r["policy"] == policy]
        lost = [r["lost"] for r in rows]
        wins = sum(r["outcome"] == "victory" for r in rows)
        stats: Counter = sum((r["stats"] for r in rows), Counter())
        leaks: Counter = sum((r["leaks"] for r in rows), Counter())
        n = len(rows)
        print(f"{policy:8s} wins {wins}/{n}  lives lost mean {statistics.mean(lost):5.1f} range {min(lost)}-{max(lost)}  "
              f"curses {stats['cursed'] / n:4.1f} cleansed {stats['cleansed'] / n:4.1f} doors broken {stats['door_broken'] / n:3.1f}  "
              f"lives lost by wave {' '.join(f'{w + 1}:{leaks[w] / n:.1f}' for w in sorted(leaks))}")


if __name__ == "__main__":
    main()

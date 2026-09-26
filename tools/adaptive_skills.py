"""Choose the adaptive player's skills per location by playing them, as a person who has replayed it would.

    uv run python tools/adaptive_skills.py                       # every location on Normal, then write the choice
    uv run python tools/adaptive_skills.py --locations caves --seeds 0-7 --dry

For every location (and difficulty) the adaptive player's themed orders of the skill tree
(:data:`hellward.sim.players.adaptive.ORDERS`) are cut to the sigils the campaign has earned by then, and each
distinct set is played on training seeds with fresh worlds, at a life factor where the location is hard for the
player (found first by bisection with its default order). The order whose set keeps the most lives is written to
``hellward/sim/players/plans/adaptive.json``, which the player reads. Only training seeds (0-99) are used:
evaluation seeds stay unseen.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import DIFFICULTIES, LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players.adaptive import ORDERS, PLANS, Adaptive, learn  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402

TRAINING = range(0, 100)


def score(job: tuple[str, str, str, int, int, float]) -> float:
    """Lives kept at a victory; a fall scores minus the waves it never saw."""
    location, difficulty, order, sigils, seed, hp = job
    player = Adaptive(order=order)
    world, _ = defend(LOCATIONS[location], DIFFICULTIES[difficulty], player, seed=seed, sigils=sigils,
                      planner=planner.smart, hp=hp)
    if world.outcome == "victory":
        return float(world.lives)
    return float(world.wave - len(LOCATIONS[location].waves))


def edge(pool: ProcessPoolExecutor, location: str, difficulty: str, sigils: int, seeds: list[int]) -> float:
    """The life factor at which the default order starts to lose, bisected on the median of a few seeds."""
    low, high = 0.5, 16.0
    while high / low > 1.08:
        mid = (low * high) ** 0.5
        scores = list(pool.map(score, [(location, difficulty, "", sigils, s, mid) for s in seeds]))
        if statistics.median(scores) > 0:
            low = mid
        else:
            high = mid
    return low


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--locations", default=",".join(ORDER[1:]))
    parser.add_argument("--difficulty", default="normal")
    parser.add_argument("--seeds", default="0-7", help="training seeds, a-b")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--dry", action="store_true", help="print the choice without writing it")
    args = parser.parse_args()
    a, b = (int(x) for x in args.seeds.split("-"))
    seeds = list(range(a, b + 1))
    if not set(seeds) <= set(TRAINING):
        raise SystemExit("screen on training seeds (0-99) only")
    plans = json.loads(PLANS.read_text()) if PLANS.exists() else {}
    chosen = plans.setdefault(args.difficulty, {})
    with ProcessPoolExecutor(args.workers) as pool:
        for location in args.locations.split(","):
            sigils = 36 if args.difficulty == "hell" else 2 * ORDER.index(location)
            hp = edge(pool, location, args.difficulty, sigils, seeds[:3])
            sets: dict[frozenset[str], str] = {}
            for name in ORDERS:
                sets.setdefault(learn(LOCATIONS[location], sigils, ORDERS[name]), name)
            jobs = [(location, args.difficulty, name, sigils, s, hp) for name in sets.values() for s in seeds]
            results = list(pool.map(score, jobs))
            ranked = []
            for i, name in enumerate(sets.values()):
                got = results[i * len(seeds):(i + 1) * len(seeds)]
                ranked.append((statistics.mean(got), sum(1 for g in got if g > 0), name))
            ranked.sort(reverse=True)
            print(f"{location} ({args.difficulty}, {sigils} sigils, life x{hp:.2f}):")
            for mean, wins, name in ranked:
                skills = sorted(learn(LOCATIONS[location], sigils, ORDERS[name]))
                print(f"   {name:9s} mean {mean:5.1f}  wins {wins}/{len(seeds)}  {', '.join(skills)}")
            chosen[location] = ranked[0][2]
    if args.dry:
        return
    PLANS.parent.mkdir(exist_ok=True)
    PLANS.write_text(json.dumps(plans, indent=2, sort_keys=True) + "\n")
    print(f"wrote {PLANS}")


if __name__ == "__main__":
    main()

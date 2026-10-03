"""M9, absolute armor: an Arrow-only build against one with Ballistas in it, for the same gold.

    uv run python tools/armor_ab.py                       # the Catacombs and the Jungle, seeds 1000-1007
    uv run python tools/armor_ab.py --locations catacombs,docks --seeds 1000-1003

Both builds are the ordinary defender's (towers on the tiles that watch the most path, gates in the arches, no
skills, no rank above the first): the light one raises twelve Arrows, the heavy one six Arrows and four Ballistas,
the same 144 gold at the opening's prices. For each location it bisects each build's margin on every seed: the
largest factor on every monster's life (the location's own life factor, as tools/margin.py scales it) it still wins
at, to 2%. M9 holds at a location where the light build's median margin is below 1, so it loses at the real life,
and the heavy build's is at least 1. It runs the compiled simulation.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes
    fastsim.activate()

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS  # noqa: E402
from hellward.sim.players.hands import defend, reference_kit  # noqa: E402
from hellward.sim.players.ordinary import Ordinary  # noqa: E402
from tools.margin import LOW, HIGH, STEP, seed_list  # noqa: E402
from tools.tuning import life_margin  # noqa: E402

BUILDS = {"light": (("arrow",), 12), "heavy": (("arrow", "ballista", "arrow", "ballista", "arrow"), 10)}


def wins(build: str, key: str, seed: int, life: float) -> bool:
    rotation, towers = BUILDS[build]
    player = Ordinary(rotation=rotation, towers=towers)
    world, _ = defend(reference_kit(LOCATIONS[key], player.draft(LOCATIONS[key], 0), seed),
                      player, planner=planner.smart, hardness=life)
    return world.outcome == "victory"


def margin(build: str, key: str, seed: int) -> float:
    return life_margin(lambda life: wins(build, key, seed, life), LOW, HIGH, step=STEP, check_low=True,
                       check_high=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--locations", default="catacombs,jungle")
    parser.add_argument("--seeds", default="1000-1007")
    parser.add_argument("--jobs", type=int, default=5)
    args = parser.parse_args()
    keys, seeds = args.locations.split(","), seed_list(args.seeds)
    jobs = [(build, key, seed) for key in keys for build in BUILDS for seed in seeds]
    with ProcessPoolExecutor(args.jobs) as pool:
        found = dict(zip(jobs, pool.map(margin, *zip(*jobs))))
    for key in keys:
        light, heavy = (statistics.median(found[(build, key, s)] for s in seeds) for build in BUILDS)
        held = light < 1.0 <= heavy
        print(f"{key:13s} light (12 Arrows) M {light:5.2f}  heavy (6 Arrows, 4 Ballistas) M {heavy:5.2f}  "
              f"M9 {'met' if held else 'missed'}", flush=True)


if __name__ == "__main__":
    main()

"""Whether different runs end in different builds, pushed by their relics (M5).

    uv run python tools/adapt.py                # the planned player on the jungle, ten tuning seeds
    uv run python tools/adapt.py --seeds 1000,1001 --no-tree   # the same defence with no relic read

Each seed takes the jungle's eight camp offers the way a person would — the offered relic sharing most
verbs with the run's takes, pacts declined — then the planned player drafts for the jungle with the tree
reading its takes and defends against smart leaders. It prints each seed's takes, the tower kinds standing
at the end and the outcome, then how many distinct end-builds the seeds grew and how many held. M5 wants
six distinct builds over ten seeds; the tree earns them only if the defences still hold.

It runs the compiled simulation (:mod:`hellward.fastsim`, built on first use);
``HELLWARD_INTERPRETED=1`` runs the source.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes, not as a library
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players.hands import defend, reference_kit  # noqa: E402
from hellward.sim.players.planned import Planned  # noqa: E402
from hellward.sim.relics import DOWNSIDES, RELICS, draw  # noqa: E402

LOCATION = "jungle"   # every tower on offer, and the planned player holds it at HEAD
CAMPS = ORDER.index(LOCATION)   # camps before it: the run takes this many relics
SEEDS = tuple(range(1000, 1010))


def takes(seed: int) -> tuple[str, ...]:
    """Eleven camp takes the way a person takes: most verbs shared with the run's takes, pacts declined."""
    held: tuple[str, ...] = ()
    for index in range(CAMPS):
        offered = [key for key in draw(seed, index, held) if key not in DOWNSIDES]
        if not offered:
            continue
        verbs = Counter(RELICS[key].verb for key in held)
        held += (max(offered, key=lambda k: (verbs[RELICS[k].verb], -offered.index(k))),)
    return held


def end_build(seed: int, relics: tuple[str, ...], *, tree: bool = True) -> tuple[str, frozenset[str]]:
    """The temple defended with these takes: the outcome and the tower kinds standing at the end."""
    location = LOCATIONS[LOCATION]
    player = Planned()
    learned = player.draft(location, 3 * ORDER.index(LOCATION), relics if tree else ())
    world, _ = defend(reference_kit(location, learned, seed, relics=relics), player, planner=planner.smart)
    return world.outcome or "undecided", frozenset(t.kind.key for t in world.towers.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="M5: distinct end-builds over ten seeds.")
    parser.add_argument("--seeds", default=",".join(str(s) for s in SEEDS))
    parser.add_argument("--no-tree", action="store_true", help="draft with no relic read")
    args = parser.parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    builds: list[frozenset[str]] = []
    wins = 0
    for seed in seeds:
        held = takes(seed)
        outcome, kinds = end_build(seed, held, tree=not args.no_tree)
        builds.append(kinds)
        wins += outcome == "victory"
        print(f"seed {seed}: {outcome} {{{', '.join(sorted(kinds))}}}  takes {', '.join(held)}", flush=True)
    print(f"distinct end-builds: {len(set(builds))} over {len(seeds)} seeds; victories: {wins}/{len(seeds)}")


if __name__ == "__main__":
    main()

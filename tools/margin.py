"""How much more monster life a player can still beat, location by location: what each location's life factor
(``Location.life``) and each difficulty's are tuned with (docs/campaign.md, "Tuning by simulation").

    python3 ~/saga/tools/slot.py -- caffeinate -i uv run python tools/margin.py apprentice
    uv run python tools/margin.py warden --difficulty hell --locations caves,hells_gate --seeds 1000-1003
    uv run python tools/margin.py warden --difficulty hell --leaders random   # how much the leaders' choices cost

For every location it bisects, on each seed, the largest factor on every monster's life (``defend(hp=...)``; the
spells do not grow with it, as they do not with a difficulty) at which the player still wins, to 2%, and prints the
median and the range. A defence holds whole until the monsters outgrow it and then collapses within a few percent,
so the margin, not the lives kept, is what tells an easy location from a hard one. The player's sigils are the campaign's: two per earlier location on Normal, the whole tree on Hell, unless
``--sigils`` says otherwise. ``--leaders random`` makes the leaders curse at random: the margin against them over
the margin against the smart ones is how much the leaders' choices are worth. It runs the compiled simulation.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes
    fastsim.activate()

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import DIFFICULTIES, LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402
from hellward.sim.skills import TREE_COST  # noqa: E402

LOW, HIGH, STEP = 0.2, 12.0, 1.02


def wins(player: str, key: str, difficulty: str, seed: int, sigils: int, leaders: str, hp: float) -> bool:
    policy = planner.smart if leaders == "smart" else planner.RandomLeaders(seed)
    world, _ = defend(LOCATIONS[key], DIFFICULTIES[difficulty], PLAYERS[player](seed), seed=seed, sigils=sigils,
                      planner=policy, hp=hp)
    return world.outcome == "victory"


def margin(player: str, key: str, difficulty: str, seed: int, sigils: int, leaders: str) -> float:
    """The largest life factor won, bisected in ratio to STEP; 0 when even LOW is lost."""
    if not wins(player, key, difficulty, seed, sigils, leaders, LOW):
        return 0.0
    low, high = LOW, HIGH
    if wins(player, key, difficulty, seed, sigils, leaders, high):
        return high
    while high / low > STEP:
        mid = (low * high) ** 0.5
        if wins(player, key, difficulty, seed, sigils, leaders, mid):
            low = mid
        else:
            high = mid
    return low


def seed_list(text: str) -> list[int]:
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("player", choices=sorted(PLAYERS))
    parser.add_argument("--difficulty", default="normal", choices=sorted(DIFFICULTIES))
    parser.add_argument("--locations", default=",".join(ORDER))
    parser.add_argument("--seeds", default="1000-1007")
    parser.add_argument("--sigils", type=int, default=None)
    parser.add_argument("--leaders", default="smart", choices=("smart", "random"))
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    keys = args.locations.split(",")
    seeds = seed_list(args.seeds)

    def budget(key: str) -> int:
        if args.sigils is not None:
            return args.sigils
        return TREE_COST if args.difficulty == "hell" else 2 * ORDER.index(key)

    jobs = [(args.player, key, args.difficulty, seed, budget(key), args.leaders) for key in keys for seed in seeds]
    with ProcessPoolExecutor(args.jobs) as pool:
        found = list(pool.map(margin, *zip(*jobs)))
    for i, key in enumerate(keys):
        values = found[i * len(seeds):(i + 1) * len(seeds)]
        print(f"{args.player:10s} {args.difficulty:6s} {args.leaders:6s} {key:11s} life {LOCATIONS[key].life:4.2f}  M median {statistics.median(values):5.2f}"
              f"  range {min(values):5.2f}-{max(values):5.2f}", flush=True)


if __name__ == "__main__":
    main()

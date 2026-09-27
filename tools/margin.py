"""How much more monster life a player can still beat, location by location: what each location's life factor
(``Location.life``) is tuned with (docs/campaign.md, "Tuning by simulation").

    python3 ~/saga/tools/slot.py -- caffeinate -i uv run python tools/margin.py apprentice
    uv run python tools/margin.py veteran --locations tristram --seeds 1000-1001 --jobs 2
    uv run python tools/margin.py veteran --leaders random   # how much the leaders' choices cost
    uv run python tools/margin.py --replay replays/20260101T120000Z-tristram.json   # a person's build, at its
        # location and seed only: how much harder it could still have been won

For every location it bisects, on each seed, the largest factor on every monster's life (by replacing
``Location.life`` with ``Location.life * k``; the spells grow with it) at which the player still wins, to 2%,
and prints the median and the range. A defence holds whole until the monsters outgrow it and then collapses
within a few percent, so the margin, not the lives kept, is what tells an easy location from a hard one.
The player's sigils are the campaign's: three per earlier location, unless ``--sigils`` says otherwise.
``--leaders random`` makes the leaders curse at random: the margin against them over the margin against the
smart ones is how much the leaders' choices are worth. ``--curse-scale`` multiplies every curse radius
(0 = only the marked tile). It runs the compiled simulation.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes
    fastsim.activate()

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.ghost import Ghost  # noqa: E402
from hellward.sim.players.hands import Player, defend  # noqa: E402
from hellward.sim.skills import cost  # noqa: E402

LOW, HIGH, STEP = 0.2, 12.0, 1.02


def contender(who: str, seed: int) -> Player:
    """A player by its name, or the ghost of a logged defence as ``replay:<path>``."""
    return Ghost(who.removeprefix("replay:")) if who.startswith("replay:") else PLAYERS[who](seed)


def wins(who: str, key: str, seed: int, sigils: int, leaders: str, life_mult: float, curse_scale: float = 1.0) -> bool:
    policy = planner.smart if leaders == "smart" else planner.RandomLeaders(seed)
    loc = dataclasses.replace(LOCATIONS[key], life=LOCATIONS[key].life * life_mult)
    world, _ = defend(loc, contender(who, seed), seed=seed, sigils=sigils, planner=policy, hp=1.0, curse_scale=curse_scale)
    return world.outcome == "victory"


def margin(who: str, key: str, seed: int, sigils: int, leaders: str, curse_scale: float = 1.0) -> float:
    """The largest life factor won, bisected in ratio to STEP; 0 when even LOW is lost."""
    if not wins(who, key, seed, sigils, leaders, LOW, curse_scale):
        return 0.0
    low, high = LOW, HIGH
    if wins(who, key, seed, sigils, leaders, high, curse_scale):
        return high
    while high / low > STEP:
        mid = (low * high) ** 0.5
        if wins(who, key, seed, sigils, leaders, mid, curse_scale):
            low = mid
        else:
            high = mid
    return low


def seed_list(text: str) -> list[int]:
    first, _, last = text.partition("-")
    return list(range(int(first), int(last or first) + 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("player", nargs="?", choices=sorted(PLAYERS))
    parser.add_argument("--replay", default=None, help="a battle scene's log: bisect its ghost's margin instead, "
                        "at the log's location and seed only")
    parser.add_argument("--locations", default=",".join(ORDER))
    parser.add_argument("--seeds", default="1000-1007")
    parser.add_argument("--sigils", type=int, default=None)
    parser.add_argument("--leaders", default="smart", choices=("smart", "random"))
    parser.add_argument("--curse-scale", type=float, default=1.0)
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    if args.replay is not None:
        if args.player is not None:
            parser.error("--replay takes the place of a player name, not both")
        ghost_main(args)
        return
    if args.player is None:
        parser.error("a player name or --replay is required")
    keys = args.locations.split(",")
    seeds = seed_list(args.seeds)

    def budget(key: str) -> int:
        if args.sigils is not None:
            return args.sigils
        return 3 * ORDER.index(key)

    jobs = [(args.player, key, seed, budget(key), args.leaders, args.curse_scale) for key in keys for seed in seeds]
    with ProcessPoolExecutor(args.jobs) as pool:
        found = list(pool.map(margin, *zip(*jobs)))
    for i, key in enumerate(keys):
        values = found[i * len(seeds):(i + 1) * len(seeds)]
        print(f"{args.player:10s} {args.leaders:6s} {key:11s} life {LOCATIONS[key].life:4.2f}  M median {statistics.median(values):5.2f}"
              f"  range {min(values):5.2f}-{max(values):5.2f}", flush=True)


def ghost_main(args: argparse.Namespace) -> None:
    """Bisect the margin of the ghost built from ``--replay``'s log: its location only, its seed only."""
    log = json.loads(Path(args.replay).read_text())
    key, seed = log["location"], log["seed"]
    sigils = cost(frozenset(log["skills"]))
    if args.sigils is not None:
        sigils = args.sigils
    found = margin(f"replay:{args.replay}", key, seed, sigils, args.leaders, args.curse_scale)
    print(f"{'ghost':10s} {args.leaders:6s} {key:11s} life {LOCATIONS[key].life:4.2f}  M {found:5.2f}", flush=True)


if __name__ == "__main__":
    main()

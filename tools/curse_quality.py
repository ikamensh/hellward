"""How close the leaders' curses are to the best curse they could have cast.

    uv run python tools/curse_quality.py                 # 60 real decision moments, every policy
    uv run python tools/curse_quality.py --moments 20 --horizon 20

Moments are taken from whole defences: the scripted defender plays against smart leaders, and every few
decisions the world is copied at the instant a leader asks what to curse. For each moment every curse the
leader could cast on every tower in its reach is played out *exactly*: the game's own step (0.05 s) for
``--horizon`` seconds, against casting nothing. That is the truth the policies are scored against:

* **share of best**: the gain of the policy's pick over the gain of the best pick (1.0 = optimal);
* **normalized**: where the pick lands between the worst and the best option (0 worst, 1 best);
* **top-1**: how often the pick *is* the best option.

``random`` is scored by its expectation over all options. ``smart`` runs with the timing look-ahead off,
so every moment compares a choice of target; the timing check below the table then asks whether the
moments smart would have waited through were worth waiting for.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import planner  # noqa: E402
from hellward.sim.autoplay import Defender  # noqa: E402
from hellward.sim.model import SIM_DT, World  # noqa: E402

POLICIES = ("smart", "greedy", "nearest", "random")


def moments(count: int, every: int) -> list[tuple[World, int]]:
    """Worlds copied at the instant a leader asks, from a few whole defences."""
    found: list[tuple[World, int]] = []
    seen = 0
    game = 0
    while len(found) < count:
        def recorder(world: World, leader_id: int) -> planner.Inline:
            nonlocal seen
            seen += 1
            decision = planner.decide(world, leader_id)
            if seen % every == 0 and len(found) < count and len(planner.candidates(world, world.monster(leader_id))) >= 2:
                found.append((world.clone(), leader_id))
            return planner.Inline(decision)

        world = World(seed=game, planner=recorder)
        world.lives = 10_000
        defender = Defender(shift=game % 5, towers=(13, 15)[game // 5 % 2])
        while world.outcome is None and world.time < 1800 and len(found) < count:
            defender.act(world, SIM_DT)
            world.step(SIM_DT)
            world.events.clear()
        game += 1
    return found


def judge(world: World, leader_id: int, horizon: float) -> dict:
    leader = world.monster(leader_id)
    options = planner.candidates(world, leader)
    base = planner.rollout(world, leader_id, None, horizon, SIM_DT)
    truth = {(o.curse, o.tower): planner.rollout(world, leader_id, o, horizon, SIM_DT) - base for o in options}
    started = time.perf_counter()
    smart = planner.decide(world, leader_id, timing=False)
    smart_ms = (time.perf_counter() - started) * 1000
    timed = planner.decide(world, leader_id)
    picks = {
        "smart": smart.cast or (smart.options[0] if smart.options else None),
        "greedy": planner.greedy(world, leader_id).result().cast,
        "nearest": planner.nearest(world, leader_id).result().cast,
    }
    values = {name: truth[(o.curse, o.tower)] if o is not None else 0.0 for name, o in picks.items()}
    values["random"] = statistics.mean(truth.values())
    wait = None
    if timed.cast is None and timed.later is not None and smart.options:
        now = smart.options[0]
        later = timed.later
        wait = (planner.rollout(world, leader_id, planner.Option(now.curse, now.tower), horizon + 4, SIM_DT),
                planner.rollout(world, leader_id, later, horizon + 4, SIM_DT))
    return {"best": max(truth.values()), "worst": min(truth.values()), "values": values, "options": len(truth),
            "smart_ms": smart_ms, "rollouts": smart.rollouts, "wait": wait}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--moments", type=int, default=60)
    parser.add_argument("--every", type=int, default=3, help="keep every n-th decision")
    parser.add_argument("--horizon", type=float, default=16.0)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    cases = moments(args.moments, args.every)
    with ProcessPoolExecutor(args.jobs) as pool:
        results = list(pool.map(judge, [w for w, _ in cases], [i for _, i in cases], [args.horizon] * len(cases)))
    useful = [r for r in results if r["best"] > 1.0]
    print(f"{len(results)} moments, {len(useful)} where some curse helps the pack; "
          f"{statistics.mean(r['options'] for r in results):.1f} options each on average\n")
    print(f"{'policy':8s} {'share of best':>14s} {'normalized':>11s} {'top-1':>7s}")
    for name in POLICIES:
        share = statistics.mean(max(0.0, r["values"][name]) / r["best"] for r in useful)
        normal = statistics.mean((r["values"][name] - r["worst"]) / (r["best"] - r["worst"]) for r in useful if r["best"] > r["worst"])
        top = statistics.mean(r["values"][name] >= r["best"] - 1e-6 for r in useful)
        print(f"{name:8s} {share:14.3f} {normal:11.3f} {top:7.2f}")
    print(f"\nsmart: {statistics.mean(r['rollouts'] for r in results):.1f} rollouts and "
          f"{statistics.mean(r['smart_ms'] for r in results):.0f} ms per decision (max {max(r['smart_ms'] for r in results):.0f} ms)")
    waits = [r["wait"] for r in results if r["wait"] is not None]
    if waits:
        right = sum(later >= now for now, later in waits)
        print(f"timing: smart would have waited at {len(waits)} moments; waiting was right at {right} of them "
              f"(mean gain of waiting {statistics.mean(later - now for now, later in waits):+.0f} life)")


if __name__ == "__main__":
    main()

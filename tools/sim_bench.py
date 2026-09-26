"""Processor time of whole defences, from source and compiled: what the balance tools pay per defence.

    uv run python tools/sim_bench.py                          # every location, source and compiled, the speed-up
    uv run python tools/sim_bench.py --locations caves --repeat 3
    uv run python tools/sim_bench.py --decisions               # how long the leaders take to choose, per location

Every location is defended once by the ordinary player (``hands.defend``) against smart leaders, on seed 1.
Each run is a fresh process: source (``HELLWARD_INTERPRETED=1``) and compiled (:mod:`hellward.sim.fastsim`)
alternate, so that both meet the same load on a shared machine, and each is timed by the processor time of the
defence alone (its events are kept, and written out after the clock stops). The fastest of ``--repeat`` runs
counts.

``--decisions`` plays the same defence inline on the build this tool runs and times every ``planner.decide``
call instead: per location it prints how many decisions there were and their median, p95 and max.

A run also prints a digest of every event with its time and of the world at the end (:func:`digest`); the source
and the compiled digests must agree, so a speed change that is only a speed change prints the same digests.
``tests/test_fastsim.py`` holds the compiled simulation to them.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program, not as a library (tests/test_fastsim.py)
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.model import World  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402

SEED = 1
#: What a world carries that is not its state: fixed for the defence (by name), or deliberately not cloned.
CONFIG = {"location", "level", "waves", "hardness", "perks", "tower_levels"}
UNCLONED = {"planner", "record", "events"}


def canon(value: Any) -> str:
    """A value written out exactly: every number by its value to the bit, every object by all its attributes.

    An integer is written as the float it equals: a compiled class's ``float`` field holds ``6.0`` where the
    source's table wrote ``6``, the same number."""
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    if value is None or isinstance(value, (bool, str)):
        return repr(value)
    if isinstance(value, (int, float)):
        return float(value).hex() if float(value) == value else repr(value)
    if isinstance(value, (tuple, list)):
        return "(" + ",".join(canon(v) for v in value) + ")"
    if isinstance(value, dict):
        return "{" + ",".join(f"{canon(k)}:{canon(v)}" for k, v in value.items()) + "}"
    if hasattr(value, "getstate"):   # the world's random stream
        return canon(value.getstate())
    if hasattr(value, "key") and hasattr(value, "name"):   # a monster's or a tower's kind: a row of a table
        return f"<{value.key}>"
    return type(value).__name__ + "{" + ",".join(f"{name}={canon(getattr(value, name))}" for name in attributes(value)) + "}"


def attributes(value: Any) -> list[str]:
    """Every attribute an object carries, sorted: a compiled class lists them in ``__mypyc_attrs__``, where the
    source's keeps them in ``__slots__`` or its ``__dict__``."""
    if dataclasses.is_dataclass(value):
        return sorted(f.name for f in dataclasses.fields(value))
    names = getattr(type(value), "__mypyc_attrs__", None) or getattr(type(value), "__slots__", None) or vars(value)
    return sorted(name for name in names if not name.startswith("__"))


def state(world: World) -> str:
    """The world written out, all but its configuration (named) and what a clone leaves out."""
    parts = [f"{world.location.key}:{world.hardness}:{canon(world.perks)}"]
    for name in attributes(world):
        if name not in CONFIG | UNCLONED:
            parts.append(f"{name}={canon(getattr(world, name))}")
    return "\n".join(parts)


def play(key: str, seed: int = SEED) -> tuple[World, list[tuple[float, list[tuple]]]]:
    """One defence of a location by the ordinary player against smart leaders, and every step's events with its
    time. Events are kept as they are: nothing the world emits is changed after (a bolt moves as a new bolt)."""
    events: list[tuple[float, list[tuple]]] = []

    def watch(world: World) -> None:
        if world.events:
            events.append((world.time, list(world.events)))

    world, _ = defend(LOCATIONS[key], PLAYERS["ordinary"](seed), seed=seed, sigils=0, planner=planner.smart,
                      watch=watch)
    return world, events


def digest(world: World, events: list[tuple[float, list[tuple]]]) -> str:
    """Every event with its time, and the world at the end."""
    written = hashlib.sha256()
    for at, happened in events:
        for event in happened:
            written.update(f"{at.hex()} {canon(event)}\n".encode())
    written.update(state(world).encode())
    return written.hexdigest()[:16]


def defence(key: str, seed: int = SEED) -> tuple[World, str]:
    """One defence of a location, and its digest."""
    world, events = play(key, seed)
    return world, digest(world, events)


def timed(key: str) -> dict[str, Any]:
    started = time.process_time()
    world, events = play(key)
    cpu = time.process_time() - started
    return {"cpu": cpu, "digest": digest(world, events), "outcome": world.outcome, "lives": world.lives,
            "compiled": fastsim.compiled()}


def run(key: str, env: dict[str, str]) -> dict[str, Any]:
    """One timed defence in a fresh process of this script."""
    done = subprocess.run([sys.executable, __file__, "--one", key], env=env, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"the run of {key} failed:\n{done.stderr}")
    return json.loads(done.stdout)


def decision_times(key: str, seed: int = SEED) -> list[float]:
    """Seconds every ``planner.decide`` call took in one defence of a location by the adaptive player (strong enough
    to meet every wave's leaders) with the campaign's sigils, decided inline on the build this tool runs."""
    took: list[float] = []

    def timing(world: World, leader_id: int):  # what defend calls as its planner, timed
        started = time.perf_counter()
        try:
            return planner.smart(world, leader_id)
        finally:
            took.append(time.perf_counter() - started)

    defend(LOCATIONS[key], PLAYERS["adaptive"](seed), seed=seed, sigils=3 * ORDER.index(key), planner=timing)
    return took


def describe(took: list[float]) -> tuple[int, float, float, float]:
    """A decision-time sample as count, median, p95 and max, in milliseconds."""
    ms = sorted(t * 1000 for t in took)
    median = statistics.median(ms)
    p95 = ms[min(len(ms) - 1, math.ceil(0.95 * len(ms)) - 1)]
    return len(ms), median, p95, ms[-1]


def decisions(keys: list[str]) -> None:
    """One inline defence per location, timing every ``planner.decide`` call."""
    print(f"decisions inline ({'compiled' if fastsim.compiled() else 'source'} simulation)")
    print(f"{'location':12s} {'decides':>8s} {'median ms':>10s} {'p95 ms':>10s} {'max ms':>10s}")
    for key in keys:
        took = decision_times(key)
        if not took:
            print(f"{key:12s} {0:8d} {'—':>10s} {'—':>10s} {'—':>10s}", flush=True)
            continue
        count, median, p95, maximum = describe(took)
        print(f"{key:12s} {count:8d} {median:10.1f} {p95:10.1f} {maximum:10.1f}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--locations", default=",".join(LOCATIONS))
    parser.add_argument("--repeat", type=int, default=1, help="runs of each kind per location; the fastest counts")
    parser.add_argument("--decisions", action="store_true",
                        help="time every planner.decide call per location instead of the source/compiled bench")
    parser.add_argument("--one", help=argparse.SUPPRESS)   # a single timed run, which the bench starts
    args = parser.parse_args()
    if args.one:
        print(json.dumps(timed(args.one)))
        return
    if args.decisions:
        decisions(args.locations.split(","))
        return
    clean = {k: v for k, v in os.environ.items() if k not in (fastsim.ENV, fastsim.OPT_OUT)}
    kinds = {"source": {**clean, fastsim.OPT_OUT: "1"}, "compiled": {**clean, fastsim.ENV: str(fastsim.build())}}
    print(f"{'location':12s} {'outcome':8s} {'source s':>9s} {'compiled s':>11s} {'speed-up':>9s}  digest")
    totals = dict.fromkeys(kinds, 0.0)
    for key in args.locations.split(","):
        best: dict[str, dict[str, Any]] = {}
        for _ in range(args.repeat):
            for kind, env in kinds.items():
                result = run(key, env)
                if result["compiled"] != (kind == "compiled"):
                    raise RuntimeError(f"the {kind} run of {key} ran the other simulation")
                if kind not in best or result["cpu"] < best[kind]["cpu"]:
                    best[kind] = result
        source, compiled = best["source"], best["compiled"]
        for kind in kinds:
            totals[kind] += best[kind]["cpu"]
        same = "same" if source["digest"] == compiled["digest"] else f"DIFFERS: compiled {compiled['digest']}"
        print(f"{key:12s} {source['outcome']:8s} {source['cpu']:9.2f} {compiled['cpu']:11.2f} "
              f"{source['cpu'] / compiled['cpu']:8.1f}x  {source['digest']} {same}", flush=True)
    print(f"{'all':12s} {'':8s} {totals['source']:9.2f} {totals['compiled']:11.2f} "
          f"{totals['source'] / totals['compiled']:8.1f}x")


if __name__ == "__main__":
    main()

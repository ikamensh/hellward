"""The warden's builds, searched offline the way a player who replays a location many times finds them.

    uv run python tools/warden_plans.py search cathedral                         # with the campaign's sigils
    uv run python tools/warden_plans.py search hells_gate --sigils 36
    uv run python tools/warden_plans.py check cathedral                          # margins: the stored plan and the draft

A plan (``hellward/sim/players/warden.py``: the skills, and a list of steps the warden takes as the gold comes) is
played with every monster's life raised until it starts to lose lives. The search mutates it (a tower's kind or
tile, the order of the steps, a step more or fewer, the skills, when to call waves early), keeps a mutant that
loses no more lives over the training seeds, and raises the life again once the best plan loses none (or no
more than ``--slack`` a seed). The best is stored in ``hellward/sim/players/plans/warden.json`` with how it was
found. ``--leaders greedy`` (the default) screens against the cheap estimate-only leaders; ``check`` measures the
margin against the rollout leaders.

Every seed played here is a training seed (0-99): the evaluation seeds (1000 and up) are never seen.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes, not as a library
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402
from hellward.sim.players.warden import (  # noqa: E402
    PLANS, Plan, Step, Warden, draft_build, draft_skills, fingerprint, plan_key, tile_value,
)
from hellward.sim.skills import (  # noqa: E402
    SKILLS, UNLOCK, above, can_learn, cost, kept, perks, tower_levels, unlocked,
)
from tools.tuning import life_margin  # noqa: E402

LEADERS = {"smart": planner.smart, "greedy": planner.greedy}
UNCAPPED = 100_000
LIMIT = 3000.0
TRAINING = range(0, 100)
EARLY = (0.5, 0.7, 0.9, 1.01)     # when to call waves early: a share of the mana orb (1.01: never)
RAISE = 1.05                       # the life is raised by this once the best plan loses nothing
JUMP = 40                          # a tower jumps to one of this many best tiles for its kind


# -- Playing a plan -------------------------------------------------------------------------------


def lost(row: dict, key: str, sigils: int, seed: int, hp: float, leaders: str) -> int:
    """Lives a plan loses in one defence with every monster's life times ``hp``, counted past a fall."""
    if seed not in TRAINING:
        raise ValueError(f"seed {seed} is not a training seed")
    world, _ = defend(LOCATIONS[key], Warden(plan=Plan.of(row)), seed=seed, sigils=sigils,
                      planner=LEADERS[leaders], hp=hp, lives=UNCAPPED, limit=LIMIT)
    return UNCAPPED - world.lives


def won(row: dict, key: str, sigils: int, seed: int, hp: float, leaders: str) -> bool:
    if seed not in TRAINING:
        raise ValueError(f"seed {seed} is not a training seed")
    world, _ = defend(LOCATIONS[key], Warden(plan=Plan.of(row)), seed=seed, sigils=sigils,
                      planner=LEADERS[leaders], hp=hp)
    return world.outcome == "victory"


def margin(row: dict, key: str, sigils: int, seed: int, leaders: str, hi: float = 16.0) -> float:
    """The largest factor on every monster's life at which the plan still wins, bisected to 2% (0 when it loses at 1)."""
    return life_margin(lambda life: won(row, key, sigils, seed, life, leaders), 1.0, hi, check_low=True)


# -- Mutations ------------------------------------------------------------------------------------


def tidy(steps: list[Step], location: Location) -> list[Step]:
    """A playable list: one build per tile, at most two ranks after it, each gate once."""
    built: dict[tuple[int, int], int] = {}
    gates: set[int] = set()
    out = []
    for step in steps:
        if step.what == "build":
            if step.tile in built or not location.level.buildable(*step.tile):
                continue
            built[step.tile] = 0
        elif step.what == "up":
            if built.get(step.tile, 2) >= 2:
                continue
            built[step.tile] += 1
        else:
            if step.door in gates:
                continue
            gates.add(step.door)
        out.append(step)
    return out


def reskill(learned: frozenset[str], sigils: int, rng: random.Random, stage: int,
            must: frozenset[str] = frozenset()) -> frozenset[str]:
    """Unlearn a skill nothing below needs (never a ``must``), then learn at random until the sigils run out."""
    base: frozenset[str] = frozenset()
    for key in sorted(must):
        if can_learn(base, key, sigils, stage):
            base |= {key}
    learned = base | kept(learned - base, sigils - cost(base), stage)
    leaves = [k for k in learned if k not in must
              and not any(above(SKILLS[o]) is SKILLS[k] for o in learned)]
    if leaves:
        learned = learned - {rng.choice(sorted(leaves))}
    while True:
        options = [k for k in SKILLS if can_learn(learned, k, sigils, stage)]
        if not options:
            return learned
        learned = learned | {rng.choice(options)}


def mutate(plan: Plan, location: Location, sigils: int, rng: random.Random) -> Plan:
    steps = list(plan.steps)
    stage = ORDER.index(location.key)
    skills, early = kept(plan.skills, sigils, stage), plan.early
    kinds = location.arsenal.towers
    level = location.level
    tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
    for _ in range(rng.choice((1, 1, 2, 3))):
        builds = [i for i, s in enumerate(steps) if s.what == "build"]
        move = rng.choice(("kind", "nudge", "jump", "shift", "shift", "rank", "tower", "gate", "drop", "skills", "early"))
        if move in ("kind", "nudge", "jump") and builds:
            i = rng.choice(builds)
            old = steps[i]
            kind, tile = old.kind, old.tile
            if move == "kind":
                open_kinds = [k for k in kinds if k != old.kind and unlocked(k, skills)] or [old.kind]
                kind = rng.choice(open_kinds)
            elif move == "nudge":
                tile = (old.tile[0] + rng.randint(-2, 2), old.tile[1] + rng.randint(-2, 2))
            else:
                reach = plan_reach(kind, skills)
                best = sorted(tiles, key=lambda t: -tile_value(location, kind, t, reach))[:JUMP]
                tile = rng.choice(best)
            if not level.buildable(*tile) or any(j != i and s.what == "build" and s.tile == tile for j, s in enumerate(steps)):
                continue
            steps = [Step("up", tile=tile) if s.what == "up" and s.tile == old.tile else s for s in steps]
            steps[i] = Step("build", kind, tile)
        elif move == "shift" and steps:
            step = steps.pop(rng.randrange(len(steps)))
            steps.insert(rng.randrange(len(steps) + 1), step)
        elif move == "rank" and builds:
            tile = steps[rng.choice(builds)].tile
            first = next(i for i, s in enumerate(steps) if s.what == "build" and s.tile == tile)
            steps.insert(rng.randint(first + 1, len(steps)), Step("up", tile=tile))
        elif move == "tower":
            kind = rng.choice([k for k in kinds if unlocked(k, skills)] or list(kinds))
            reach = plan_reach(kind, skills)
            free = [t for t in tiles if not any(s.what == "build" and s.tile == t for s in steps)]
            tile = rng.choice(sorted(free, key=lambda t: -tile_value(location, kind, t, reach))[:JUMP])
            steps.insert(rng.randrange(len(steps) + 1), Step("build", kind, tile))
        elif move == "gate":
            unset = [i for i in range(len(level.doors)) if Step("gate", door=i) not in steps]
            if unset:
                steps.insert(rng.randrange(len(steps) + 1), Step("gate", door=rng.choice(unset)))
        elif move == "drop" and steps:
            step = steps.pop(rng.randrange(len(steps)))
            if step.what == "build":
                steps = [s for s in steps if not (s.what == "up" and s.tile == step.tile)]
        elif move == "skills":
            used = {s.kind for s in steps if s.what == "build"}
            must = frozenset(u for k in used if (u := UNLOCK[k]) is not None)
            skills = reskill(skills, sigils, rng, stage, must)
        elif move == "early":
            early = rng.choice(EARLY)
    return Plan(skills, tuple(tidy(steps, location)), early, plan.map)


def plan_reach(kind: str, learned: frozenset[str]) -> float:
    return tower_levels(kind, perks(learned))[1].range


# -- The search -----------------------------------------------------------------------------------


def stored(key: str, sigils: int) -> tuple[dict, dict]:
    """Every stored row, and the row for this location's plan: the stored one, or the draft."""
    rows = json.loads(PLANS.read_text()) if PLANS.exists() else {}
    location = LOCATIONS[key]
    found = rows.get(plan_key(location, sigils))
    if found is not None and found["map"] == fingerprint(location):
        return rows, found
    return rows, draft(location, sigils).row()


def draft(location: Location, sigils: int) -> Plan:
    learned = draft_skills(location, sigils)
    return Plan(learned, draft_build(location, learned), map=fingerprint(location))


def score(pool: ProcessPoolExecutor, rows: list[dict], key: str, sigils: int, seeds: list[int],
          hp: float, leaders: str) -> list[int]:
    jobs = [(row, key, sigils, seed, hp, leaders) for row in rows for seed in seeds]
    lives = list(pool.map(lost, *zip(*jobs)))
    return [sum(lives[i * len(seeds):(i + 1) * len(seeds)]) for i in range(len(rows))]


def starting_life(requested: float | None, margins: Iterable[float]) -> float:
    """Start at ordinary life when a draft loses every seed; raising zero life cannot progress."""
    if requested is not None:
        if not math.isfinite(requested) or requested <= 0:
            raise ValueError("starting life must be finite and positive")
        return requested
    return max(1.0, statistics.median(margins))


def search(args: argparse.Namespace) -> None:
    key = args.location
    sigils = args.sigils if args.sigils is not None else 3 * ORDER.index(key)
    location = LOCATIONS[key]
    seeds = list(range(args.seeds))
    rng = random.Random(args.rng)
    rows, row = stored(key, sigils)
    best = draft(location, sigils) if args.fresh else Plan.of(row)
    used = {s.kind for s in best.steps if s.what == "build"}
    must = frozenset(u for k in used if (u := UNLOCK[k]) is not None)
    best = Plan(kept(must | best.skills, sigils, ORDER.index(key)), best.steps, best.early,
                fingerprint(location))
    evaluated = 0
    started = time.time()
    with ProcessPoolExecutor(args.jobs) as pool:
        margins = (pool.map(margin, *zip(*[(best.row(), key, sigils, s, args.leaders)
                                          for s in seeds])) if args.hp is None else ())
        hp = starting_life(args.hp, margins)
        best_score = score(pool, [best.row()], key, sigils, seeds, hp, args.leaders)[0]
        print(f"{key} sigils {sigils}: start at life x{hp:.2f}, {best_score} lives lost", flush=True)
        for round_ in range(args.rounds):
            while best_score <= args.slack * len(seeds):
                hp *= RAISE
                best_score = score(pool, [best.row()], key, sigils, seeds, hp, args.leaders)[0]
                print(f"  life x{hp:.2f}: {best_score} lives lost", flush=True)
            mutants = [mutate(best, location, sigils, rng) for _ in range(args.width)]
            scores = score(pool, [m.row() for m in mutants], key, sigils, seeds, hp, args.leaders)
            evaluated += len(mutants)
            i = min(range(len(mutants)), key=lambda j: (scores[j], len(mutants[j].steps)))
            if scores[i] <= best_score:
                if scores[i] < best_score:
                    print(f"  round {round_ + 1}: {best_score} -> {scores[i]} lives lost at x{hp:.2f}", flush=True)
                best, best_score = mutants[i], scores[i]
    rows[plan_key(location, sigils)] = best.row() | {
        "searched": {"leaders": args.leaders, "seeds": f"0-{args.seeds - 1}", "life": round(hp, 3), "lost": best_score,
                     "plans": evaluated}}
    PLANS.parent.mkdir(parents=True, exist_ok=True)
    PLANS.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n")
    print(f"stored after {evaluated} plans in {time.time() - started:.0f}s: life x{hp:.2f}, {best_score} lives lost")


def check(args: argparse.Namespace) -> None:
    """Margins against the rollout leaders on held-out training seeds: the stored plan and the draft."""
    key = args.location
    sigils = args.sigils if args.sigils is not None else 3 * ORDER.index(key)
    _, row = stored(key, sigils)
    rows = {"stored": row, "draft": draft(LOCATIONS[key], sigils).row()}
    seeds = list(range(args.first, args.first + args.seeds))
    with ProcessPoolExecutor(args.jobs) as pool:
        for name, r in rows.items():
            found = list(pool.map(margin, *zip(*[(r, key, sigils, s, "smart") for s in seeds])))
            print(f"{key} {name:6s} margin median {statistics.median(found):.2f} min {min(found):.2f}  "
                  f"{' '.join(f'{m:.2f}' for m in found)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("search", "check"):
        p = sub.add_parser(name)
        p.add_argument("location", choices=list(LOCATIONS))
        p.add_argument("--sigils", type=int)
        p.add_argument("--jobs", type=int, default=5)
    s = sub.choices["search"]
    s.add_argument("--rounds", type=int, default=60)
    s.add_argument("--width", type=int, default=5, help="mutants tried each round")
    s.add_argument("--seeds", type=int, default=4, help="training seeds 0..N-1")
    s.add_argument("--leaders", default="greedy", choices=list(LEADERS))
    s.add_argument("--hp", type=float, help="the life to start at (default: the plan's margin)")
    s.add_argument("--fresh", action="store_true", help="start from the draft, not the stored plan")
    s.add_argument("--slack", type=int, default=0,
                   help="lives a seed may lose before the life is raised: for a location that always leaks a little")
    s.add_argument("--rng", type=int, default=1)
    c = sub.choices["check"]
    c.add_argument("--first", type=int, default=10, help="the first held-out training seed")
    c.add_argument("--seeds", type=int, default=8)
    args = parser.parse_args()
    {"search": search, "check": check}[args.command](args)


if __name__ == "__main__":
    main()

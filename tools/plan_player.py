"""Find the planned player's build for each location by playing whole defences.

    uv run python tools/plan_player.py plan tristram graveyard
    uv run python tools/plan_player.py plan all --generations 50
    uv run python tools/plan_player.py plan hells_gate --resume   # climb on from the stored plan
    uv run python tools/plan_player.py table                     # the evaluation table, against the ordinary player

``plan`` is how a person who has replayed a location many times comes to know it, done by a machine. It starts
from a few builds a person would try first (towers on the tiles that watch the most path, the elements the
location's monsters feel most, the gates early) and plays each on training seeds against the leaders. Then it
climbs: each generation plays the build and a handful of changed copies of it (a tower moved, its element
changed, a step brought forward, a skill ranked higher, a spell's threshold moved) on the same fresh training
seeds, and keeps the best (or, when it is only as good, the change, so the climb can cross a plateau). Seeds
rotate through 0-99 so a build cannot learn one seed by heart. Most defences are played against *lite* leaders:
the smart leaders' own look-ahead at a coarser step with fewer rollouts, several times cheaper and much closer
to them than the greedy estimate alone. The last builds climbed through are played against the smart leaders to
choose the one written to ``hellward/sim/players/plans/``; the build the climb began from is always among them,
so a resumed climb cannot lose what it had. While a build holds with most of its life, every monster's
life is raised, so the climb keeps finding a difference to climb on: a build that holds at more life holds with
more to spare at the real one.

``table`` plays every location with ``3 * i`` sigils (``i`` its place in the campaign), on the evaluation seeds 1000 on, against the smart leaders.
Run heavy jobs through ``~/saga/tools/slot.py`` with ``caffeinate -i``.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import MONSTERS, TOWERS  # noqa: E402
from hellward.sim.model import DOOR_STOP, JOSTLE, World  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402
from hellward.sim.players.planned import Plan, Planned, load, plan_path  # noqa: E402
from hellward.sim.skills import SKILLS  # noqa: E402



def lite(world: World, leader_id: int) -> planner.Inline:
    """The smart leaders' look-ahead made cheap: a coarser step, four rollouts, no waiting for a better moment."""
    return planner.Inline(planner.decide(world, leader_id, dt=0.2, shortlist=4, timing=False))


LEADERS = {"greedy": planner.greedy, "lite": lite, "smart": planner.smart}
TRAINING = 100                # seeds 0-99; the evaluation seeds start at 1000
SEARCH = "lite"               # the leaders most defences are played against
CALLS = (0.0, 30.0, 50.0, 70.0, 100.0, 125.0)
RESERVES = (0.0, 20.0, 30.0, 45.0, 60.0)
WORTHS = ("smite_worth", "cleanse_worth", "meteor_worth", "orb_worth")
HOLD = 36.0                   # a build scoring this (16 lives kept) has room: the monsters' life goes up
FALTER = 26.0                 # below this (a fall, or 6 lives) it comes down again
TOP_TILES = 40                # tiles a moved or added tower may jump to
FIRST_TOWERS = 12             # towers in a first build


# -- Playing ------------------------------------------------------------------------------------------


def sigils_for(location: str) -> int:
    return 3 * ORDER.index(location)


def score(world: World) -> float:
    """20 plus the lives kept for a victory; for a fall, 20 times the share of the host slain before it."""
    if world.outcome == "victory":
        return 20.0 + world.lives
    total = sum(g.count for w in world.waves for g in w.groups)
    return 20.0 * world.kills / total


def play(plan: dict, location: str, sigils: int, seed: int, hp: float, leaders: str) -> float:
    world, _ = defend(LOCATIONS[location], Planned(plan=Plan.from_json(plan)), seed=seed, sigils=sigils,
                      planner=LEADERS[leaders], hp=hp)
    return score(world)


def evaluate(pool: ProcessPoolExecutor, plans: list[Plan], location: str, seeds: list[int], hp: float,
             leaders: str) -> list[float]:
    """Each plan's mean score over the same seeds."""
    sigils = sigils_for(location)
    jobs = [(p.to_json(), location, sigils, s, hp, leaders) for p in plans for s in seeds]
    results = list(pool.map(play, *zip(*jobs)))
    n = len(seeds)
    return [statistics.mean(results[i * n:(i + 1) * n]) for i in range(len(plans))]


# -- The builds a person tries first --------------------------------------------------------------------


def fit(location: Location, kind: str) -> float:
    """The share of the location's monster life a tower kind's element is felt by."""
    total = felt = 0.0
    element = TOWERS[kind].element
    for wave in location.waves:
        for group in wave.groups:
            monster = MONSTERS[group.kind]
            life = monster.hp * wave.hp * group.count
            total += life
            felt += life * max(0.0, monster.taken(element))
    return felt / total


def ranked_tiles(location: Location, reach: float, door_bonus: float) -> list[tuple[int, int]]:
    """Buildable tiles by how much path they watch, a gate's queue counting extra."""
    level = location.level
    queues = [s - DOOR_STOP - JOSTLE / 2 for s in level.door_s]
    scored = []
    for y in range(level.height):
        for x in range(level.width):
            if not level.buildable(x, y):
                continue
            spans = level.coverage((x, y), reach)
            watched = sum(b - a for a, b in spans)
            if watched <= 0:
                continue
            watched += door_bonus * sum(1 for q in queues if any(a <= q <= b for a, b in spans))
            scored.append((watched, (x, y)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [tile for _, tile in scored]


def first_plan(location: Location, kinds: list[str]) -> Plan:
    """Twelve towers of the given kinds (in turn) on the best tiles for their reach, the gates after the third, then
    ranks and further towers in turn."""
    used: set[tuple[int, int]] = set()
    placed = []
    for i in range(FIRST_TOWERS):
        kind = kinds[i % len(kinds)]
        reach = TOWERS[kind].levels[1].range
        bonus = 6.0 if kind == "frost" else 3.0
        tile = next(t for t in ranked_tiles(location, reach, bonus) if t not in used)
        used.add(tile)
        placed.append((kind, tile))
    steps: list[tuple] = []
    gates = [("gate", i) for i in range(len(location.level.doors))] if location.arsenal.gates else []
    rank_queue = [("rank", tile) for _, tile in placed] * 2
    for i, (kind, tile) in enumerate(placed):
        steps.append(("build", kind, tile))
        if i == 2:
            steps.extend(gates)
        if i >= 3:
            steps.append(rank_queue.pop(0))
    steps.extend(rank_queue)
    return Plan(skills=first_skills(kinds, location), steps=steps, calls=[100.0] + [0.0] * (len(location.waves) - 1))


def first_skills(kinds: list[str], location: Location) -> list[str]:
    column = {"pyre": "fire", "storm": "lightning", "frost": "cold", "plague": "poison"}
    order = []
    for kind in dict.fromkeys(kinds):
        order += [k for k, s in SKILLS.items() if s.column == column[kind]]
    if location.arsenal.gates:
        order += ["holy_shield", "salvation", "thorns"]
    order += ["warmth", "soul_harvest", "spell_mastery"]
    order += [k for k in SKILLS if k not in order]
    tier = {k: SKILLS[k].tier for k in order}
    return sorted(order, key=lambda k: (tier[k], order.index(k)))


MIXES = (("pyre", "frost"), ("frost", "frost", "pyre"), ("storm", "frost"), ("pyre", "frost", "storm", "plague", "pyre", "storm"),
         ("plague", "pyre", "frost"), ("pyre", "pyre", "storm"))


def first_plans(location: Location) -> list[Plan]:
    """A person's first tries: a few mixes of the kinds on offer, and the two it feels most, each twelve towers."""
    arsenal = location.arsenal.towers
    by_fit = sorted(arsenal, key=lambda k: -fit(location, k))
    mixes = [tuple(k for k in mix if k in arsenal) for mix in MIXES] + [tuple(by_fit[:2])]
    return [first_plan(location, list(mix)) for mix in dict.fromkeys(m for m in mixes if m)]


# -- Changes ------------------------------------------------------------------------------------------


def repaired(plan: Plan) -> Plan:
    """The plan with every rank after its tower's build, at most two ranks a tower, one build a tile, one step a
    gate."""
    built: set[tuple[int, int]] = set()
    ranks: dict[tuple[int, int], int] = {}
    gates: set[int] = set()
    steps: list[tuple] = []
    early: list[tuple] = []    # ranks that came before their tower's build: they follow it

    def rank(step: tuple) -> None:
        if ranks.get(step[1], 0) < 2:
            ranks[step[1]] = ranks.get(step[1], 0) + 1
            steps.append(step)

    for step in plan.steps:
        if step[0] == "build":
            if step[2] in built:
                continue
            built.add(step[2])
            steps.append(step)
            for waiting in [s for s in early if s[1] == step[2]]:
                rank(waiting)
            early = [s for s in early if s[1] != step[2]]
        elif step[0] == "rank":
            if step[1] in built:
                rank(step)
            else:
                early.append(step)
        elif step[1] not in gates:
            gates.add(step[1])
            steps.append(step)
    plan.steps = steps
    return plan


def mutate(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> Plan:
    """A copy of the plan with one to three changes."""
    child = Plan.from_json(json.loads(json.dumps(plan.to_json())))
    child.trained = {}
    for _ in range(rng.choice((1, 1, 2, 3))):
        rng.choice(CHANGES)(child, location, rng, tiles)
    return repaired(child)


def _builds(plan: Plan) -> list[int]:
    return [i for i, s in enumerate(plan.steps) if s[0] == "build"]


def _retile(plan: Plan, tile: tuple[int, int], new: tuple[int, int]) -> None:
    plan.steps = [(s[0], s[1], new) if s[0] == "build" and s[2] == tile else ("rank", new) if s[0] == "rank" and s[1] == tile
                  else s for s in plan.steps]


def move_tower(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    builds = _builds(plan)
    if not builds:
        return
    _, _, tile = plan.steps[rng.choice(builds)]
    taken = {plan.steps[i][2] for i in builds}
    if rng.random() < 0.6:
        near = [(tile[0] + dx, tile[1] + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
        free = [t for t in near if location.level.buildable(*t) and t not in taken]
    else:
        free = [t for t in tiles if t not in taken]
    if free:
        _retile(plan, tile, rng.choice(free))


def change_kind(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    builds = _builds(plan)
    kinds = location.arsenal.towers
    if builds and len(kinds) > 1:
        i = rng.choice(builds)
        _, kind, tile = plan.steps[i]
        plan.steps[i] = ("build", rng.choice([k for k in kinds if k != kind]), tile)


def move_step(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    if len(plan.steps) < 2:
        return
    step = plan.steps.pop(rng.randrange(len(plan.steps)))
    plan.steps.insert(rng.randrange(len(plan.steps) + 1), step)


def swap_steps(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    if len(plan.steps) < 2:
        return
    i = rng.randrange(len(plan.steps) - 1)
    plan.steps[i], plan.steps[i + 1] = plan.steps[i + 1], plan.steps[i]


def add_tower(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    taken = {plan.steps[i][2] for i in _builds(plan)}
    free = [t for t in tiles if t not in taken]
    if free:
        at = rng.randrange(len(plan.steps) + 1)
        plan.steps.insert(at, ("build", rng.choice(location.arsenal.towers), rng.choice(free)))


def drop_tower(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    builds = _builds(plan)
    if len(builds) > 2:
        tile = plan.steps[rng.choice(builds)][2]
        plan.steps = [s for s in plan.steps if not (s[0] == "build" and s[2] == tile) and not (s[0] == "rank" and s[1] == tile)]


def add_rank(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    builds = _builds(plan)
    if builds:
        i = rng.choice(builds)
        plan.steps.insert(rng.randrange(i + 1, len(plan.steps) + 1), ("rank", plan.steps[i][2]))


def drop_rank(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    ranks = [i for i, s in enumerate(plan.steps) if s[0] == "rank"]
    if ranks:
        plan.steps.pop(rng.choice(ranks))


def toggle_gate(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    if not location.level.doors:
        return
    index = rng.randrange(len(location.level.doors))
    have = [i for i, s in enumerate(plan.steps) if s[0] == "gate" and s[1] == index]
    if have:
        plan.steps.pop(have[0])
    else:
        plan.steps.insert(rng.randrange(len(plan.steps) + 1), ("gate", index))


def change_skill(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    key = plan.skills.pop(rng.randrange(len(plan.skills)))
    plan.skills.insert(rng.randrange(min(len(plan.skills) + 1, 8)), key)


def promote_column(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    """A skill brought forward with the ones above it, so a deep skill can be learned in one change."""
    skill = SKILLS[rng.choice(plan.skills)]
    chain = [k for k, s in SKILLS.items() if s.column == skill.column and s.tier <= skill.tier]
    rest = [k for k in plan.skills if k not in chain]
    at = rng.randrange(min(len(rest) + 1, 6))
    plan.skills = rest[:at] + chain + rest[at:]


def change_call(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    plan.calls[rng.randrange(len(plan.calls))] = rng.choice(CALLS)


def change_spells(plan: Plan, location: Location, rng: random.Random, tiles: list[tuple[int, int]]) -> None:
    what = rng.choice(WORTHS + ("reserve", "rebuild"))
    if what == "reserve":
        plan.reserve = rng.choice(RESERVES)
    elif what == "rebuild":
        plan.rebuild = rng.choice(("now", "break", "never"))
    else:
        setattr(plan, what, round(getattr(plan, what) * rng.choice((0.6, 0.8, 1.25, 1.6)), 2))


CHANGES = (move_tower, move_tower, move_tower, change_kind, change_kind, move_step, move_step, swap_steps, swap_steps,
           add_tower, drop_tower, add_rank, drop_rank, toggle_gate, change_skill, promote_column, change_call,
           change_spells, change_spells)


# -- The climb ----------------------------------------------------------------------------------------


def first_build(pool: ProcessPoolExecutor, location_key: str, offset: int,
                log) -> tuple[Plan, float, int]:
    """The best of the first builds, the monsters' life at which it stops holding with room to spare, and the
    defences it took to find them."""
    candidates = first_plans(LOCATIONS[location_key])
    screen = [(offset + 90 + j) % TRAINING for j in range(4)]
    hp, defences = 1.0, 0
    while True:
        scores = evaluate(pool, candidates, location_key, screen, hp, SEARCH)
        defences += len(candidates) * len(screen)
        best = max(range(len(candidates)), key=lambda i: scores[i])
        log(f"  first builds at life x{hp:.2f}: {' '.join(f'{s:.1f}' for s in scores)}")
        if scores[best] < HOLD or hp > 4.0:
            return candidates[best], hp, defences
        hp *= 1.2


def climb(pool: ProcessPoolExecutor, location_key: str, generations: int, children: int, per: int,
          confirm: int, resume: bool, log) -> Plan:
    """The climb for one location, from the first builds or, with ``resume``, from the plan the
    player holds now (and at the life it was found at)."""
    location = LOCATIONS[location_key]
    before = load(location_key).trained if resume else {}
    done = before.get("generations", 0)
    rng = random.Random(f"{location_key}-{done}")
    tiles = ranked_tiles(location, 3.0, 3.0)[:TOP_TILES]
    start = time.time()
    offset = ORDER.index(location_key) * 17
    seeds = lambda g: [(offset + (done + g) * per + j) % TRAINING for j in range(per)]   # noqa: E731

    if resume:
        parent, hp, defences = load(location_key), before.get("life", 1.0), 0
    else:
        parent, hp, defences = first_build(pool, location_key, offset, log)
    trail = [parent]
    for g in range(generations):
        kids = [mutate(parent, location, rng, tiles) for _ in range(children)]
        scores = evaluate(pool, [parent] + kids, location_key, seeds(g), hp, SEARCH)
        defences += (1 + children) * per
        parent_score = scores[0]
        k = max(range(children), key=lambda i: (scores[1 + i], -i))
        moved = ""
        if scores[1 + k] > parent_score:
            parent, parent_score, moved = kids[k], scores[1 + k], " *"
            trail.append(parent)
        elif scores[1 + k] == parent_score:   # as good on these seeds: drift, so the climb can cross a plateau
            parent, moved = kids[k], " ="
        log(f"  gen {g:3d} life x{hp:.2f} build {scores[0]:5.1f} best change {scores[1 + k]:5.1f}{moved}")
        if parent_score >= HOLD:
            hp *= 1.06
        elif parent_score < FALTER and hp > 0.6:
            hp /= 1.06

    trail.append(parent)
    finalists = list({json.dumps(p.to_json(), sort_keys=True): p for p in trail[:1] + trail[-4:]}.values())
    finals = [(offset + 60 + j) % TRAINING for j in range(confirm)]
    smart = evaluate(pool, finalists, location_key, finals, hp, "smart")
    defences += len(finalists) * len(finals)
    chosen = finalists[max(range(len(finalists)), key=lambda i: smart[i])]
    at_one = evaluate(pool, [chosen], location_key, finals, 1.0, "smart")[0]
    defences += len(finals)
    log(f"  finalists against smart leaders at life x{hp:.2f}: {' '.join(f'{s:.1f}' for s in smart)}; "
        f"chosen at x1: {at_one:.1f}")
    chosen.trained = {"confirmed_on": finals, "life": round(hp, 3), "smart_score": round(max(smart), 2),
                      "smart_score_at_1": round(at_one, 2), "defences": before.get("defences", 0) + defences,
                      "minutes": round(before.get("minutes", 0) + (time.time() - start) / 60, 1),
                      "generations": done + generations}
    return chosen


# -- The table ----------------------------------------------------------------------------------------


def table_row(player: str, location: str, sigils: int, seed: int) -> dict:
    world, record = defend(LOCATIONS[location], PLAYERS[player](seed), seed=seed, sigils=sigils,
                           planner=planner.smart)
    return {"player": player, "location": location, "seed": seed, "outcome": world.outcome,
            "lives": world.lives, "spells": dict(record.spells), "landed": record.landed, "broken": record.broken}


def table(pool: ProcessPoolExecutor, players: list[str], seeds: list[int]) -> None:
    runs = [(loc, 3 * i) for i, loc in enumerate(ORDER)]
    jobs = [(p, loc, sig, s) for loc, sig in runs for p in players for s in seeds]
    rows = list(pool.map(table_row, *zip(*jobs)))
    for loc, sig in runs:
        for p in players:
            mine = [r for r in rows if r["player"] == p and r["location"] == loc]
            lives = [r["lives"] for r in mine]
            wins = sum(r["outcome"] == "victory" for r in mine)
            spells = sum((r["spells"].get(k, 0) for r in mine for k in r["spells"]), 0) / len(mine)
            landed = statistics.mean(r["landed"] for r in mine)
            broken = statistics.mean(r["broken"] for r in mine)
            print(f"{loc:11s} sigils {sig:2d}  {p:9s} wins {wins}/{len(mine)}  lives median "
                  f"{statistics.median(lives):4.1f} fewest {min(lives):2d}  curses landed {landed:4.1f} broken {broken:4.1f}  "
                  f"spells {spells:4.1f}", flush=True)


def dumps(plan: Plan) -> str:
    """The plan as JSON a person can read: one field a line, one step a line."""
    data = plan.to_json()
    steps = ",\n  ".join(json.dumps(step) for step in data.pop("steps"))
    lines = [f" {json.dumps(key)}: {json.dumps(value)}" for key, value in data.items()]
    return "{\n" + ",\n".join(lines) + f',\n "steps": [\n  {steps}\n ]\n}}\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=("plan", "table"))
    parser.add_argument("locations", nargs="*", default=["all"])
    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--children", type=int, default=7)
    parser.add_argument("--per", type=int, default=3, help="training seeds each build plays per generation")
    parser.add_argument("--confirm", type=int, default=8, help="training seeds the finalists play against smart leaders")
    parser.add_argument("--resume", action="store_true", help="climb on from the stored plans instead of the first builds")
    parser.add_argument("--players", default="planned,ordinary")
    parser.add_argument("--seeds", type=int, default=8, help="evaluation seeds for the table, from 1000")
    parser.add_argument("--jobs", type=int, default=5)
    args = parser.parse_args()
    with ProcessPoolExecutor(args.jobs, mp_context=multiprocessing.get_context("spawn")) as pool:
        if args.what == "table":
            table(pool, args.players.split(","), list(range(1000, 1000 + args.seeds)))
            return
        keys = list(ORDER) if args.locations == ["all"] else args.locations
        for key in keys:
            print(f"{key}:", flush=True)
            plan = climb(pool, key, args.generations, args.children, args.per, args.confirm, args.resume,
                         lambda line: print(line, flush=True))
            path = plan_path(key)
            path.parent.mkdir(exist_ok=True)
            path.write_text(dumps(plan))
            print(f"  wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path} "
                  f"({plan.trained})", flush=True)


if __name__ == "__main__":
    main()

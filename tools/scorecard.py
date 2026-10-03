"""Every measurable criterion of docs/design-criteria.md, with its number and whether it is met.

    uv run python tools/scorecard.py              # the checks that read the content tables
    uv run python tools/scorecard.py --json OUT   # the same, written as JSON for the evidence folder

A check reads the game's own tables (hellward/sim/data and the campaign), never a copy of their numbers. Criteria
that need bot runs are listed as not yet measured until their measurement exists.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim.balance import BALANCE  # noqa: E402
from hellward.sim.campaign import ACTS, LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import CURSES, MAX_POISON_STACKS, MONSTERS, SPELLS, START_LIVES, TOWERS, TowerKind, felt_hit  # noqa: E402
from hellward.sim.model import ATTUNE_GOLD, World  # noqa: E402
from hellward.sim.relics import DOWNSIDES, ENABLES, RELICS, VERBS, draw  # noqa: E402
from tools.maps import (LEAST_CLUSTERED, LEAST_OCCUPIED, MOST_PRIME, REFERENCE_REACH, survey, traffic,  # noqa: E402
                        worth_map)

ATTACKS = ("bolt", "chain", "nova", "venom", "hook")   # tower attacks that deal damage; the others are mechanics towers


@dataclass(frozen=True)
class Result:
    id: str
    what: str
    value: str
    met: bool | None   # None: not measured yet


def spawns(location: Location) -> Iterator[tuple[str, float, int]]:
    """(monster kind, life, wave index) for every authored spawn of a location."""
    for index, wave in enumerate(location.waves):
        for group in wave.groups:
            life = MONSTERS[group.kind].hp
            for _ in range(group.count):
                yield group.kind, life, index


def is_boss(kind: str) -> bool:
    return MONSTERS[kind].boss


def bodies_per_wave() -> Result:
    most = max(sum(group.count for group in wave.groups) for location in LOCATIONS.values() for wave in location.waves)
    return Result("G2.1", "most monsters in one wave", str(most), most <= 30)


def three_ranks() -> Result:
    counts = sorted({len(kind.levels) for kind in TOWERS.values()})
    return Result("G2.3", "ranks per tower", ", ".join(map(str, counts)), counts == [3])


def number_scale() -> list[Result]:
    first = LOCATIONS[ORDER[0]]
    first_life = next(spawns(first))[1]
    first_hit = min(kind.levels[0].damage for kind in TOWERS.values() if kind.attack in ATTACKS)
    last = LOCATIONS[ORDER[-1]]
    ordinary = [life for kind, life, _ in spawns(last) if not is_boss(kind)]
    every = [(kind, life) for location in LOCATIONS.values() for kind, life, _ in spawns(location)]
    biggest = max(life for kind, life in every if not is_boss(kind))
    boss = max((life for kind, life in every if is_boss(kind)), default=0.0)
    top_hit = max(level.damage for kind in TOWERS.values() if kind.attack in ATTACKS for level in kind.levels)
    toughest = max(ordinary)
    return [
        Result("G2.4", "first monster's life", f"{first_life:.1f}", 8 <= first_life <= 12),
        Result("G2.4", "weakest first-rank hit", f"{first_hit:g}", 1 <= first_hit <= 2),
        Result("G2.4", "last location's toughest ordinary life", f"{toughest:.0f}", 60 <= toughest <= 100),
        Result("G2.4", "largest non-boss life", f"{biggest:.0f}", biggest <= 200),
        Result("G2.4", "largest boss life", f"{boss:.0f}", boss <= 1000),
        Result("G2.4", "largest tower hit (before bonuses)", f"{top_hit:g}", top_hit <= 30),
    ]


def felt_dps(kind: TowerKind, rank: int, location: Location) -> float:
    """A rank's damage per second as the location's host feels its hits (and its venom, as many stacks as its darts
    keep up), each monster kind weighed by its share of the life that comes: the location's armor and element mix."""
    level = kind.levels[rank]
    life: dict[str, float] = {}
    for monster, hp, _ in spawns(location):
        life[monster] = life.get(monster, 0.0) + hp
    total = sum(life.values())
    stacks = min(MAX_POISON_STACKS, level.rate * level.poison_time)
    return sum(hp / total * (level.rate * felt_hit(level.damage, kind.element, MONSTERS[monster])
                             + level.poison * stacks * MONSTERS[monster].taken(kind.element))
               for monster, hp in life.items())


def rank_economy() -> list[Result]:
    """Upgrading buys less damage per gold than a new rank-I tower, and more per cell, at every location that offers
    the tower, against that location's armor mix. The worst location's marginal damage per gold is shown. Not the Hook
    Tower: its ranks buy pulls, not damage."""
    out = []
    for key, kind in TOWERS.items():
        if kind.attack not in ATTACKS or kind.attack == "hook":
            continue
        cost = [level.cost for level in kind.levels]
        worst: tuple[float, str, list[float]] | None = None
        met = True
        for location in LOCATIONS.values():
            if key not in location.arsenal.towers:
                continue
            dps = [felt_dps(kind, rank, location) for rank in range(3)]
            per_gold = [dps[0] / cost[0]] + [(dps[r] - dps[r - 1]) / cost[r] for r in (1, 2)]
            cheaper = all(per_gold[r] < per_gold[0] for r in (1, 2))
            denser = all(dps[r] > dps[0] for r in (1, 2))
            met = met and cheaper and denser
            slack = per_gold[0] - max(per_gold[1], per_gold[2])
            if worst is None or slack < worst[0]:
                worst = (slack, location.key, per_gold)
        assert worst is not None
        out.append(Result("R3", f"{kind.name}: damage per gold by rank, at {worst[1]}",
                          " / ".join(f"{v:.3f}" for v in worst[2]), met))
    return out


def no_dispel() -> Result:
    """No spell lifts a curse (Cleanse, Salvation's ward) or breaks a chant (tests/test_spells.py plays them all)."""
    dispels = [name for name in ("cleanse",) if name in SPELLS or hasattr(World, name)]
    return Result("S1", "spells that lift a curse or break a chant", ", ".join(dispels) or "none", not dispels)


def hymn_seeks() -> list[Result]:
    """S3: Battle Hymn doubles a tower's rate for 6 s, and the leaders' curses go for the boosted tower:
    eight smart defences of the caves, the hymned share of the aimed towers against the hymned share in
    reach at each chant (tools/balance.py). The lift isolates the choice itself (a random curser reads
    1.0x by construction); the planner prices a tower at its hymned rate, so the seeking is emergent."""
    from tools.balance import chant_lift, match
    hymn = SPELLS["hymn"]
    chants = [c for i in range(8) for c in match("smart", i, 8, "caves")["chants"]]
    lift, hymned, expected = chant_lift(chants)
    return [Result("S3", "hymn's rate and lasting", f"x{hymn.rate:g} for {hymn.lasting:g} s",
                   hymn.rate == 2.0 and hymn.lasting == 6.0),
            Result("S3", "leaders' hymn lift over eight smart caves defences",
                   f"{lift:.1f}x ({hymned}/{expected:.1f} over {len(chants)} chants)",
                   lift >= 1.5 and expected >= 2.0)]


def armor_duels() -> list[Result]:
    """M9: in each act from the Catacombs on, a location a light build loses and a heavy build of equal
    gold wins (tools/armor.py: pure arrows against pure ballistae at 3:2 counts on shared tiles). The
    tripwire fights two seeds; tests/test_armor.py fights six."""
    from tools.armor import capped, duel, full
    gate_light, gate_heavy, gate_cost = duel("hells_gate", capped, 9, [0, 1])
    temple_light, temple_heavy, temple_cost = duel("temple", full, 9, [0, 1])
    caves_light, _, caves_cost = duel("caves", capped, 9, [0, 1])
    return [
        Result("M9", "hells_gate: light loses, heavy wins (108 gold)",
               f"light {' '.join(gate_light)} heavy {' '.join(gate_heavy)}",
               gate_cost == 108 and all(o.startswith("d") for o in gate_light)
               and all(o.startswith("v") for o in gate_heavy)),
        Result("M9", "temple: light loses, heavy wins (300 gold)",
               f"light {' '.join(temple_light)} heavy {' '.join(temple_heavy)}",
               temple_cost == 300 and all(o.startswith("d") for o in temple_light)
               and all(o.startswith("v") for o in temple_heavy)),
        Result("M9", "caves control: light holds unarmored at 108 gold", " ".join(caves_light),
               caves_cost == 108 and all(o.startswith("v") for o in caves_light)),
    ]


def verb_rates() -> list[Result]:
    """V1/V2: each verb earns 3-40 a wave in a build that leans into it (tools/verbs.py), at least
    twice what the same plan earns without the lean. Leak's ceiling is the lives themselves: twenty
    over five waves, so its tripwire sits at 2.5. Curse is the pulse (about one landing a wave,
    whatever stands): its check is the clump's catch over the spread build's."""
    from tools.verbs import ab
    rows = []
    for verb in ("cast", "leak", "charge", "debuff", "corpse"):
        leans, plains, outcomes, _, _ = ab(verb, [0, 1])
        lean = sum(leans) / len(leans)
        plain = sum(plains) / len(plains)
        floor = 2.5 if verb == "leak" else 3.0
        won = all(o.startswith("v") for o in outcomes)
        rows.append(Result("V1", f"{verb}: the lean earns {floor:g}-40 a wave",
                           f"{lean:.1f}/wave ({' '.join(outcomes)})", won and floor <= lean <= 40))
        ratio = lean / plain if plain > 0 else float("inf")
        rows.append(Result("V2", f"{verb}: the lean earns 2x the plain build",
                           f"{lean:.1f} vs {plain:.1f}" if plain > 0 else f"{lean:.1f} vs none",
                           won and (plain <= 0 or ratio >= 2.0)))
    leans, _, outcomes, took_lean, took_plain = ab("curse", [0, 1])
    lean = sum(leans) / len(leans)
    catch_lean = sum(took_lean) / len(took_lean) if took_lean else 0.0
    catch_plain = sum(took_plain) / len(took_plain) if took_plain else 0.0
    won = all(o.startswith("v") for o in outcomes)
    rows.append(Result("V1", "curse stays the pulse: the lean takes 3 or fewer a wave",
                       f"{lean:.1f}/wave ({' '.join(outcomes)})", won and lean <= 3.0))
    rows.append(Result("V2", "curse: the clump catches 2x the spread build a landing",
                       f"{catch_lean:.1f} vs {catch_plain:.1f} towers",
                       won and catch_plain > 0 and catch_lean >= 2.0 * catch_plain))
    return rows


COSTS: tuple[tuple[str, str, Callable[[], bool]], ...] = (
    ("cast", "idols and hymns cost gold and mana",
     lambda: TOWERS["idol"].levels[0].cost > 0 and SPELLS["hymn"].mana > 0),
    ("charge", "attunement costs battle gold", lambda: ATTUNE_GOLD > 0),
    ("corpse", "frost towers cost gold", lambda: TOWERS["frost"].levels[0].cost > 0),
    ("curse", "a curse lasts on the tower it takes",
     lambda: all(spec.duration > 0 for spec in CURSES.values())),
    ("debuff", "plague towers cost gold, and venom overflows past its maximum",
     lambda: TOWERS["plague"].levels[0].cost > 0 and MAX_POISON_STACKS >= 1),
    ("leak", "a leak costs sanctuary lives", lambda: START_LIVES > 0),
)


def verb_costs() -> list[Result]:
    """V3: leaning into a verb costs something real, and some relic turns that cost into payoff."""
    return [Result("V3", f"{verb}: {words}; read by {reader}",
                   f"{words}; read by {reader}",
                   backed and reader != "no relic")
            for verb, words, backed_fn in COSTS
            for backed in [backed_fn()]
            for reader in [", ".join(key for key, spec in RELICS.items()
                                      if spec.verb == verb and spec.writes) or "no relic"]]


def tower_verbs() -> Result:
    """V4: each mechanics tower (no damage of its own) produces or consumes one verb."""
    mechanics = sorted(key for key, kind in TOWERS.items() if kind.attack not in ATTACKS)
    tagged = sorted(key for key in mechanics
                    if TOWERS[key].verb in VERBS and TOWERS[key].verb_role in ("produce", "consume"))
    bare = [key for key in mechanics if key not in tagged]
    value = ", ".join(tagged) + (f" (bare: {', '.join(bare)})" if bare else "")
    return Result("V4", "mechanics towers with one verb", value or "none",
                  not bare and bool(tagged))


def relic_pool() -> list[Result]:
    """V5: most relics read one verb and write another. V7: the pool holds forty, a quarter of
    them open tech the run has not reached, and every one of them — the pacts with their
    downsides loudest — arrives as the camp's offered choice, never forced (take_relic refuses
    anything unoffered; tests/test_run_server.py holds the refusal)."""
    converters = [key for key, spec in RELICS.items() if spec.verb in VERBS and spec.writes]
    offered: set[str] = set()
    for seed in range(200):
        offered.update(draw(seed, 0, ()))
    pacts = sorted(DOWNSIDES)
    return [
        Result("V5", "relics reading one verb and writing another",
               f"{len(converters)}/{len(RELICS)}", len(converters) / len(RELICS) >= 0.6),
        Result("V7", "the pool holds forty relics", str(len(RELICS)), len(RELICS) == 40),
        Result("V7", "a quarter of the pool enables unreached tech",
               f"{len(ENABLES)}/{len(RELICS)}: {', '.join(sorted(ENABLES))}",
               set(ENABLES) <= set(RELICS) and len(ENABLES) / len(RELICS) >= 0.25),
        Result("V7", "every relic is offered somewhere, pacts as choices",
               f"{len(offered)}/{len(RELICS)} offered; pacts: {', '.join(pacts)}",
               offered == set(RELICS) and all(p in offered for p in pacts)),
    ]


def verb_set() -> list[Result]:
    """V6: consuming a debuff is a verb; V8: every relic's counter rides in the client state."""
    from hellward.server.protocol import state
    world = World(LOCATIONS["tristram"], seed=3, relics=("spite",))
    world.progress["spite"] = 1
    counters = state(world)["relic_counters"]
    return [Result("V6", "debuff consumed is a verb", ", ".join(VERBS), "debuff" in VERBS),
            Result("V8", "relic counters in the client state", json.dumps(counters),
                   counters == {"spite": 1})]


def tower_kinds() -> list[Result]:
    mechanics = [kind.name for kind in TOWERS.values() if kind.attack not in ATTACKS]
    share = len(mechanics) / len(TOWERS)
    return [Result("M4", "tower kinds", str(len(TOWERS)), len(TOWERS) >= 14),
            Result("M6", "share of mechanics towers", f"{share:.0%}", share >= 0.4),
            tree_too_dear()]


def tree_too_dear() -> Result:
    """M4's floor: the whole tree costs at least 2.5x a perfect run's points without packs — every sigil
    (three for lives, three for goals, a location) plus the levels the campaign's kills and clears reach.
    Packs pay more (bounded: three a location for the bots, decaying repeats for a person); tools/runs.py
    quotes the true ratio, strong-30's tree over 72 plus its highest level."""
    from hellward.sim.skills import TREE_COST
    from hellward.sim.xp import XP_NEXT_BASE, XP_NEXT_GROWTH, clear_xp, kill_xp
    total = sum(sum(group.count * kill_xp(MONSTERS[group.kind].hp) for group in wave.groups)
                + clear_xp(number)
                for location in LOCATIONS.values() for number, wave in enumerate(location.waves, start=1))
    level, need = 1, XP_NEXT_BASE
    while total >= need:
        total -= need
        level += 1
        need = XP_NEXT_BASE + XP_NEXT_GROWTH * (level - 1) * (level - 1)
    perfect = 6 * len(LOCATIONS) + level
    return Result("M4", "tree over a packless perfect run's points",
                  f"{TREE_COST}/{perfect} = {TREE_COST / perfect:.2f}x", TREE_COST >= 2.5 * perfect)


def xp_bar() -> list[Result]:
    """M2's bar: the first level-up lands in Tristram's second wave, the campaign's kills and clears reach
    about fifty-five levels by the Temple, and a level-up refills the mana orb and tells the view."""
    from hellward.sim.model import World  # noqa: E402
    from hellward.sim.xp import XP_NEXT_BASE, XP_NEXT_GROWTH, clear_xp, kill_xp, xp_next  # noqa: E402

    waves = LOCATIONS["tristram"].waves
    first = sum(g.count * kill_xp(MONSTERS[g.kind].hp) for g in waves[0].groups) + clear_xp(1)
    second = sum(g.count * kill_xp(MONSTERS[g.kind].hp) for g in waves[1].groups) + clear_xp(2)
    total = sum(sum(g.count * kill_xp(MONSTERS[g.kind].hp) for g in w.groups) + clear_xp(n)
                for location in LOCATIONS.values() for n, w in enumerate(location.waves, start=1))
    level, need, spent = 1, XP_NEXT_BASE, 0.0
    while spent + need <= total:
        spent += need
        level += 1
        need = XP_NEXT_BASE + XP_NEXT_GROWTH * (level - 1) * (level - 1)
    world = World(LOCATIONS["tristram"], seed=1)
    world.mana = 5.0
    world._earn(xp_next(1) + 1.0)
    refills = world.mana == world.mana_max and ("level_up", 2) in world.events
    return [Result("M2", "first level-up in Tristram's second wave",
                   f"wave one {first:.0f} < {XP_NEXT_BASE:.0f} <= {first + second:.0f} waves one and two",
                   first < XP_NEXT_BASE <= first + second),
            Result("M2", "levels by the Temple", f"{level} over {total:.0f} XP", 50 <= level <= 60),
            Result("M2", "a level-up refills the mana orb and tells the view",
                   "mana full, level_up told" if refills else "no refill", refills)]


def real_estate() -> list[Result]:
    """Each map's scarce ground, by tools/maps.py: the worst map against each target."""
    maps = {key: survey(LOCATIONS[key]) for key in ORDER}
    occupied = min(maps, key=lambda key: maps[key].occupied_share)
    crowded = max(maps, key=lambda key: len(maps[key].prime))
    scattered = min(maps, key=lambda key: maps[key].clustered_share)
    return [
        Result("R1", "least occupied ground beside the halls", f"{maps[occupied].occupied_share:.0%} ({occupied})",
               maps[occupied].occupied_share >= LEAST_OCCUPIED),
        Result("R1", "most prime cells on a map", f"{len(maps[crowded].prime)} ({crowded})",
               len(maps[crowded].prime) <= MOST_PRIME),
        Result("R5", "fewest prime cells near another (maps only)",
               f"{maps[scattered].clustered_share:.0%} ({scattered})",
               maps[scattered].clustered_share >= LEAST_CLUSTERED),
    ]


def worth_and_cells() -> list[Result]:
    """R2: a battle's start carries every offered kind's per-cell coverage; R7: every frame's state carries
    each taken cell with its waves left, and each mark with its seconds."""
    from hellward.server.protocol import battle_start, state
    world = World(LOCATIONS["tristram"], seed=1)
    start = battle_start(world, demo=True, breach_claim=None)
    kinds = set(start["worth"]) == set(LOCATIONS["tristram"].arsenal.towers)
    bare = bool(start["worth"]["arrow"]["bare"])
    world.blighted[(3, 4)] = (2, "webbed")
    found = state(world)
    taken = found["blighted"] == [[3, 4, 2, "webbed"]] and isinstance(found["blight_marks"], list)
    return [Result("R2", "per-cell coverage in the battle's start", f"{len(start['worth'])} kinds",
                   kinds and bare),
            Result("R7", "a taken cell in the frame's state", str(found["blighted"]), taken)]


def blight_kinds() -> list[Result]:
    """R6's content half: a kind that takes empty cells walks each act's waves, its mark burning at least 1.5 s
    before it lands, its cells taken for two cleared waves (tests/test_blight.py plays the engine)."""
    blighters = {key for key, kind in MONSTERS.items() if kind.blight is not None}
    out = []
    for act, keys in ACTS.items():
        walked = {g.kind for key in keys for wave in LOCATIONS[key].waves for g in wave.groups}
        mine = sorted(blighters & walked)
        spec = all(MONSTERS[key].blight is not None and MONSTERS[key].blight.telegraph >= 1.5
                   and MONSTERS[key].blight.waves == 2 for key in mine)
        out.append(Result("R6", f"act {act}'s cell-takers", ", ".join(mine) or "none", bool(mine) and spec))
    return out


def power_table() -> list[Result]:
    """G3.4: at every location, the reference board's damage per second covers the last
    wave's life per second. The reference board is the best board the location's gold buys: at most 8 towers
    and not all rank III, each buy maximizing the worst walked route's supply over demand (Hooks buy pulls,
    not damage). Each route's demand is its monsters' life over their seconds inside the covered stretch;
    each tower's supply is its felt damage per second against the last wave's mix, weighed by life. Chains,
    splashes and venom beyond one stack are left out, so the board is weaker here than in a fight. The row
    says whether gold or cells bind."""
    out = []
    for key in ORDER:
        location = LOCATIONS[key]
        mix = _last_mix(location)
        total = sum(mix.values())
        shares = {kind: life / total for kind, life in mix.items()}
        gold = BALANCE.starting_gold() + sum(BALANCE.wave_income(i) for i in range(len(location.waves)))
        worth = worth_map(location.level, traffic(location))
        kinds = [k for k in location.arsenal.towers if TOWERS[k].attack in ATTACKS and TOWERS[k].attack != "hook"]
        routes = [r for r in location.level.routes
                  if any(g.route == r.key for g in location.waves[-1].groups)]
        cells: list = []
        for route in routes:
            top = sorted(worth, key=lambda c: (_cover_len(route, c, REFERENCE_REACH), worth[c]), reverse=True)
            cells += [c for c in top[:6] if _cover_len(route, c, REFERENCE_REACH) > 0]
        cells = list(dict.fromkeys(cells))
        board: dict = {}
        left = gold
        while True:
            offer = _best_buy(location, routes, board, cells, kinds, shares, left)
            if offer is None:
                break
            (cell, placed), price = offer
            board[cell] = placed
            left -= price
        binds = "gold" if left < min(TOWERS[k].levels[0].cost for k in kinds) else "cells"
        route, worst = min(_ratios(location, routes, board, shares).items(), key=lambda kv: kv[1])
        out.append(Result("G3.4", f"{key}: worst route's supply over demand ({route}; {binds} binds)",
                          f"{worst:.2f}", worst >= 1.0))
    return out


def _last_mix(location: Location) -> dict[str, float]:
    """The last wave's kinds with their life."""
    wave = location.waves[-1]
    mix: dict[str, float] = {}
    for group in wave.groups:
        life = MONSTERS[group.kind].hp * group.count
        mix[group.kind] = mix.get(group.kind, 0.0) + life
    return mix


def _felt_dps(kind: str, rank: int, shares: dict[str, float]) -> float:
    """A rank's damage per second against a kind mix: each hit as felt, weighed by the kind's life share."""
    tower, level = TOWERS[kind], TOWERS[kind].levels[rank]
    return sum(share * level.rate * felt_hit(level.damage, tower.element, MONSTERS[monster])
               for monster, share in shares.items())


def _best_buy(location: Location, routes: list, board: dict, cells: list, kinds: list[str],
              shares: dict[str, float], gold: int):
    """The buy that most raises the worst walked route's ratio: a new rank-I tower of the best damage per
    gold, or a rank up (at most 8 towers, at most seven at rank III); None when nothing affordable helps."""
    base = min(_ratios(location, routes, board, shares).values())
    new_kind = max(kinds, key=lambda k: _felt_dps(k, 0, shares) / TOWERS[k].levels[0].cost)
    tops = sum(1 for placed in board.values() if placed[1] == 2)
    best = None
    for cell in cells:
        if cell in board:
            kind, rank = board[cell]
            if rank == 2 or (rank == 1 and tops >= 7):
                continue
            price = TOWERS[kind].levels[rank + 1].cost
            if price > gold:
                continue
            trial = {**board, cell: (kind, rank + 1)}
        else:
            if len(board) >= 8:
                continue
            price = TOWERS[new_kind].levels[0].cost
            if price > gold:
                continue
            trial = {**board, cell: (new_kind, 0)}
        if base <= 0:
            key = _covered_key(location, routes, trial, shares)
            if best is None or key > best[0]:
                best = (key, price, (cell, trial[cell]))
            continue
        worst = min(_ratios(location, routes, trial, shares).values())
        if worst > base + 1e-9 and (best is None or (worst, -price) > (best[0], -best[1])):
            best = (worst, price, (cell, trial[cell]))
    if base <= 0:
        if best is None or best[0] <= _covered_key(location, routes, board, shares):
            return None
        return best[2], best[1]
    return None if best is None else (best[2], best[1])


def _covered_key(location: Location, routes: list, board: dict, shares: dict[str, float]) -> tuple:
    """How much of the walked routes a board reaches: routes covered, then tiles covered."""
    cover = _cover(location, routes, board, shares)
    return (sum(1 for supply, spans in cover.values() if spans > 0),
            round(sum(spans for supply, spans in cover.values()), 6))


def _ratios(location: Location, routes: list, board: dict, shares: dict[str, float]) -> dict[str, float]:
    """Each walked route's supply over demand: the towers covering it deal their felt damage per second;
    its monsters' life arrives over their seconds inside the covered stretch."""
    wave = location.waves[-1]
    cover = _cover(location, routes, board, shares)
    ratios = {}
    for route in routes:
        groups = [g for g in wave.groups if g.route == route.key]
        supply, covered = cover[route.key]
        demand = sum(MONSTERS[g.kind].hp * g.count
                      * MONSTERS[g.kind].speed / covered for g in groups) if covered else float("inf")
        ratios[route.key] = supply / demand if demand else 1.0
    return ratios or {"main": 0.0}


def _cover(location: Location, routes: list, board: dict, shares: dict[str, float]) -> dict[str, tuple]:
    """Each walked route's supply and covered tiles: the towers covering it, and the union they reach."""
    found: dict[str, tuple] = {}
    for route in routes:
        spans: list = []
        supply = 0.0
        for cell, (kind, rank) in board.items():
            reached = route.coverage(cell, TOWERS[kind].levels[rank].range)
            if reached:
                spans += reached
                supply += _felt_dps(kind, rank, shares)
        found[route.key] = (supply, _union_length(spans))
    return found


def _cover_len(route, cell: tuple[int, int], reach: float) -> float:
    return _union_length(route.coverage(cell, reach))


def _union_length(spans: list[tuple[float, float]]) -> float:
    total, end = 0.0, -1.0
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def adapt_sets() -> set[frozenset[str]]:
    """The planned player's draft tower-kind sets over the harness seeds, its tree reading each seed's takes."""
    from hellward.sim.players.planned import Planned  # noqa: E402
    from tools.adapt import LOCATION as ADAPT_LOCATION  # noqa: E402
    from tools.adapt import SEEDS as ADAPT_SEEDS  # noqa: E402
    from tools.adapt import takes as adapt_takes  # noqa: E402

    location = LOCATIONS[ADAPT_LOCATION]
    sigils = 3 * ORDER.index(ADAPT_LOCATION)
    sets = set()
    for seed in ADAPT_SEEDS:
        player = Planned()
        player.draft(location, sigils, adapt_takes(seed))
        sets.add(frozenset(s[1] for s in player.plan.steps if s[0] == "build"))
    return sets


def relic_builds() -> Result:
    """M5: different runs end in different builds, pushed by their relics. Draft sets stand for end-builds:
    tools/adapt.py plays the same seeds out and its ends match these drafts kind for kind."""
    sets = adapt_sets()
    return Result("M5", "distinct tower sets over 10 seeds of the strongest bot",
                  f"{len(sets)}/10 draft sets (ends: tools/adapt.py)", len(sets) >= 6)


def bot_table() -> Result:
    """T2: a middling bot and a strong bot whose tree policy reads its relics, and a Kit corpus feeding
    the per-location tools."""
    import ast

    from hellward.sim.players.apprentice import Apprentice  # noqa: E402
    from tools.corpus import FEEDERS  # noqa: E402

    middling = isinstance(Apprentice().draft(LOCATIONS["caves"], 12), frozenset)
    sets = adapt_sets()
    reads = len(sets) >= 2
    fed = []
    for name in FEEDERS:
        tree = ast.parse((Path(__file__).parent / f"{name}.py").read_text())
        if any(isinstance(node, ast.ImportFrom) and node.module in ("tools.corpus", "corpus")
               for node in ast.walk(tree)):
            fed.append(name)
    value = f"middling apprentice {'reads' if middling else 'missing'}; planned reads relics ({len(sets)} sets); " \
        f"corpus feeds {len(fed)}/{len(FEEDERS)} ({', '.join(fed)})"
    return Result("T2", "middling and strong bots; the strong one reads relics; a Kit corpus",
                  value, middling and reads and len(fed) == len(FEEDERS))


CHECKS: tuple[Callable[[], Result | list[Result]], ...] = (
    bodies_per_wave, three_ranks, number_scale, rank_economy, no_dispel, hymn_seeks, tower_kinds, real_estate,
    worth_and_cells, blight_kinds, power_table, armor_duels, verb_rates, verb_costs, tower_verbs, verb_set,
    relic_pool, relic_builds, bot_table, xp_bar,
)

NOT_YET = (
    "G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G2.2", "G2.5", "G2.6", "G3.1", "G3.2", "G3.3",
    "M1", "M2", "M3", "M5", "M7", "M10", "S2", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8",
    "R4", "T2", "T4",
)


def results() -> list[Result]:
    out: list[Result] = []
    for check in CHECKS:
        found = check()
        out.extend(found if isinstance(found, list) else [found])
    measured = {r.id for r in out}
    out.extend(Result(id, "not measured yet", "", None) for id in NOT_YET if id not in measured)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, help="also write the results here")
    args = parser.parse_args()
    rows = results()
    for r in rows:
        mark = {True: "MET ", False: "MISS", None: "    "}[r.met]
        print(f"{mark} {r.id:<6} {r.what:<48} {r.value}")
    met = sum(1 for r in rows if r.met)
    missed = sum(1 for r in rows if r.met is False)
    print(f"\n{met} met, {missed} missed, {sum(1 for r in rows if r.met is None)} not measured yet")
    if args.json:
        args.json.write_text(json.dumps([r.__dict__ for r in rows], indent=1))


if __name__ == "__main__":
    main()

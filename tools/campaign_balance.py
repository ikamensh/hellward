"""The campaign's balance table: what the locations are tuned against (docs/campaign.md,
"Tuning by simulation").

    python3 ~/saga/tools/slot.py -- caffeinate -i uv run python tools/campaign_balance.py --margin --leaders --out DIR
    uv run python tools/campaign_balance.py --players ordinary --seeds 1000-1003 --out DIR     # a quick look

Every scripted player (:data:`hellward.sim.players.PLAYERS`) defends every location in the campaign's order,
over the evaluation seeds, against the smart leaders, through a person's hands
(:func:`hellward.sim.players.hands.defend`). A whole table is thousands of defences: run it through the
machine's slot queue, as above.

* **Sigils.** Each defence gets the sigils the best player has earned by then: the sum of B*'s median
  sigils on the earlier locations. So the locations are played in order, and unless ``--sigils N`` gives
  every defence the same budget, what is played must start the campaign (Tristram on).
* **B\\*** at a location is the player with the best median lives; ties go to more wins, then to
  more mean lives. The table marks it.
* ``--margin``: M, the largest factor on every monster's life at which B* still wins, bisected to 2% between
  0.4 and 4 on each of the first 8 seeds; the table gives the median. The factor leaves the spells as they
  are: M is what raising the location's life would give.
* ``--leaders``: B* with its skills against the smart leaders and against random ones, the lives uncapped (as
  ``balance.py`` counts them). Leader impact is the lives lost to smart minus those lost to random, and that as a
  share of the lives lost to smart.

The other columns: wins of N and the median and fewest lives kept; curse-seconds held on towers per leader
spawned; chants broken, the share of all the chants the leaders began that a spell broke (a broken pondering is
not a chant); spells cast per defence (C Cleanse, S Smite, M Meteor, O Frozen Orb); seconds per defence the mana
orb sat full; the 95th percentile of the leaders' decision time. Under the table every target of the design is
PASS, FAIL or open (nothing failed, something unmeasured).
``--out DIR`` keeps the table as ``table.md`` and every defence as a JSON line in ``runs.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from concurrent.futures import Executor, ProcessPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hellward.sim import fastsim  # noqa: E402

# The compiled simulation, before anything imports the rules: in the main process and in every worker (a spawned worker
# imports this module again as __mp_main__), unless HELLWARD_INTERPRETED is set. Every run records what it ran on.
BUILD = "source"
if __name__ in ("__main__", "__mp_main__"):
    _built = fastsim.activate()
    BUILD = _built.name if _built is not None else "source"

from hellward.sim import campaign, planner  # noqa: E402
from hellward.sim.content import MONSTERS, START_LIVES  # noqa: E402
from hellward.sim.model import Planner, World  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.hands import defend, react_for  # noqa: E402

SEEDS = "1000-1019"                    # the evaluation seeds; offline planning may use 0-99
UNCAPPED = 10_000                      # the sanctuary's life in the leader A/B, so every life lost counts
MARGIN_SEEDS = 8
MARGIN_RANGE = (0.4, 4.0)              # taken as a win and a fall without playing them
MARGIN_STEP = 1.02
LEADERS = {"smart": lambda seed: planner.smart, "random": planner.RandomLeaders}
EASY = ("tristram", "graveyard")       # they teach, and may be easy
BELOW = ("catacombs", "caves", "hells_gate")   # the ordinary defender loses at least one of these
SPELL_LETTERS = {"cleanse": "C", "smite": "S", "meteor": "M", "orb": "O"}
COLUMNS = ("location", "player", "sigils", "wins/N", "median lives", "fewest", "M", "leader impact",
           "curse-s/leader", "chants broken", "spells", "mana capped s", "decision p95 ms",
           "towers/curse")

VETERAN_TARGETS_ACT1 = (1.5, 1.4, 1.3, 1.2, 1.15, 1.1)
VETERAN_TARGETS_ACT2 = (1.4, 1.3, 1.2, 1.15, 1.1, 1.05)
VETERAN_TOLERANCE = 0.07


# -- One defence ----------------------------------------------------------------------------------------------------


class Timed:
    """A leader policy that keeps how long each of its decisions took, in milliseconds."""

    def __init__(self, policy: Planner) -> None:
        self.policy = policy
        self.ms: list[float] = []

    def __call__(self, world: World, leader_id: int) -> object:
        start = time.perf_counter()
        handle = self.policy(world, leader_id)
        self.ms.append((time.perf_counter() - start) * 1000)
        return handle


def leaders_spawned(world: World) -> int:
    """Leaders that walked onto the map: every one in the waves called, but those still to come."""
    called = [g.kind for w in world.waves[:world.wave + 1] for g in w.groups for _ in range(g.count)]
    waiting = [kind for _, kind in world.schedule]
    return sum(MONSTERS[k].leader is not None for k in called) - sum(MONSTERS[k].leader is not None for k in waiting)


def play(player: str, location: str, seed: int, sigils: int, *, leaders: str = "smart",
         life: float = 1.0, lives: int | None = None, curse_scale: float = 1.0) -> dict:
    """One defence, and everything the table and the tuning read from it. ``life`` multiplies the location's own life
    factor, the tuning knob (the spells grow with it), as tools/margin.py does."""
    place = campaign.LOCATIONS[location]
    policy = Timed(LEADERS[leaders](seed))
    started = time.process_time()
    world, record = defend(replace(place, life=place.life * life), PLAYERS[player](seed), seed=seed, sigils=sigils,
                           planner=policy, lives=lives, curse_scale=curse_scale)
    start_lives = START_LIVES if lives is None else lives
    caught = record.towers_caught
    return {
        "player": player, "build": BUILD, "location": location, "seed": seed,
        "react": round(react_for(seed), 4), "skills": sorted(record.skills), "leaders": leaders, "life": life,
        "sigils": sigils, "start_lives": start_lives, "outcome": world.outcome, "lives": world.lives,
        "lost": start_lives - world.lives,
        "earned": campaign.sigils(world.outcome, world.lives) if lives is None else None,
        "waves": world.wave + 1, "game_seconds": round(world.time, 2),
        "leaks": [record.leaks[w] for w in range(len(place.waves))],
        "spells": dict(record.spells), "mana_capped": round(record.mana_capped, 2),
        "chants": record.chants, "broken": record.broken, "broken_chants": record.broken_chants,
        "landed": record.landed, "warded": record.warded, "fizzled": record.fizzled,
        "curse_seconds": round(record.curse_seconds, 2), "leaders_spawned": leaders_spawned(world),
        "towers_per_curse": round(sum(caught) / len(caught), 2) if caught else None,
        "decide_ms": [round(ms, 3) for ms in policy.ms], "cpu_seconds": round(time.process_time() - started, 3),
    }


def margin(player: str, location: str, seed: int, sigils: int, curse_scale: float = 1.0,
           leaders: str = "smart") -> tuple[float, list[dict]]:
    """The largest factor on the location's life at which the player still wins this seed, to 2%, and its runs."""
    low, high = MARGIN_RANGE
    runs = []
    while high / low > MARGIN_STEP:
        mid = math.sqrt(low * high)
        run = play(player, location, seed, sigils, leaders=leaders, life=mid, curse_scale=curse_scale)
        runs.append(run)
        if run["outcome"] == "victory":
            low = mid
        else:
            high = mid
    return low, runs


# -- The campaign, in order -----------------------------------------------------------------------------------------


@dataclass
class Stage:
    """One location: the sigils it was played with, its runs, B*, and B*'s own measures."""

    location: str
    sigils: int
    runs: list[dict]
    best: str
    margins: list[float] = field(default_factory=list)
    margin_runs: list[dict] = field(default_factory=list)
    uncapped: dict[str, list[dict]] = field(default_factory=dict)   # B* against each leader policy, lives uncapped
    corner_m_cs0: list[float] = field(default_factory=list)
    corner_m_cs1: list[float] = field(default_factory=list)
    vet_m_random: list[float] = field(default_factory=list)
    vet_m_smart: list[float] = field(default_factory=list)


def campaign_order() -> list[str]:
    return list(campaign.ORDER)


def best(runs: list[dict], players: list[str]) -> str:
    """B*: the best median lives; ties go to more wins, then to more mean lives."""
    def standing(player: str) -> tuple[float, int, float]:
        mine = [r for r in runs if r["player"] == player]
        lives = [r["lives"] for r in mine]
        return statistics.median(lives), sum(r["outcome"] == "victory" for r in mine), statistics.mean(lives)
    return max(players, key=standing)


def play_campaign(pool: Executor, players: list[str], stages: list[str], seeds: list[int],
                  sigils: int | None) -> list[Stage]:
    """Every player on every stage in order, each with the budget B* has earned before it (or ``sigils``)."""
    done = []
    earned = 0
    for location in stages:
        budget = earned if sigils is None else sigils
        started = time.perf_counter()
        jobs = [(p, location, seed, budget) for p in players for seed in seeds]
        runs = list(pool.map(play, *zip(*jobs)))
        stage = Stage(location, budget, runs, best(runs, players))
        earned += statistics.median_low(r["earned"] for r in runs if r["player"] == stage.best)
        note(f"{location}: {len(runs)} defences with {budget} sigils, B* {stage.best} "
             f"({time.perf_counter() - started:.0f} s)")
        done.append(stage)
    return done


def measure_best(pool: Executor, stages: list[Stage], seeds: list[int], *, margins: bool, leaders: bool) -> None:
    """B*'s margin and the leader A/B on every stage, all at once."""
    pending = []
    for s in stages:
        if margins:
            pending += [(s, "margin", pool.submit(margin, s.best, s.location, seed, s.sigils, 1.0))
                        for seed in seeds[:MARGIN_SEEDS]]
            # Also measure corner at curse_scale 0 and 1, veteran against random/smart
            if "corner" in PLAYERS:
                pending += [(s, "margin_cs0", pool.submit(margin, "corner", s.location, seed, s.sigils, 0.0))
                            for seed in seeds[:MARGIN_SEEDS]]
                pending += [(s, "margin_cs1", pool.submit(margin, "corner", s.location, seed, s.sigils, 1.0))
                            for seed in seeds[:MARGIN_SEEDS]]
            if "veteran" in PLAYERS:
                pending += [(s, "margin_vet_random", pool.submit(margin, "veteran", s.location, seed, s.sigils, 1.0, "random"))
                            for seed in seeds[:MARGIN_SEEDS]]
                pending += [(s, "margin_vet_smart", pool.submit(margin, "veteran", s.location, seed, s.sigils, 1.0, "smart"))
                            for seed in seeds[:MARGIN_SEEDS]]
        if leaders:
            pending += [(s, policy, pool.submit(play, s.best, s.location, seed, s.sigils, leaders=policy,
                                                lives=UNCAPPED, curse_scale=1.0)) for policy in LEADERS for seed in seeds]
    started = time.perf_counter()
    for s, kind, future in pending:
        if kind == "margin":
            m, runs = future.result()
            s.margins.append(m)
            s.margin_runs += runs
        elif kind == "margin_cs0":
            m, _ = future.result()
            if not hasattr(s, "corner_m_cs0"):
                s.corner_m_cs0 = []
            s.corner_m_cs0.append(m)
        elif kind == "margin_cs1":
            m, _ = future.result()
            if not hasattr(s, "corner_m_cs1"):
                s.corner_m_cs1 = []
            s.corner_m_cs1.append(m)
        elif kind == "margin_vet_random":
            m, _ = future.result()
            if not hasattr(s, "vet_m_random"):
                s.vet_m_random = []
            s.vet_m_random.append(m)
        elif kind == "margin_vet_smart":
            m, _ = future.result()
            if not hasattr(s, "vet_m_smart"):
                s.vet_m_smart = []
            s.vet_m_smart.append(m)
        else:
            s.uncapped.setdefault(kind, []).append(future.result())
    if pending:
        note(f"B*'s margin and leader A/B: {len(pending)} jobs ({time.perf_counter() - started:.0f} s)")


# -- The table ------------------------------------------------------------------------------------------------------


def ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def p95(values: list[float]) -> float | None:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None


def impact(stage: Stage) -> tuple[float, float | None]:
    """Lives lost to the smart leaders minus those lost to random ones, and that as a share of those lost to smart."""
    smart = statistics.mean(r["lost"] for r in stage.uncapped["smart"])
    delta = smart - statistics.mean(r["lost"] for r in stage.uncapped["random"])
    return delta, ratio(delta, smart)


def rows(stages: list[Stage], players: list[str]) -> list[dict]:
    """A row per player on every stage, with B*'s margin and leader impact on its own row."""
    out = []
    for s in stages:
        for player in players:
            runs = [r for r in s.runs if r["player"] == player]
            lives = [r["lives"] for r in runs]
            won = [r["lives"] for r in runs if r["outcome"] == "victory"]
            mine = player == s.best
            held = sum(r["curse_seconds"] for r in runs)
            caught = [r["towers_per_curse"] for r in runs if r.get("towers_per_curse") is not None]
            towers_per_curse = statistics.mean(caught) if caught else None
            row = {
                "location": s.location, "player": player, "best": mine,
                "sigils": s.sigils, "wins": len(won), "n": len(runs), "median": statistics.median(lives),
                "fewest": min(lives), "lives_in_wins": statistics.median(won) if won else None,
                "M": statistics.median(s.margins) if mine and s.margins else None,
                "impact": impact(s) if mine and s.uncapped else None,
                "curse_per_leader": ratio(held, sum(r["leaders_spawned"] for r in runs)),
                "broken_share": ratio(sum(r["broken_chants"] for r in runs), sum(r["chants"] for r in runs)),
                "spells": {k: sum(r["spells"].get(k, 0) for r in runs) / len(runs) for k in SPELL_LETTERS},
                "mana_capped": statistics.mean(r["mana_capped"] for r in runs),
                "p95_ms": p95([ms for r in runs for ms in r["decide_ms"]]),
                "towers_per_curse": towers_per_curse,
            }
            if mine and s.margins:
                row["M_cs1"] = statistics.median(s.margins)
            if player == "corner" and s.corner_m_cs0:
                row["M_cs0"] = statistics.median(s.corner_m_cs0)
            if player == "corner" and s.corner_m_cs1:
                row["M_cs1"] = statistics.median(s.corner_m_cs1)
            if player == "veteran" and s.vet_m_random:
                row["M_random"] = statistics.median(s.vet_m_random)
            if player == "veteran" and s.vet_m_smart:
                row["M_smart"] = statistics.median(s.vet_m_smart)
            out.append(row)
    return out


def number(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def percent(share: float | None) -> str:
    return "—" if share is None else f"{100 * share:.0f}%"


def show_margin(m: float | None) -> str:
    low, high = MARGIN_RANGE
    if m is None:
        return "—"
    if m <= low:
        return f"<{low * MARGIN_STEP:.2f}"   # it fell at every factor tried
    if m * MARGIN_STEP >= high:
        return f">{m:.2f}"                  # it won at every factor tried
    return f"{m:.2f}"


def show_impact(impact: tuple[float, float | None] | None) -> str:
    return "—" if impact is None else f"{impact[0]:+.1f} ({percent(impact[1])})"


def cells(row: dict) -> list[str]:
    spells = " ".join(f"{SPELL_LETTERS[k]}{n:.1f}" for k, n in row["spells"].items() if n)
    towers_curse = number(row.get("towers_per_curse"), 2) if row.get("towers_per_curse") is not None else "—"
    return [
        row["location"], row["player"] + (" B*" if row["best"] else ""), str(row["sigils"]),
        f"{row['wins']}/{row['n']}", f"{row['median']:g}", str(row["fewest"]), show_margin(row["M"]),
        show_impact(row["impact"]), number(row["curse_per_leader"]), percent(row["broken_share"]),
        spells or "—", number(row["mana_capped"], 0), number(row["p95_ms"], 0), towers_curse,
    ]


def markdown(header: list[str], body: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(r) + " |" for r in body]


# -- The targets ----------------------------------------------------------------------------------------------------


class Verdict:
    """One target of the design, judged over the rows it covers."""

    def __init__(self, target: str) -> None:
        self.target = target
        self.played = False
        self.failed: dict[str, list[str]] = {}
        self.unmeasured: list[str] = []

    def check(self, where: str, ok: bool | None, what: str, missing: str = "") -> None:
        self.played = True
        if ok is None:
            if missing not in self.unmeasured:
                self.unmeasured.append(missing)
        elif not ok:
            self.failed.setdefault(where, []).append(what)

    def result(self) -> list[str]:
        if not self.played:
            return [self.target, "—", "not played"]
        failed = [f"{where}: {', '.join(whats)}" for where, whats in self.failed.items()]
        detail = "; ".join(failed + ([f"unmeasured: {', '.join(self.unmeasured)}"] if self.unmeasured else []))
        verdict = "FAIL" if self.failed else "open" if self.unmeasured else "PASS"
        return [self.target, verdict, detail or "all met"]


def within(value: float | None, low: float, high: float = math.inf) -> bool | None:
    return None if value is None else low <= value <= high


def targets(table: list[dict]) -> list[list[str]]:
    ACT1, ACT2 = campaign.ACTS[1], campaign.ACTS[2]
    veteran_m = Verdict("Veteran's M per location: Act I ≈1.5,1.4,1.3,1.2,1.15,1.1 (±0.07); Act II ≈1.4,1.3,1.2,1.15,1.1,1.05 (±0.07)")
    bstar_min = Verdict("B* (best of warden, planned, adaptive) M ≥ 1.2 everywhere")
    apprentice_early = Verdict("Apprentice wins Act I's first two locations")
    corner_falloff = Verdict("Corner's M falls ≥ 20% from curse_scale 0 to 1 and sits below Veteran's")
    veteran_leader_gap = Verdict("From each act's third location on, Veteran's M against random ≥ 1.10× against smart")
    veteran_towers_curse = Verdict("Mean towers caught per landed curse for Veteran ≈ 2")
    
    for row in table:
        where = row["location"]
        if row["player"] == "veteran":
            if where in ACT1:
                idx = ACT1.index(where)
                target = VETERAN_TARGETS_ACT1[idx]
                veteran_m.check(where, within(row.get("M_smart"), target - VETERAN_TOLERANCE, target + VETERAN_TOLERANCE),
                               f"M {show_margin(row.get('M_smart'))} vs target {target:.2f}", "M (--margin)")
            elif where in ACT2:
                idx = ACT2.index(where)
                target = VETERAN_TARGETS_ACT2[idx]
                veteran_m.check(where, within(row.get("M_smart"), target - VETERAN_TOLERANCE, target + VETERAN_TOLERANCE),
                               f"M {show_margin(row.get('M_smart'))} vs target {target:.2f}", "M (--margin)")
        if row["best"] and row["M"] is not None:
            bstar_min.check(where, row["M"] >= 1.2, f"B* M {show_margin(row['M'])}", "M (--margin)")
        if row["player"] == "apprentice":
            if where in ACT1[:2]:
                apprentice_early.check(where, row["wins"] == row["n"], f"won {row['wins']}/{row['n']}")
        if row["player"] == "corner" and row.get("M_cs0") is not None and row.get("M_cs1") is not None:
            falloff = 1.0 - row["M_cs1"] / row["M_cs0"]
            corner_falloff.check(where, falloff >= 0.2, f"falloff {falloff:.0%} < 20%", "M at curse_scale 0 and 1")
        if row["player"] == "veteran" and row.get("M_random") is not None and row.get("M_smart") is not None:
            if where in ACT1[2:] or where in ACT2[2:]:
                ratio = row["M_random"] / row["M_smart"] if row["M_smart"] > 0 else 0
                veteran_leader_gap.check(where, ratio >= 1.10, f"ratio {ratio:.2f} < 1.10", "M against random/smart")
        if row["player"] == "veteran" and row.get("towers_per_curse") is not None:
            veteran_towers_curse.check(where, within(row["towers_per_curse"], 1.5, 2.5),
                                       f"towers/curse {row['towers_per_curse']:.2f}", "towers_per_curse (--margin)")
    sharp = ["The planner stays sharp: share of the best ≥ 0.85 on every location", "—", "tools/curse_quality.py"]
    return [veteran_m.result(), bstar_min.result(), apprentice_early.result(), corner_falloff.result(),
            veteran_leader_gap.result(), veteran_towers_curse.result(), sharp]


def ordinary_loses(table: list[dict]) -> list[str]:
    target = "The ordinary defender loses at least one of the Catacombs, the Caves and Hell's Gate"
    mine = [r for r in table if r["player"] == "ordinary" and r["location"] in BELOW]
    lost = [f"{r['location']} {r['n'] - r['wins']}/{r['n']}" for r in mine if r["wins"] < r["n"]]
    if lost:
        return [target, "PASS", "lost " + ", ".join(lost)]
    if len(mine) == len(BELOW):
        return [target, "FAIL", "it won every one of them"]
    return [target, "open" if mine else "—", "not all three played"]


# -- The command ----------------------------------------------------------------------------------------------------


def note(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def commit() -> str:
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                           text=True, check=True)
    return head.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")


def seed_list(text: str) -> list[int]:
    """Seeds as ``1000-1019`` or ``1,5,9`` or both."""
    out: list[int] = []
    for part in text.split(","):
        first, _, last = part.partition("-")
        out += range(int(first), int(last or first) + 1)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--players", default=",".join(PLAYERS), help="default: every registered player")
    parser.add_argument("--locations", default=",".join(campaign.ORDER))
    parser.add_argument("--seeds", default=SEEDS, help=f"default {SEEDS}")
    parser.add_argument("--sigils", type=int, help="every defence gets this many, instead of what B* has earned")
    parser.add_argument("--margin", action="store_true", help="bisect B*'s margin M on every location")
    parser.add_argument("--leaders", action="store_true", help="B* against smart and random leaders, lives uncapped")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True, help="directory for table.md and runs.jsonl")
    args = parser.parse_args(argv)
    players, locations = args.players.split(","), args.locations.split(",")
    for asked, known in ((players, PLAYERS), (locations, campaign.LOCATIONS)):
        if set(asked) - set(known):
            parser.error(f"unknown: {', '.join(sorted(set(asked) - set(known)))}; known: {', '.join(known)}")
    stages = [loc for loc in campaign_order() if loc in locations]
    if args.sigils is None and stages != campaign_order()[:len(stages)]:
        parser.error("the sigils follow the campaign: play it from its start (Tristram on) or give --sigils N")
    seeds = seed_list(args.seeds)
    head = commit()
    started = time.perf_counter()
    with ProcessPoolExecutor(args.jobs) as pool:
        played = play_campaign(pool, players, stages, seeds, args.sigils)
        measure_best(pool, played, seeds, margins=args.margin, leaders=args.leaders)
    table = rows(played, players)
    lines = [
        "# Campaign balance", "",
        f"Commit {head}, simulation {BUILD}; players {', '.join(players)}; seeds {args.seeds} ({len(seeds)}); "
        f"sigils {'fixed at ' + str(args.sigils) if args.sigils is not None else 'as B* earns them'}; "
        f"{time.perf_counter() - started:.0f} s with {args.jobs} jobs.", "",
        *markdown(list(COLUMNS), [cells(r) for r in table]), "",
        "B* has the best median lives. M: median over the first 8 seeds of the largest life factor B* still wins at "
        "(the spells do not grow with it). "
        "Leader impact: lives lost to smart minus random leaders, uncapped, and its share of those lost to smart. "
        "Chants broken: of all the chants begun. Spells per defence: C Cleanse, S Smite, M Meteor, O Frozen Orb.", "",
        "## Targets", "",
        *markdown(["target", "result", "detail"], targets(table)),
    ]
    text = "\n".join(lines) + "\n"
    print(text)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "table.md").write_text(text)
    with (args.out / "runs.jsonl").open("w") as f:
        for s in played:
            uncapped = [r for runs in s.uncapped.values() for r in runs]
            for kind, runs in (("campaign", s.runs), ("margin", s.margin_runs), ("leaders", uncapped)):
                for r in runs:
                    f.write(json.dumps({"run": kind, "commit": head, **r}) + "\n")


if __name__ == "__main__":
    main()

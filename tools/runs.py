"""Full runs through the campaign, for stage 3's exit criteria.

Each run starts a :class:`~hellward.run.Run`, deals every location's Kit, defends it with a bot, and settles
the result back into the run: the pool and gold carried on, the sigils and points, the goals drawn and judged.
Two modes: real runs (G3.1: the middling bot wins few, the strong bot most) and ``--immortal`` (the pool cannot
end the run, but lost life is counted: G3.2's gold and levels per act, M3's goal rates, the tree's opened share).
Every bot's Kit at every location is written as the corpus ``<out>/corpus/``, which the per-location tools take
their Kits from; ``summary.json`` holds every run for the scorecard.

The middling bot is the warden playing the stored steps with redrafted skills: the book's shape at a full
purse, a MIDDLING_SKIP share fumbled, played with veteran hands; the strong bot plays the stored plans whole.
Both summon bonus waves by one rule on
what a person sees: the last wave clean, the pool comfortable, the wager in hand, the margin felt
over the pack's life, at most three a location, the stake by the pool's comfort. While the waves
stay clean the coming break's wager is kept back for it — deep in from strength, shallower only from
a purse holding twice — as a person saving for a wager would. ``--nobonus`` stills the rule, for the
wager's worth against the same runs.

It runs the compiled simulation (:mod:`hellward.fastsim`, built on first use), which plays as the source does;
``HELLWARD_INTERPRETED=1`` runs the source instead. ``HELLWARD_NOPURSUIT`` (a comma list of
``family,gate,hymn,bonus``) stills those goal pursuits, for the ablation of what the chasing costs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes, not as a library
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.run import HYMN_N, MET, Run, camp, finish, kit, learn, observe_world, start, take_relic  # noqa: E402
from hellward.run.goals import Hymn  # noqa: E402
from hellward.sim import planner, skills as tree  # noqa: E402
from hellward.sim.balance import BALANCE  # noqa: E402
from hellward.sim.bonus import EARLY, UNITS, draw  # noqa: E402
from hellward.sim.campaign import ACT_ENDS, LOCATIONS, ORDER  # noqa: E402
from hellward.sim.model import Refused  # noqa: E402
from hellward.sim.players.hands import defend, reference_kit  # noqa: E402
from hellward.sim.players.warden import Warden, draft_skills  # noqa: E402

BOTS = ("middling", "strong")
IMMORTAL_LIVES = 10 ** 9   # the pool cannot empty, but every life lost is counted
POOL_STAKES = (20, 20, 18)   # the pool for stakes 3, 2 and 1, both bots: boards differ, comfort does not
BONUS_CAP = 3   # summons a location at most
MARGIN = {"strong": 0.4, "middling": 0.25}   # the felt margin by bot: the build's worth over
                             # the pack's life, below which no stake is taken (the middling bot feels luckier)


def _stored_sigils() -> dict[str, int]:
    """The sigils that play each location's stored plan, from the warden's plan book."""
    book = Path(__file__).resolve().parent.parent / "hellward/sim/players/plans/warden.json"
    plans = json.loads(book.read_text())
    found: dict[str, int] = {}
    for key in plans:
        location, sigils = key.rsplit("/", 1)
        found[location] = max(int(sigils), found.get(location, -1))
    return found


MIDDLING_SKIP = 0.13   # the middling bot's fumbled share of its redrafted skills (0: 29/30, 0.1: 9, 0.13: 5, 0.15: 3, 0.3: 0)


def _player(bot: str, seed: str = "") -> Warden:
    if bot == "middling":
        # the searched builds read worse and played slower: fumbled drafts, veteran hands
        skip = float(env) if (env := os.environ.get("HELLWARD_SKIP")) is not None else MIDDLING_SKIP
        return Warden(redraft_skills=True, skip=skip, seed=seed, reaction=(0.8, 1.2), aim_gap=1.0)
    return Warden()


SKILL_SHARE = {"strong": 1.0, "middling": 1.0}   # the stored purse's share the bot's skills spend


def _sigils(bot: str, run: Run, location: str, stored: dict[str, int]) -> int:
    share = float(env) if (env := os.environ.get("HELLWARD_SHARE")) is not None else SKILL_SHARE[bot]
    if location in stored:
        return stored[location] if bot == "strong" else int(share * stored[location])
    return int(share * (run.skill_points + tree.cost(run.learned)))


def _learn(run: Run, location: str) -> Run:
    """The camp's learning: the draft's skills within the run's points, top tier first."""
    total = run.skill_points + tree.cost(run.learned)
    for key in sorted(draft_skills(LOCATIONS[location], total) - run.learned,
                      key=lambda s: (tree.SKILLS[s].tier, s)):
        try:
            run = learn(run, key)
        except ValueError:
            continue
    return run


def _wager(stake: int) -> int:
    """The stake's wager in gold."""
    return UNITS[stake - 1] * BALANCE.income_unit()


def _pack_hp(location, stake: int, seed: int, index: int, repeats: int, wave: int) -> float:
    """The stake's pack's life to chew through, read from the break's preview."""
    return draw(location, stake, seed, index, repeats, wave).hp


def _pack_lives(location, stake: int, seed: int, index: int, repeats: int, wave: int) -> int:
    """The stake's pack's lives at risk: what the pool loses if it all leaks."""
    return draw(location, stake, seed, index, repeats, wave).lives


VETO_SPARE = 4   # lives the pool keeps past a pack's total failure: the waves after still tax


PURSUE_MARGIN = 0.30        # the pursued second stake's bar: fought lean, under the felt margin
PURSUE_DEEP = 3             # the pursued second stake goes from this wave on (from 0): never on a thin build
RICH_POOL = 25              # the pool that buys the dear pursuits: the family, the gate's rush


def _stake(bot: str, pool: int, leaked: bool, repeats: int, wave: int, gold: int,
           location, seed: int, index: int, spent: int, pursue: int = 0) -> int | None:
    """The bonus rule's stake, or no summon: the last wave clean, from the break after wave ``EARLY``
    on (the sim's gate, ``wave`` is the latest cleared, from 0), the pool comfortable for the stake,
    the wager in hand, the felt margin over the pack's life, at most a location's cap — and never
    a pack whose lives leave the pool under its spare. Pursuing the bonus goal (its stake),
    the second stake goes deep in on the pursuit's bar."""
    if leaked or repeats >= BONUS_CAP or wave + 1 < EARLY:
        return None
    for stake in (3, 2, 1):
        if pool < POOL_STAKES[3 - stake] or gold < _wager(stake):
            continue
        if pursue >= 2 and stake == 2 and wave >= PURSUE_DEEP:
            bar = PURSUE_MARGIN
        else:
            bar = MARGIN[bot]
        if spent < bar * _pack_hp(location, stake, seed, index, repeats, wave):
            continue
        if pool < _pack_lives(location, stake, seed, index, repeats, wave) + VETO_SPARE:
            continue
        return stake
    return None


def _reserve(bot: str, pool: int, leaked: bool, repeats: int, wave: int, gold: int,
             stakes: tuple[int, ...], location, seed: int, index: int, spent: int,
             pursue: int = 0) -> int:
    """The coming break's wager, held back for it: after a clean wave, from a wave whose break can
    summon, the top stake's wager the pool is comfortable with and the felt margin covers — deep in
    (wave 3 on) taken from strength, shallower only from a purse holding twice. Else nothing, and
    the gold all builds. ``wave`` is the wave being fought, from 0. Pursuing the bonus goal, the
    second stake's wager is held on the pursuit's bar, never ragged. A wager is never held
    for a pack whose lives leave the pool under its spare."""
    if leaked or repeats >= BONUS_CAP or wave < 1:
        return 0
    for stake in stakes:
        if pool < POOL_STAKES[3 - stake]:
            continue
        if wave < 3 and gold < 2 * _wager(stake):
            continue
        if pursue >= 2 and stake == 2 and wave >= PURSUE_DEEP:
            bar = PURSUE_MARGIN
        else:
            bar = MARGIN[bot]
        if spent < bar * _pack_hp(location, stake, seed, index, repeats, wave):
            continue
        if pool < _pack_lives(location, stake, seed, index, repeats, wave) + VETO_SPARE:
            continue
        return _wager(stake)
    return 0


def play_run(seed: int, bot: str, locations: tuple[str, ...], immortal: bool,
             out: Path | None, nobonus: bool = False, record_breaks: list | None = None,
             force_stake: int = 0, grant_wager: bool = False, force_pool: int = 0) -> dict:
    """One run: every location's Kit defended and settled. The summary is JSON-able."""
    run = start(seed)
    stored = _stored_sigils()
    summary: dict = {"seed": seed, "bot": bot, "immortal": immortal, "locations": {}, "goals": {},
                     "levels": [], "gold": {}, "reached": 0, "sim_seconds": 0.0, "summons": [],
                     "fights": [], "bonus_net": 0, "misfires": 0, "granted": 0,
                     "breaks": record_breaks if record_breaks is not None else [],
                     "wave_leaks": [] if record_breaks is not None else []}
    for key in locations:
        assert run.location.key == key, f"the run is at {run.location.key}, not {key}"
        played = kit(run)
        events: list = []
        state = {"leaks": 0, "last_clean": True, "repeats": 0, "pack": None, "pool": run.pool,
                 "fight_leaks": 0, "lives": IMMORTAL_LIVES if immortal else run.pool}
        player = _player(bot, f"{seed}/{key}")
        pursue = 0   # the drawn bonus goal's stake, when the run pursues it
        off = os.environ.get("HELLWARD_NOPURSUIT", "").split(",")
        for drawn in run.drawn:   # the lean and the leaders by standard play; the dear goals only when rich
            if drawn.key == "family" and "family" not in off and run.pool >= RICH_POOL:
                player.family_goal = drawn.arg
            elif drawn.key == "gate" and "gate" not in off and run.pool >= RICH_POOL:
                player.gate_rush = True
            elif drawn.key == "hymn" and "hymn" not in off:
                player.hymn_chase = HYMN_N + 2
            elif drawn.key == "bonus" and "bonus" not in off:
                pursue = int(drawn.arg)

        def watch(world, _key=key, _run=run, _state=state, _player=player) -> None:
            for e in world.events:
                events.append(e)
                if e[0] == "leak":
                    _state["leaks"] += 1
                    if world.bonus is not None:
                        _state["fight_leaks"] += e[3]
                elif e[0] == "cleared":   # ordinary waves only; packs settle as "bonus"
                    _state["last_clean"] = _state["leaks"] == 0
                    if record_breaks is not None:
                        summary["wave_leaks"].append([_key, e[1], _state["leaks"]])
                    _state["leaks"] = 0
                elif e[0] == "bonus" and e[2] in ("cleared", "failed"):
                    if e[2] == "failed":
                        _state["leaks"] = 0   # the pack's leaks judge the wager, not the next wave
                    cleared = e[2] == "cleared"
                    if cleared and _state["pack"] is not None:
                        summary["bonus_net"] += _state["pack"].wager + _state["pack"].profit
                    net = _state["pack"].profit if cleared else -_state["pack"].wager
                    summary["fights"].append([_key, e[1], cleared, world.wave, net,
                                              _player.built_out, _state["fight_leaks"],
                                              _state["fight_spent"], _state["fight_hp"]])
                    _state["fight_leaks"] = 0
            pool = _state["pool"] - (_state["lives"] - world.lives)
            stakes = (force_stake,) if force_stake else (3, 2, 1)
            spent = sum(t.spent for t in world.towers.values())
            _player.reserve = 0 if nobonus else _reserve(bot, pool, not _state["last_clean"],
                                                         _state["repeats"], world.wave,
                                                         world.gold, stakes, LOCATIONS[_key],
                                                         _run.seed, _run.index, spent, pursue)
            if world.bonus is not None or world.break_left is None:
                return
            if record_breaks is not None:
                point = (world.wave, _state["repeats"], len(summary["fights"]))
                if _state.get("recorded") != point:   # once per decision point, when the break opens
                    _state["recorded"] = point
                    record_breaks.append([_key, world.wave, pool, not _state["last_clean"],
                                          _state["repeats"], world.gold, _player.built_out,
                                          spent, pursue, _player.done,
                                          len(_player.chosen.steps) if _player.chosen else 0])
            if nobonus:
                return
            stake: int | None
            if force_stake:
                stake = force_stake
                comfort = force_pool or POOL_STAKES[3 - force_stake]
                if (not _state["last_clean"] or _state["repeats"] >= BONUS_CAP
                        or world.wave + 1 < EARLY or pool < comfort):
                    stake = None
                elif grant_wager and world.gold < _wager(force_stake):
                    summary["granted"] += _wager(force_stake) - world.gold
                    world.gold = _wager(force_stake)
            else:
                stake = _stake(bot, pool, not _state["last_clean"], _state["repeats"], world.wave,
                               world.gold, LOCATIONS[_key], _run.seed, _run.index, spent, pursue)
            if stake is None:
                return
            pack = draw(LOCATIONS[_key], stake, _run.seed, _run.index, _state["repeats"],
                          world.wave)
            if world.gold < pack.wager:
                return
            try:
                world.summon(pack)
            except Refused:
                summary["misfires"] += 1
            else:
                _state["pack"] = pack
                _state["repeats"] += 1   # counted here: defend clears the summoned event this step emits
                _state["fight_spent"] = sum(t.spent for t in world.towers.values())
                _state["fight_hp"] = pack.hp
                summary["bonus_net"] -= pack.wager
                summary["summons"].append((_key, stake))

        dealt = reference_kit(played.location, player.draft(played.location, _sigils(bot, run, key, stored)),
                              played.seed, relics=run.relics, counters=run.counters)
        world, record = defend(dealt, player, planner=planner.smart,
                              lives=IMMORTAL_LIVES if immortal else run.pool, watch=watch)
        strikes = sum(n for key, n in record.spells.items() if key != "hymn")
        world.events = events
        lives = IMMORTAL_LIVES if immortal else None
        result = observe_world(played, world, run.drawn, lives=lives)
        if immortal:   # the pool never ends the run, but the lost life is counted against it
            result = replace(result, lives_left=run.pool - result.lives_lost)
        run = finish(run, result)
        if run.offer:   # the bots take the camp's first relic, no choosing
            run = take_relic(run, run.offer[0])
            summary.setdefault("relics", []).append([key, run.relics[-1]])
        summary["sim_seconds"] += world.time
        summary["reached"] += 1
        catches = [len(e[4]) for e in events if e[0] == "cursed"]
        summary["locations"][key] = {"won": result.won, "lives_lost": result.lives_lost,
                                     "pool": run.pool, "gold": run.gold, "level": run.level,
                                     "sigils": run.records[-1].sigils,
                                     "goals": [(d.key, d.arg, v) for d, v in result.goals],
                                     "towers": len(world.towers), "builds": world.builds,
                                     "curses": len(catches),
                                     "caught": round(sum(catches) / len(catches), 2) if catches else 0.0,
                                     "blights": world.blights,
                                     "blight_cells": len(world.blighted_cells),
                                     "spells": world.spells_cast, "spell_kills": world.spell_kills,
                                     "casts": world.player_casts, "strikes": strikes,
                                     "kills": world.kills, "waves": max(1, world.wave + 1)}
        for goal, verdict in run.records[-1].goals:
            met, pursued = summary["goals"].get(goal.key, (0, 0))
            if goal.key == "family" and not player.pursued_family:
                continue   # a family not worth pursuing is not a pursuit
            if goal.key == "gate" and not player.gate_rush:
                continue   # a gate never rushed is not a pursuit
            if goal.key == "bonus" and not any(f[1] >= 2 for f in summary["fights"] if f[0] == key):
                continue   # a bonus never wagered at stake 2 is not a pursuit
            summary["goals"][goal.key] = (met + (verdict == MET), pursued + 1)
        _diagnose(summary, key, [d for d, _ in result.goals], player, events)
        if out is not None:
            path = out / "corpus" / bot / str(seed) / f"{key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(played.to_json(), indent=2))
        if run.lost and not immortal:
            summary["loss_at"] = key
            break
        run = camp(run)
        if run.won or run.index >= len(locations):
            break
        run = _learn(run, ORDER[run.index])
    summary["won"] = run.won or (immortal and summary["reached"] == len(locations))
    summary["pool"] = run.pool
    summary["carried"] = run.gold
    summary["level"] = run.level
    summary["tree"] = tree.cost(run.learned) / tree.TREE_COST
    for act, end in ACT_ENDS.items():
        if end in summary["locations"]:
            place = summary["locations"][end]
            summary["gold"][f"act{act}"] = place["gold"] / LOCATIONS[end].start_gold
            summary["levels"].append(place["level"])
    return summary


def _diagnose(summary: dict, key: str, drawn: list, player: Warden, events: list) -> None:
    """The pursuit's diagnostics per drawn goal: clean hymns, the family's leaks, the gate's story."""
    diag = summary.setdefault("diag", {})
    for goal in drawn:
        if goal.key == "hymn":
            fold = Hymn("999")
            for e in events:
                fold.observe(e)
            fold.observe(("end",))
            diag.setdefault("hymn_clean", []).append([key, fold.clean])
        elif goal.key == "family":
            diag.setdefault("family", []).append(
                [key, player.fair_lost, player.pursued_family, player.family is not None])
        elif goal.key == "gate":
            wave, built, broken = -1, -1, 0
            for e in events:
                if e[0] == "wave":
                    wave = e[1]
                elif e[0] == "door_built" and built < 0:
                    built = wave
                elif e[0] == "door_broken":
                    broken += 1
            diag.setdefault("gate", []).append([key, built, broken])
        elif goal.key == "lean":
            standing, most = 0, 0
            for e in events:
                if e[0] == "built":
                    standing += 1
                    most = max(most, standing)
                elif e[0] == "sold":
                    standing -= 1
            diag.setdefault("lean", []).append([key, most])


def _report(summaries: list[dict], immortal: bool) -> list[str]:
    """The exit criteria's lines over the runs."""
    lines = []
    if all(s["reached"] == len(ORDER) or "loss_at" in s for s in summaries):
        won = sum(1 for s in summaries if s["won"])
        lines.append(f"runs won: {won}/{len(summaries)}")
    reached = sum(s["reached"] for s in summaries) / len(summaries)
    pool = sum(s["pool"] for s in summaries) / len(summaries)
    lines.append(f"mean reached: {reached:.1f} locations, mean pool left: {pool:.1f}")
    if immortal:
        gold = [s["gold"].get(f"act{act}", 0.0) for s in summaries for act in (1, 2)]
        lines.append(f"mean act-end gold multiple of stipend: {sum(gold) / len(gold):.2f}")
        gained = [s["level"] - 1 for s in summaries]
        lines.append(f"mean levels gained: {sum(gained) / len(gained):.1f}")
    met: dict[str, list[int]] = {}
    for summary in summaries:
        for goal, (made, pursued) in summary["goals"].items():
            pair = met.setdefault(goal, [0, 0])
            pair[0] += made
            pair[1] += pursued
    for goal in sorted(met):
        made, pursued = met[goal]
        lines.append(f"goal {goal}: {made}/{pursued} met")
    summons = [s for summary in summaries for s in summary["summons"]]
    if summons:
        by_stake = {stake: sum(1 for _, s in summons if s == stake) for stake in (1, 2, 3)}
        net = sum(s["bonus_net"] for s in summaries)
        lines.append(f"summons: {len(summons)} " + " ".join(f"stake{s} {by_stake[s]}" for s in (1, 2, 3))
                       + f", net {net:+d} gold")
    misfires = sum(s["misfires"] for s in summaries)
    if misfires:
        lines.append(f"the rule misfired {misfires} times (refused summons)")
    granted = sum(s.get("granted", 0) for s in summaries)
    if granted:
        lines.append(f"granted {granted} gold of wagers (research: true net adds it back)")
    losses: dict[str, int] = {}
    for summary in summaries:
        if "loss_at" in summary:
            losses[summary["loss_at"]] = losses.get(summary["loss_at"], 0) + 1
    if losses:
        lines.append("losses: " + ", ".join(f"{key} {count}" for key, count in sorted(losses.items())))
    opened = sum(s["tree"] for s in summaries) / len(summaries)
    lines.append(f"mean tree opened: {opened:.0%}")
    top = max(s["level"] for s in summaries)
    lines.append(f"tree over a perfect run's points: {tree.TREE_COST}/{72 + top} = "
                 f"{tree.TREE_COST / (72 + top):.2f}x (M4: at least 2.5x)")
    places = [place for s in summaries for place in s["locations"].values()]
    towers = [p["towers"] for p in places]
    lines.append(f"towers standing at a defence's end: mean {sum(towers) / len(towers):.1f} "
                 f"most {max(towers)} (R4: low with no cap)")
    curses = sum(p["curses"] for p in places)
    caught = sum(p["caught"] * p["curses"] for p in places)
    lines.append(f"landed curses caught {caught / curses:.2f} towers on average over {curses} "
                 f"(R5: at least 1.5)" if curses else "no curse landed")
    cells = [(key, p["blight_cells"]) for s in summaries for key, p in s["locations"].items() if p["blight_cells"]]
    if cells:
        counts = [c for _, c in cells]
        lines.append(f"blighted cells a location that has blight: {min(counts)}-{max(counts)} "
                     f"(R6: 1-5, {len(cells)} defences)")
    casts = sum(p["casts"] for p in places)
    strikes = sum(p["strikes"] for p in places)
    waves = sum(p["waves"] for p in places)
    kills = sum(p["kills"] for p in places)
    by_spell = sum(p["spell_kills"] for p in places)
    lines.append(f"spells a wave: {casts / waves:.2f} ({strikes / waves:.2f} striking, no hymn) "
                 f"over {waves} waves (S2: about two)")
    lines.append(f"spells' share of the kills: {by_spell / kills:.1%} over {kills} kills (S2: at most 15%)"
                 if kills else "no kills")
    minutes = sum(s["sim_seconds"] for s in summaries) / len(summaries) / 60
    lines.append(f"mean run: {minutes:.1f} sim-minutes")
    return lines


def main(argv: list[str] | None = None) -> list[dict]:
    """Play the runs, write the corpus and the summaries, print the criteria's lines."""
    parser = argparse.ArgumentParser(description="Full runs through the campaign.")
    parser.add_argument("--bot", choices=BOTS, default="middling")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--seed0", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--immortal", action="store_true")
    parser.add_argument("--nobonus", action="store_true", help="never summon: the wager's control")
    parser.add_argument("--record-breaks", action="store_true",
                        help="record every break's decision point (location, wave, pool, leaked,"
                        " repeats, gold, built_out) and every wave's leaks into the summary")
    parser.add_argument("--force-stake", type=int, choices=(1, 2, 3), default=0,
                        help="research: summon this stake wherever a clean wave, the early gate,"
                        " the cap and the pool's comfort allow, instead of the rule's stake")
    parser.add_argument("--grant-wager", action="store_true",
                        help="research with --force-stake: grant the wager's shortfall, to test"
                        " the pack's fairness apart from the economy's savings")
    parser.add_argument("--force-pool", type=int, default=0,
                        help="research with --force-stake: the pool's comfort, instead of the rule's")
    parser.add_argument("--share", type=float, default=None,
                        help="research: the stored purse's share the bot's skills spend,"
                        " instead of SKILL_SHARE")
    parser.add_argument("--skip", type=float, default=None,
                        help="research: the middling bot's fumbled share of its drafts,"
                        " instead of MIDDLING_SKIP")
    parser.add_argument("--locations", default=",".join(ORDER),
                        help="a head of the campaign, in order (a run always starts at Tristram)")
    parser.add_argument("--out", default="runs")
    args = parser.parse_args(argv)
    if args.share is not None:
        os.environ["HELLWARD_SHARE"] = str(args.share)
    if args.skip is not None:
        os.environ["HELLWARD_SKIP"] = str(args.skip)
    locations = tuple(key for key in ORDER if key in args.locations.split(","))
    out = Path(args.out)
    seeds = list(range(args.seed0, args.seed0 + args.seeds))
    records: list = [[] if args.record_breaks else None for _ in seeds]
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            summaries = list(pool.map(play_run, seeds, [args.bot] * len(seeds),
                                      [locations] * len(seeds), [args.immortal] * len(seeds),
                                      [out] * len(seeds), [args.nobonus] * len(seeds), records,
                                      [args.force_stake] * len(seeds),
                                      [args.grant_wager] * len(seeds),
                                      [args.force_pool] * len(seeds)))
    else:
        summaries = [play_run(seed, args.bot, locations, args.immortal, out, args.nobonus, record,
                              args.force_stake, args.grant_wager, args.force_pool)
                     for seed, record in zip(seeds, records)]
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summaries, indent=2))
    lines = _report(summaries, args.immortal)
    print("\n".join(lines))
    return summaries


if __name__ == "__main__":
    main()

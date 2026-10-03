"""Each verb's rate in a build that leans into it, against one that does not (V1/V2).

    uv run python tools/verbs.py           # every verb's leaning build against its plain one
    uv run python tools/verbs.py --seeds 4  # more seeds per side

A leaning build earns its verb a handful to a few dozen times a wave (V1: 3-40), at least twice
what a build that does not lean earns (V2). Curse is the pulse, not a flow: the leaders pace it
about once a wave whatever stands, so its check is the clump's multiple over the spread build,
and the curse relics pay in spikes. Charge leans on gold (attuned strikers spend the spare
purse); corpse leans on the Charnel Pyre until Shatter is learnt.

It runs the compiled simulation (:mod:`hellward.fastsim`, built on first use), which plays as the source does;
``HELLWARD_INTERPRETED=1`` runs the source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward import fastsim  # noqa: E402

if __name__ in ("__main__", "__mp_main__"):   # run as a program or as one of its worker processes, not as a library
    fastsim.activate()   # the compiled simulation, unless HELLWARD_INTERPRETED is set

from hellward.sim import planner  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.players.hands import defend, reference_kit  # noqa: E402
from hellward.sim.players.planned import Plan, Planned, load  # noqa: E402
from hellward.sim.relics import VERBS  # noqa: E402
from tools.armor import tiles  # noqa: E402


def base_builds(key: str) -> tuple[list[str], list[tuple[str, tuple[int, int]]]]:
    base = load(key)
    out = [(s[1], tuple(s[2])) for s in base.steps if len(s) == 3 and s[0] == "build"]
    return list(base.skills), out


def rate(key: str, skills: list[str], builds: list[tuple[str, tuple[int, int]]], seed: int, *,
         ranks: bool = False, relics: tuple[str, ...] = (), gold: int | None = None,
         reserve: float | None = None, meteor_worth: float | None = None,
         ) -> tuple[str, dict[str, float], list[int]]:
    """One defence's outcome, each verb's mean count a wave (the unfinished last wave excluded),
    and the towers each curse landing took."""
    base = load(key)
    steps = [("build", kind, tile) for kind, tile in builds]
    if ranks:
        steps += [("rank", tile) for _, tile in builds]
    plan = Plan(skills=skills, steps=steps, calls=list(base.calls), rebuild=base.rebuild,
                smite_worth=base.smite_worth, meteor_worth=base.meteor_worth if meteor_worth is None
                else meteor_worth, orb_worth=base.orb_worth,
                reserve=base.reserve if reserve is None else reserve)
    learned = plan.learn(99, ORDER.index(key))
    waves, last, took = [], {}, []
    def watch(world):  # noqa: ANN001, ANN202
        for e in world.events:
            if e[0] == "wave":
                waves.append({v: world.verb_count.get(v, 0) - last.get(v, 0) for v in VERBS})
                last.update(world.verb_count)
            elif e[0] == "cursed":
                took.append(len(e[4]))
    world, _ = defend(reference_kit(LOCATIONS[key], learned, seed, relics=relics, gold=gold),
                      Planned(plan=plan), planner=planner.smart, watch=watch)
    if waves:   # the last wave has no closing bell: its tail belongs to it, not to nowhere
        for v in VERBS:
            waves[-1][v] += world.verb_count.get(v, 0) - last.get(v, 0)
    mean = {v: sum(w[v] for w in waves) / len(waves) for v in VERBS} if waves else dict.fromkeys(VERBS, 0.0)
    return f"{world.outcome[0]}{world.lives}", mean, took


def buildables(key: str) -> set[tuple[int, int]]:
    level = LOCATIONS[key].level
    return {(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)}


def bunch(key: str, n: int) -> list[tuple[int, int]]:
    """Adjacent tiles from the best: the clump area curses catch whole."""
    pool = buildables(key)
    out, front = [], [tiles(key)[0]]
    while front and len(out) < n:
        t = front.pop(0)
        if t in out:
            continue
        out.append(t)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                u = (t[0] + dx, t[1] + dy)
                if u in pool and u not in out and u not in front:
                    front.append(u)
    return out


def _shrine_spare(key: str, builds: list[tuple[str, tuple[int, int]]]) -> tuple[int, int]:
    """A free tile nearest the shrine: the censer's post, where the leaks walk past."""
    taken = {tile for _, tile in builds}
    ex, ey = LOCATIONS[key].level.waypoints[-1]
    return min(buildables(key) - taken, key=lambda t: (t[0] - ex) ** 2 + (t[1] - ey) ** 2)


def spec() -> dict[str, tuple[tuple, tuple]]:
    """Each verb's leaning build against its plain one: (key, skills, builds, ranks, relics, gold).

    Both sides stand on the searched plan and differ by the lean alone: the engine's towers,
    skill or relic added, taken away, or moved. Each side must still win for the ratio to mean
    anything (a dying defence leaks and starves)."""
    cskills, cbuilds = base_builds("caves")
    tskills, tbuilds = base_builds("tristram")
    dskills, dbuilds = base_builds("docks")
    dtaken = {tile for _, tile in dbuilds}
    spare = next(t for t in tiles("docks") if t not in dtaken)
    idols = [("idol", tile) if 1 <= i <= 3 else (kind, tile)
             for i, (kind, tile) in enumerate(cbuilds)]
    kinds = [kind for kind, _ in cbuilds]
    frost_at = [i for i, kind in enumerate(kinds) if kind == "frost"][:3]
    swapped = list(kinds)
    for good, weak in zip((1, 3, 4), frost_at):
        swapped[good], swapped[weak] = swapped[weak], swapped[good]
    frosted = [(swapped[i], tile) for i, (_, tile) in enumerate(cbuilds)]
    clump = bunch("tristram", len(tbuilds))
    return {
        "cast": (("caves", cskills + ["unlock_idol", "unlock_hymn"], idols, False, (), None),
                 ("caves", cskills, cbuilds, False, (), None)),
        "leak": (("caves", cskills + ["unlock_censer"],
                  [(kind, tile) for i, (kind, tile) in enumerate(cbuilds) if i not in (0, 2, 5, 7)] +
                  [("censer", _shrine_spare("caves", cbuilds))], False, (), None),
                 ("caves", cskills, cbuilds, False, (), None)),
        "curse": (("tristram", tskills, [(kind, clump[i]) for i, (kind, _) in enumerate(tbuilds)],
                   False, (), None),
                  ("tristram", tskills, tbuilds, False, (), None)),
        "charge": (("docks", dskills + ["unlock_well"], dbuilds + [("well", spare)],
                    False, (), 500),
                  ("docks", dskills, dbuilds, False, (), None)),
        "debuff": (("caves", cskills, cbuilds, False, (), None),
                   ("caves", cskills, [("pyre", t) if k == "plague" else (k, t)
                                       for k, t in cbuilds], False, (), None)),
        "corpse": (("caves", cskills, frosted, False, ("charnel",), None),
                   ("caves", cskills, cbuilds, False, (), None)),
    }


EXTRA: dict[str, dict] = {
    "leak": {"reserve": 0.0, "meteor_worth": 1.5},   # the porous defence slings spells to live
}


def ab(verb: str, seeds: list[int]
       ) -> tuple[list[float], list[float], list[str], list[int], list[int]]:
    """The verb's per-wave rate in its leaning and plain builds, with the leaning outcomes and
    the towers each curse landing took per side (placement sets the catch)."""
    lean, plain = spec()[verb]
    extra = EXTRA.get(verb, {})
    leans, plains, outcomes, took_lean, took_plain = [], [], [], [], []
    for seed in seeds:
        outcome, mean, took = rate(*lean[:3], seed, ranks=lean[3], relics=lean[4], gold=lean[5],
                                    **extra)
        leans.append(mean[verb])
        outcomes.append(outcome)
        took_lean += took
        _, mean, took = rate(*plain[:3], seed, ranks=plain[3], relics=plain[4], gold=plain[5])
        plains.append(mean[verb])
        took_plain += took
    return leans, plains, outcomes, took_lean, took_plain


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, default=2)
    args = parser.parse_args()
    verbs = ("cast", "leak", "curse", "charge", "debuff", "corpse")
    seeds = list(range(args.seeds))
    for verb in verbs:
        leans, plains, outcomes, took_lean, took_plain = ab(verb, seeds)
        lmean = sum(leans) / len(leans)
        pmean = sum(plains) / len(plains) if any(plains) else 0.0
        ratio = f"{lmean / pmean:.1f}x" if pmean > 0 else "all of it"
        line = (f"{verb:7s} lean {' '.join(f'{v:.1f}' for v in leans)} ({' '.join(outcomes)}) "
                f"plain {' '.join(f'{v:.1f}' for v in plains)} -> {ratio}")
        if verb == "curse":
            catch = (sum(took_lean) / len(took_lean) if took_lean else 0.0,
                     sum(took_plain) / len(took_plain) if took_plain else 0.0)
            line += f" catch {catch[0]:.1f} vs {catch[1]:.1f} towers a landing"
        print(line)


if __name__ == "__main__":
    main()

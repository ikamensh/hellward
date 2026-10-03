"""The tree: a strong player's draft-time read of the run's relics.

A person who holds the Charnel Pyre builds frost; who holds a charter raises what it opens; who is paid
for curses clumps into them. The tree is that read as ordered branches: each branch fires on the verbs the
held relics read and seeds the build with the engines that feed them — idols for cast readers, a well for
charge readers, a censer for leak readers, frost and plague for debuff readers, frost and an altar for
corpse readers — raises what the charters open with no skill, and spends curse, build and upgrade payoffs
on extra towers and ranks. Curse readers also clump (drafts only: searched tiles stand) and never raise an
effigy, which would eat the curse gold they are paid.

It works on plain data — skills lists and ``(kind, tile)`` builds — so both strong players share it: the
planned player operates on its searched plan, the veteran on its draft. Wanted unlocks go in with the other
unlocks, early, and the sigils drop tail bonuses to pay for them: learning idols instead of arrow mastery,
as a person would. An engine the sigils cannot fund is unswapped again, so a read plan always raises. With
no relics every branch sleeps and the plan stands exactly as searched.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.campaign import ORDER, Location
from hellward.sim.content import TOWERS
from hellward.sim.relics import RELICS
from hellward.sim.skills import SKILLS, UNLOCK, can_learn, unlock_skills

READERS: dict[str, frozenset[str]] = {}
for _key, _spec in RELICS.items():
    if _spec.verb:
        READERS.setdefault(_spec.verb, frozenset())
        READERS[_spec.verb] |= {_key}

CHARTER_KINDS: dict[str, tuple[str, ...]] = {
    # what each charter raises with no skill; the grove charter opens no effigy, which would eat its curse gold
    "storm_charter": ("storm",),
    "hook_charter": ("hook", "knife"),
    "grove_charter": ("grove",),
    "altar_charter": ("altar",),
}

ENGINE_SKILLS: dict[str, tuple[str, str]] = {
    # the unlock and the adept an engine kind wants beside it; the sigils keep what they can
    "idol": ("unlock_idol", "adept_idol"),
    "well": ("unlock_well", "adept_well"),
    "censer": ("unlock_censer", "adept_censer"),
    "frost": ("unlock_frost", "adept_cold"),
    "altar": ("unlock_altar", "adept_bone"),
    "plague": ("unlock_plague", "adept_poison"),
    "storm": ("unlock_storm", "adept_lightning"),
    "hook": ("unlock_hook", "adept_hook"),
    "knife": ("unlock_knife", "adept_knife"),
    "grove": ("unlock_grove", "adept_nature"),
}

KIND_OF: dict[str, str] = {skill: kind for kind, skill in UNLOCK.items() if skill is not None}

SKILL_KIND: dict[str, str] = {skill: kind for kind, pair in ENGINE_SKILLS.items() for skill in pair}

SWAPS_MAX = 6    # seeded engines at most: the searched core stands
BUILDS_MAX = 4   # extra towers at most: payoffs spend, never flood


@dataclass(frozen=True)
class Reading:
    """What the branches want for a set of held relics."""

    engines: tuple[tuple[str, int], ...] = ()   # (kind, count) to seed, in branch order
    skills: tuple[str, ...] = ()                # unlocks and adepts to learn, unlocks first
    builds: int = 0                             # extra towers to append, for curse and build payoffs
    ranks: int = 0                              # extra ranks to append, for upgrade payoffs
    tight: bool = False                         # curse readers: clump for the curse gold (drafts only)


def read(relics: tuple[str, ...] | frozenset[str]) -> Reading:
    """The branches' wants for held relics. Unknown keys are skipped: an old save's relic never breaks a draft."""
    verbs = {RELICS[key].verb for key in relics if key in RELICS} - {""}
    engines: list[tuple[str, int]] = []
    unlocks: list[str] = []
    adepts: list[str] = []

    def want(kind: str, count: int) -> None:
        engines.append((kind, count))
        unlock, adept = ENGINE_SKILLS[kind]
        if unlock not in unlocks:
            unlocks.append(unlock)
        if adept not in adepts:
            adepts.append(adept)

    if "cast" in verbs:
        want("idol", 2)
    if "charge" in verbs:
        want("well", 1)
    if "leak" in verbs:
        want("censer", 1)
    if "debuff" in verbs:
        want("frost", 1)
        want("plague", 1)
    if "corpse" in verbs:
        want("frost", 1)
        want("altar", 1)
    builds = (2 if "curse" in verbs else 0) + (2 if "build" in verbs else 0)
    ranks = 2 if "upgrade" in verbs else 0
    for key in sorted(relics):
        if key in CHARTER_KINDS:
            engines += [(kind, 1) for kind in CHARTER_KINDS[key]]
    return Reading(tuple(engines), tuple(unlocks + adepts), builds, ranks, "curse" in verbs)


def chartered(relics: tuple[str, ...] | frozenset[str]) -> frozenset[str]:
    """The kinds the held charters raise with no skill."""
    return frozenset(kind for key in relics if key in CHARTER_KINDS for kind in CHARTER_KINDS[key])


def tight(relics: tuple[str, ...] | frozenset[str]) -> bool:
    """Whether curse readers clump the draft for the curse gold."""
    return read(relics).tight


def insert_skills(skills: list[str], want: tuple[str, ...]) -> list[str]:
    """Wanted skills beside the other unlocks, early, each once: the sigils drop tail bonuses to pay for them."""
    out = list(skills)
    at = 0
    for i, key in enumerate(out):
        if key.startswith("unlock_"):
            at = i + 1
    for key in want:
        if key not in out:
            out.insert(at, key)
            at += 1
    return out


def learnable(kind: str, stage: int) -> bool:
    """Whether the kind's unlock can be learned by this stage of the campaign."""
    key = UNLOCK[kind]
    return key is None or stage >= SKILLS[key].first_location


def learn_ordered(skills: list[str], sigils: int, stage: int) -> frozenset[str]:
    """The skills of an ordered list that fit in ``sigils``, each as soon as the one above it is learned."""
    learned: frozenset[str] = frozenset()
    grew = True
    while grew:
        grew = False
        for key in skills:
            if can_learn(learned, key, sigils, stage):
                learned, grew = learned | {key}, True
    return learned


def missing_unlocks(builds: list[tuple[str, tuple[int, int]]], learned: frozenset[str],
                    relics: tuple[str, ...] | frozenset[str]) -> frozenset[str]:
    """The unlocks the builds need that the learned skills lack, never a chartered kind's."""
    free = chartered(relics)
    return (frozenset(u for kind, _ in builds if kind not in free
                      for u in [UNLOCK[kind]] if u is not None)
            - unlock_skills(learned))


def swap_kinds(builds: list[tuple[str, tuple[int, int]]], engines: tuple[tuple[str, int], ...],
               curse: bool = False) -> tuple[list[tuple[str, tuple[int, int]]],
                                             list[tuple[tuple[int, int], str, str]]]:
    """Seeded engines in place of the most-built kinds, tiles kept, at most six: the searched core stands.
    A lone aura or amplifier is never swapped away, the opening's first two towers never seed engines — they
    hold the first waves while the engines come online behind them — and curse readers trade an effigy, which
    would eat their curse gold, for the core's damage. Returns the seeded builds and the swaps as
    ``(tile, victim, engine)``."""
    kinds = [kind for kind, _ in builds]
    swapped = [False] * len(builds)
    swaps: list[tuple[tuple[int, int], str, str]] = []
    if curse:
        core = max(set(kinds), key=lambda k: (kinds.count(k), kinds.index(k)))
        for i, kind in enumerate(kinds):
            if kind == "effigy" and core != "effigy":
                swaps.append((builds[i][1], kind, core))
                kinds[i], swapped[i] = core, True
    done = 0
    for engine, count in engines:
        for _ in range(count):
            if done >= SWAPS_MAX:
                return [(kinds[i], builds[i][1]) for i in range(len(builds))], swaps
            best = -1
            for i, kind in enumerate(kinds):
                if swapped[i] or kind == engine or i < 2:
                    continue
                if kinds.count(kind) == 1 and TOWERS[kind].attack in ("aura", "amplify"):
                    continue
                if best < 0 or (kinds.count(kind), i) > (kinds.count(kinds[best]), best):
                    best = i
            if best < 0:
                return [(kinds[i], builds[i][1]) for i in range(len(builds))], swaps
            swaps.append((builds[best][1], kinds[best], engine))
            kinds[best], swapped[best] = engine, True
            done += 1
    return [(kinds[i], builds[i][1]) for i in range(len(builds))], swaps


def unswap(skills: list[str], seeded: list[tuple[str, tuple[int, int]]],
           swaps: list[tuple[tuple[int, int], str, str]], unlock: str,
           ) -> tuple[list[str], list[tuple[str, tuple[int, int]]],
                      list[tuple[tuple[int, int], str, str]], bool]:
    """An unfunded engine back out: its tiles build their victims again and its unlock leaves the list (its
    adept stays, unlearnable, harmless). Whether any tile changed: a base unlock never unswaps."""
    if unlock not in KIND_OF:
        return skills, seeded, swaps, False
    kind = KIND_OF[unlock]
    back = {tile: victim for tile, victim, engine in swaps if engine == kind}
    if not back:
        return skills, seeded, swaps, False
    seeded = [(back.get(tile, k), tile) for k, tile in seeded]
    swaps = [swap for swap in swaps if swap[2] != kind]
    return [s for s in skills if s != unlock], seeded, swaps, True


def extra_tiles(location: Location, kind: str, used: list[tuple[int, int]], count: int) -> list[tuple[int, int]]:
    """The free buildable tiles watching most path, for the payoffs' extra towers."""
    level = location.level
    reach = TOWERS[kind].levels[0].range
    taken = set(used)
    found: list[tuple[int, int]] = []
    for _ in range(count):
        best: tuple[int, int] | None = None
        most = -1.0
        for y in range(level.height):
            for x in range(level.width):
                tile = (x, y)
                if tile in taken or not level.buildable(x, y):
                    continue
                watched = 0.0
                for route in level.routes:
                    if route.key.startswith("breach"):
                        continue
                    watched += sum(b - a for a, b in route.coverage(tile, reach))
                if best is None or (watched, -y, -x) > (most, -best[1], -best[0]):
                    best, most = tile, watched
        if best is None:
            return found
        taken.add(best)
        found.append(best)
    return found


def adjust(skills: list[str], builds: list[tuple[str, tuple[int, int]]],
           relics: tuple[str, ...] | frozenset[str], location: Location,
           ) -> tuple[list[str], list[tuple[str, tuple[int, int]]],
                      list[tuple[tuple[int, int], str, str]]]:
    """A plan's skills and builds read for its relics: the engines' unlocks beside the other unlocks, the
    engines seeded into the builds. Engines the arsenal lacks or the stage cannot unlock are skipped, and
    with no relics the plan stands exactly as searched. Returns the skills, the seeded builds and the swaps."""
    reading = read(relics)
    if not relics:
        return skills, builds, []
    stage = ORDER.index(location.key)
    free = chartered(relics)
    engines = tuple((kind, count) for kind, count in reading.engines
                    if kind in location.arsenal.towers
                    and (kind in free or learnable(kind, stage)))
    kept = {kind for kind, _ in engines} - free
    want = tuple(key for key in reading.skills if SKILL_KIND.get(key) in kept)
    seeded, swaps = swap_kinds(builds, engines, reading.tight)
    return insert_skills(skills, want), seeded, swaps


def extras(seeded: list[tuple[str, tuple[int, int]]], builds: list[tuple[str, tuple[int, int]]],
           reading: Reading, location: Location,
           ) -> tuple[list[tuple[str, tuple[int, int]]], list[tuple[int, int]]]:
    """The payoffs' extra towers — the core's damage on the tiles watching most path — and the tiles to rank,
    the seeded engines first."""
    counts = [kind for kind, _ in seeded]
    damage = [k for k in set(counts) if TOWERS[k].attack not in ("aura", "amplify")]
    pool = damage or list(set(counts))
    core = max(pool, key=lambda k: (counts.count(k), k))
    tiles = extra_tiles(location, core, [tile for _, tile in seeded], min(reading.builds, BUILDS_MAX))
    engine_tiles = [tile for (kind, tile), (was, _) in zip(seeded, builds) if kind != was]
    rest = [tile for _, tile in seeded if tile not in engine_tiles]
    return [(core, tile) for tile in tiles], (engine_tiles + rest)[:reading.ranks]


__all__ = ["BUILDS_MAX", "CHARTER_KINDS", "ENGINE_SKILLS", "KIND_OF", "READERS", "SWAPS_MAX", "Reading",
           "adjust", "chartered", "extra_tiles", "extras", "insert_skills", "learn_ordered", "learnable",
           "missing_unlocks", "read", "swap_kinds", "tight", "unswap"]

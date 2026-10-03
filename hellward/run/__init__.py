"""The run: the campaign as one run through all twelve locations, with Diablo's XP bar.

A :class:`Run` is pure rules with no I/O: the pool of sanctuary life, the carried gold, the XP and levels, the
skill and reskill points, the learned skills, and per location its sigils and the goals it drew. :func:`start`
begins one; :func:`kit` deals the current location's defence; :func:`camp` heals between locations;
:func:`finish` settles a defence's :class:`DefenceResult` back into the run. :func:`learn` and :func:`unlearn`
spend points on the tree through :mod:`hellward.sim.skills`, so they follow whatever tree the data holds;
:func:`bonus_pack` draws a bonus wave's pack, wager and preview.

``finish(run, world)`` from the stage-3 plan is :func:`observe_world` (a defence's result from its world) then
:func:`finish`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Any, Final

from hellward.run.goals import FAILED, MET, OPEN, Drawn, describe, make
from hellward.sim import skills, tuning
from hellward.sim.bonus import BonusPack
from hellward.sim.bonus import EARLY as BONUS_EARLY
from hellward.sim.bonus import draw as bonus_pack
from hellward.sim.bonus import preview as bonus_preview
from hellward.sim.xp import clear_xp, kill_xp, xp_next
from hellward.sim.campaign import ACT_ENDS, LOCATIONS, ORDER, offers
from hellward.sim.content import MONSTERS, TOWERS
from hellward.sim.items import Loadout
from hellward.sim.kit import Kit
from hellward.sim.locations.common import Location
from hellward.sim.relics import RELICS
from hellward.sim.relics import draw as draw_relics

__all__ = ["FAILED", "MET", "OPEN", "BonusPack", "DefenceResult", "Drawn", "Record", "Run", "add_xp", "bonus_pack",
           "bonus_preview", "camp", "clear_xp", "describe", "dismantle", "draw_goals", "finish", "from_json",
           "gold_floor", "kill_xp", "kit", "learn", "lives_sigils", "observe_world", "start", "take_relic",
           "to_json", "unlearn", "xp_next"]

LIFE: Final = tuning.integer("run.life")
CAMP_HEAL: Final = tuning.number("run.camp_heal")
GOLD_FLOOR: Final = tuning.number("run.gold_floor")
DISMANTLE_REFUND: Final = tuning.number("run.dismantle_refund")
RESKILL_EVERY: Final = tuning.integer("run.reskill_every")
SIGIL_LOST: Final = tuning.numbers("run.sigil_lost")
LEAN_N: Final = tuning.integer("run.goals.lean_n")
HYMN_N: Final = tuning.integer("run.goals.hymn_n")



@dataclass(frozen=True)
class Record:
    """How one location of the run went: what it cost, what it drew, what it paid."""

    location: str
    lives_lost: int
    lives_sigils: int
    goals: tuple[tuple[Drawn, str], ...] = ()   # each drawn goal with its closing verdict

    @property
    def sigils(self) -> int:
        """Every sigil the location paid: the lives sigils and one per met goal."""
        return self.lives_sigils + sum(1 for _, verdict in self.goals if verdict == MET)


@dataclass(frozen=True)
class Run:
    """One run: everything carried from location to location."""

    seed: int
    index: int                    # the next location's place in the campaign's order
    pool: int                     # the sanctuary life left
    gold: int                     # the gold carried in
    xp: float
    level: int
    skill_points: int             # unspent
    reskill_points: int           # unspent
    learned: frozenset[str]
    records: tuple[Record, ...]
    drawn: tuple[Drawn, ...]       # the current location's goals, drawn at its camp
    salvage: int
    equipped: tuple[str, ...]     # the patterns worn, as a loadout's equipped
    counters: tuple[tuple[str, int], ...] = ()   # each relic's count toward its firing, carried on
    relics: tuple[str, ...] = ()  # the relics won, a location at a time
    offer: tuple[str, ...] = ()   # the camp's choice after a held location, until one is taken

    @property
    def location(self) -> Location:
        return LOCATIONS[ORDER[self.index]]

    @property
    def won(self) -> bool:
        return self.index >= len(ORDER) and self.pool > 0

    @property
    def lost(self) -> bool:
        return self.pool <= 0


def draw_goals(seed: int, index: int, location: Location) -> tuple[Drawn, ...]:
    """The location's three goals, drawn by the run's seed: lean and bonus always qualify; the gate needs
    gates, the hymn the Hymn, the leaders a leader in the waves, and one family a tower that is not physical."""
    rng = random.Random(f"goals:{seed}:{index}")
    leaders = sorted({group.kind for wave in location.waves for group in wave.groups
                      if MONSTERS[group.kind].leader is not None})
    elements = sorted({TOWERS[kind].element.value for kind in location.arsenal.towers
                       if TOWERS[kind].element.value != "physical"})
    eligible = ["lean", "bonus"]
    if location.arsenal.gates:
        eligible.append("gate")
    if "hymn" in location.arsenal.spells:
        eligible.append("hymn")
    if leaders:
        eligible.append("leaders")
    if elements:
        eligible.append("family")
    drawn: list[Drawn] = []
    for key in rng.sample(eligible, min(3, len(eligible))):
        if key == "lean":
            drawn.append(Drawn(key, str(LEAN_N)))
        elif key == "gate":
            drawn.append(Drawn(key, ""))
        elif key == "family":
            drawn.append(Drawn(key, rng.choice([*elements, "!physical"])))
        elif key == "leaders":
            drawn.append(Drawn(key, ""))   # every leader: the fold names no kind
        elif key == "hymn":
            drawn.append(Drawn(key, str(HYMN_N)))
        else:
            drawn.append(Drawn(key, "2"))
    return tuple(drawn)


def start(seed: int) -> Run:
    """A run's beginning: a full pool, empty hands, and Tristram's goals already drawn."""
    location = LOCATIONS[ORDER[0]]
    return Run(seed=seed, index=0, pool=LIFE, gold=0, xp=0.0, level=1, skill_points=0, reskill_points=0,
               learned=frozenset(), records=(), drawn=draw_goals(seed, 0, location), salvage=0, equipped=())


def gold_floor(location: Location) -> int:
    """The start gold's floor: carried gold is topped up to this share of the stage-2 stipend."""
    return round(location.start_gold * GOLD_FLOOR)


def kit(run: Run) -> Kit:
    """The current location's defence: the carried gold topped up, the pool as its lives, the run's seed
    mixed with the location's place so no two defences roll alike."""
    return Kit(location=run.location, learned=run.learned, loadout=Loadout(run.equipped),
               gold=max(run.gold, gold_floor(run.location)), lives=run.pool, seed=run.seed * 128 + run.index,
               xp=run.xp, level=run.level, relics=run.relics, counters=run.counters)


def camp(run: Run) -> Run:
    """The camp between locations: its share of the missing life returns, rounded up, never past
    a full pool — and before an act's end the pool fills: the last sanctuary burns bright."""
    if run.index < len(ORDER) and ORDER[run.index] in ACT_ENDS.values():
        return replace(run, pool=LIFE)
    missing = max(0, LIFE - run.pool)
    return replace(run, pool=run.pool + math.ceil(missing * CAMP_HEAL))


def add_xp(run: Run, amount: float) -> tuple[Run, int]:
    """The run with XP added: each level gives a skill point, and every fourth a reskill point. The comparison
    forgives float dust, so exactly enough XP always levels."""
    run, gained = replace(run, xp=run.xp + amount), 0
    while run.xp + 1e-9 >= xp_next(run.level):
        run = replace(run, xp=run.xp - xp_next(run.level), level=run.level + 1,
                      skill_points=run.skill_points + 1)
        gained += 1
        if run.level % RESKILL_EVERY == 0:
            run = replace(run, reskill_points=run.reskill_points + 1)
    return run, gained


def location_xp(key: str) -> float:
    """The XP a packless perfect defence of ``key`` awards: every group's kills, every wave's clear."""
    location = LOCATIONS[key]
    return sum(sum(group.count * kill_xp(MONSTERS[group.kind].hp) for group in wave.groups)
               + clear_xp(number) for number, wave in enumerate(location.waves, start=1))


def arrival(key: str) -> tuple[int, float]:
    """The (level, xp) a packless perfect run carries into ``key``: the earlier locations' XP, levelled."""
    total = sum(location_xp(earlier) for earlier in ORDER[:ORDER.index(key)])
    level, need = 1, xp_next(1)
    while total + 1e-9 >= need:
        total, level = total - need, level + 1
        need = xp_next(level)
    return level, total


def lives_sigils(lost: int) -> int:
    """The lives sigils: three for none lost, then by the tuning's thresholds."""
    return sum(1 for most in SIGIL_LOST if lost <= most)


def dismantle(costs: int) -> int:
    """The carried gold every standing tower's cost dismantles for."""
    return int(costs * DISMANTLE_REFUND)


def learn(run: Run, key: str) -> Run:
    """The run with a skill learned for its points; a refusal names its reason."""
    if key not in skills.SKILLS:
        raise ValueError(f"no skill {key!r}")
    if key in run.learned:
        raise ValueError(f"{skills.SKILLS[key].name} is already learned")
    need = skills.above(skills.SKILLS[key])
    if need is not None and need.key not in run.learned:
        raise ValueError(f"{skills.SKILLS[key].name} needs {need.name}")
    if run.index < skills.SKILLS[key].first_location:
        raise ValueError(f"{skills.SKILLS[key].name} opens later in the campaign")
    if skills.SKILLS[key].cost > run.skill_points:
        raise ValueError(f"{skills.SKILLS[key].name} costs {skills.SKILLS[key].cost} points")
    return replace(run, learned=run.learned | {key}, skill_points=run.skill_points - skills.SKILLS[key].cost)


def unlearn(run: Run, column: str) -> Run:
    """The run with the column's bottom skill unlearned: a reskill point goes, its points return."""
    bottom = [key for key in run.learned if skills.SKILLS[key].column == column]
    if not bottom:
        raise ValueError(f"nothing in {column} to unlearn")
    key = max(bottom, key=lambda k: skills.SKILLS[k].tier)
    if run.reskill_points < 1:
        raise ValueError("no reskill point to unlearn with")
    return replace(run, learned=run.learned - {key}, skill_points=run.skill_points + skills.SKILLS[key].cost,
                   reskill_points=run.reskill_points - 1)


def take_relic(run: Run, key: str) -> Run:
    """The run with the camp's offered relic taken; anything unoffered is refused."""
    if key not in run.offer:
        raise ValueError(f"no {RELICS[key].name if key in RELICS else key!r} is offered at this camp")
    return replace(run, relics=(*run.relics, key), offer=())


@dataclass(frozen=True)
class DefenceResult:
    """What one defence settled: the pool and gold left, what stood, what it earned, how the goals closed."""

    won: bool
    lives_left: int
    lives_lost: int
    gold_left: int
    tower_costs: int              # every standing tower's cost, for the dismantle
    xp_earned: float
    goals: tuple[tuple[Drawn, str], ...]   # each drawn goal with its live verdict
    salvage_earned: int
    relics: tuple[tuple[str, int], ...] = ()   # each relic's count toward its firing, carried on


def observe_world(kit: Kit, world: Any, drawn: tuple[Drawn, ...], *, lives: int | None = None) -> DefenceResult:
    """A defence's result from its world: the pool and gold left, the standing towers' cost, the held salvage,
    the XP earned past the Kit's, and every drawn goal's fold over the recorded events. ``lives`` is the
    defence's starting lives when the world did not start from the Kit's (an immortal run's huge pool)."""
    goals: list[tuple[Drawn, str]] = []
    for goal in drawn:
        fold = make(goal)
        fold.start(kit)
        for event in world.events:
            fold.observe(event)
        fold.observe(("end",))
        goals.append((goal, fold.verdict()))
    left = max(0, world.lives)
    first = kit.lives if lives is None else lives
    return DefenceResult(won=world.outcome == "victory", lives_left=left, lives_lost=first - left,
                         gold_left=world.gold, tower_costs=sum(t.spent for t in world.towers.values()),
                         xp_earned=world.xp_total, goals=tuple(goals), salvage_earned=world.salvage_held,
                         relics=tuple(sorted(world.progress.items())))


def to_json(run: Run) -> dict[str, Any]:
    """The run as JSON: the save's form, one a resume reads back exactly."""
    return {"seed": run.seed, "index": run.index, "pool": run.pool, "gold": run.gold, "xp": run.xp,
            "level": run.level, "skill_points": run.skill_points, "reskill_points": run.reskill_points,
            "learned": sorted(run.learned),
            "records": [{"location": r.location, "lives_lost": r.lives_lost, "lives_sigils": r.lives_sigils,
                         "goals": [[g.key, g.arg, v] for g, v in r.goals]} for r in run.records],
            "drawn": [[g.key, g.arg] for g in run.drawn], "salvage": run.salvage,
            "equipped": list(run.equipped), "counters": [list(pair) for pair in run.counters],
            "relics": list(run.relics), "offer": list(run.offer)}


def from_json(data: dict[str, Any]) -> Run:
    """The run from :func:`to_json`'s shape; a location outside the campaign is refused."""
    learned = frozenset(str(s) for s in data.get("learned", ()))
    records = tuple(Record(str(r["location"]), int(r["lives_lost"]), int(r["lives_sigils"]),
                           tuple((Drawn(str(g[0]), str(g[1])), str(g[2])) for g in r.get("goals", ())))
                    for r in data.get("records", ()))
    for record in records:
        if record.location not in LOCATIONS:
            raise ValueError(f"a run's record is outside the campaign: {record.location!r}")
    run = Run(seed=int(data.get("seed", 0)), index=int(data.get("index", 0)), pool=int(data.get("pool", LIFE)),
              gold=int(data.get("gold", 0)), xp=float(data.get("xp", 0.0)), level=int(data.get("level", 1)),
              skill_points=int(data.get("skill_points", 0)), reskill_points=int(data.get("reskill_points", 0)),
              learned=learned, records=records,
              drawn=tuple(Drawn(str(g[0]), str(g[1])) for g in data.get("drawn", ())),
              salvage=int(data.get("salvage", 0)), equipped=tuple(str(p) for p in data.get("equipped", ())),
              counters=tuple((str(pair[0]), int(pair[1])) for pair in data.get("counters", ())),
              relics=tuple(str(r) for r in data.get("relics", ())),
              offer=tuple(str(r) for r in data.get("offer", ())))
    if not 0 <= run.index <= len(ORDER):
        raise ValueError(f"a run's location is outside the campaign: {run.index}")
    return run


def finish(run: Run, result: DefenceResult) -> Run:
    """The run with a defence settled: the pool and gold left, the dismantle, the XP and its points, and the
    sigils (the lives sigils and one per met goal). A loss ends the run at its location: the record keeps
    the lives lost, but every goal fails and nothing pays; a win draws the next location's goals."""
    if not result.won:
        record = Record(run.location.key, result.lives_lost, 0,
                        tuple((goal, FAILED) for goal, _ in result.goals))
        return replace(run, pool=0, records=(*run.records, record))
    folded = tuple((goal, verdict if verdict != OPEN else make(goal).close_default)
                   for goal, verdict in result.goals)
    record = Record(run.location.key, result.lives_lost, lives_sigils(result.lives_lost), folded)
    run = replace(run, pool=result.lives_left, gold=result.gold_left + dismantle(result.tower_costs),
                  salvage=run.salvage + result.salvage_earned, records=(*run.records, record),
                  skill_points=run.skill_points + record.sigils, index=run.index + 1,
                  counters=result.relics, offer=draw_relics(run.seed, run.index, run.relics))
    run, _ = add_xp(run, result.xp_earned)
    if run.index >= len(ORDER):
        return replace(run, drawn=())
    return replace(run, drawn=draw_goals(run.seed, run.index, run.location))




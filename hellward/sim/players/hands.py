"""What a scripted player sees and does: a person's view of a defence, and a person's hands.

A player reads the world as a person reads the screen: where every monster walks, its life, the towers and
the curses on them, the gates, the gold and the mana. Leaders are the exception. A person sees a leader ponder
(the dots over its head) and chant (the beam to a tower) and answers a moment later, so :meth:`Hands.threats`
shows each sign only :attr:`Hands.react` seconds of game time after it appears, with where the leader stood when
it appeared: a person aims there, not where the leader has walked since. A player never reads a leader's
mind: not its planner, its cooldown or its chant's clock; it does not clone the live world to see the future, and
it never pauses (``tests/test_players.py`` holds every player's source to this). Its aimed spells (Smite, Meteor,
Frozen Orb) come at most one each :data:`AIM_GAP` seconds; Battle Hymn, aimed at a tower, is a click on the panel.
Everything else it does through the world's own commands, as the panel does.

:func:`defend` plays one defence from its start and returns the world and a :class:`Record` of what happened,
for the balance tools.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from hellward.sim.campaign import Location
from hellward.sim.content import Curse
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.kit import Kit
from hellward.sim.model import SIM_DT, START_LIVES, Planner, Refused, World, curse_radius
from hellward.sim.sums import int_sum

REACT = (0.5, 0.8)    # a person answers a leader's sign this long after it appears, drawn per seed
AIM_GAP = 0.5         # seconds between two aimed spells


class Player(Protocol):
    """A scripted player. It may also say how quick its hands are: ``reaction``, the range a leader's sign is seen
    late by (default :data:`REACT`), and ``aim_gap``, the seconds between two aimed spells (default :data:`AIM_GAP`)."""

    name: str

    def draft(self, location: Location, sigils: int) -> frozenset[str]:
        """The skills it would learn for this location with ``sigils``: the dealers' question when they build
        its Kit. What it defends with is the Kit's learned, which may be anything."""

    def act(self, hands: Hands) -> None:
        """Called before every step of the world; a player decides as often as it likes."""


@dataclass(frozen=True)
class Sign:
    leader: int
    kind: str                     # "ponder" (the dots) or "chant" (the beam)
    since: float                  # when it appeared
    at: tuple[float, float]       # where the leader stood then: where a person's aim goes
    spot: tuple[int, int] = (-1, -1)   # a chant's marked tile: the rune circle is drawn on it
    curse: Curse | None = None    # a chant's curse: its colour and sigil show which
    radius: float = 0.0           # the circle's radius, widening included (0 for a pondering)


@dataclass
class Record:
    """What happened in a defence, counted from its events."""

    chants: int = 0               # curses the leaders began to chant
    landed: int = 0
    fizzled: int = 0              # chants that ended with their tower gone or their leader out of reach
    curse_seconds: float = 0.0    # seconds of curses held on towers, summed over towers
    mana_capped: float = 0.0      # seconds the mana orb sat full
    spells: Counter = field(default_factory=Counter)
    leaks: Counter = field(default_factory=Counter)   # lives lost by wave
    skills: frozenset[str] = frozenset()              # what the player learned for it
    towers_caught: list[int] = field(default_factory=list)  # number of towers caught per landed curse
    raised: int = 0               # monsters raised by a leader
    burned: float = 0.0           # mana burned by curses
    strikes: int = 0              # a boss's strikes at the shrine
    hooked: int = 0               # monsters a hook dragged back


def ready(world: World, spell: str, spare: float = 0.0) -> bool:
    """Whether a spell can be cast now, as its slot on the panel shows: offered here, its unlock learned,
    gathered again after its last cast, and paid for with ``spare`` mana still in hand."""
    return (spell in world.arsenal.spells and spell not in world.perks.locked
            and world.recharge.get(spell, 0.0) <= 0 and world.mana - spare >= world.spell_cost(spell))


def react_for(seed: int, reaction: tuple[float, float] = REACT) -> float:
    return reaction[0] + (reaction[1] - reaction[0]) * random.Random(seed * 7919 + 17).random()


class Hands:
    def __init__(self, world: World, react: float, aim_gap: float = AIM_GAP) -> None:
        self.world = world
        self.react = react
        self.aim_gap = aim_gap
        self.record = Record()
        self._signs: dict[int, Sign] = {}
        self._last_aim = -1e9

    def observe(self, events: list[tuple], dt: float = SIM_DT) -> None:
        """Take in one step's events (the caller clears them)."""
        world = self.world
        record = self.record
        for e in events:
            kind = e[0]
            if kind == "ponder":
                self._sign(e[1], "ponder")
            elif kind == "plan":
                self._signs.pop(e[1], None)
            elif kind == "chant":
                self._sign(e[1], "chant", e[3], e[2])
                record.chants += 1
            elif kind == "mark":
                self._sign(e[1], "mark", e[3], e[2])  # a mark is a sign like a chant
                record.chants += 1
            elif kind == "cursed":
                self._signs.pop(e[1], None)
                record.landed += 1
                record.towers_caught.append(len(e[4]))
            elif kind == "fizzle":
                self._signs.pop(e[1], None)
                record.fizzled += 1
            elif kind == "death":
                self._signs.pop(e[1], None)
            elif kind == "leak":
                self._signs.pop(e[1], None)
                record.leaks[world.wave] += e[3]
            elif kind == "returned":
                record.leaks[world.wave] += e[3]
                record.strikes += 1
            elif kind == "hook":
                record.hooked += 1
            elif kind == "raised":
                record.raised += 1
            elif kind == "burned":
                record.burned += e[2]
        record.curse_seconds += int_sum(len(t.curses) for t in world.towers.values()) * dt
        if world.mana >= world.mana_max - 1e-9:
            record.mana_capped += dt

    def _sign(self, leader: int, kind: str, spot: tuple[int, int] = (-1, -1), curse: Curse | None = None) -> None:
        m = self.world.monster(leader)
        if m is not None:   # a leader killed in the step it spoke leaves no sign
            radius = curse_radius(curse, m.kind) if curse is not None else 0.0
            self._signs[leader] = Sign(leader, kind, self.world.time, self.world.position(m), spot, curse, radius)

    def threats(self) -> list[Sign]:
        """The leaders' signs a person has taken in by now, the oldest first: those most about to curse."""
        seen = [s for s in self._signs.values() if s.since + self.react <= self.world.time + 1e-9]
        return sorted(seen, key=lambda s: (s.kind not in ("chant", "mark"), s.since, s.leader))

    # -- Spells ------------------------------------------------------------------------------------

    def _aimed(self) -> None:
        if self.world.time - self._last_aim < self.aim_gap - 1e-9:
            raise Refused("One aimed spell at a time.")

    def smite(self, monster_id: int) -> None:
        self._aimed()
        self.world.smite(monster_id)
        self._cast("smite")

    def meteor(self, x: float, y: float) -> None:
        self._aimed()
        self.world.meteor(x, y)
        self._cast("meteor")

    def orb(self, x: float, y: float) -> None:
        self._aimed()
        self.world.orb(x, y)
        self._cast("orb")

    def hymn(self, tower_id: int) -> None:
        self.world.hymn(tower_id)
        self.record.spells["hymn"] += 1

    def _cast(self, spell: str) -> None:
        self._last_aim = self.world.time
        self.record.spells[spell] += 1


def reference_kit(location: Location, learned: frozenset[str], seed: int, *,
                loadout: Loadout = EMPTY_LOADOUT, gold: int | None = None,
                lives: int | None = None) -> Kit:
    """The Kit today's convention deals: the location's start gold and sanctuary lives, the learned skills,
    and the seed. The per-location tools deal from here, so one defence then and now starts the same."""
    return Kit(location=location, learned=learned, loadout=loadout, seed=seed,
               gold=location.start_gold if gold is None else gold,
               lives=START_LIVES if lives is None else lives)


def defend(kit: Kit, player: Player, *, planner: Planner | None, hardness: float = 1.0,
           lives: int | None = None, limit: float = 3000.0, curse_scale: float = 1.0,
           watch: Callable[[World], None] | None = None) -> tuple[World, Record]:
    """One defence played to its end by a player, from its Kit. ``hardness`` scales every monster's life,
    leaving the spells as they are (the balance tools' margin); ``lives`` replaces the sanctuary's (the
    balance tools set it huge to count every life lost); *watch* sees the world after every step, with that
    step's events. A defence still undecided after ``limit`` seconds is a bug. ``curse_scale`` multiplies
    every curse radius (0 = only the marked tile)."""
    world = kit.world(hardness=hardness, planner=planner, record=True, curse_scale=curse_scale)
    if lives is not None:
        world.lives = lives
    react = react_for(kit.seed, getattr(player, 'reaction', REACT))
    aim_gap = getattr(player, 'aim_gap', AIM_GAP)
    hands = Hands(world, react, aim_gap)
    hands.record.skills = kit.learned
    while world.outcome is None and world.time < limit:
        player.act(hands)
        world.step(SIM_DT)
        if watch is not None:
            watch(world)
        hands.observe(world.events)
        world.events.clear()
    if world.outcome is None:
        where = f"{kit.location.key}, seed {kit.seed}"
        raise RuntimeError(f"{player.name} on {where}: undecided after {world.time:.0f} s")
    return world, hands.record

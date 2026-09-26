"""What a scripted player sees and does: a person's view of a defence, and a person's hands.

A player reads the world as a person reads the screen: where every monster walks, its life, the towers and
the curses on them, the gates, the gold and the mana. Leaders are the exception. A person sees a leader ponder
(the dots over its head) and chant (the beam to a tower) and answers a moment later, so :meth:`Hands.threats`
shows each sign only :attr:`Hands.react` seconds of game time after it appears. A player never reads a leader's
mind: not its planner, its cooldown or its chant's clock; it does not clone the live world to see the future, and
it never pauses (``tests/test_players.py`` holds every player's source to this). Its aimed spells (Smite, Meteor,
Frozen Orb) come at most one each :data:`AIM_GAP` seconds. Everything else it does through the world's own
commands, as the panel does.

:func:`defend` plays one defence from its start and returns the world and a :class:`Record` of what happened,
for the balance tools.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Protocol

from hellward.sim.campaign import Difficulty, Location
from hellward.sim.content import Curse
from hellward.sim.model import SIM_DT, Planner, Refused, World
from hellward.sim.skills import cost, perks

REACT = (0.5, 0.8)    # a person answers a leader's sign this long after it appears, drawn per seed
AIM_GAP = 0.5         # seconds between two aimed spells


class Player(Protocol):
    name: str

    def skills(self, location: Location, difficulty: Difficulty, sigils: int) -> frozenset[str]:
        """The skills it learns for this defence, costing at most ``sigils`` (unlearning is free)."""

    def act(self, hands: Hands) -> None:
        """Called before every step of the world; a player decides as often as it likes."""


@dataclass(frozen=True)
class Sign:
    leader: int
    kind: str                     # "ponder" (the dots) or "chant" (the beam)
    since: float                  # when it appeared
    tower: int = -1               # a chant's tower: the beam points at it
    curse: Curse | None = None    # a chant's curse: its colour and sigil show which


@dataclass
class Record:
    """What happened in a defence, counted from its events."""

    chants: int = 0               # curses the leaders began to chant
    broken: int = 0               # ponderings and chants a spell broke
    landed: int = 0
    warded: int = 0               # curses that broke on a ward
    fizzled: int = 0              # chants whose leader died or walked out of reach
    curse_seconds: float = 0.0    # seconds of curses held on towers, summed over towers
    mana_capped: float = 0.0      # seconds the mana orb sat full
    spells: Counter = field(default_factory=Counter)
    leaks: Counter = field(default_factory=Counter)   # lives lost by wave


def react_for(seed: int) -> float:
    return REACT[0] + (REACT[1] - REACT[0]) * random.Random(seed * 7919 + 17).random()


class Hands:
    def __init__(self, world: World, react: float) -> None:
        self.world = world
        self.react = react
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
                self._signs[e[1]] = Sign(e[1], "ponder", world.time)
            elif kind == "plan":
                self._signs.pop(e[1], None)
            elif kind == "chant":
                self._signs[e[1]] = Sign(e[1], "chant", world.time, e[3], e[2])
                record.chants += 1
            elif kind == "broken":
                self._signs.pop(e[1], None)
                record.broken += 1
            elif kind == "cursed":
                self._signs.pop(e[1], None)
                record.landed += 1
            elif kind == "ward_holds":
                self._signs.pop(e[1], None)
                record.warded += 1
            elif kind == "fizzle":
                self._signs.pop(e[1], None)
                record.fizzled += 1
            elif kind == "death":
                self._signs.pop(e[1], None)
            elif kind == "leak":
                self._signs.pop(e[1], None)
                record.leaks[world.wave] += e[3]
        record.curse_seconds += sum(len(t.curses) for t in world.towers.values()) * dt
        if world.mana >= world.mana_max - 1e-9:
            record.mana_capped += dt

    def threats(self) -> list[Sign]:
        """The leaders' signs a person has taken in by now, the oldest first: those most about to curse."""
        seen = [s for s in self._signs.values() if s.since + self.react <= self.world.time + 1e-9]
        return sorted(seen, key=lambda s: (s.kind != "chant", s.since, s.leader))

    # -- Spells ------------------------------------------------------------------------------------

    def _aimed(self) -> None:
        if self.world.time - self._last_aim < AIM_GAP - 1e-9:
            raise Refused("One aimed spell at a time.")

    def smite(self, monster_id: int) -> None:
        self._aimed()
        self.world.smite(monster_id)
        self._cast("smite")

    def smite_threat(self) -> bool:
        """The panel's Q with a leader pondering or chanting: smite the one closest to cursing. Whether it cast."""
        threats = self.threats()
        if not threats:
            return False
        self.smite(threats[0].leader)
        return True

    def meteor(self, x: float, y: float) -> None:
        self._aimed()
        self.world.meteor(x, y)
        self._cast("meteor")

    def orb(self, x: float, y: float) -> None:
        self._aimed()
        self.world.orb(x, y)
        self._cast("orb")

    def cleanse(self, tower_id: int) -> None:
        self.world.cleanse(tower_id)
        self.record.spells["cleanse"] += 1

    def _cast(self, spell: str) -> None:
        self._last_aim = self.world.time
        self.record.spells[spell] += 1


def defend(location: Location, difficulty: Difficulty, player: Player, *, seed: int, sigils: int,
           planner: Planner | None, hp: float = 1.0, limit: float = 3000.0) -> tuple[World, Record]:
    """One defence played to its end by a player; ``hp`` scales every monster's life (the balance tools' margin)."""
    learned = player.skills(location, difficulty, sigils)
    if cost(learned) > sigils:
        raise ValueError(f"{player.name} learned {cost(learned)} sigils' worth of skills with {sigils}")
    world = World(location, difficulty=replace(difficulty, hp=difficulty.hp * hp), perks=perks(learned), seed=seed,
                  planner=planner)
    world.record = True
    hands = Hands(world, react_for(seed))
    while world.outcome is None and world.time < limit:
        player.act(hands)
        world.step(SIM_DT)
        hands.observe(world.events)
        world.events.clear()
    return world, hands.record


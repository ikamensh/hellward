"""The rules: a fixed-step simulation of one defence, with no saga2d in it.

The scene steps a :class:`World` in whole :data:`SIM_DT` s. The leaders' planner clones the world and steps
the clones at a coarser ``dt`` to look ahead, so a step must be cheap, deterministic and free of anything
the clone does not carry. Randomness only decides where in the corridor a monster walks (``lane``) and how
far back from a door it queues (``jostle``); it comes from the world's own seeded stream.

A world is one :class:`~hellward.sim.campaign.Location`, with the player's learned skills
(:class:`~hellward.sim.skills.Perks`) baked in when it begins.

Events for the view are appended to :attr:`World.events` when ``record`` is on; clones switch it off.

Compiled by mypyc (:mod:`hellward.sim.fastsim`), a class's ``__new__`` runs its ``__init__``, so there is no blank
object to fill: copies are made by the constructors, and the classes whose constructor needs arguments say in
``__reduce__`` how they are pickled.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Final

from hellward.sim.campaign import CATHEDRAL, Location
from hellward.sim.content import (
    BURN_RADIUS, CONTAGION_REACH, CORPSE_RADIUS, CORPSE_SHARE, CURSES, DOOR, EARLY_CALL_GOLD, HURRICANE_RADIUS,
    HURRICANE_SLOW, MANA_START, MAX_POISON_STACKS, MONSTERS, SELL_REFUND, SHATTER_RADIUS, SHATTER_SHARE, SOUL, SPELLS,
    START_LIVES, THORNS, TOWERS, TWISTER_HELD, TWISTER_PERIOD, TWISTER_RADIUS, WARD, WAVE_BREAK, Curse, Element,
    MonsterKind, TowerKind, TowerLevel,
)
from hellward.sim.skills import NO_PERKS, RANK_SKILL, SKILLS, Perks, baked

if TYPE_CHECKING:
    from hellward.sim.planner import Decision

SIM_DT: Final = 0.05
DOOR_STOP: Final = 0.45         # how far before a door's centre the front of a queue stands
JOSTLE: Final = 0.6             # the queue behind a door is this deep
CHAIN_JUMP: Final = 1.7         # how far chain lightning leaps
DECIDE_DELAY: Final = 0.5       # a leader ponders this long between asking its planner and starting to chant
HOLD_RETRY: Final = 1.0         # a leader that holds its curse thinks again after this long
CAST_SLACK: Final = 1.0         # a curse lands if the tower is within reach + slack when the chant ends
FIRST_WAVE_BREAK: Final = 30.0
LEAK_WEIGHT: Final = 2.0        # a monster through the sanctuary gate is worth twice its life to its side
BLAZE_TIME: Final = 2.0         # seconds the floor burns where a fireball lands, under Blaze


class Refused(Exception):
    """A command the rules do not allow right now; the message says why, for the player."""


class Monster:
    __slots__ = ("id", "kind", "hp", "max_hp", "s", "lane", "jostle", "chill", "chill_left", "frozen", "poison", "wave",
                 "cooldown", "asking", "ask_left", "chant_curse", "chant_spot", "chant_left", "door",
                 "amplified", "amplify", "risen", "marking")

    def __init__(self, id: int, kind: MonsterKind, wave: int, lane: float, jostle: float, hp: float, cooldown: float) -> None:
        self.id = id
        self.kind = kind
        self.hp = hp
        self.max_hp = hp
        self.s = 0.0
        self.lane = lane
        self.jostle = jostle
        self.chill = 0.0
        self.chill_left = 0.0
        self.frozen = 0.0                     # seconds it stays frozen solid (Frozen Orb)
        self.poison: list[list[float]] = []   # [dps, seconds left] per stack
        self.wave = wave
        self.cooldown = cooldown
        self.asking: Any = None               # the planner's handle while a leader waits for its answer
        self.ask_left = 0.0
        self.chant_curse: Curse | None = None
        self.chant_spot: tuple[int, int] = (-1, -1)
        self.chant_left = 0.0
        self.door = -1                        # the door socket it is battering, or -1
        self.amplified = 0.0                  # seconds of Amplify Damage left
        self.amplify = 0.0                    # the fraction it takes extra (0.3 = 30% more damage)
        self.risen = False                    # has this monster been raised once already
        self.marking = False                  # is this leader currently marking (instead of chanting)

    def copy(self) -> Monster:
        """Everything but a leader's pending question to its planner."""
        m = Monster(self.id, self.kind, self.wave, self.lane, self.jostle, self.hp, self.cooldown)
        m.max_hp, m.s, m.chill, m.chill_left, m.frozen = self.max_hp, self.s, self.chill, self.chill_left, self.frozen
        m.poison = [stack[:] for stack in self.poison]
        m.chant_curse, m.chant_spot, m.chant_left, m.door = self.chant_curse, self.chant_spot, self.chant_left, self.door
        m.amplified, m.amplify = self.amplified, self.amplify
        m.risen, m.marking = self.risen, self.marking
        return m

    def __reduce__(self) -> tuple[Any, ...]:
        return Monster, (self.id, self.kind, self.wave, self.lane, self.jostle, self.hp, self.cooldown), self.__getstate__()

    @property
    def speed(self) -> float:
        if self.frozen > 0:
            return 0.0
        return self.kind.speed * (1.0 - self.chill) if self.chill_left > 0 else self.kind.speed

    @property
    def chanting(self) -> bool:
        return self.chant_curse is not None


class Tower:
    __slots__ = ("id", "kind", "levels", "level", "tile", "cooldown", "curses", "ward", "spent", "spans", "spans_reach",
                 "timer")

    def __init__(self, id: int, kind: TowerKind, levels: tuple[TowerLevel, ...], tile: tuple[int, int]) -> None:
        self.id = id
        self.kind = kind
        self.levels = levels                  # its kind's ranks with the player's skills in them
        self.level = 0
        self.tile = tile
        self.cooldown = 0.0
        self.curses: dict[Curse, float] = {}
        self.ward = 0.0                       # seconds no curse can land on it (Salvation)
        self.spent = levels[0].cost
        self.spans: tuple[tuple[float, float], ...] = ()   # the path it reaches, for the reach it had last
        self.spans_reach = -1.0
        self.timer = 0.0                      # a grove's twister clock

    def copy(self) -> Tower:
        t = Tower(self.id, self.kind, self.levels, self.tile)
        t.level, t.cooldown, t.curses = self.level, self.cooldown, dict(self.curses)
        t.ward, t.spent, t.spans, t.spans_reach = self.ward, self.spent, self.spans, self.spans_reach
        t.timer = self.timer
        return t

    def __reduce__(self) -> tuple[Any, ...]:
        return Tower, (self.id, self.kind, self.levels, self.tile), self.__getstate__()

    @property
    def stats(self) -> TowerLevel:
        return self.levels[self.level]

    @property
    def centre(self) -> tuple[float, float]:
        return self.tile[0] + 0.5, self.tile[1] + 0.5

    def damage_mult(self) -> float:
        value = 1.0
        for curse in self.curses:
            value *= CURSES[curse].damage
        return value

    def rate_mult(self) -> float:
        value = 1.0
        for curse in self.curses:
            value *= CURSES[curse].rate
        return value

    def range_mult(self) -> float:
        value = 1.0
        for curse in self.curses:
            value *= CURSES[curse].range
        return value

    @property
    def silenced(self) -> bool:
        for curse in self.curses:
            if CURSES[curse].silenced:
                return True
        return False

    @property
    def reach(self) -> float:
        return self.stats.range * self.range_mult()


class Door:
    __slots__ = ("index", "tile", "s", "hp", "built", "rubble")

    def __init__(self, index: int, tile: tuple[int, int], s: float) -> None:
        self.index = index
        self.tile = tile
        self.s = s
        self.hp = 0.0
        self.built = False
        self.rubble = False    # broken: it cannot be warded again until the fight dies down between waves

    def copy(self) -> Door:
        d = Door(self.index, self.tile, self.s)
        d.hp, d.built, d.rubble = self.hp, self.built, self.rubble
        return d

    def __reduce__(self) -> tuple[Any, ...]:
        return Door, (self.index, self.tile, self.s), self.__getstate__()


class Bolt:
    """A firebolt or a venom dart in flight; it lands on its monster, or where that monster fell.

    A bolt is never changed: each step makes a flying bolt anew, so clones and the view keep the ones they were
    given. It is a class of its own rather than a dataclass, whose ``__init__`` runs interpreted when compiled."""

    __slots__ = ("id", "tower", "kind", "target", "left", "damage", "element", "splash", "poison", "poison_time",
                 "origin", "last")

    def __init__(self, id: int, tower: int, kind: str, target: int, left: float, damage: float, element: Element,
                 splash: float, poison: float, poison_time: float, origin: tuple[float, float],
                 last: tuple[float, float]) -> None:
        self.id = id
        self.tower = tower
        self.kind = kind                # the tower kind's key
        self.target = target
        self.left = left                # seconds to impact
        self.damage = damage
        self.element = element
        self.splash = splash
        self.poison = poison
        self.poison_time = poison_time
        self.origin = origin
        self.last = last                # the target's last known position

    def __reduce__(self) -> tuple[Any, ...]:
        return Bolt, (self.id, self.tower, self.kind, self.target, self.left, self.damage, self.element, self.splash,
                      self.poison, self.poison_time, self.origin, self.last)


@dataclass(frozen=True)
class Meteor:
    at: float                   # when it lands
    x: float
    y: float
    damage: float
    burn: float                 # damage per second of the floor it sets burning


class Hazard:
    """Burning floor: every walker on it takes fire damage each second (flyers pass over)."""

    __slots__ = ("x", "y", "radius", "dps", "left")

    def __init__(self, x: float, y: float, radius: float, dps: float, left: float) -> None:
        self.x, self.y, self.radius, self.dps, self.left = x, y, radius, dps, left

    def copy(self) -> Hazard:
        return Hazard(self.x, self.y, self.radius, self.dps, self.left)

    def __reduce__(self) -> tuple[Any, ...]:
        return Hazard, (self.x, self.y, self.radius, self.dps, self.left)


@dataclass
class ForcedCurse:
    """A curse a rollout lands at a fixed time, standing in for a leader's chant."""

    at: float
    leader: int
    curse: Curse
    spot: tuple[int, int]


def curse_radius(curse: Curse, leader_kind: MonsterKind | None) -> float:
    """The radius a curse falls in when this kind casts it: its own radius, widened by its leader."""
    widen = 0.0
    if leader_kind is not None and leader_kind.leader is not None:
        widen = leader_kind.leader.widen
    return CURSES[curse].radius + widen


Planner = Callable[["World", int], Any]   # returns a handle with .result() -> Decision


class World:
    def __init__(self, location: Location = CATHEDRAL, *, hardness: float = 1.0, perks: Perks = NO_PERKS,
                 seed: int = 0, planner: Planner | None = None, record: bool = True) -> None:
        self.location = location
        self.level = location.level
        self.waves = location.waves
        self.perks = perks
        self.tower_levels = baked(perks)
        self.hardness = hardness   # every monster's life is multiplied by this; the spells are not
        self.rng = random.Random(seed)
        self.planner = planner
        self.record = record
        self.events: list[tuple] = []
        self.time = 0.0
        self.gold = location.start_gold
        self.lives = START_LIVES
        self.mana = min(MANA_START, perks.mana_max)
        self.towers: dict[int, Tower] = {}
        self.doors = [Door(i, tile, s) for i, (tile, s) in enumerate(zip(self.level.doors, self.level.door_s))]
        self.monsters: list[Monster] = []     # alive and on the map, furthest along first
        self.bolts: list[Bolt] = []
        self.meteors: list[Meteor] = []
        self.hazards: list[Hazard] = []
        self.wave = -1                        # index of the latest wave called
        self.schedule: list[tuple[float, str]] = []   # (seconds after the wave began, monster kind), soonest last
        self.wave_time = 0.0
        self.break_left: float | None = FIRST_WAVE_BREAK
        self.wave_alive: dict[int, int] = {}
        self.unpaid: list[int] = []           # waves whose clearing bonus is still to come
        self.leaked_life = 0.0                # monster life that reached the sanctuary, weighted (the planner's score)
        self.forced: list[ForcedCurse] = []
        self.outcome: str | None = None       # "victory" or "defeat"
        self.kills = 0
        self.curses_landed = 0
        self.cleanses = 0
        self.spells_cast = 0
        self.chants_broken = 0
        self.recharge: dict[str, float] = {}  # seconds each spell still gathers itself after a cast
        self._next_id = 1

    # -- Copies for the planner ---------------------------------------------------------

    def clone(self) -> World:
        """A private copy to look ahead in: no events, no planner, its own random stream."""
        w = World(self.location, hardness=self.hardness, perks=self.perks, record=False)
        w.rng.setstate(self.rng.getstate())
        w.time, w.gold, w.lives, w.mana = self.time, self.gold, self.lives, self.mana
        w.towers = {i: t.copy() for i, t in self.towers.items()}
        w.doors = [d.copy() for d in self.doors]
        w.monsters = [m.copy() for m in self.monsters]
        w.bolts = list(self.bolts)       # bolts and meteors are never changed in place
        w.meteors = list(self.meteors)
        w.hazards = [h.copy() for h in self.hazards]
        w.recharge = dict(self.recharge)
        w.wave, w.schedule, w.wave_time, w.break_left = self.wave, list(self.schedule), self.wave_time, self.break_left
        w.wave_alive, w.unpaid = dict(self.wave_alive), list(self.unpaid)
        w.leaked_life, w.forced, w.outcome, w.kills, w._next_id = self.leaked_life, [], self.outcome, self.kills, self._next_id
        w.curses_landed, w.cleanses, w.spells_cast, w.chants_broken = self.curses_landed, self.cleanses, self.spells_cast, self.chants_broken
        return w

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _emit(self, *event: Any) -> None:
        if self.record:
            self.events.append(event)

    # -- Queries ------------------------------------------------------------------------

    def monster(self, monster_id: int) -> Monster | None:
        for m in self.monsters:
            if m.id == monster_id:
                return m
        return None

    def position(self, m: Monster) -> tuple[float, float]:
        return self.level.point(m.s)

    def tower_at(self, tile: tuple[int, int]) -> Tower | None:
        for t in self.towers.values():
            if t.tile == tile:
                return t
        return None

    def caught(self, spot: tuple[int, int], radius: float) -> list[Tower]:
        """The towers standing within ``radius`` tiles of ``spot``'s tile, in id order."""
        found = []
        sx, sy = spot
        for t in self.towers.values():
            if (t.tile[0] - sx) ** 2 + (t.tile[1] - sy) ** 2 <= radius * radius:
                found.append(t)
        found.sort(key=lambda t: t.id)
        return found

    def in_reach(self, tower: Tower, s: float) -> bool:
        for a, b in self.level.coverage(tower.tile, tower.reach):
            if a <= s <= b:
                return True
        return False

    @property
    def spawning(self) -> bool:
        return bool(self.schedule)

    @property
    def can_call_wave(self) -> bool:
        return self.outcome is None and not self.schedule and self.wave + 1 < len(self.waves)

    def leaders(self) -> list[Monster]:
        return [m for m in self.monsters if m.kind.leader is not None]

    @property
    def mana_max(self) -> float:
        return self.perks.mana_max

    @property
    def gate_life(self) -> float:
        return self.perks.gate_life

    def spell_cost(self, key: str) -> float:
        if key == "cleanse":
            return self.perks.cleanse_cost
        return SPELLS[key].mana * self.perks.spell_cost

    def power(self) -> float:
        """How hard a spell strikes: with the monsters' life now, and with Spell Mastery."""
        return self.waves[max(self.wave, 0)].hp * self.location.life * self.perks.spell_power

    def cost(self, kind: str) -> int:
        return self.tower_levels[kind][0].cost

    # -- Commands -----------------------------------------------------------------------

    def build(self, kind: str, tile: tuple[int, int]) -> Tower:
        tower_kind = TOWERS[kind]
        if kind not in self.location.arsenal.towers:
            raise Refused(f"No {tower_kind.name} can be raised in {self.location.called}.")
        if not self.level.buildable(*tile):
            raise Refused("Towers stand on the bare floor, not on the path, the walls or the pits.")
        if self.tower_at(tile) is not None:
            raise Refused("A tower already stands there.")
        levels = self.tower_levels[kind]
        cost = levels[0].cost
        if self.gold < cost:
            raise Refused(f"{tower_kind.name} costs {cost} gold.")
        self.gold -= cost
        tower = Tower(self._id(), tower_kind, levels, tile)
        self.towers[tower.id] = tower
        self._emit("built", tower.id)
        return tower

    def upgrade_cost(self, tower: Tower) -> int | None:
        if tower.level + 1 >= len(tower.levels):
            return None
        return tower.levels[tower.level + 1].cost

    def rank_needs(self, tower: Tower) -> str | None:
        """The skill that would allow the tower's next rank, or None when it may be bought (or is at its top)."""
        nxt = tower.level + 1
        if nxt >= len(tower.levels):
            return None
        if nxt <= self.perks.top(tower.kind.key):
            return None
        pair = RANK_SKILL.get(tower.kind.key)
        if pair is None:
            return None
        return pair[0] if nxt <= 1 else pair[1]

    def upgrade(self, tower_id: int) -> None:
        tower = self.towers[tower_id]
        cost = self.upgrade_cost(tower)
        if cost is None:
            raise Refused(f"{tower.kind.name} is at its highest rank.")
        need = self.rank_needs(tower)
        if need is not None:
            raise Refused(f"Learn {SKILLS[need].name} in the skill tree (K).")
        if self.gold < cost:
            raise Refused(f"The next rank costs {cost} gold.")
        self.gold -= cost
        tower.level += 1
        tower.spent += cost
        self._emit("upgraded", tower.id)

    def sell(self, tower_id: int) -> int:
        tower = self.towers[tower_id]
        if tower.curses:
            raise Refused("The curse holds it.")
        del self.towers[tower_id]
        refund = int(tower.spent * SELL_REFUND)
        self.gold += refund
        self._emit("sold", tower.id, tower.tile, refund)
        return refund

    def build_door(self, index: int) -> None:
        if not self.location.arsenal.gates:
            raise Refused(f"There are no arches to ward in {self.location.called}.")
        door = self.doors[index]
        if door.built:
            raise Refused("The gate already stands.")
        if door.rubble:
            raise Refused("The arch lies in rubble until the fight dies down between waves.")
        if self.gold < DOOR.cost:
            raise Refused(f"A warded gate costs {DOOR.cost} gold.")
        for m in self.monsters:
            if not m.kind.flying and abs(m.s - door.s) < 0.6:
                raise Refused("Monsters stand in the arch.")
        self.gold -= DOOR.cost
        door.built, door.hp = True, self.gate_life
        self._emit("door_built", index)

    def _spend(self, key: str) -> None:
        if key not in self.location.arsenal.spells:
            raise Refused(f"{SPELLS[key].name} is not yours to cast in {self.location.called}.")
        left = self.recharge.get(key, 0.0)
        if left > 0:
            raise Refused(f"{SPELLS[key].name} gathers itself again: {math.ceil(left)} s.")
        cost = self.spell_cost(key)
        if self.mana < cost:
            raise Refused(f"{SPELLS[key].name} takes {cost:.0f} mana.")
        self.mana -= cost
        self.spells_cast += 1
        if SPELLS[key].recharge > 0:
            self.recharge[key] = SPELLS[key].recharge

    def cleanse(self, tower_id: int) -> None:
        tower = self.towers[tower_id]
        if not tower.curses:
            if not self.perks.salvation:
                raise Refused("That tower carries no curse.")
            self._spend("cleanse")
            self.cleanses += 1
            tower.ward = WARD
            self._emit("cleansed", tower.id, [])
            return
        self._spend("cleanse")
        self.cleanses += 1
        lifted = sorted(tower.curses)
        tower.curses.clear()
        if self.perks.salvation:
            tower.ward = WARD
        self._emit("cleansed", tower.id, lifted)

    def smite(self, monster_id: int) -> None:
        m = self.monster(monster_id)
        if m is None or m.hp <= 0:
            raise Refused("There is nothing there to smite.")
        self._spend("smite")
        self._emit("smite", m.id, self.level.point(m.s))
        if m.chant_curse is not None or m.asking is not None:
            self._break(m)
        self._hurt(m, SPELLS["smite"].damage * self.power(), None)
        self._bury()   # cast between steps: what it killed must not walk on into the next one

    def meteor(self, x: float, y: float) -> None:
        self._inside_map(x, y)
        self._spend("meteor")
        spec = SPELLS["meteor"]
        power = self.power()
        self.meteors.append(Meteor(self.time + spec.delay, x, y, spec.damage * power, spec.burn * power))
        self._emit("meteor_cast", x, y, spec.delay)

    def orb(self, x: float, y: float) -> None:
        self._inside_map(x, y)
        self._spend("orb")
        spec = SPELLS["orb"]
        damage = spec.damage * self.power()
        struck = self._around(x, y, spec.radius, flyers=True)
        self._emit("orb", x, y, [m.id for m in struck])
        for m in struck:
            m.frozen = max(m.frozen, spec.lasting)
            m.door = -1
            if m.chant_curse is not None or m.asking is not None:
                self._break(m)
        for m in struck:
            self._hurt(m, damage, Element.COLD)
        self._bury()

    def _inside_map(self, x: float, y: float) -> None:
        if not (0 <= x <= self.level.width and 0 <= y <= self.level.height):
            raise Refused("That is outside the walls.")

    def _around(self, x: float, y: float, radius: float, *, flyers: bool) -> list[Monster]:
        found = []
        level = self.level
        for m in self.monsters:
            if m.hp <= 0 or (m.kind.flying and not flyers):
                continue
            mx, my = level.point(m.s)
            if (mx - x) ** 2 + (my - y) ** 2 <= radius * radius:
                found.append(m)
        return found

    def call_wave(self) -> None:
        if not self.can_call_wave:
            raise Refused("The next wave cannot be called yet.")
        if self.break_left is not None and self.wave >= 0:
            bonus = int(self.break_left * EARLY_CALL_GOLD)
            self.gold += bonus
        self._start_wave()

    def _start_wave(self) -> None:
        self.wave += 1
        self.break_left = None
        self.wave_time = 0.0
        schedule = []
        for group in self.waves[self.wave].groups:
            for i in range(group.count):
                schedule.append((group.start + i * group.interval, group.kind))
        schedule.sort(reverse=True)
        self.schedule = schedule
        self.wave_alive[self.wave] = len(schedule)
        self.unpaid.append(self.wave)
        self._emit("wave", self.wave)

    # -- The step -----------------------------------------------------------------------

    def step(self, dt: float = SIM_DT) -> None:
        if self.outcome is not None:
            return
        self.time += dt
        self.mana = min(self.perks.mana_max, self.mana + self.perks.mana_regen * dt)
        if self.recharge:
            for key in list(self.recharge):
                left = self.recharge[key] - dt
                if left <= 0:
                    del self.recharge[key]
                else:
                    self.recharge[key] = left
        self._spawn(dt)
        self._leaders(dt)
        self._move(dt)
        self._towers(dt)
        self._bolts(dt)
        self._meteors()
        self._afflictions(dt)
        self._curses(dt)
        self._waves(dt)
        planner = self.planner
        if planner is not None:   # only a world with a planner has leaders that ask
            for m in self.monsters:
                if m.asking is _ASK:   # asked now, at a step boundary, so the planner's clone starts where a step would
                    m.asking = planner(self, m.id)

    def _spawn(self, dt: float) -> None:
        if self.break_left is not None:
            self.break_left -= dt
            if self.break_left <= 0 and self.wave + 1 < len(self.waves):
                self._start_wave()
            return
        if not self.schedule:
            return
        self.wave_time += dt
        while self.schedule and self.schedule[-1][0] <= self.wave_time:
            _, key = self.schedule.pop()
            kind = MONSTERS[key]
            cooldown = kind.leader.first_cast if kind.leader is not None else 0.0
            m = Monster(self._id(), kind, self.wave, self.rng.uniform(-0.28, 0.28), self.rng.uniform(0.0, JOSTLE),
                        kind.hp * self.waves[self.wave].hp * self.location.life * self.hardness, cooldown)
            self.monsters.append(m)
            self._emit("spawn", m.id)

    def _leaders(self, dt: float) -> None:
        for fc in self.forced:
            if fc.at <= self.time:
                self._land(fc.leader, fc.curse, fc.spot)
        if self.forced:
            self.forced = [fc for fc in self.forced if fc.at > self.time]
        for m in self.monsters:
            spec = m.kind.leader
            if spec is None:
                continue
            if m.chant_curse is not None:
                m.chant_left -= dt
                if m.chant_left <= 0:
                    self._land(m.id, m.chant_curse, m.chant_spot)
                    m.chant_curse, m.chant_spot = None, (-1, -1)
                    m.marking = False
                continue
            if m.asking is not None:
                m.ask_left -= dt
                if m.ask_left <= 0:
                    decision: Decision = m.asking.result()
                    m.asking = None
                    self._emit("plan", m.id, decision)
                    if m.frozen > 0:
                        m.cooldown = HOLD_RETRY   # frozen while it made up its mind: it cannot chant
                    elif decision.cast is None:
                        m.cooldown = decision.retry
                    else:
                        if spec.mark > 0:
                            m.chant_curse, m.chant_spot, m.chant_left = decision.cast.curse, decision.cast.spot, spec.mark
                            m.marking = True
                            m.cooldown = spec.cooldown
                            self._emit("mark", m.id, decision.cast.curse, decision.cast.spot)
                        else:
                            m.chant_curse, m.chant_spot, m.chant_left = decision.cast.curse, decision.cast.spot, spec.channel
                            m.marking = False
                            m.cooldown = spec.cooldown
                            self._emit("chant", m.id, decision.cast.curse, decision.cast.spot)
                continue
            m.cooldown -= dt
            if m.cooldown <= 0 and self.planner is not None and self.towers and m.frozen <= 0:
                m.asking = _ASK
                m.ask_left = DECIDE_DELAY
                self._emit("ponder", m.id)

    def _break(self, m: Monster) -> None:
        """A leader's pondering or chant broken by a spell: the curse never comes, and its whole cooldown starts again.
        A mark cannot be broken: Smite and Frozen Orb on a marking leader damage/freeze it but do not break the mark."""
        if m.marking:
            return
        spot = m.chant_spot
        m.chant_curse, m.chant_spot, m.chant_left = None, (-1, -1), 0.0
        m.asking, m.ask_left = None, 0.0
        spec = m.kind.leader
        if spec is not None:
            m.cooldown = spec.cooldown
        self.chants_broken += 1
        self._emit("broken", m.id, spot)

    def _land(self, leader_id: int, curse: Curse, spot: tuple[int, int]) -> None:
        leader = self.monster(leader_id)
        if leader is None:
            self._emit("fizzle", leader_id, spot)
            return
        spec = leader.kind.leader
        x, y = self.level.point(leader.s)
        cx, cy = spot[0] + 0.5, spot[1] + 0.5
        if spec is None or _hypot(cx - x, cy - y) > spec.cast_range + CAST_SLACK:
            self._emit("fizzle", leader_id, spot)
            return
        caught = self.caught(spot, curse_radius(curse, leader.kind))
        cursed: list[int] = []
        for tower in caught:
            if tower.ward > 0:
                self._emit("ward_holds", leader_id, tower.id, curse)
            else:
                tower.curses[curse] = CURSES[curse].duration
                cursed.append(tower.id)
        if cursed:
            self.curses_landed += 1
            self._emit("cursed", leader_id, spot, curse, tuple(cursed))
            if spec is not None and spec.burn > 0:
                amount = spec.burn * len(cursed)
                if self.mana > 0:
                    burned = min(self.mana, amount)
                    self.mana -= burned
                    self._emit("burned", leader_id, burned)
        elif not any(t.ward > 0 for t in caught):
            self._emit("fizzle", leader_id, spot)
        leader.marking = False

    def _move(self, dt: float) -> None:
        doors = [d for d in self.doors if d.built]
        end = self.level.length
        monsters = self.monsters
        groves: list[tuple[float, float]] = []
        if self.perks.hurricane:
            for t in self.towers.values():
                if t.kind.key == "grove" and not t.silenced:
                    groves.append((t.tile[0] + 0.5, t.tile[1] + 0.5))
        leaked = False
        ordered, last = True, math.inf   # whether those still on the map run furthest first, as they did
        for m in monsters:
            if m.frozen > 0:
                m.frozen -= dt
                m.door = -1
                if m.chill_left > 0:
                    m.chill_left -= dt
            else:
                if m.chill_left > 0:
                    m.chill_left -= dt
                    speed = m.kind.speed * (1.0 - m.chill)
                else:
                    speed = m.kind.speed
                if groves and not m.kind.flying:
                    mx, my = self.level.point(m.s)
                    for gx, gy in groves:
                        dx, dy = mx - gx, my - gy
                        if dx * dx + dy * dy <= HURRICANE_RADIUS * HURRICANE_RADIUS:
                            speed *= HURRICANE_SLOW
                            break
                s = m.s + speed * dt
                m.door = -1
                if not m.kind.flying:
                    for d in doors:
                        stop = d.s - DOOR_STOP - m.jostle
                        if m.s <= stop + 1e-9 < s or stop - 1e-9 <= m.s < d.s:
                            s = min(s, stop)
                            if s >= stop - 1e-6:
                                m.door = d.index
                            break
                m.s = s
                if s >= end:
                    self.lives -= m.kind.lives
                    self.leaked_life += m.max_hp * LEAK_WEIGHT
                    self._count_off(m)
                    self._emit("leak", m.id, m.kind.key, m.kind.lives)
                    leaked = True
                    continue
            if m.s > last:
                ordered = False
            last = m.s
        if leaked:   # through the sanctuary gate: those that walked to the path's end, and only they
            monsters = self.monsters = [m for m in monsters if m.s < end]
        if not ordered:   # someone overtook
            _furthest_first(monsters)
        if self.lives <= 0 and self.outcome is None:
            self.lives = 0
            self.outcome = "defeat"
            self._emit("defeat")
        thorns = self.perks.thorns
        for m in monsters:
            if m.door >= 0:
                d = self.doors[m.door]
                blow = m.kind.door_dps * dt
                if m.chill_left > 0:
                    blow *= 1.0 - m.chill
                d.hp -= blow
                if thorns:
                    self._hurt(m, m.kind.door_dps * dt * THORNS, None, quiet=True)
                if d.hp <= 0 and d.built:
                    d.built, d.hp, d.rubble = False, 0.0, True
                    self._emit("door_broken", d.index)
                    doors = [x for x in doors if x.built]

    def _aura_mult(self, tower: Tower) -> float:
        """How much harder a tower strikes under the groves: 1 plus the best aura on it.

        Worked out when the damage is dealt, never kept on the world, so a clone never shares it.
        A grove's aura is not a reach: Dim Vision and Decrepify do nothing to it, Bone Prison stops it."""
        best = 0.0
        tx, ty = tower.tile[0] + 0.5, tower.tile[1] + 0.5
        for g in self.towers.values():
            if g.kind.key != "grove" or g.silenced:
                continue
            stats = g.levels[g.level]
            dx, dy = g.tile[0] + 0.5 - tx, g.tile[1] + 0.5 - ty
            if dx * dx + dy * dy <= stats.range * stats.range:
                bonus = stats.damage * (g.damage_mult() if g.curses else 1.0)
                if bonus > best:
                    best = bonus
        return 1.0 + best

    def _twister(self, t: Tower, dt: float) -> None:
        """A grove's root: every 4 s the walker nearest the sanctuary within 2.5 tiles stays put for 1.5 s."""
        if not self.perks.twister:
            return
        t.timer += dt
        if t.timer < TWISTER_PERIOD:
            return
        t.timer -= TWISTER_PERIOD
        gx, gy = t.tile[0] + 0.5, t.tile[1] + 0.5
        best: Monster | None = None
        for m in self.monsters:
            if m.hp <= 0 or m.kind.flying or m.kind.lives >= 2:
                continue
            x, y = self.level.point(m.s)
            dx, dy = x - gx, y - gy
            if dx * dx + dy * dy <= TWISTER_RADIUS * TWISTER_RADIUS and (best is None or m.s > best.s):
                best = m
        if best is not None:
            best.frozen = max(best.frozen, TWISTER_HELD)
            best.door = -1
            self._emit("twister", t.id, best.id)

    def _altar(self, t: Tower, stats: TowerLevel, spans: tuple[tuple[float, float], ...], near: float, far: float) -> None:
        """An altar's pulse: amplify the thickest knot of monsters in reach.

        Among the monsters in reach that are not amplified, the centre whose circle of the knot
        radius holds the most of their life (ties: furthest along the path) lends its circle every
        monster in it — flyers too — the bonus for the lasting. It does not stack."""
        monsters = self.monsters
        level = self.level
        cand: list[Monster] = []
        for m in monsters:
            if m.s < near:
                break
            if m.hp > 0 and m.s <= far and m.amplified <= 0 and _inside(m.s, spans):
                cand.append(m)
        if not cand:
            t.cooldown = 0.0   # no monster in reach: no cast, the timer waits
            return
        knot = stats.splash
        knot2 = knot * knot
        centres: list[tuple[Monster, float, float]] = []
        for m in cand:
            x, y = level.point(m.s)
            centres.append((m, x, y))
        best_c: Monster | None = None
        best_x, best_y, best_life = 0.0, 0.0, -1.0
        for c, cx, cy in centres:
            total = 0.0
            for m, x, y in centres:
                dx, dy = x - cx, y - cy
                if dx * dx + dy * dy <= knot2 + 1e-9:
                    total += m.hp
            if best_c is None:
                best_c, best_x, best_y, best_life = c, cx, cy, total
            elif total > best_life or (total == best_life and c.s > best_c.s):
                best_c, best_x, best_y, best_life = c, cx, cy, total
        if best_c is None:
            t.cooldown = 0.0
            return
        bonus = stats.damage * (t.damage_mult() if t.curses else 1.0)
        lasting = stats.lasting
        hit: list[int] = []
        for m in monsters:
            if m.hp <= 0:
                continue
            x, y = level.point(m.s)
            dx, dy = x - best_x, y - best_y
            if dx * dx + dy * dy <= knot2 + 1e-9:
                if m.amplify < bonus:
                    m.amplify = bonus
                if m.amplified < lasting:
                    m.amplified = lasting
                hit.append(m.id)
        rate = stats.rate * (t.rate_mult() if t.curses else 1.0)
        t.cooldown += 1.0 / rate
        self._emit("amplify", t.id, (best_x, best_y), tuple(hit))

    def _towers(self, dt: float) -> None:
        monsters = self.monsters
        if not monsters:
            for t in self.towers.values():
                t.cooldown = max(0.0, t.cooldown - dt)
            return
        level = self.level
        static = self.perks.static_field
        for t in self.towers.values():
            if t.cooldown > 0:
                t.cooldown -= dt
                if t.cooldown > 0:
                    continue
            if t.curses and t.silenced:
                t.cooldown = 0.0
                continue
            attack = t.kind.attack
            if attack == "aura":   # a grove never attacks; its timer waits while silenced (above)
                self._twister(t, dt)
                t.cooldown = 0.0
                continue
            stats = t.levels[t.level]
            reach = stats.range * t.range_mult() if t.curses else stats.range
            if reach != t.spans_reach:
                t.spans, t.spans_reach = level.coverage(t.tile, reach), reach
            spans = t.spans
            if not spans:
                t.cooldown = 0.0
                continue
            # The monsters run furthest first and the spans along the path: none past the last span's end can be in
            # reach, and after the first short of the first span's start, none is.
            near, far = spans[0][0], spans[-1][1]
            if attack == "amplify":
                self._altar(t, stats, spans, near, far)
                continue
            if attack == "nova":
                hit = []
                for m in monsters:
                    if m.s < near:
                        break
                    if m.hp > 0 and m.s <= far and _inside(m.s, spans):
                        hit.append(m)
            elif attack == "venom":   # the strongest it can poison
                best = None
                for m in monsters:
                    if m.s < near:
                        break
                    if (m.hp > 0 and m.s <= far and (best is None or m.hp > best.hp) and m.kind.taken(Element.POISON) > 0
                            and _inside(m.s, spans)):
                        best = m
                hit = [best] if best is not None else []
            else:
                hit = []
                for m in monsters:
                    if m.s < near:
                        break
                    if m.hp > 0 and m.s <= far and _inside(m.s, spans):
                        if not hit:
                            hit = [m]
                            if not (static and attack == "chain") or m.kind.leader is not None:
                                break
                        elif m.kind.leader is not None:   # Static Field: a leader in reach draws the first strike
                            hit = [m]
                            break
            if not hit:
                t.cooldown = 0.0
                continue
            aura = self._aura_mult(t)
            damage = stats.damage * (t.damage_mult() if t.curses else 1.0) * aura
            rate = stats.rate * (t.rate_mult() if t.curses else 1.0)
            t.cooldown += 1.0 / rate
            if attack == "nova":
                self._emit("nova", t.id)
                for m in hit:
                    chill = stats.chill * m.kind.taken(Element.COLD)   # the slow follows cold resistance
                    if chill > 0.0:
                        if chill >= m.chill or m.chill_left <= 0:
                            m.chill = chill
                        m.chill_left = max(m.chill_left, stats.chill_time)
                    self._hurt(m, damage, t.kind.element)
            elif attack == "chain":
                self._chain(t, hit[0], damage, stats.chains)
            else:
                target = hit[0]
                origin = t.centre
                last = self.level.point(target.s)
                distance = _hypot(last[0] - origin[0], last[1] - origin[1])
                bolt = Bolt(self._id(), t.id, t.kind.key, target.id, distance / t.kind.bolt_speed, damage, t.kind.element,
                            stats.splash, stats.poison * aura, stats.poison_time, origin, last)
                self.bolts.append(bolt)
                self._emit("bolt", bolt)

    def _chain(self, tower: Tower, first: Monster, damage: float, jumps: int) -> None:
        level = self.level
        static = self.perks.static_field
        struck = [first]
        struck_ids = {first.id}
        where = [level.point(first.s)]
        current, pos = first, where[0]
        for _ in range(jumps):
            best, best_d, best_leader = None, CHAIN_JUMP, False
            for m in self.monsters:
                if m.hp <= 0 or m.id in struck_ids:
                    continue
                if abs(m.s - current.s) > CHAIN_JUMP * 4:   # the path winds, but never that tightly
                    continue
                x, y = level.point(m.s)
                d = _hypot(x - pos[0], y - pos[1])
                if d >= CHAIN_JUMP:
                    continue
                leader = static and m.kind.leader is not None
                if (leader and not best_leader) or (leader == best_leader and d < best_d):
                    best, best_d, best_leader = m, d, leader
            if best is None:
                break
            struck.append(best)
            struck_ids.add(best.id)
            pos = level.point(best.s)
            where.append(pos)
            current = best
        self._emit("chain", tower.id, [m.id for m in struck], where)
        keeps = self.perks.leap_keeps
        for i, m in enumerate(struck):
            self._hurt(m, damage * keeps ** i, Element.LIGHTNING)

    def _bolts(self, dt: float) -> None:
        if not self.bolts:
            return
        flying = []
        for b in self.bolts:
            target = self.monster(b.target)
            if target is not None and target.hp <= 0:
                target = None
            last = self.level.point(target.s) if target is not None else b.last
            left = b.left - dt
            if left > 0:
                flying.append(Bolt(b.id, b.tower, b.kind, b.target, left, b.damage, b.element, b.splash, b.poison,
                                   b.poison_time, b.origin, last))
                continue
            struck: list[Monster] = []
            if b.splash > 0:
                struck = self._around(last[0], last[1], b.splash, flyers=True)
                if self.perks.blaze and b.kind == "pyre":
                    self.hazards.append(Hazard(last[0], last[1], b.splash, b.damage / 3.0, BLAZE_TIME))
            elif target is not None:
                struck.append(target)
            self._emit("impact", b, last, [m.id for m in struck])
            for m in struck:
                if b.poison > 0:
                    self._poison(m, b.poison, b.poison_time)
                self._hurt(m, b.damage if m is target or b.splash <= 0 else b.damage * 0.6, b.element)
        self.bolts = flying

    def _meteors(self) -> None:
        if not self.meteors:
            return
        landing = [mt for mt in self.meteors if mt.at <= self.time + 1e-9]
        if not landing:
            return
        self.meteors = [mt for mt in self.meteors if mt.at > self.time + 1e-9]
        spec = SPELLS["meteor"]
        for mt in landing:
            struck = self._around(mt.x, mt.y, spec.radius, flyers=True)
            self._emit("meteor", mt.x, mt.y, [m.id for m in struck])
            for m in struck:
                self._hurt(m, mt.damage, Element.FIRE)
            self.hazards.append(Hazard(mt.x, mt.y, BURN_RADIUS, mt.burn, spec.lasting))

    def _poison(self, m: Monster, dps: float, seconds: float) -> None:
        if m.kind.taken(Element.POISON) <= 0:
            return
        if len(m.poison) >= MAX_POISON_STACKS:
            m.poison.sort(key=lambda stack: stack[1])
            m.poison.pop(0)
        m.poison.append([dps, seconds])

    def _afflictions(self, dt: float) -> None:
        for m in self.monsters:
            if not m.poison:
                continue
            total = 0.0
            for stack in m.poison:
                span = min(dt, stack[1])
                total += stack[0] * span
                stack[1] -= dt
            m.poison = [stack for stack in m.poison if stack[1] > 0]
            if total > 0:
                self._hurt(m, total, Element.POISON, quiet=True)
        if self.hazards:
            for h in self.hazards:
                for m in self._around(h.x, h.y, h.radius, flyers=False):
                    self._hurt(m, h.dps * min(dt, h.left), Element.FIRE, quiet=True)
                h.left -= dt
            self.hazards = [h for h in self.hazards if h.left > 0]
        for m in self.monsters:
            if m.amplified > 0:
                m.amplified = max(0.0, m.amplified - dt)
        if any(m.hp <= 0 for m in self.monsters):
            self._bury()

    def taken(self, m: Monster, element: Element | None) -> float:
        """The share of a blow of this element that the monster feels; holy damage (None) is felt whole."""
        if element is None:
            return 1.0
        resist = m.kind.resist.get(element, 0.0)
        if resist < 1.0 and self.perks.lower_resist and m.poison:
            resist -= 0.25
        return 1.0 - resist

    def _hurt(self, m: Monster, amount: float, element: Element | None, *, quiet: bool = False, bursts: bool = True) -> None:
        if m.hp <= 0:
            return
        taken = self.taken(m, element)
        if taken > 0 and m.amplified > 0:
            taken *= 1.0 + m.amplify   # an immunity (taken 0) stays 0
        m.hp -= amount * taken
        if not quiet:
            self._emit("hit", m.id, element)
        if m.hp <= 0:
            self._died(m, element, bursts)

    def _died(self, m: Monster, element: Element | None, bursts: bool) -> None:
        # A monster its kind's shaman stands near rises once, unless a burst tore it apart (bursts=False: a burst
        # killed it)
        if bursts and not m.risen and m.kind.leader is None:
            raise_kind = m.kind.key
            for leader in self.monsters:
                if leader.hp > 0 and leader.kind.leader is not None:
                    spec = leader.kind.leader
                    if spec.raises == raise_kind:
                        lx, ly = self.level.point(leader.s)
                        mx, my = self.level.point(m.s)
                        if (lx - mx) ** 2 + (ly - my) ** 2 <= spec.raise_reach ** 2:
                            # Raise the monster
                            m.risen = True
                            m.hp = m.max_hp * 0.5
                            m.frozen = max(m.frozen, 1.0)
                            self._emit("raised", m.id, leader.id)
                            return  # Monster doesn't die, no bounty, no kill, no wave count-off

        # If a marking leader dies, its mark fizzles
        if m.marking:
            self._emit("fizzle", m.id, m.chant_spot)
            m.marking = False
            m.chant_curse, m.chant_spot, m.chant_left = None, (-1, -1), 0.0

        self.gold += m.kind.bounty
        self.kills += 1
        where = self.level.point(m.s)
        self._emit("death", m.id, m.kind.key, element, where, m.kind.bounty)
        amplified = m.amplified > 0
        if amplified and self.perks.life_tap:
            self.mana = min(self.perks.mana_max, self.mana + m.kind.bounty / 5)
        if m.kind.leader is not None and self.perks.soul_harvest:
            self.mana = min(self.perks.mana_max, self.mana + SOUL)
        if self.perks.contagion and m.poison:
            self._spread(m, where)
        if bursts and self.perks.shatter and m.chill_left > 0:
            around = [o for o in self._around(where[0], where[1], SHATTER_RADIUS, flyers=True) if o is not m]
            self._emit("shatter", m.id, where)
            for o in around:   # a monster a burst kills does not burst in turn
                self._hurt(o, m.max_hp * SHATTER_SHARE, Element.COLD, quiet=True, bursts=False)
        if bursts and self.perks.corpse_explosion and amplified:
            around = [o for o in self._around(where[0], where[1], CORPSE_RADIUS, flyers=True) if o is not m]
            self._emit("corpse_explosion", where[0], where[1])
            for o in around:   # a monster a burst kills does not burst in turn
                self._hurt(o, m.max_hp * CORPSE_SHARE, None, quiet=True, bursts=False)

    def _spread(self, m: Monster, where: tuple[float, float]) -> None:
        """Contagion: a dead monster's venom goes to the nearest living monster it can poison."""
        best, best_d = None, CONTAGION_REACH * CONTAGION_REACH
        for o in self.monsters:
            if o is m or o.hp <= 0 or o.kind.taken(Element.POISON) <= 0:
                continue
            x, y = self.level.point(o.s)
            d = (x - where[0]) ** 2 + (y - where[1]) ** 2
            if d <= best_d:
                best, best_d = o, d
        if best is None:
            return
        for dps, left in m.poison:
            self._poison(best, dps, left)
        self._emit("contagion", m.id, best.id)

    def _bury(self) -> None:
        for m in self.monsters:
            if m.hp <= 0:
                self._count_off(m)
        self.monsters = [m for m in self.monsters if m.hp > 0]

    def _count_off(self, m: Monster) -> None:
        self.wave_alive[m.wave] -= 1

    def _curses(self, dt: float) -> None:
        if any(m.hp <= 0 for m in self.monsters):
            self._bury()
        for t in self.towers.values():
            if t.ward > 0:
                t.ward = max(0.0, t.ward - dt)
            if not t.curses:
                continue
            for curse in list(t.curses):
                left = t.curses[curse] - dt
                if left <= 0:
                    del t.curses[curse]
                    self._emit("curse_ended", t.id, curse)
                else:
                    t.curses[curse] = left

    def _waves(self, dt: float) -> None:
        if self.wave < 0 or self.outcome is not None:
            return
        for w in list(self.unpaid):
            if self.wave_alive[w] == 0 and (w < self.wave or not self.schedule):
                self.unpaid.remove(w)
                bonus = self.waves[w].bonus
                self.gold += bonus
                for d in self.doors:
                    if d.built:
                        d.hp += (self.gate_life - d.hp) * self.perks.gate_mend
                self._emit("cleared", w, bonus)
        if self.schedule or self.monsters or self.break_left is not None or self.unpaid:
            return
        if self.wave + 1 >= len(self.waves):
            self.outcome = "victory"
            self._emit("victory")
        else:
            self.break_left = WAVE_BREAK
            for d in self.doors:   # the fight has died down: a broken arch can take a gate again
                d.rubble = False


_ASK: Final = object()   # a leader that has decided to ask, for the end of this step
_hypot: Final = math.hypot   # looked up once: compiled, it is a call into Python, and a chain calls it for each leap


def _furthest_first(monsters: list[Monster]) -> None:
    """Sort by s, furthest first, keeping the order of equals: what ``sort(key=s, reverse=True)`` makes of the
    list, by insertion, since between two steps only a few monsters overtake (compiled, a key function is a call
    into Python for every monster)."""
    for i in range(1, len(monsters)):
        m = monsters[i]
        j = i - 1
        while j >= 0 and monsters[j].s < m.s:
            monsters[j + 1] = monsters[j]
            j -= 1
        monsters[j + 1] = m


def _inside(s: float, spans: tuple[tuple[float, float], ...]) -> bool:
    for a, b in spans:
        if a <= s <= b:
            return True
    return False

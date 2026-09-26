"""The rules: a fixed-step simulation of one defence, with no saga2d in it.

The scene steps a :class:`World` in whole :data:`SIM_DT` s. The leaders' planner clones the world and steps
the clones at a coarser ``dt`` to look ahead, so a step must be cheap, deterministic and free of anything
the clone does not carry. Randomness only decides where in the corridor a monster walks (``lane``) and how
far back from a door it queues (``jostle``); it comes from the world's own seeded stream.

A world is one :class:`~hellward.sim.campaign.Location` at one difficulty, with the player's learned skills
(:class:`~hellward.sim.skills.Perks`) baked in when it begins.

Events for the view are appended to :attr:`World.events` when ``record`` is on; clones switch it off.

The mutable classes are ``serializable`` for mypyc (:mod:`hellward.sim.fastsim`): compiled, ``cls.__new__(cls)``
then makes a blank object, as in Python, instead of calling ``__init__``, and a compiled world can be pickled.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Callable

from mypy_extensions import mypyc_attr

from hellward.sim.campaign import CATHEDRAL, NORMAL, Difficulty, Location
from hellward.sim.content import (
    BURN_RADIUS, CONTAGION_REACH, CURSES, DOOR, EARLY_CALL_GOLD, MANA_START, MAX_POISON_STACKS, MONSTERS, SELL_REFUND,
    SHATTER_RADIUS, SHATTER_SHARE, SOUL, SPELLS, START_LIVES, THORNS, TOWERS, WARD, WAVE_BREAK, Curse, Element,
    MonsterKind, TowerKind, TowerLevel,
)
from hellward.sim.skills import NO_PERKS, Perks, tower_levels

if TYPE_CHECKING:
    from hellward.sim.planner import Decision

SIM_DT = 0.05
DOOR_STOP = 0.45         # how far before a door's centre the front of a queue stands
JOSTLE = 0.6             # the queue behind a door is this deep
CHAIN_JUMP = 1.7         # how far chain lightning leaps
DECIDE_DELAY = 0.5       # a leader ponders this long between asking its planner and starting to chant
HOLD_RETRY = 1.0         # a leader that holds its curse thinks again after this long
CAST_SLACK = 1.0         # a curse lands if the tower is within reach + slack when the chant ends
FIRST_WAVE_BREAK = 30.0
LEAK_WEIGHT = 2.0        # a monster through the sanctuary gate is worth twice its life to its side
BLAZE_TIME = 2.0         # seconds the floor burns where a fireball lands, under Blaze

_by_s = attrgetter("s")


class Refused(Exception):
    """A command the rules do not allow right now; the message says why, for the player."""


@mypyc_attr(serializable=True)
class Monster:
    __slots__ = ("id", "kind", "hp", "max_hp", "s", "lane", "jostle", "chill", "chill_left", "frozen", "poison", "wave",
                 "cooldown", "asking", "ask_left", "chant_curse", "chant_tower", "chant_left", "door")

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
        self.chant_tower = -1
        self.chant_left = 0.0
        self.door = -1                        # the door socket it is battering, or -1

    def copy(self) -> Monster:
        m = Monster.__new__(Monster)
        m.id, m.kind, m.hp, m.max_hp, m.s, m.lane, m.jostle = self.id, self.kind, self.hp, self.max_hp, self.s, self.lane, self.jostle
        m.chill, m.chill_left, m.frozen, m.wave, m.cooldown = self.chill, self.chill_left, self.frozen, self.wave, self.cooldown
        m.poison = [stack[:] for stack in self.poison]
        m.asking, m.ask_left = None, 0.0
        m.chant_curse, m.chant_tower, m.chant_left, m.door = self.chant_curse, self.chant_tower, self.chant_left, self.door
        return m

    @property
    def speed(self) -> float:
        if self.frozen > 0:
            return 0.0
        return self.kind.speed * (1.0 - self.chill) if self.chill_left > 0 else self.kind.speed

    @property
    def chanting(self) -> bool:
        return self.chant_curse is not None


@mypyc_attr(serializable=True)
class Tower:
    __slots__ = ("id", "kind", "levels", "level", "tile", "cooldown", "curses", "ward", "spent", "spans", "spans_reach")

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

    def copy(self) -> Tower:
        t = Tower.__new__(Tower)
        t.id, t.kind, t.levels, t.level, t.tile, t.cooldown = self.id, self.kind, self.levels, self.level, self.tile, self.cooldown
        t.curses = dict(self.curses)
        t.ward, t.spent, t.spans, t.spans_reach = self.ward, self.spent, self.spans, self.spans_reach
        return t

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


@mypyc_attr(serializable=True)
class Door:
    __slots__ = ("index", "tile", "s", "hp", "built")

    def __init__(self, index: int, tile: tuple[int, int], s: float) -> None:
        self.index = index
        self.tile = tile
        self.s = s
        self.hp = 0.0
        self.built = False

    def copy(self) -> Door:
        d = Door.__new__(Door)
        d.index, d.tile, d.s, d.hp, d.built = self.index, self.tile, self.s, self.hp, self.built
        return d


@dataclass
class Bolt:
    """A firebolt or a venom dart in flight; it lands on its monster, or where that monster fell."""

    id: int
    tower: int
    kind: str          # the tower kind's key
    target: int
    left: float        # seconds to impact
    damage: float
    element: Element
    splash: float
    poison: float
    poison_time: float
    origin: tuple[float, float]
    last: tuple[float, float]   # the target's last known position


@dataclass(frozen=True)
class Meteor:
    at: float                   # when it lands
    x: float
    y: float
    damage: float
    burn: float                 # damage per second of the floor it sets burning


@mypyc_attr(serializable=True)
class Hazard:
    """Burning floor: every walker on it takes fire damage each second (flyers pass over)."""

    __slots__ = ("x", "y", "radius", "dps", "left")

    def __init__(self, x: float, y: float, radius: float, dps: float, left: float) -> None:
        self.x, self.y, self.radius, self.dps, self.left = x, y, radius, dps, left

    def copy(self) -> Hazard:
        return Hazard(self.x, self.y, self.radius, self.dps, self.left)


@dataclass
class ForcedCurse:
    """A curse a rollout lands at a fixed time, standing in for a leader's chant."""

    at: float
    leader: int
    curse: Curse
    tower: int


Planner = Callable[["World", int], Any]   # returns a handle with .result() -> Decision


@mypyc_attr(serializable=True)
class World:
    def __init__(self, location: Location = CATHEDRAL, *, difficulty: Difficulty = NORMAL, perks: Perks = NO_PERKS,
                 seed: int = 0, planner: Planner | None = None, record: bool = True) -> None:
        self.location = location
        self.level = location.level
        self.waves = location.waves
        self.difficulty = difficulty
        self.perks = perks
        self.tower_levels = {kind: tower_levels(kind, perks) for kind in TOWERS}
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
        self._next_id = 1

    # -- Copies for the planner ---------------------------------------------------------

    def clone(self) -> World:
        """A private copy to look ahead in: no events, no planner, its own random stream."""
        w = World.__new__(World)
        w.location, w.level, w.waves, w.difficulty, w.perks = self.location, self.level, self.waves, self.difficulty, self.perks
        w.tower_levels, w.planner, w.record, w.events = self.tower_levels, None, False, []
        w.rng = random.Random()
        w.rng.setstate(self.rng.getstate())
        w.time, w.gold, w.lives, w.mana = self.time, self.gold, self.lives, self.mana
        w.towers = {i: t.copy() for i, t in self.towers.items()}
        w.doors = [d.copy() for d in self.doors]
        w.monsters = [m.copy() for m in self.monsters]
        w.bolts = list(self.bolts)       # bolts and meteors are never changed in place
        w.meteors = list(self.meteors)
        w.hazards = [h.copy() for h in self.hazards]
        w.wave, w.schedule, w.wave_time, w.break_left = self.wave, list(self.schedule), self.wave_time, self.break_left
        w.wave_alive, w.unpaid = dict(self.wave_alive), list(self.unpaid)
        w.leaked_life, w.forced, w.outcome, w.kills, w._next_id = self.leaked_life, [], self.outcome, self.kills, self._next_id
        w.curses_landed, w.cleanses, w.spells_cast = self.curses_landed, self.cleanses, self.spells_cast
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
        return self.waves[max(self.wave, 0)].hp * self.difficulty.hp * self.perks.spell_power

    def cost(self, kind: str) -> int:
        return self.tower_levels[kind][0].cost

    # -- Commands -----------------------------------------------------------------------

    def build(self, kind: str, tile: tuple[int, int]) -> Tower:
        tower_kind = TOWERS[kind]
        if kind not in self.location.arsenal.towers:
            raise Refused(f"No {tower_kind.name} can be raised in {self.location.name}.")
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

    def upgrade(self, tower_id: int) -> None:
        tower = self.towers[tower_id]
        cost = self.upgrade_cost(tower)
        if cost is None:
            raise Refused(f"{tower.kind.name} is at its highest rank.")
        if self.gold < cost:
            raise Refused(f"The next rank costs {cost} gold.")
        self.gold -= cost
        tower.level += 1
        tower.spent += cost
        self._emit("upgraded", tower.id)

    def sell(self, tower_id: int) -> int:
        tower = self.towers.pop(tower_id)
        refund = int(tower.spent * SELL_REFUND)
        self.gold += refund
        self._emit("sold", tower.id, tower.tile, refund)
        return refund

    def build_door(self, index: int) -> None:
        if not self.location.arsenal.gates:
            raise Refused(f"There are no arches to ward in {self.location.name}.")
        door = self.doors[index]
        if door.built:
            raise Refused("The gate already stands.")
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
            raise Refused(f"{SPELLS[key].name} is not yours to cast in {self.location.name}.")
        cost = self.spell_cost(key)
        if self.mana < cost:
            raise Refused(f"{SPELLS[key].name} takes {cost:.0f} mana.")
        self.mana -= cost
        self.spells_cast += 1

    def cleanse(self, tower_id: int) -> None:
        tower = self.towers[tower_id]
        if not tower.curses:
            raise Refused("That tower carries no curse.")
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

    def _inside_map(self, x: float, y: float) -> None:
        if not (0 <= x <= self.level.width and 0 <= y <= self.level.height):
            raise Refused("That is outside the walls.")

    def _around(self, x: float, y: float, radius: float, *, flyers: bool) -> list[Monster]:
        found = []
        point = self.level.point
        for m in self.monsters:
            if m.hp <= 0 or (m.kind.flying and not flyers):
                continue
            mx, my = point(m.s)
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
            cooldown = kind.leader.first_cast * self.difficulty.leader_pace if kind.leader is not None else 0.0
            m = Monster(self._id(), kind, self.wave, self.rng.uniform(-0.28, 0.28), self.rng.uniform(0.0, JOSTLE),
                        kind.hp * self.waves[self.wave].hp * self.difficulty.hp, cooldown)
            self.monsters.append(m)
            self._emit("spawn", m.id)

    def _leaders(self, dt: float) -> None:
        for fc in self.forced:
            if fc.at <= self.time:
                self._land(fc.leader, fc.curse, fc.tower)
        if self.forced:
            self.forced = [fc for fc in self.forced if fc.at > self.time]
        for m in self.monsters:
            spec = m.kind.leader
            if spec is None:
                continue
            if m.chant_curse is not None:
                m.chant_left -= dt
                if m.chant_left <= 0:
                    self._land(m.id, m.chant_curse, m.chant_tower)
                    m.chant_curse, m.chant_tower = None, -1
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
                        m.chant_curse, m.chant_tower, m.chant_left = decision.cast.curse, decision.cast.tower, spec.channel
                        m.cooldown = spec.cooldown * self.difficulty.leader_pace
                        self._emit("chant", m.id, decision.cast.curse, decision.cast.tower)
                continue
            m.cooldown -= dt
            if m.cooldown <= 0 and self.planner is not None and self.towers and m.frozen <= 0:
                m.asking = _ASK
                m.ask_left = DECIDE_DELAY
                self._emit("ponder", m.id)

    def _break(self, m: Monster) -> None:
        """A leader's pondering or chant broken by a spell: the curse never comes, and its whole cooldown starts again."""
        tower = m.chant_tower
        m.chant_curse, m.chant_tower, m.chant_left = None, -1, 0.0
        m.asking, m.ask_left = None, 0.0
        spec = m.kind.leader
        if spec is not None:
            m.cooldown = spec.cooldown * self.difficulty.leader_pace
        self._emit("broken", m.id, tower)

    def _land(self, leader_id: int, curse: Curse, tower_id: int) -> None:
        leader = self.monster(leader_id)
        tower = self.towers.get(tower_id)
        if leader is None or tower is None:
            self._emit("fizzle", leader_id, tower_id)
            return
        spec = leader.kind.leader
        x, y = self.level.point(leader.s)
        cx, cy = tower.centre
        if spec is None or math.hypot(cx - x, cy - y) > spec.cast_range + CAST_SLACK:
            self._emit("fizzle", leader_id, tower_id)
            return
        if tower.ward > 0:
            self._emit("ward_holds", leader_id, tower_id, curse)
            return
        tower.curses[curse] = CURSES[curse].duration
        self.curses_landed += 1
        self._emit("cursed", leader_id, tower_id, curse)

    def _move(self, dt: float) -> None:
        doors = [d for d in self.doors if d.built]
        end = self.level.length
        survivors = []
        for m in self.monsters:
            if m.frozen > 0:
                m.frozen -= dt
                m.door = -1
                if m.chill_left > 0:
                    m.chill_left -= dt
                survivors.append(m)
                continue
            if m.chill_left > 0:
                m.chill_left -= dt
                speed = m.kind.speed * (1.0 - m.chill)
            else:
                speed = m.kind.speed
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
                continue
            survivors.append(m)
        survivors.sort(key=_by_s, reverse=True)
        self.monsters = survivors
        if self.lives <= 0 and self.outcome is None:
            self.lives = 0
            self.outcome = "defeat"
            self._emit("defeat")
        thorns = self.perks.thorns
        for m in survivors:
            if m.door >= 0:
                d = self.doors[m.door]
                blow = m.kind.door_dps * dt
                if m.chill_left > 0:
                    blow *= 1.0 - m.chill
                d.hp -= blow
                if thorns:
                    self._hurt(m, m.kind.door_dps * dt * THORNS, None, quiet=True)
                if d.hp <= 0 and d.built:
                    d.built, d.hp = False, 0.0
                    self._emit("door_broken", d.index)
                    doors = [x for x in doors if x.built]

    def _towers(self, dt: float) -> None:
        monsters = self.monsters
        if not monsters:
            for t in self.towers.values():
                t.cooldown = max(0.0, t.cooldown - dt)
            return
        coverage = self.level.coverage
        static = self.perks.static_field
        for t in self.towers.values():
            if t.cooldown > 0:
                t.cooldown -= dt
                if t.cooldown > 0:
                    continue
            if t.curses and t.silenced:
                t.cooldown = 0.0
                continue
            stats = t.levels[t.level]
            reach = stats.range * t.range_mult() if t.curses else stats.range
            if reach != t.spans_reach:
                t.spans, t.spans_reach = coverage(t.tile, reach), reach
            spans = t.spans
            attack = t.kind.attack
            if attack == "nova":
                hit = [m for m in monsters if m.hp > 0 and _inside(m.s, spans)]
            elif attack == "venom":   # the strongest it can poison
                best = None
                for m in monsters:
                    if m.hp > 0 and (best is None or m.hp > best.hp) and m.kind.taken(Element.POISON) > 0 and _inside(m.s, spans):
                        best = m
                hit = [best] if best is not None else []
            else:
                hit = []
                for m in monsters:
                    if m.hp > 0 and _inside(m.s, spans):
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
            damage = stats.damage * (t.damage_mult() if t.curses else 1.0)
            rate = stats.rate * (t.rate_mult() if t.curses else 1.0)
            t.cooldown += 1.0 / rate
            if attack == "nova":
                self._emit("nova", t.id)
                for m in hit:
                    if stats.chill >= m.chill or m.chill_left <= 0:
                        m.chill = stats.chill
                    m.chill_left = max(m.chill_left, stats.chill_time)
                    self._hurt(m, damage, t.kind.element)
            elif attack == "chain":
                self._chain(t, hit[0], damage, stats.chains)
            else:
                target = hit[0]
                origin = t.centre
                last = self.level.point(target.s)
                distance = math.hypot(last[0] - origin[0], last[1] - origin[1])
                bolt = Bolt(self._id(), t.id, t.kind.key, target.id, distance / t.kind.bolt_speed, damage, t.kind.element,
                            stats.splash, stats.poison, stats.poison_time, origin, last)
                self.bolts.append(bolt)
                self._emit("bolt", bolt)

    def _chain(self, tower: Tower, first: Monster, damage: float, jumps: int) -> None:
        point = self.level.point
        static = self.perks.static_field
        struck = [first]
        where = [point(first.s)]
        current, pos = first, where[0]
        for _ in range(jumps):
            best, best_d, best_leader = None, CHAIN_JUMP, False
            for m in self.monsters:
                if m.hp <= 0 or m in struck:
                    continue
                if abs(m.s - current.s) > CHAIN_JUMP * 4:   # the path winds, but never that tightly
                    continue
                x, y = point(m.s)
                d = math.hypot(x - pos[0], y - pos[1])
                if d >= CHAIN_JUMP:
                    continue
                leader = static and m.kind.leader is not None
                if (leader and not best_leader) or (leader == best_leader and d < best_d):
                    best, best_d, best_leader = m, d, leader
            if best is None:
                break
            struck.append(best)
            pos = point(best.s)
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
        m.hp -= amount * self.taken(m, element)
        if not quiet:
            self._emit("hit", m.id, element)
        if m.hp <= 0:
            self._died(m, element, bursts)

    def _died(self, m: Monster, element: Element | None, bursts: bool) -> None:
        self.gold += m.kind.bounty
        self.kills += 1
        where = self.level.point(m.s)
        self._emit("death", m.id, m.kind.key, element, where, m.kind.bounty)
        if m.kind.leader is not None and self.perks.soul_harvest:
            self.mana = min(self.perks.mana_max, self.mana + SOUL)
        if self.perks.contagion and m.poison:
            self._spread(m, where)
        if bursts and self.perks.shatter and m.chill_left > 0:
            around = [o for o in self._around(where[0], where[1], SHATTER_RADIUS, flyers=True) if o is not m]
            self._emit("shatter", m.id, where)
            for o in around:   # a monster a burst kills does not burst in turn
                self._hurt(o, m.max_hp * SHATTER_SHARE, Element.COLD, quiet=True, bursts=False)

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


_ASK = object()   # a leader that has decided to ask, for the end of this step


def _inside(s: float, spans: tuple[tuple[float, float], ...]) -> bool:
    for a, b in spans:
        if a <= s <= b:
            return True
    return False

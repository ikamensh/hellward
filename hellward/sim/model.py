"""The rules: a fixed-step simulation of one defence, with no saga2d in it.

The scene steps a :class:`World` in whole :data:`SIM_DT` s. The leaders' planner clones the world and steps
the clones at a coarser ``dt`` to look ahead, so a step must be cheap, deterministic and free of anything
the clone does not carry. Randomness only decides where in the corridor a monster walks (``lane``) and how
far back from a door it queues (``jostle``); it comes from the world's own seeded stream.

Events for the view are appended to :attr:`World.events` when ``record`` is on; clones switch it off.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from operator import attrgetter
from typing import TYPE_CHECKING, Any, Callable

from hellward.sim.content import (
    CLEANSE_COST, CURSES, DOOR, EARLY_CALL_GOLD, MANA_MAX, MANA_REGEN, MANA_START, MAX_POISON_STACKS, MONSTERS,
    SELL_REFUND, START_GOLD, START_LIVES, TOWERS, WAVE_BREAK, WAVES, Curse, Element, MonsterKind, TowerKind,
    TowerLevel, Wave,
)
from hellward.sim.level import CATHEDRAL, Level

if TYPE_CHECKING:
    from hellward.sim.planner import Decision

SIM_DT = 0.05
DOOR_STOP = 0.45         # how far before a door's centre the front of a queue stands
JOSTLE = 0.6             # the queue behind a door is this deep
CHAIN_JUMP = 1.7         # how far chain lightning leaps
CHAIN_FALLOFF = 0.85     # damage kept per leap
DECIDE_DELAY = 0.25      # between a leader asking its planner and starting to chant
HOLD_RETRY = 1.0         # a leader that holds its curse thinks again after this long
CAST_SLACK = 1.0         # a curse lands if the tower is within reach + slack when the chant ends
FIRST_WAVE_BREAK = 30.0
LEAK_WEIGHT = 2.0        # a monster through the sanctuary gate is worth twice its life to its side

_by_s = attrgetter("s")


class Refused(Exception):
    """A command the rules do not allow right now; the message says why, for the player."""


class Monster:
    __slots__ = ("id", "kind", "hp", "s", "lane", "jostle", "chill", "chill_left", "poison", "wave",
                 "cooldown", "asking", "ask_left", "chant_curse", "chant_tower", "chant_left", "door")

    def __init__(self, id: int, kind: MonsterKind, wave: int, lane: float, jostle: float, hp: float) -> None:
        self.id = id
        self.kind = kind
        self.hp = hp
        self.s = 0.0
        self.lane = lane
        self.jostle = jostle
        self.chill = 0.0
        self.chill_left = 0.0
        self.poison: list[list[float]] = []   # [dps, seconds left] per stack
        self.wave = wave
        self.cooldown = kind.leader.first_cast if kind.leader else 0.0
        self.asking: Any = None               # the planner's handle while a leader waits for its answer
        self.ask_left = 0.0
        self.chant_curse: Curse | None = None
        self.chant_tower = -1
        self.chant_left = 0.0
        self.door = -1                        # the door socket it is battering, or -1

    def copy(self) -> Monster:
        m = Monster.__new__(Monster)
        m.id, m.kind, m.hp, m.s, m.lane, m.jostle = self.id, self.kind, self.hp, self.s, self.lane, self.jostle
        m.chill, m.chill_left, m.wave, m.cooldown = self.chill, self.chill_left, self.wave, self.cooldown
        m.poison = [stack[:] for stack in self.poison]
        m.asking, m.ask_left = None, 0.0
        m.chant_curse, m.chant_tower, m.chant_left, m.door = self.chant_curse, self.chant_tower, self.chant_left, self.door
        return m

    @property
    def speed(self) -> float:
        return self.kind.speed * (1.0 - self.chill) if self.chill_left > 0 else self.kind.speed

    @property
    def chanting(self) -> bool:
        return self.chant_curse is not None


class Tower:
    __slots__ = ("id", "kind", "level", "tile", "cooldown", "curses", "spent")

    def __init__(self, id: int, kind: TowerKind, tile: tuple[int, int]) -> None:
        self.id = id
        self.kind = kind
        self.level = 0
        self.tile = tile
        self.cooldown = 0.0
        self.curses: dict[Curse, float] = {}
        self.spent = kind.levels[0].cost

    def copy(self) -> Tower:
        t = Tower.__new__(Tower)
        t.id, t.kind, t.level, t.tile, t.cooldown, t.spent = self.id, self.kind, self.level, self.tile, self.cooldown, self.spent
        t.curses = dict(self.curses)
        return t

    @property
    def stats(self) -> TowerLevel:
        return self.kind.levels[self.level]

    @property
    def centre(self) -> tuple[float, float]:
        return self.tile[0] + 0.5, self.tile[1] + 0.5

    def multiplier(self, what: str) -> float:
        value = 1.0
        for curse in self.curses:
            value *= getattr(CURSES[curse], what)
        return value

    @property
    def silenced(self) -> bool:
        return any(CURSES[c].silenced for c in self.curses)

    @property
    def reach(self) -> float:
        return self.stats.range * self.multiplier("range")


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


@dataclass
class ForcedCurse:
    """A curse a rollout lands at a fixed time, standing in for a leader's chant."""

    at: float
    leader: int
    curse: Curse
    tower: int


Planner = Callable[["World", int], Any]   # returns a handle with .result() -> Decision


class World:
    def __init__(self, level: Level = CATHEDRAL, *, seed: int = 0, waves: tuple[Wave, ...] = WAVES,
                 planner: Planner | None = None, record: bool = True) -> None:
        self.level = level
        self.waves = waves
        self.rng = random.Random(seed)
        self.planner = planner
        self.record = record
        self.events: list[tuple] = []
        self.time = 0.0
        self.gold = START_GOLD
        self.lives = START_LIVES
        self.mana = MANA_START
        self.towers: dict[int, Tower] = {}
        self.doors = [Door(i, tile, s) for i, (tile, s) in enumerate(zip(level.doors, level.door_s))]
        self.monsters: list[Monster] = []     # alive and on the map, furthest along first
        self.bolts: list[Bolt] = []
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
        self._next_id = 1

    # -- Copies for the planner ---------------------------------------------------------

    def clone(self) -> World:
        """A private copy to look ahead in: no events, no planner, its own random stream."""
        w = World.__new__(World)
        w.level, w.waves, w.planner, w.record, w.events = self.level, self.waves, None, False, []
        w.rng = random.Random()
        w.rng.setstate(self.rng.getstate())
        w.time, w.gold, w.lives, w.mana = self.time, self.gold, self.lives, self.mana
        w.towers = {i: t.copy() for i, t in self.towers.items()}
        w.doors = [d.copy() for d in self.doors]
        w.monsters = [m.copy() for m in self.monsters]
        w.bolts = list(self.bolts)   # bolts are never mutated in place
        w.wave, w.schedule, w.wave_time, w.break_left = self.wave, list(self.schedule), self.wave_time, self.break_left
        w.wave_alive, w.unpaid = dict(self.wave_alive), list(self.unpaid)
        w.leaked_life, w.forced, w.outcome, w.kills, w._next_id = self.leaked_life, [], self.outcome, self.kills, self._next_id
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

    # -- Commands -----------------------------------------------------------------------

    def build(self, kind: str, tile: tuple[int, int]) -> Tower:
        tower_kind = TOWERS[kind]
        if not self.level.buildable(*tile):
            raise Refused("Towers stand on the cathedral floor, not on the path or the walls.")
        if self.tower_at(tile) is not None:
            raise Refused("A tower already stands there.")
        cost = tower_kind.levels[0].cost
        if self.gold < cost:
            raise Refused(f"{tower_kind.name} costs {cost} gold.")
        self.gold -= cost
        tower = Tower(self._id(), tower_kind, tile)
        self.towers[tower.id] = tower
        self._emit("built", tower.id)
        return tower

    def upgrade_cost(self, tower: Tower) -> int | None:
        if tower.level + 1 >= len(tower.kind.levels):
            return None
        return tower.kind.levels[tower.level + 1].cost

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
        door = self.doors[index]
        if door.built:
            raise Refused("The gate already stands.")
        if self.gold < DOOR.cost:
            raise Refused(f"A warded gate costs {DOOR.cost} gold.")
        for m in self.monsters:
            if not m.kind.flying and abs(m.s - door.s) < 0.6:
                raise Refused("Monsters stand in the arch.")
        self.gold -= DOOR.cost
        door.built, door.hp = True, DOOR.hp
        self._emit("door_built", index)

    def cleanse(self, tower_id: int) -> None:
        tower = self.towers[tower_id]
        if not tower.curses:
            raise Refused("That tower carries no curse.")
        if self.mana < CLEANSE_COST:
            raise Refused(f"Cleansing takes {CLEANSE_COST:.0f} mana.")
        self.mana -= CLEANSE_COST
        lifted = sorted(tower.curses)
        tower.curses.clear()
        self._emit("cleansed", tower.id, lifted)

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
        self.mana = min(MANA_MAX, self.mana + MANA_REGEN * dt)
        self._spawn(dt)
        self._leaders(dt)
        self._move(dt)
        self._towers(dt)
        self._bolts(dt)
        self._afflictions(dt)
        self._curses(dt)
        self._waves(dt)
        for m in self.monsters:
            if m.asking is _ASK:   # asked now, at a step boundary, so the planner's clone starts where a step would
                m.asking = self.planner(self, m.id)

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
            m = Monster(self._id(), kind, self.wave, self.rng.uniform(-0.28, 0.28), self.rng.uniform(0.0, JOSTLE),
                        kind.hp * self.waves[self.wave].hp)
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
                    if decision.cast is None:
                        m.cooldown = decision.retry
                    else:
                        m.chant_curse, m.chant_tower, m.chant_left = decision.cast.curse, decision.cast.tower, spec.channel
                        m.cooldown = spec.cooldown
                        self._emit("chant", m.id, decision.cast.curse, decision.cast.tower)
                continue
            m.cooldown -= dt
            if m.cooldown <= 0 and self.planner is not None and self.towers:
                m.asking = _ASK
                m.ask_left = DECIDE_DELAY

    def _land(self, leader_id: int, curse: Curse, tower_id: int) -> None:
        leader = self.monster(leader_id)
        tower = self.towers.get(tower_id)
        if leader is None or tower is None:
            self._emit("fizzle", leader_id, tower_id)
            return
        x, y = self.level.point(leader.s)
        cx, cy = tower.centre
        if math.hypot(cx - x, cy - y) > leader.kind.leader.cast_range + CAST_SLACK:
            self._emit("fizzle", leader_id, tower_id)
            return
        tower.curses[curse] = CURSES[curse].duration
        self._emit("cursed", leader_id, tower_id, curse)

    def _move(self, dt: float) -> None:
        doors = [d for d in self.doors if d.built]
        end = self.level.length
        survivors = []
        for m in self.monsters:
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
                self.leaked_life += m.kind.hp * LEAK_WEIGHT
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
        for m in survivors:
            if m.door >= 0:
                d = self.doors[m.door]
                blow = m.kind.door_dps * dt
                if m.chill_left > 0:
                    blow *= 1.0 - m.chill
                d.hp -= blow
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
        for t in self.towers.values():
            if t.cooldown > 0:
                t.cooldown -= dt
                if t.cooldown > 0:
                    continue
            if t.curses and t.silenced:
                t.cooldown = 0.0
                continue
            stats = t.kind.levels[t.level]
            spans = coverage(t.tile, stats.range * t.multiplier("range") if t.curses else stats.range)
            attack = t.kind.attack
            if attack == "nova":
                hit = [m for m in monsters if m.hp > 0 and _inside(m.s, spans)]
            elif attack == "venom":
                best = None
                for m in monsters:
                    if m.hp > 0 and (best is None or m.hp > best.hp) and _inside(m.s, spans):
                        best = m
                hit = [best] if best is not None else []
            else:
                hit = []
                for m in monsters:
                    if m.hp > 0 and _inside(m.s, spans):
                        hit = [m]
                        break
            if not hit:
                t.cooldown = 0.0
                continue
            damage = stats.damage * (t.multiplier("damage") if t.curses else 1.0)
            rate = stats.rate * (t.multiplier("rate") if t.curses else 1.0)
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
        struck = [first]
        where = [point(first.s)]
        current, pos = first, where[0]
        for _ in range(jumps):
            best, best_d = None, CHAIN_JUMP
            for m in self.monsters:
                if m.hp <= 0 or m in struck:
                    continue
                if abs(m.s - current.s) > CHAIN_JUMP * 4:   # the path winds, but never that tightly
                    continue
                x, y = point(m.s)
                d = math.hypot(x - pos[0], y - pos[1])
                if d < best_d:
                    best, best_d = m, d
            if best is None:
                break
            struck.append(best)
            pos = point(best.s)
            where.append(pos)
            current = best
        self._emit("chain", tower.id, [m.id for m in struck], where)
        for i, m in enumerate(struck):
            self._hurt(m, damage * CHAIN_FALLOFF ** i, Element.LIGHTNING)

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
                for m in self.monsters:
                    if m.hp <= 0:
                        continue
                    x, y = self.level.point(m.s)
                    if math.hypot(x - last[0], y - last[1]) <= b.splash:
                        struck.append(m)
            elif target is not None:
                struck.append(target)
            self._emit("impact", b, last, [m.id for m in struck])
            for m in struck:
                if b.poison > 0:
                    self._poison(m, b.poison, b.poison_time)
                self._hurt(m, b.damage if m is target or b.splash <= 0 else b.damage * 0.6, b.element)
        self.bolts = flying

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
        if any(m.hp <= 0 for m in self.monsters):
            self._bury()

    def _hurt(self, m: Monster, amount: float, element: Element, *, quiet: bool = False) -> None:
        if m.hp <= 0:
            return
        m.hp -= amount * m.kind.taken(element)
        if not quiet:
            self._emit("hit", m.id, element)
        if m.hp <= 0:
            self.gold += m.kind.bounty
            self.kills += 1
            self._emit("death", m.id, m.kind.key, element, self.level.point(m.s), m.kind.bounty)

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
                        d.hp += (DOOR.hp - d.hp) * DOOR.repair
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

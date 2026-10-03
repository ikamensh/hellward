"""The rules: a fixed-step simulation of one defence, with no saga2d in it.

The scene steps a :class:`World` in whole :data:`SIM_DT` s. The leaders' planner clones the world and steps
the clones at a coarser ``dt`` to look ahead, so a step must be cheap, deterministic and free of anything
the clone does not carry. Randomness chooses a wanderer's committed route, its visual lane, and how
far back from a door it queues (``jostle``); it comes from the world's own seeded stream.

A world is one :class:`~hellward.sim.campaign.Location`, with the player's learned skills
(:class:`~hellward.sim.skills.Perks`) baked in when it begins.

Events for the view are appended to :attr:`World.events` when ``record`` is on; clones switch it off.

Compiled by mypyc (:mod:`hellward.fastsim`), a class's ``__new__`` runs its ``__init__``, so there is no blank
object to fill: copies are made by the constructors, and the classes whose constructor needs arguments say in
``__reduce__`` how they are pickled.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable, Final

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.bonus import Bonus, BonusPack
from hellward.sim.bonus import EARLY as BONUS_EARLY
from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import CATHEDRAL, ORDER, Arsenal, Location
from hellward.sim.content import (
    BURN_RADIUS, CONTAGION_REACH, CORPSE_RADIUS, CORPSE_SHARE, CURSES, DOOR, EARLY_CALL_GOLD, HURRICANE_RADIUS,
    HURRICANE_SLOW, MANA_START, MAX_POISON_STACKS, MONSTERS, SELL_REFUND, SHATTER_RADIUS, SHATTER_SHARE, SOUL, SPELLS,
    START_LIVES, THORNS, TOWERS, TWISTER_HELD, TWISTER_PERIOD, TWISTER_RADIUS, WAVE_BREAK, Curse, Element,
    MonsterKind, TowerKind, TowerLevel, felt_hit, felt_over_time,
)
from hellward.sim.items import EMPTY_LOADOUT, Loadout, PATTERNS
from hellward.sim.level import Level
from hellward.sim.modes import MODES
from hellward.sim.relics import (
    BELL_MANA,
    BELLOWS_MANA,
    BELLOWS_WELL,
    BLOOD_GOLD,
    BLOOD_LIVES,
    CANTICLE_WELL,
    HOARD_REACH,
    MARTYR_GOLD,
    MASTERWORK_MANA,
    RELICS,
    SCAFFOLD_GOLD,
    SPITE_MANA,
    TRANCE_RATE,
    TRANCE_TIME,
)
from hellward.sim.skills import NO_PERKS, RANK_SKILL, SKILLS, SPELL_UNLOCK, UNLOCK, Perks, baked
from hellward.sim import worth as cell_worth
from hellward.sim.xp import clear_xp, kill_xp, xp_next

if TYPE_CHECKING:
    from hellward.sim.planner import Decision

SIM_DT: Final = 0.05            # the clock's step: not a tuning value (replays and the protocol count steps)
SKIP_STEPS: Final = 3600        # a grind prediction's and a skip's longest look: three sim-minutes
ATTUNE_GOLD: Final = 25         # an attunement's price in battle gold, per tower
ATTUNABLE: Final = ("bolt", "chain", "venom")   # the shots that spend charges; the hook drags and the supports sing, and attunement would idle on them
CHARGES_MAX: Final = 3.0        # the charges an attuned tower holds
CHARGE_EVERY: Final = 15.0      # seconds per charge regained
CHARGED_COOLDOWN: Final = 3.0   # seconds after an empowered shot before the next
EMPOWER: Final = 3.0            # an empowered shot's damage
IDOL_EVERY = (45.0, 32.0, 22.0)   # the idol's rite, seconds per rank: a free smite. Not Final:
CENSER_HURT = (30.0, 60.0, 100.0)   # the immolation's damage, per rank. mypyc miscompiles a Final tuple read by a
WELL_EVERY = (20.0, 15.0, 11.0)   # the well's watering, seconds per rank: a charge given. variable subscript.
DOOR_STOP: Final = tuning.number("battle.door_stop")
JOSTLE: Final = tuning.number("battle.jostle")
CHAIN_JUMP: Final = tuning.number("battle.chain_jump")
DECIDE_DELAY: Final = tuning.number("battle.decide_delay")
HOLD_RETRY: Final = tuning.number("battle.hold_retry")
CAST_SLACK: Final = tuning.number("battle.cast_slack")
FIRST_WAVE_BREAK: Final = tuning.number("battle.first_wave_break")
LEAK_WEIGHT: Final = tuning.number("battle.leak_weight")
BLAZE_TIME: Final = tuning.number("battle.skills.blaze_time")
SPLASH_SHARE: Final = tuning.number("battle.splash_share")
KNIFE_STANDING: Final = tuning.number("battle.knife_standing")
HOOK_PULL: Final = tuning.number("battle.hook_pull")
HOOK_PAST: Final = tuning.number("battle.hook_past")
HYMN_RATE: Final = SPELLS["hymn"].rate
HOOK: Final = 1                 # the Hook's bit in Monster.moved: each mover kind moves a monster back once
BLIGHT_MAX: Final = 5         # blighted and marked cells at once
BLIGHT_CELLS: Final = 5       # cells a defence takes in all: R6 wants one to five a location that has blight
BLIGHT_RETRY: Final = 2.0     # seconds before a blighter without a cell looks again


class Refused(Exception):
    """A command the rules do not allow right now; the message says why, for the player."""


class Monster:
    __slots__ = ("id", "kind", "hp", "max_hp", "s", "route", "bounty", "salvage", "breach", "elite_name", "speed_factor",
                 "lane", "jostle", "chill", "chill_left", "frozen", "poison", "wave",
                 "cooldown", "asking", "ask_left", "chant_curse", "chant_spot", "chant_left", "door",
                 "blight_cd", "blight_cell", "blight_left", "blight_wave",
                 "amplified", "amplify", "risen", "marking", "moved", "strikes", "bonus")

    def __init__(self, id: int, kind: MonsterKind, wave: int, lane: float, jostle: float, hp: float, cooldown: float,
                 route: str = "main", bounty: int | None = None, salvage: int = 0, breach: bool = False,
                 elite_name: str = "", speed_factor: float = 1.0, bonus: bool = False) -> None:
        self.id = id
        self.kind = kind
        self.hp = hp
        self.max_hp = hp
        self.s = 0.0
        self.route = route
        self.bounty = kind.bounty if bounty is None else bounty
        self.salvage = salvage
        self.breach = breach
        self.elite_name = elite_name
        self.speed_factor = speed_factor
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
        self.blight_cd = kind.blight.delay if kind.blight is not None else 0.0
        self.blight_cell: tuple[int, int] = (-1, -1)   # the cell its mark burns on, while it marks
        self.blight_left = 0.0
        self.blight_wave = -1                 # the wave it marked in last: once a wave
        self.amplified = 0.0                  # seconds of Amplify Damage left
        self.amplify = 0.0                    # the fraction it takes extra (0.3 = 30% more damage)
        self.risen = False                    # has this monster been raised once already
        self.marking = False                  # is this leader currently marking (instead of chanting)
        self.moved = 0                        # a bit per mover kind that has moved it back (HOOK)
        self.strikes = 0                      # a boss's strikes at the shrine
        self.bonus = bonus                    # a summoned pack's monster: no bounty, no XP, its leak fails the pack

    def copy(self) -> Monster:
        """Everything but a leader's pending question to its planner."""
        m = Monster(self.id, self.kind, self.wave, self.lane, self.jostle, self.hp, self.cooldown, self.route,
                    self.bounty, self.salvage, self.breach, self.elite_name, self.speed_factor, self.bonus)
        m.max_hp, m.s, m.chill, m.chill_left, m.frozen = self.max_hp, self.s, self.chill, self.chill_left, self.frozen
        m.poison = [stack[:] for stack in self.poison]
        m.chant_curse, m.chant_spot, m.chant_left, m.door = self.chant_curse, self.chant_spot, self.chant_left, self.door
        m.blight_cd, m.blight_cell, m.blight_left, m.blight_wave = (self.blight_cd, self.blight_cell, self.blight_left,
                                                                   self.blight_wave)
        m.amplified, m.amplify = self.amplified, self.amplify
        m.risen, m.marking, m.moved, m.strikes = self.risen, self.marking, self.moved, self.strikes
        return m

    def __reduce__(self) -> tuple[Any, ...]:
        return Monster, (self.id, self.kind, self.wave, self.lane, self.jostle, self.hp, self.cooldown, self.route,
                         self.bounty, self.salvage, self.breach, self.elite_name, self.speed_factor,
                         self.bonus), self.__getstate__()

    @property
    def speed(self) -> float:
        if self.frozen > 0:
            return 0.0
        return (self.kind.speed * self.speed_factor * (1.0 - self.chill) if self.chill_left > 0
                else self.kind.speed * self.speed_factor)

    @property
    def chanting(self) -> bool:
        return self.chant_curse is not None


class Tower:
    __slots__ = ("id", "kind", "levels", "level", "tile", "cooldown", "curses", "hymn", "spent", "spans", "spans_reach",
                 "timer", "mode", "attuned", "charges", "charged_at")

    def __init__(self, id: int, kind: TowerKind, levels: tuple[TowerLevel, ...], tile: tuple[int, int]) -> None:
        self.id = id
        self.kind = kind
        self.levels = levels                  # its kind's ranks with the player's skills in them
        self.level = 0
        self.tile = tile
        self.cooldown = 0.0
        self.curses: dict[Curse, float] = {}
        self.hymn = 0.0                       # seconds of Battle Hymn left: it attacks HYMN_RATE times as fast
        self.spent = levels[0].cost
        self.spans: tuple[tuple[float, float], ...] = ()   # the path it reaches, for the reach it had last
        self.spans_reach = -1.0
        self.timer = 0.0                      # a grove's twister clock
        self.mode = "first"                   # its strategy: foremost until taught otherwise
        self.attuned = False                  # whether it holds charges for empowered shots
        self.charges = 0.0                    # charges held, to CHARGES_MAX, one per CHARGE_EVERY seconds
        self.charged_at = -1e9                # when it last spent a charge: the cooldown starts here

    def copy(self) -> Tower:
        t = Tower(self.id, self.kind, self.levels, self.tile)
        t.level, t.cooldown, t.curses = self.level, self.cooldown, dict(self.curses)
        t.hymn, t.spent, t.spans, t.spans_reach = self.hymn, self.spent, self.spans, self.spans_reach
        t.timer, t.mode = self.timer, self.mode
        t.attuned, t.charges = self.attuned, self.charges
        t.charged_at = self.charged_at
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
        """What its curses and a Battle Hymn make of its attacks per second."""
        value = HYMN_RATE if self.hymn > 0 else 1.0
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
    """A firebolt, a venom dart, a bolt or a knife in flight; it lands on its monster, or where that monster fell.
    ``damage`` is the hit, ``factor`` the aura it was loosed under (a factor of the damage pipeline).

    A bolt is never changed: each step makes a flying bolt anew, so clones and the view keep the ones they were
    given. It is a class of its own rather than a dataclass, whose ``__init__`` runs interpreted when compiled."""

    __slots__ = ("id", "tower", "kind", "target", "left", "damage", "element", "splash", "poison", "poison_time",
                 "chill", "chill_time", "leader_bonus", "factor",
                 "origin", "last")

    def __init__(self, id: int, tower: int, kind: str, target: int, left: float, damage: float, element: Element,
                 splash: float, poison: float, poison_time: float, origin: tuple[float, float],
                 last: tuple[float, float], chill: float = 0.0, chill_time: float = 0.0,
                 leader_bonus: float = 0.0, factor: float = 1.0) -> None:
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
        self.chill = chill
        self.chill_time = chill_time
        self.leader_bonus = leader_bonus
        self.factor = factor
        self.origin = origin
        self.last = last                # the target's last known position

    def __reduce__(self) -> tuple[Any, ...]:
        return Bolt, (self.id, self.tower, self.kind, self.target, self.left, self.damage, self.element, self.splash,
                      self.poison, self.poison_time, self.origin, self.last, self.chill, self.chill_time,
                      self.leader_bonus, self.factor)


@dataclass(frozen=True)
class Meteor:
    at: float                   # when it lands
    x: float
    y: float
    damage: float
    burn: float                 # damage per second of the floor it sets burning


class Hazard:
    """Burning floor: every walker on it takes fire damage each second (flyers pass over)."""

    __slots__ = ("x", "y", "radius", "dps", "left", "spell")

    def __init__(self, x: float, y: float, radius: float, dps: float, left: float, spell: bool = False) -> None:
        self.x, self.y, self.radius, self.dps, self.left = x, y, radius, dps, left
        self.spell = spell   # a meteor's burning floor (a pyre's is its tower's)

    def copy(self) -> Hazard:
        return Hazard(self.x, self.y, self.radius, self.dps, self.left, self.spell)

    def __reduce__(self) -> tuple[Any, ...]:
        return Hazard, (self.x, self.y, self.radius, self.dps, self.left, self.spell)


@dataclass
class ForcedCurse:
    """A curse a rollout lands at a fixed time, standing in for a leader's chant."""

    at: float
    leader: int
    curse: Curse
    spot: tuple[int, int]


def curse_radius(curse: Curse, leader_kind: MonsterKind | None, curse_scale: float = 1.0) -> float:
    """The radius a curse falls in when this kind casts it: its own radius, widened by its leader, scaled by curse_scale."""
    widen = 0.0
    if leader_kind is not None and leader_kind.leader is not None:
        widen = leader_kind.leader.widen
    return (CURSES[curse].radius + widen) * curse_scale


Planner = Callable[["World", int], Any]   # returns a handle with .result() -> Decision


class World:
    def __init__(self, location: Location = CATHEDRAL, *, hardness: float = 1.0, perks: Perks = NO_PERKS,
                 seed: int = 0, planner: Planner | None = None, record: bool = True, curse_scale: float = 1.0,
                 loadout: Loadout = EMPTY_LOADOUT, xp: float = 0.0, xp_level: int = 1,
                 arsenal: Arsenal | None = None, relics: tuple[str, ...] = (),
                 counters: tuple[tuple[str, int], ...] = (), foresight: bool = True) -> None:
        self.location = location
        self.arsenal = location.arsenal if arsenal is None else arsenal
        self.relics = relics   # the run's relics, won a location at a time
        self.progress = {key: n for key, n in counters if key in relics}   # each relic's count toward its firing
        self.stage = ORDER.index(location.key)
        self.level = location.level
        self.waves = location.waves
        self.perks = perks
        self.loadout = Loadout(tuple(key for key in loadout.equipped if PATTERNS[key].first_location <= self.stage + 1))
        self.tower_levels = baked(perks, self.loadout)
        self.hardness = hardness   # every monster's life is multiplied by this; the spells are not
        self.curse_scale = curse_scale  # multiplies every curse radius (0 = only the marked tile)
        self.rng = random.Random(seed)
        self.route_rng = random.Random(seed ^ 0x51DE)
        ordinary_spawns = 0
        for wave in self.waves:
            for group in wave.groups:
                ordinary_spawns += group.count
        self.loot_ordinals = frozenset(random.Random(seed ^ 0x5A17).sample(
            range(ordinary_spawns), min(BALANCE.salvage_budget, ordinary_spawns)))
        self.spawn_ordinal = 0
        self.salvage_held = 0
        self.salvage_sold = 0
        self.planner = planner
        self.record = record
        self.events: list[tuple] = []
        self.time = 0.0
        self.gold = location.start_gold
        self.lives = START_LIVES
        self.mana = min(MANA_START, self.mana_max)
        self.xp = xp                    # the run's progress to the next level, counted on from here
        self.xp_level = xp_level        # the run's level (``level`` is the map): each level-up refills the mana
        self.xp_total = 0.0             # every point earned this defence, for the run's settling
        self.towers: dict[int, Tower] = {}
        self.cleared: set[tuple[int, int]] = set()   # boulders cleared, now open floor
        self.doors = [Door(i, tile, s) for i, (tile, s) in enumerate(zip(self.level.doors, self.level.door_s))]
        self.monsters: list[Monster] = []     # alive and on the map, nearest the sanctuary first
        self.bolts: list[Bolt] = []
        self.meteors: list[Meteor] = []
        self.hazards: list[Hazard] = []
        self.wave = -1                        # index of the latest wave called
        self.schedule: list[tuple[float, str, str]] = []   # (wave time, monster kind, authored route), soonest last
        self.gold_schedule: list[int] = []     # each scheduled spawn's allocated gold, soonest last
        self.breach_schedule: list[bool] = []
        self.elite_schedule: list[bool] = []
        self.bonus_schedule: list[bool] = []
        self.bonus: Bonus | None = None        # the summoned pack, while it lives
        self.breach_spec = BREACHES.get(location.key)
        self.breach_mode: str | None = None
        self.breach_remaining = 0
        self.breach_failed = False
        self.breach_cleared = False
        self.wave_time = 0.0
        self.break_left: float | None = FIRST_WAVE_BREAK
        self.wave_alive: dict[int, int] = {}
        self.unpaid: list[int] = []           # waves whose clearing bonus is still to come
        self.leaked_life = 0.0                # monster life that reached the sanctuary, weighted (the planner's score)
        self.forced: list[ForcedCurse] = []
        self.outcome: str | None = None       # "victory" or "defeat"
        self.kills = 0
        self.curses_landed = 0
        self.spells_cast = 0
        self.spell_kills = 0   # kills whose finishing blow was a cast: a player's, the idol's or a relic's
        self.player_casts = 0   # casts by the player's own hand (S2 counts these a wave)
        self.wasted_charges = 0   # empowered shots a plain one would have killed with
        self.foresight = foresight   # the forge's teaching: spend a charge only where it kills
        self.blighted: dict[tuple[int, int], tuple[int, str]] = {}   # taken cells: cleared waves left, what it is
        self.blights = 0                  # cells taken this defence, for the run's settling
        self.blighted_cells: set[tuple[int, int]] = set()   # every cell taken this defence
        self.builds = 0       # the verbs, counted where they happen: towers raised, ranks bought,
        self.upgrades = 0     # spells cast (spells_cast), curses landing (curses_landed) and leaks
        self.leaks = 0
        self.fervor = 0.0     # the Battle Trance's seconds left: every tower quickened while they last
        self.recharge: dict[str, float] = {}  # seconds each spell still gathers itself after a cast
        self._next_id = 1

    # -- Copies for the planner ---------------------------------------------------------

    def clone(self) -> World:
        """A private copy to look ahead in: no events, no planner, its own random stream."""
        w = World(self.location, hardness=self.hardness, perks=self.perks, record=False, curse_scale=self.curse_scale,
                  loadout=self.loadout, arsenal=self.arsenal)
        w.tower_levels = self.tower_levels   # the derived ranks are copied, not rebuilt
        w.rng.setstate(self.rng.getstate())
        w.route_rng.setstate(self.route_rng.getstate())
        w.loot_ordinals, w.spawn_ordinal = self.loot_ordinals, self.spawn_ordinal
        w.salvage_held, w.salvage_sold = self.salvage_held, self.salvage_sold
        w.time, w.gold, w.lives, w.mana = self.time, self.gold, self.lives, self.mana
        w.xp, w.xp_level, w.xp_total = self.xp, self.xp_level, self.xp_total
        w.towers = {i: t.copy() for i, t in self.towers.items()}
        w.cleared = set(self.cleared)
        w.doors = [d.copy() for d in self.doors]
        w.monsters = [m.copy() for m in self.monsters]
        w.bolts = list(self.bolts)       # bolts and meteors are never changed in place
        w.meteors = list(self.meteors)
        w.hazards = [h.copy() for h in self.hazards]
        w.recharge = dict(self.recharge)
        w.wave, w.schedule, w.wave_time, w.break_left = self.wave, list(self.schedule), self.wave_time, self.break_left
        w.gold_schedule = list(self.gold_schedule)
        w.breach_schedule, w.elite_schedule = list(self.breach_schedule), list(self.elite_schedule)
        w.bonus_schedule = list(self.bonus_schedule)
        w.bonus = None if self.bonus is None else replace(self.bonus)
        w.breach_mode, w.breach_remaining = self.breach_mode, self.breach_remaining
        w.breach_failed, w.breach_cleared = self.breach_failed, self.breach_cleared
        w.wave_alive, w.unpaid = dict(self.wave_alive), list(self.unpaid)
        w.leaked_life, w.forced, w.outcome, w.kills, w._next_id = self.leaked_life, [], self.outcome, self.kills, self._next_id
        w.curses_landed, w.spells_cast = self.curses_landed, self.spells_cast
        w.spell_kills = self.spell_kills
        w.player_casts = self.player_casts
        w.wasted_charges, w.foresight = self.wasted_charges, self.foresight
        w.blighted, w.blights, w.blighted_cells = dict(self.blighted), self.blights, set(self.blighted_cells)
        w.relics = self.relics
        w.progress = dict(self.progress)
        w.builds, w.upgrades, w.leaks, w.fervor = self.builds, self.upgrades, self.leaks, self.fervor
        return w

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _emit(self, *event: Any) -> None:
        if self.record:
            self.events.append(event)

    def _earn(self, amount: float) -> None:
        """Count XP: each level crossed refills the mana orb and is told to the view."""
        self.xp_total += amount
        self.xp += amount
        while self.xp + 1e-9 >= xp_next(self.xp_level):
            self.xp -= xp_next(self.xp_level)
            self.xp_level += 1
            self.mana = self.mana_max
            self._emit("level_up", self.xp_level)

    # -- Queries ------------------------------------------------------------------------

    def monster(self, monster_id: int) -> Monster | None:
        for m in self.monsters:
            if m.id == monster_id:
                return m
        return None

    def position(self, m: Monster) -> tuple[float, float]:
        return self.level.route(m.route).point(m.s)

    def heading(self, m: Monster) -> tuple[float, float]:
        return self.level.route(m.route).heading(m.s)

    def remaining(self, m: Monster) -> float:
        return self.level.route(m.route).length - m.s

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

    def striking_reach(self, tower: Tower) -> float:
        """How far the tower's strikes reach: its own reach, plus the Hoarder's Seal for an attuned tower
        with full charges."""
        reach = tower.reach
        if "hoard" in self.relics and tower.attuned and tower.charges >= CHARGES_MAX:
            reach += HOARD_REACH
        return reach

    def in_reach(self, tower: Tower, s: float, route: str = "main") -> bool:
        spans = (self.level.coverage(tower.tile, self.striking_reach(tower)) if route == "main"
                 else self.level.route(route).coverage(tower.tile, self.striking_reach(tower)))
        for a, b in spans:
            if a <= s <= b:
                return True
        return False

    def _tower_covers(self, tower: Tower, monster: Monster, spans: tuple[tuple[float, float], ...], reach: float) -> bool:
        if monster.route == "main":
            return _inside(monster.s, spans)
        x, y = self.position(monster)
        cx, cy = tower.centre
        return (x - cx) ** 2 + (y - cy) ** 2 <= reach * reach

    @property
    def spawning(self) -> bool:
        return bool(self.schedule)

    @property
    def can_call_wave(self) -> bool:
        return (self.outcome is None and not self.schedule and self.wave + 1 < len(self.waves)
                and self.bonus is None)

    @property
    def early_call_bonus(self) -> int:
        """Gold shown and paid for ending the current break early."""
        return int(self.break_left * EARLY_CALL_GOLD) if self.break_left is not None and self.wave >= 0 else 0

    @property
    def breach_offered(self) -> bool:
        spec = self.breach_spec
        return (spec is not None and self.outcome is None and self.breach_mode is None
                and self.wave == spec.after_wave and self.break_left is not None
                and not self.schedule and self.wave_alive.get(self.wave, 0) == 0)

    @property
    def breach_opened(self) -> bool:
        return self.breach_mode in ("cash", "trophy")

    def choose_breach(self, mode: str) -> None:
        """Choose a side pack and reward, or leave its entrance sealed this run."""
        if not self.breach_offered:
            raise Refused("No sealed side entrance is offered at this break.")
        if mode not in ("decline", "cash", "trophy"):
            raise Refused("Choose cash, trophy, or decline the side entrance.")
        self.breach_mode = mode
        self._emit("breach_choice", mode)

    def leaders(self) -> list[Monster]:
        return [m for m in self.monsters if m.kind.leader is not None]

    @property
    def mana_max(self) -> float:
        return (self.perks.mana_max - (CANTICLE_WELL if "canticle" in self.relics else 0.0)
                - (BELLOWS_WELL if "bellows" in self.relics else 0.0))

    @property
    def spells(self) -> tuple[str, ...]:
        """The spells offered: the arsenal's unlocked, and the Canticle's Hymn where neither holds it."""
        offered = tuple(k for k in self.arsenal.spells if k not in self.perks.locked)
        if "canticle" in self.relics and "hymn" not in offered:
            offered += ("hymn",)
        return offered

    def _fervor(self) -> float:
        """What the Battle Trance makes of every tower's attacks per second."""
        return TRANCE_RATE if self.fervor > 0 else 1.0

    def _relic(self, verb: str, amount: float = 0.0, who: Monster | Tower | None = None) -> None:
        """A verb happened: every held relic that reads it counts one, and fires on its count. `who` is the verb's
        subject where it has one: the tower raised or ranked, the leader whose curse landed."""
        for key in self.relics:
            spec = RELICS[key]
            if spec.verb != verb:
                continue
            n = self.progress.get(key, 0) + 1
            self.progress[key] = n
            if n % spec.every != 0:
                continue
            if key == "tithe":
                self.gold += round(amount)
            elif key == "scaffold":
                self.gold += SCAFFOLD_GOLD
            elif key == "whetstone":
                self.gold += round(amount / 2)
            elif key == "masterwork":
                self.mana = min(self.mana_max, self.mana + MASTERWORK_MANA)
            elif key == "trance":
                self.fervor = TRANCE_TIME
            elif key == "deep_well":
                self.mana = min(self.mana_max, self.mana + amount / 2)
            elif key == "spite":
                self.mana = min(self.mana_max, self.mana + SPITE_MANA)
            elif key == "martyr":
                self.gold += MARTYR_GOLD
            elif key == "blood_money":
                self.gold += round(amount) * BLOOD_GOLD
                self.lives -= BLOOD_LIVES
            elif key == "bell":
                for tower in self.towers.values():
                    if tower.attuned:
                        tower.charges = min(CHARGES_MAX, tower.charges + 1.0)
                self.mana = max(0.0, self.mana - BELL_MANA)
            elif key == "candle":
                if isinstance(who, Monster) and who.hp > 0:
                    self._answer(who)
            elif key == "volatile":
                foremost: Monster | None = None
                for monster in self.monsters:
                    if monster.hp > 0 and (foremost is None or self.remaining(monster) < self.remaining(foremost)):
                        foremost = monster
                if foremost is not None:
                    self._answer(foremost)
            elif key == "temper" or key == "lodestone":
                if isinstance(who, Tower) and not who.attuned:
                    who.attuned = True
                    who.charges = CHARGES_MAX
                    self._emit("attuned", who.id)
            elif key == "bellows":
                self.mana = min(self.mana_max, self.mana + BELLOWS_MANA)
            elif key == "stormglass":
                for tower in self.towers.values():
                    if tower.attuned:
                        tower.charges = min(CHARGES_MAX, tower.charges + 1.0)
            self._emit("relic", key, spec.name)

    def _answer(self, monster: Monster) -> None:
        """A relic's answering smite: free, and a cast that counts, like the idol's rite. No bury: the slain
        walk no further this step (every phase skips hp <= 0, like the censer's dead) and the step's end
        buries them — burying here would mutate the monster list the caller walks."""
        self._emit("smite", monster.id, self.position(monster))
        self._hurt(monster, felt_hit(SPELLS["smite"].damage * self.power(), None, monster.kind), None, spell=True)
        self.spells_cast += 1
        self._relic("cast", 0.0)

    @property
    def gate_life(self) -> float:
        return self.perks.gate_life

    @property
    def door_cost(self) -> int:
        return DOOR.cost

    def spell_cost(self, key: str) -> float:
        return SPELLS[key].mana * self.perks.spell_cost

    def power(self) -> float:
        """How hard a spell strikes: its authored damage, with Spell Mastery."""
        return self.perks.spell_power

    def cost(self, kind: str) -> int:
        return self.tower_levels[kind][0].cost

    def buildable(self, x: int, y: int) -> bool:
        """Whether a tower can stand here now: the bare floor, or a boulder cleared this defence."""
        return self.level.buildable(x, y) or ((x, y) in self.level.boulders and (x, y) in self.cleared)

    def clear(self, tile: tuple[int, int]) -> int:
        """Clear a boulder during a break, opening its cell: one income unit, then two, then three."""
        if self.outcome is not None or self.break_left is None:
            raise Refused("Boulders can be cleared only during a wave break.")
        if tile not in self.level.boulders or tile in self.cleared:
            raise Refused("No boulder stands there.")
        price = BALANCE.income_unit() * (len(self.cleared) + 1)
        if self.gold < price:
            raise Refused(f"Clearing costs {price} gold.")
        self.gold -= price
        self.cleared.add(tile)
        self._emit("cleared_boulder", tile, price)
        return price

    # -- Commands -----------------------------------------------------------------------

    def build(self, kind: str, tile: tuple[int, int]) -> Tower:
        tower_kind = TOWERS[kind]
        if kind not in self.arsenal.towers:
            raise Refused(f"No {tower_kind.name} can be raised in {self.location.called}.")
        if kind in self.perks.locked:
            key = UNLOCK[kind]
            assert key is not None
            raise Refused(f"The {tower_kind.name} is locked: learn {SKILLS[key].name} first.")
        if not self.buildable(*tile):
            raise Refused("Towers stand on the bare floor, not on the path, the walls or the pits.")
        if self.tower_at(tile) is not None:
            raise Refused("A tower already stands there.")
        if tile in self.blighted:
            waves, verb = self.blighted[tile]
            raise Refused(f"That cell is {verb} for {waves} more wave{'s' if waves != 1 else ''}.")
        levels = self.tower_levels[kind]
        cost = self.cost(kind)
        if self.gold < cost:
            raise Refused(f"{tower_kind.name} costs {cost} gold.")
        self.gold -= cost
        tower = Tower(self._id(), tower_kind, levels, tile)
        tower.spent = cost
        self.towers[tower.id] = tower
        self.builds += 1
        self._relic("build", cost, tower)
        self._emit("built", tower.id, kind)
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
        self.upgrades += 1
        self._relic("upgrade", cost, tower)
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

    def sell_salvage(self, count: int) -> int:
        """Take battle gold now in place of banking these drops after a victory."""
        if self.outcome is not None or self.break_left is None:
            raise Refused("Salvage can be sold only during a wave break.")
        if type(count) is not int or count <= 0 or count > self.salvage_held:
            raise Refused("You do not hold that much salvage.")
        gold = count * BALANCE.salvage_sale_gold()
        self.salvage_held -= count
        self.salvage_sold += count
        self.gold += gold
        self._emit("salvage_sold", count, gold)
        return gold

    def build_door(self, index: int) -> None:
        if not self.arsenal.gates:
            raise Refused(f"There are no arches to ward in {self.location.called}.")
        door = self.doors[index]
        if door.built:
            raise Refused("The gate already stands.")
        if door.rubble:
            raise Refused("The arch lies in rubble until the fight dies down between waves.")
        if self.gold < self.door_cost:
            raise Refused(f"A warded gate costs {self.door_cost} gold.")
        for m in self.monsters:
            if not m.kind.flying:
                for crossing_index, s in self.level.crossings(m.route):
                    if crossing_index == index and abs(m.s - s) < 0.6:
                        raise Refused("Monsters stand in the arch.")
        self.gold -= self.door_cost
        door.built, door.hp = True, self.gate_life
        self._emit("door_built", index)

    def _spend(self, key: str) -> None:
        if key not in self.arsenal.spells and not (key == "hymn" and "canticle" in self.relics):
            raise Refused(f"{SPELLS[key].name} is not yours to cast in {self.location.called}.")
        if key in self.perks.locked and not (key == "hymn" and "canticle" in self.relics):
            raise Refused(f"{SPELLS[key].name} is locked: learn {SKILLS[SPELL_UNLOCK[key]].name} first.")
        left = self.recharge.get(key, 0.0)
        if left > 0:
            raise Refused(f"{SPELLS[key].name} gathers itself again: {math.ceil(left)} s.")
        cost = self.spell_cost(key)
        if self.mana < cost:
            raise Refused(f"{SPELLS[key].name} takes {cost:.0f} mana.")
        self.mana -= cost
        self.spells_cast += 1
        self.player_casts += 1   # the player's own hand: the idol's rites and a relic's answers are not it
        self._relic("cast", cost)
        if SPELLS[key].recharge > 0:
            self.recharge[key] = SPELLS[key].recharge

    def hymn(self, tower_id: int) -> None:
        """Battle Hymn: the tower attacks HYMN_RATE times as fast while it lasts."""
        tower = self.towers.get(tower_id)
        if tower is None:
            raise Refused("No tower stands there to hear the hymn.")
        self._spend("hymn")
        tower.hymn = SPELLS["hymn"].lasting
        self._emit("hymn", tower.id)

    def smite(self, monster_id: int) -> None:
        m = self.monster(monster_id)
        if m is None or m.hp <= 0:
            raise Refused("There is nothing there to smite.")
        self._spend("smite")
        self._emit("smite", m.id, self.position(m))
        self._hurt(m, felt_hit(SPELLS["smite"].damage * self.power(), None, m.kind), None, spell=True)
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
        for m in struck:
            self._strike(m, damage, Element.COLD, spell=True)
        self._bury()

    def _inside_map(self, x: float, y: float) -> None:
        if not (0 <= x <= self.level.width and 0 <= y <= self.level.height):
            raise Refused("That is outside the walls.")

    def _around(self, x: float, y: float, radius: float, *, flyers: bool) -> list[Monster]:
        found = []
        for m in self.monsters:
            if m.hp <= 0 or (m.kind.flying and not flyers):
                continue
            mx, my = self.position(m)
            if (mx - x) ** 2 + (my - y) ** 2 <= radius * radius:
                found.append(m)
        return found

    def call_wave(self) -> None:
        if not self.can_call_wave:
            raise Refused("The next wave cannot be called yet.")
        self.gold += self.early_call_bonus
        self._start_wave()

    def predict_clean(self) -> bool:
        """Whether the wave now fighting ends with no losses and no orders: a clone with the leaders'
        planner steps it to its clearing. Only while a fully spawned wave fights, no pack and no breach."""
        if (self.outcome is not None or self.wave < 0 or self.break_left is not None or self.schedule
                or self.bonus is not None or self.breach_remaining > 0):
            return False
        twin = self.clone()
        twin.planner = self.planner
        lives = twin.lives
        for _ in range(SKIP_STEPS):
            twin.step(SIM_DT)
            if twin.lives < lives:
                return False
            if not twin.monsters and not twin.schedule and \
                    (twin.break_left is not None or twin.outcome is not None):
                return True
        return False

    def skip_grind(self) -> int:
        """Step the fought wave to its clearing, now: the prediction come true, and the bonus gold paid.
        Refused if a life is lost on the way (the offer was stale)."""
        lives = self.lives
        for _ in range(SKIP_STEPS):
            self.step(SIM_DT)
            if self.lives < lives:
                raise Refused("The wave was not clean: a life was lost on the way.")
            if not self.monsters and not self.schedule and \
                    (self.break_left is not None or self.outcome is not None):
                break
        bonus = BALANCE.income_unit()
        self.gold += bonus
        self._emit("skipped", self.wave, bonus)
        return bonus

    def summon(self, pack: BonusPack) -> None:
        """Wager the pack's gold on its monsters: they spawn while the break clock stops, and a clear with no
        leak pays the wager back with the profit and the XP. The stake rides in the pack, drawn by
        :func:`hellward.sim.bonus.draw`."""
        if self.outcome is not None:
            raise Refused("The defence is decided.")
        if self.bonus is not None:
            raise Refused("A bonus pack already fights.")
        if self.break_left is None:
            raise Refused("A bonus wave is summoned during a break.")
        if self.wave + 1 < BONUS_EARLY:
            raise Refused(f"Bonus waves open from wave {BONUS_EARLY}'s break.")
        if self.gold < pack.wager:
            raise Refused(f"Stake {pack.stake} takes {pack.wager} gold.")
        self.gold -= pack.wager
        tagged: list[tuple[float, str, str]] = []
        for group in pack.pack:
            self.level.route(group.route)   # a drawn pack must name a route on this map
            for i in range(group.count):
                tagged.append((group.start + i * group.interval, group.kind, group.route))
        tagged.sort(reverse=True)
        self.schedule = [(when, kind, route) for when, kind, route in tagged]
        self.breach_schedule = [False] * len(tagged)
        self.elite_schedule = [False] * len(tagged)
        self.bonus_schedule = [True] * len(tagged)
        self.gold_schedule = [0] * len(tagged)
        self.wave_time = 0.0
        saved, self.break_left = self.break_left, None
        self.wave_alive[self.wave] += len(tagged)
        self.bonus = Bonus(pack.stake, pack.wager, pack.profit, pack.xp, pack.life_factor, len(tagged),
                           fail=pack.fail, saved_break=saved)
        self._emit("bonus", pack.stake, "summoned")

    def _start_wave(self) -> None:
        if self.breach_offered:
            self.choose_breach("decline")
        self.wave += 1
        self.break_left = None
        self.wave_time = 0.0
        tagged: list[tuple[float, str, str, bool, bool]] = []
        for group in self.waves[self.wave].groups:
            self.level.route(group.route)   # an authored wave must name a route on this map
            for i in range(group.count):
                tagged.append((group.start + i * group.interval, group.kind, group.route, False, False))
        spec = self.breach_spec
        if spec is not None and self.breach_opened and self.wave == spec.after_wave + 1:
            for group_index, group in enumerate(spec.groups):
                self.level.route(group.route)
                for i in range(group.count):
                    tagged.append((group.start + i * group.interval, group.kind, group.route,
                                   True, group_index == 0))
            self.breach_remaining = spec.count
        tagged.sort(reverse=True)
        self.schedule = [(when, kind, route) for when, kind, route, _, _ in tagged]
        self.breach_schedule = [side for _, _, _, side, _ in tagged]
        self.elite_schedule = [elite for _, _, _, _, elite in tagged]
        self.bonus_schedule = [False] * len(tagged)
        ordinary_weights = tuple(MONSTERS[kind].bounty for _, kind, _, side, _ in reversed(tagged) if not side)
        side_weights = tuple(MONSTERS[kind].bounty for _, kind, _, side, _ in reversed(tagged) if side)
        ordinary_gold = BALANCE.wave_payouts(self.wave, ordinary_weights)
        side_gold = BALANCE.breach_payouts(side_weights)
        ordinary_index = 0
        side_index = 0
        payouts: list[int] = []
        for _, _, _, side, _ in reversed(tagged):
            if side:
                payouts.append(side_gold[side_index])
                side_index += 1
            else:
                payouts.append(ordinary_gold[ordinary_index])
                ordinary_index += 1
        self.gold_schedule = list(reversed(payouts))
        self.wave_alive[self.wave] = len(tagged)
        self.unpaid.append(self.wave)
        self._emit("wave", self.wave)

    # -- The step -----------------------------------------------------------------------

    def step(self, dt: float = SIM_DT) -> None:
        if self.outcome is not None:
            return
        self.time += dt
        self.mana = min(self.mana_max, self.mana + self.perks.mana_regen * dt)
        if self.fervor > 0:
            self.fervor = max(0.0, self.fervor - dt)
        if self.recharge:
            for key in list(self.recharge):
                left = self.recharge[key] - dt
                if left <= 0:
                    del self.recharge[key]
                else:
                    self.recharge[key] = left
        self._spawn(dt)
        self._leaders(dt)
        self._blight(dt)
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
            _, key, authored_route = self.schedule.pop()
            bounty = self.gold_schedule.pop()
            side = self.breach_schedule.pop()
            elite = self.elite_schedule.pop()
            is_bonus = self.bonus_schedule.pop()
            salvage = 0
            if not side and not is_bonus:
                salvage = int(self.spawn_ordinal in self.loot_ordinals)
                self.spawn_ordinal += 1
            kind = MONSTERS[key]
            cooldown = kind.leader.first_cast if kind.leader is not None else 0.0
            route_key = authored_route
            if kind.movement == "wander":
                entrance = self.level.route(authored_route).entrance
                choices = [route.key for route in self.level.routes if route.entrance == entrance]
                if len(choices) > 1:
                    route_key = self.route_rng.choice(choices)
            spec = self.breach_spec
            hp_factor = spec.elite_hp_factor if elite and spec is not None else 1.0
            speed_factor = spec.elite_speed_factor if elite and spec is not None else 1.0
            elite_name = spec.elite_name if elite and spec is not None else ""
            pack = self.bonus
            if is_bonus and pack is not None:
                hp_factor *= pack.life_factor
            m = Monster(self._id(), kind, self.wave, self.rng.uniform(-0.28, 0.28), self.rng.uniform(0.0, JOSTLE),
                        kind.hp * self.hardness * hp_factor, cooldown,
                        route_key, bounty, salvage, side, elite_name, speed_factor, bonus=is_bonus)
            self.monsters.append(m)
            self._emit("spawn", m.id, kind.key)
            if elite:
                self._emit("breach_elite", m.id, elite_name)

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
                    if decision.cast is None:
                        m.cooldown = decision.retry
                    elif spec.mark > 0:   # a mark burns on its spot, longer, before it lands
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
            if m.cooldown <= 0 and self.planner is not None and self.towers:
                m.asking = _ASK
                m.ask_left = DECIDE_DELAY
                self._emit("ponder", m.id)

    def _land(self, leader_id: int, curse: Curse, spot: tuple[int, int]) -> None:
        leader = self.monster(leader_id)
        if leader is None:
            self._emit("fizzle", leader_id, spot)
            return
        spec = leader.kind.leader
        x, y = self.position(leader)
        cx, cy = spot[0] + 0.5, spot[1] + 0.5
        if spec is None or _hypot(cx - x, cy - y) > spec.cast_range + CAST_SLACK:
            self._emit("fizzle", leader_id, spot)
            return
        cursed: list[int] = []
        rod = self._effigy(spot)
        if rod is not None:   # a warding effigy stands unsullied near the spot: the curse goes to it instead
            rod.curses[curse] = CURSES[curse].duration
            cursed.append(rod.id)
        else:
            for tower in self.caught(spot, curse_radius(curse, leader.kind, self.curse_scale)):
                tower.curses[curse] = CURSES[curse].duration
                cursed.append(tower.id)
        if cursed:
            self.curses_landed += 1
            self._relic("curse", 0.0, leader)
            self._emit("cursed", leader_id, spot, curse, tuple(cursed))
            if spec is not None and spec.burn > 0:
                amount = spec.burn * len(cursed)
                if self.mana > 0:
                    burned = min(self.mana, amount)
                    self.mana -= burned
                    self._emit("burned", leader_id, burned)
        else:
            self._emit("fizzle", leader_id, spot)
        leader.marking = False

    def _effigy(self, spot: tuple[int, int]) -> Tower | None:
        """The nearest effigy holding no curse whose reach covers the spot, if one stands."""
        cx, cy = spot[0] + 0.5, spot[1] + 0.5
        best: Tower | None = None
        nearest = 0.0
        for t in self.towers.values():
            if t.kind.key != "effigy" or t.curses:
                continue
            dx, dy = t.tile[0] + 0.5 - cx, t.tile[1] + 0.5 - cy
            reach = t.levels[t.level].range
            if dx * dx + dy * dy <= reach * reach and (best is None or dx * dx + dy * dy < nearest
                                                       or (dx * dx + dy * dy == nearest and t.id < best.id)):
                best, nearest = t, dx * dx + dy * dy
        return best

    def _blight(self, dt: float) -> None:
        for m in self.monsters:
            spec = m.kind.blight
            if spec is None or m.hp <= 0:
                continue
            if m.blight_cell != (-1, -1):
                m.blight_left -= dt
                if m.blight_left <= 0:
                    self._land_blight(m)
                continue
            if m.blight_wave == self.wave:
                continue
            m.blight_cd -= dt
            if m.blight_cd > 0:
                continue
            cell = self._blight_target(m)
            if cell is None:
                m.blight_cd = BLIGHT_RETRY
                continue
            m.blight_cell, m.blight_left, m.blight_wave = cell, spec.telegraph, self.wave
            self._emit("blight_mark", m.id, cell, spec.telegraph, spec.past)

    def _blight_target(self, m: Monster) -> tuple[int, int] | None:
        """The best empty cell in the blighter's reach: worth what a tower there would reach, the simulation's own
        reckoning. Nothing worthless, nothing taken or already marked, nothing past the fifth cell at once."""
        spec = m.kind.blight
        assert spec is not None
        marked = {o.blight_cell for o in self.monsters if o.blight_cell != (-1, -1)}
        if len(self.blighted) + len(marked) >= BLIGHT_MAX or len(self.blighted_cells) >= BLIGHT_CELLS:
            return None
        x, y = self.position(m)
        every, ground = cell_worth.shares(self.level, self.waves)
        built = frozenset(d.index for d in self.doors if d.built)
        reach = TOWERS["arrow"].levels[0].range
        best: tuple[int, int] | None = None
        most = 0.0
        for cy in range(max(0, int(y - spec.reach)), min(self.level.height, int(y + spec.reach) + 2)):
            for cx in range(max(0, int(x - spec.reach)), min(self.level.width, int(x + spec.reach) + 2)):
                cell = (cx, cy)
                if ((cell in marked or cell in self.blighted or self.tower_at(cell) is not None
                        or not self.buildable(cx, cy))
                        or _hypot(cx + 0.5 - x, cy + 0.5 - y) > spec.reach):
                    continue
                worth = cell_worth.cell(self.level, every, ground, cell, reach, built=built)
                if worth > most:
                    best, most = cell, worth
        return best

    def _land_blight(self, m: Monster) -> None:
        spec = m.kind.blight
        cell = m.blight_cell
        m.blight_cell, m.blight_left = (-1, -1), 0.0
        assert spec is not None
        if (cell in self.blighted or self.tower_at(cell) is not None or not self.buildable(*cell)
                or (cell not in self.blighted_cells and len(self.blighted_cells) >= BLIGHT_CELLS)):
            self._emit("blight_fizzle", m.id, cell)   # a tower raced the mark and won, the fifth cell went first
            return
        self.blighted[cell] = (spec.waves, spec.past)
        self.blights += 1
        self.blighted_cells.add(cell)
        self._emit("blight", m.id, cell, spec.waves, spec.past)

    def _move(self, dt: float) -> None:
        level = self.level
        monsters = self.monsters
        groves: list[tuple[float, float]] = []
        if self.perks.hurricane:
            for t in self.towers.values():
                if t.kind.key == "grove" and not t.silenced:
                    groves.append((t.tile[0] + 0.5, t.tile[1] + 0.5))
        leaked = False
        ordered, last = True, -math.inf   # whether those still on the map remain nearest the sanctuary first
        for m in monsters:
            if m.hp <= 0:   # the censer's dead walk no further this step; the step's end buries them
                continue
            route = level.route(m.route)
            if m.frozen > 0:
                m.frozen -= dt
                m.door = -1
                if m.chill_left > 0:
                    m.chill_left -= dt
            else:
                if m.chill_left > 0:
                    m.chill_left -= dt
                    speed = m.kind.speed * m.speed_factor * (1.0 - m.chill)
                else:
                    speed = m.kind.speed * m.speed_factor
                if groves and not m.kind.flying:
                    mx, my = self.position(m)
                    for gx, gy in groves:
                        dx, dy = mx - gx, my - gy
                        if dx * dx + dy * dy <= HURRICANE_RADIUS * HURRICANE_RADIUS:
                            speed *= HURRICANE_SLOW
                            break
                s = m.s + speed * dt
                m.door = -1
                if not m.kind.flying:
                    for door_index, crossing in level.crossings(m.route):
                        d = self.doors[door_index]
                        if not d.built:
                            continue
                        stop = crossing - DOOR_STOP - m.jostle
                        if m.s <= stop + 1e-9 < s or stop - 1e-9 <= m.s < crossing:
                            s = min(s, stop)
                            if s >= stop - 1e-6:
                                m.door = d.index
                            break
                m.s = s
                if s >= route.length:   # it strikes the shrine
                    self.lives -= m.kind.lives
                    self.leaked_life += m.max_hp * LEAK_WEIGHT
                    if m.bonus and self.bonus is not None:
                        self.bonus.leaked = True   # a strike or a leak fails the pack, boss or no boss
                    if m.kind.boss:   # struck back to its portal, with its life and afflictions, to walk again
                        self._censers(m)   # at the shrine, before the return
                        if m.hp <= 0:   # the immolation killed it: no return
                            ordered = False
                            continue
                        m.s, m.door = 0.0, -1
                        m.strikes += 1
                        self.leaks += 1
                        self._relic("leak", m.kind.lives)
                        self._emit("returned", m.id, m.kind.key, m.kind.lives, m.strikes)
                        ordered = False
                        continue
                    self._count_off(m)
                    self.leaks += 1
                    self._censers(m)
                    self._relic("leak", m.kind.lives)
                    self._emit("leak", m.id, m.kind.key, m.kind.lives)
                    leaked = True
                    continue
            remaining = route.length - m.s
            if remaining < last:
                ordered = False
            last = remaining
        if leaked:   # through the sanctuary gate: those that walked to the path's end, and only they
            monsters = self.monsters = [m for m in monsters if m.s < level.route(m.route).length]
        if not ordered:   # someone overtook
            _furthest_first(monsters, level)
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
                if thorns:   # holy, like Smite: no factor, no armor
                    self._hurt(m, m.kind.door_dps * dt * THORNS, None, quiet=True)
                if d.hp <= 0 and d.built:
                    d.built, d.hp, d.rubble = False, 0.0, True
                    self._emit("door_broken", d.index)

    def aura_mult(self, tower: Tower) -> float:
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
            x, y = self.position(m)
            dx, dy = x - gx, y - gy
            if dx * dx + dy * dy <= TWISTER_RADIUS * TWISTER_RADIUS and (best is None or self.remaining(m) < self.remaining(best)):
                best = m
        if best is not None:
            best.frozen = max(best.frozen, TWISTER_HELD)
            best.door = -1
            self._emit("twister", t.id, best.id)

    def _idol(self, t: Tower, dt: float) -> None:
        """The idol's rite: every so often it smites the foremost monster in reach, free — a cast
        that counts the verb, for the relics that read it."""
        t.timer += dt
        if t.timer < IDOL_EVERY[t.level]:
            return
        ix, iy = t.tile[0] + 0.5, t.tile[1] + 0.5
        radius = t.levels[t.level].range
        best: Monster | None = None
        for m in self.monsters:
            if m.hp <= 0:
                continue
            x, y = self.position(m)
            dx, dy = x - ix, y - iy
            if dx * dx + dy * dy <= radius * radius \
                    and (best is None or self.remaining(m) < self.remaining(best)):
                best = m
        if best is None:
            return
        t.timer -= IDOL_EVERY[t.level]
        self._emit("smite", best.id, self.position(best))
        self._hurt(best, felt_hit(SPELLS["smite"].damage * self.power(), None, best.kind), None, spell=True)
        self.spells_cast += 1
        self._relic("cast", 0.0)
        self._bury()   # what it killed must not walk on into the rest of this step

    def _well(self, t: Tower, dt: float) -> None:
        """The well's watering: every so often it gives a charge to the attuned neighbour with the fewest,
        if one holds less than full."""
        t.timer += dt
        if t.timer < WELL_EVERY[t.level]:
            return
        ix, iy = t.tile[0] + 0.5, t.tile[1] + 0.5
        radius = t.levels[t.level].range
        best: Tower | None = None
        for o in self.towers.values():
            if o.id == t.id or not o.attuned or o.charges >= CHARGES_MAX:
                continue
            dx, dy = o.tile[0] + 0.5 - ix, o.tile[1] + 0.5 - iy
            if dx * dx + dy * dy <= radius * radius and (best is None or o.charges < best.charges
                                                         or (o.charges == best.charges and o.id < best.id)):
                best = o
        if best is None:
            return
        t.timer -= WELL_EVERY[t.level]
        best.charges = min(CHARGES_MAX, best.charges + 1.0)
        self._emit("charge_given", t.id, best.id)
        self._relic("charge")

    def _immolate(self, t: Tower) -> None:
        """A censer's answer to a leak in its reach: every monster near it burns. Once a wave (the timer
        keeps the wave it answered, one-based: never answered is 0); the dead are buried at the step's end,
        with the other fallen."""
        if t.silenced or t.timer == float(self.wave) + 1.0:
            return
        t.timer = float(self.wave) + 1.0
        cx, cy = t.tile[0] + 0.5, t.tile[1] + 0.5
        radius = t.levels[t.level].range
        hurt = CENSER_HURT[t.level]
        for m in self.monsters:
            if m.hp <= 0 or (m.s >= self.level.route(m.route).length and m.kind.boss is None):
                continue   # the already leaked earn no bounty by burning; a striking boss still burns
            x, y = self.position(m)
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                self._hurt(m, felt_hit(hurt, None, m.kind), None)
        self._emit("immolated", t.id)

    def _censers(self, m: Monster) -> None:
        """A leak at the shrine: every censer whose reach holds it answers."""
        x, y = self.position(m)
        for t in self.towers.values():
            if t.kind.key != "censer":
                continue
            cx, cy = t.tile[0] + 0.5, t.tile[1] + 0.5
            radius = t.levels[t.level].range
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                self._immolate(t)

    def _altar(self, t: Tower, stats: TowerLevel, spans: tuple[tuple[float, float], ...], near: float,
               reach: float) -> None:
        """An altar's pulse: amplify the thickest knot of monsters in reach.

        Among the monsters in reach that are not amplified, the centre whose circle of the knot
        radius holds the most of their life (ties: nearest the sanctuary) lends its circle every
        monster in it — flyers too — the bonus for the lasting. It does not stack."""
        monsters = self.monsters
        level = self.level
        single_route = len(level.routes) == 1
        cand: list[Monster] = []
        for m in monsters:
            if single_route and m.s < near:
                break
            if m.hp > 0 and m.amplified <= 0 and self._tower_covers(t, m, spans, reach):
                cand.append(m)
        if not cand:
            t.cooldown = 0.0   # no monster in reach: no cast, the timer waits
            return
        knot = stats.splash
        knot2 = knot * knot
        centres: list[tuple[Monster, float, float]] = []
        for m in cand:
            x, y = self.position(m)
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
            elif total > best_life or (total == best_life and self.remaining(c) < self.remaining(best_c)):
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
            x, y = self.position(m)
            dx, dy = x - best_x, y - best_y
            if dx * dx + dy * dy <= knot2 + 1e-9:
                if m.amplified <= 0 or m.amplify < bonus:   # a lapsed amplification takes the new one as it is
                    m.amplify = bonus
                if m.amplified < lasting:
                    m.amplified = lasting
                hit.append(m.id)
        rate = stats.rate * (t.rate_mult() if t.curses or t.hymn > 0 else 1.0) * self._fervor()
        t.cooldown += 1.0 / rate
        self._emit("amplify", t.id, (best_x, best_y), tuple(hit))

    def _towers(self, dt: float) -> None:
        monsters = self.monsters
        if not monsters:
            for t in self.towers.values():
                t.cooldown = max(0.0, t.cooldown - dt)
                if t.attuned and t.charges < CHARGES_MAX:
                    t.charges = min(CHARGES_MAX, t.charges + dt / CHARGE_EVERY)
            return
        level = self.level
        single_route = len(level.routes) == 1
        static = self.perks.static_field
        for t in self.towers.values():
            if t.attuned and t.charges < CHARGES_MAX:
                t.charges = min(CHARGES_MAX, t.charges + dt / CHARGE_EVERY)
            if t.cooldown > 0:
                t.cooldown -= dt
                if t.cooldown > 0:
                    continue
            if t.curses and t.silenced:
                t.cooldown = 0.0
                continue
            attack = t.kind.attack
            if attack == "aura":   # support never attacks; its timer waits while silenced (above)
                if t.kind.key == "idol":
                    self._idol(t, dt)
                elif t.kind.key == "well":
                    self._well(t, dt)
                elif t.kind.key == "grove":
                    self._twister(t, dt)
                t.cooldown = 0.0
                continue
            stats = t.levels[t.level]
            reach = self.striking_reach(t)
            if reach != t.spans_reach:
                t.spans, t.spans_reach = level.coverage(t.tile, reach), reach
            spans = t.spans
            if not spans and single_route:
                t.cooldown = 0.0
                continue
            # On a single route, the ordered monsters can stop the scan before the first covered interval.
            near = spans[0][0] if spans else 0.0
            if attack == "amplify":
                self._altar(t, stats, spans, near, reach)
                continue
            if attack == "nova":
                hit = []
                for m in monsters:
                    if single_route and m.s < near:
                        break
                    if m.hp > 0 and self._tower_covers(t, m, spans, reach):
                        hit.append(m)
            elif attack == "venom":   # the strongest in reach
                best = None
                for m in monsters:
                    if single_route and m.s < near:
                        break
                    if m.hp > 0 and (best is None or m.hp > best.hp) and self._tower_covers(t, m, spans, reach):
                        best = m
                hit = [best] if best is not None else []
            elif attack == "hook":
                hooked = self._hook_target(t, spans, reach, near, single_route)
                hit = [hooked] if hooked is not None else []
            elif t.kind.key == "knife":   # a standing small monster first, else the foremost
                hit = []
                for m in monsters:
                    if single_route and m.s < near:
                        break
                    if m.hp > 0 and self._tower_covers(t, m, spans, reach):
                        if _standing(m):
                            hit = [m]
                            break
                        if not hit:
                            hit = [m]
            else:
                picked = self._pick(t, monsters, spans, reach, near, single_route, static, attack)
                hit = [picked] if picked is not None else []
            if not hit:
                t.cooldown = 0.0
                continue
            aura = self.aura_mult(t)
            damage = stats.damage * (t.damage_mult() if t.curses else 1.0)   # the hit; the aura is a factor
            if attack in ("bolt", "chain", "venom") and t.attuned and t.charges >= 1.0 \
                    and self.time - t.charged_at >= CHARGED_COOLDOWN \
                    and (not self.foresight or self._worth_charge(t, hit[0], damage * aura)):
                if hit[0].hp <= damage * aura:
                    self.wasted_charges += 1   # the plain shot would have killed with it
                damage *= EMPOWER
                t.charges -= 1.0
                t.charged_at = self.time
                self._emit("spent", t.id, hit[0].id)
                self._relic("charge")
            rate = stats.rate * (t.rate_mult() if t.curses or t.hymn > 0 else 1.0) * self._fervor()
            t.cooldown += 1.0 / rate
            if attack == "nova":
                self._emit("nova", t.id)
                for m in hit:
                    chill = stats.chill * m.kind.taken(Element.COLD)   # the slow follows the cold's factor
                    if chill > 0.0:
                        if chill >= m.chill or m.chill_left <= 0:
                            m.chill = chill
                        m.chill_left = max(m.chill_left, stats.chill_time)
                    self._strike(m, damage, t.kind.element, aura)
            elif attack == "chain":
                self._chain(t, hit[0], damage, aura, stats.chains)
            elif attack == "hook":
                self._hook(t, hit[0], damage, aura)
            else:
                target = hit[0]
                origin = t.centre
                last = self.position(target)
                distance = _hypot(last[0] - origin[0], last[1] - origin[1])
                bolt = Bolt(self._id(), t.id, t.kind.key, target.id, distance / t.kind.bolt_speed, damage, t.kind.element,
                            stats.splash, stats.poison * aura, stats.poison_time, origin, last, stats.chill, stats.chill_time,
                            stats.leader_bonus, aura)
                self.bolts.append(bolt)
                self._emit("bolt", bolt)

    def _pick(self, t: Tower, monsters: list[Monster], spans: tuple[tuple[float, float], ...], reach: float,
              near: float, single_route: bool, static: bool, attack: str) -> Monster | None:
        """The default choice of one target: foremost, unless the tower's strategy says otherwise. Ties
        go foremost; a taught tower scans all it covers, since the answer may stand anywhere in reach."""
        if t.mode == "first" and not (static and attack == "chain"):
            for m in monsters:
                if single_route and m.s < near:
                    break
                if m.hp > 0 and self._tower_covers(t, m, spans, reach):
                    return m
            return None
        best: Monster | None = None
        for m in monsters:
            if m.hp <= 0 or not self._tower_covers(t, m, spans, reach):
                continue
            if best is None:
                best = m
            elif t.mode == "strong" and m.hp > best.hp:
                best = m
            elif t.mode == "weak" and m.hp < best.hp:
                best = m
            elif t.mode == "fast" and m.speed > best.speed:
                best = m
            elif t.mode == "last":
                best = m   # nearest the sanctuary first: the last covered stands nearest the portal
            elif static and attack == "chain" and m.kind.leader is not None and best.kind.leader is None:
                best = m   # Static Field: a leader in reach draws the first strike
        return best

    def set_mode(self, tower_id: int, mode: str) -> None:
        """Teach a tower its strategy; an unknown one is refused."""
        if mode not in MODES:
            raise Refused(f"No strategy {mode!r} is taught.")
        tower = self.towers[tower_id]
        if tower.mode == mode:
            return
        tower.mode = mode
        self._emit("mode", tower.id, mode)

    def attune(self, tower_id: int) -> None:
        """Attune a tower: it holds charges for empowered shots, starting full."""
        tower = self.towers[tower_id]
        if tower.kind.attack not in ATTUNABLE:
            raise Refused(f"{tower.kind.name} never spends charges: attunement would idle.")
        if tower.attuned:
            raise Refused(f"{tower.kind.name} is already attuned.")
        if self.gold < ATTUNE_GOLD:
            raise Refused(f"Attunement costs {ATTUNE_GOLD} gold.")
        self.gold -= ATTUNE_GOLD
        tower.attuned = True
        tower.charges = CHARGES_MAX
        tower.spent += ATTUNE_GOLD
        self._emit("attuned", tower.id)

    def _worth_charge(self, t: Tower, target: Monster, damage: float) -> bool:
        """Whether the empowered shot is worth its charge: everything but the obvious waste. A kill a
        plain shot takes is held for the next target; a full tower cannot draw, so it spends even then.
        What is left spends, even what plain fire would fell in time: killing faster frees the tower for
        the queue behind, and a spent charge draws its replacement."""
        return target.hp > damage or t.charges >= CHARGES_MAX

    def _hook_target(self, t: Tower, spans: tuple[tuple[float, float], ...], reach: float, near: float,
                     single_route: bool) -> Monster | None:
        """The foremost small monster in reach at least HOOK_PAST beyond its route's spot (the route's point nearest the
        hook), not at a gate and never hooked before."""
        level = self.level
        for m in self.monsters:
            if single_route and m.s < near:
                break
            if (m.hp > 0 and m.door < 0 and not m.moved & HOOK and m.kind.small
                    and m.s >= level.nearest(m.route, t.tile) + HOOK_PAST and self._tower_covers(t, m, spans, reach)):
                return m
        return None

    def _hook(self, t: Tower, m: Monster, damage: float, aura: float) -> None:
        """The pull: HOOK_PULL tiles (times Weaken's damage share) back toward the hook's spot, never past it; a walker
        pulled into a standing gate's arch stops at its queue. Then the hit."""
        level = self.level
        spot = level.nearest(m.route, t.tile)
        pull = HOOK_PULL * (t.damage_mult() if t.curses else 1.0)
        to = max(spot, m.s - pull)
        if not m.kind.flying:
            for door_index, crossing in level.crossings(m.route):
                stop = crossing - DOOR_STOP - m.jostle
                if self.doors[door_index].built and stop < to <= crossing:
                    to = stop
        before = m.s
        m.s = to
        m.moved |= HOOK
        self._emit("hook", t.id, m.id, before, to)
        _furthest_first(self.monsters, level)
        self._strike(m, damage, t.kind.element, aura)

    def _chain(self, tower: Tower, first: Monster, damage: float, aura: float, jumps: int) -> None:
        static = self.perks.static_field
        struck = [first]
        struck_ids = {first.id}
        where = [self.position(first)]
        current, pos = first, where[0]
        for _ in range(jumps):
            best, best_d, best_leader = None, CHAIN_JUMP, False
            for m in self.monsters:
                if m.hp <= 0 or m.id in struck_ids:
                    continue
                if m.route == current.route and abs(m.s - current.s) > CHAIN_JUMP * 4:
                    continue
                x, y = self.position(m)
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
            pos = self.position(best)
            where.append(pos)
            current = best
        self._emit("chain", tower.id, [m.id for m in struck], where)
        keeps = self.perks.leap_keeps
        for i, m in enumerate(struck):
            self._strike(m, damage, Element.LIGHTNING, aura * keeps ** i)

    def _bolts(self, dt: float) -> None:
        if not self.bolts:
            return
        flying = []
        for b in self.bolts:
            target = self.monster(b.target)
            if target is not None and target.hp <= 0:
                target = None
            last = self.position(target) if target is not None else b.last
            left = b.left - dt
            if left > 0:
                flying.append(Bolt(b.id, b.tower, b.kind, b.target, left, b.damage, b.element, b.splash, b.poison,
                                   b.poison_time, b.origin, last, b.chill, b.chill_time, b.leader_bonus, b.factor))
                continue
            struck: list[Monster] = []
            if b.splash > 0:
                struck = self._around(last[0], last[1], b.splash, flyers=True)
                if self.perks.blaze and b.kind == "pyre":
                    self.hazards.append(Hazard(last[0], last[1], b.splash, b.damage * b.factor / 3.0, BLAZE_TIME))
            elif target is not None:
                struck.append(target)
            self._emit("impact", b, last, [m.id for m in struck])
            for m in struck:
                if b.poison > 0:
                    self._poison(m, b.poison, b.poison_time)
                if b.chill > 0:
                    chill = b.chill * m.kind.taken(Element.COLD)
                    if chill >= m.chill or m.chill_left <= 0:
                        m.chill = chill
                    m.chill_left = max(m.chill_left, b.chill_time)
                factor = b.factor
                if m is not target and b.splash > 0:
                    factor *= SPLASH_SHARE   # a splash's lesser blow
                elif b.kind == "knife" and _standing(m):
                    factor *= KNIFE_STANDING
                hit = b.damage
                if m.kind.leader is not None:
                    hit *= 1.0 + b.leader_bonus   # a forged pattern's hit on a leader, before the factors
                self._strike(m, hit, b.element, factor)
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
                self._strike(m, mt.damage, Element.FIRE, spell=True)
            self.hazards.append(Hazard(mt.x, mt.y, BURN_RADIUS, mt.burn, spec.lasting, spell=True))

    def _poison(self, m: Monster, dps: float, seconds: float) -> None:
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
            if total > 0:   # felt while the venom is still in it: Lower Resist reads that
                self._wither(m, total, Element.POISON)
            m.poison = [stack for stack in m.poison if stack[1] > 0]
        if self.hazards:
            for h in self.hazards:
                for m in self._around(h.x, h.y, h.radius, flyers=False):
                    self._wither(m, h.dps * min(dt, h.left), Element.FIRE, spell=h.spell)
                h.left -= dt
            self.hazards = [h for h in self.hazards if h.left > 0]
        for m in self.monsters:
            if m.amplified > 0:
                m.amplified = max(0.0, m.amplified - dt)
        if any(m.hp <= 0 for m in self.monsters):
            self._bury()

    def _exposed(self, m: Monster) -> bool:
        """Lower Resist: a poisoned monster is protected against nothing."""
        return self.perks.lower_resist and bool(m.poison)

    def taken(self, m: Monster, element: Element | None) -> float:
        """The element's factor on a blow to this monster, Lower Resist included; holy damage (None) takes none."""
        if element is None:
            return 1.0
        return m.kind.taken(element, self._exposed(m))

    def _strike(self, m: Monster, hit: float, element: Element, factor: float = 1.0,
                  *, spell: bool = False) -> None:
        """A hit, through the damage pipeline (:func:`~hellward.sim.content.felt_hit`): ``factor`` and the
        monster's amplification join the element's factor."""
        if m.hp <= 0:
            return
        if m.amplified > 0:
            factor *= 1.0 + m.amplify
        self._hurt(m, felt_hit(hit, element, m.kind, factor, exposed=self._exposed(m)), element, spell=spell)

    def _wither(self, m: Monster, amount: float, element: Element, *, spell: bool = False) -> None:
        """Damage over time: the element's factor and the amplification, no armor, no rounding."""
        if m.hp <= 0:
            return
        factor = 1.0 + m.amplify if m.amplified > 0 else 1.0
        self._hurt(m, felt_over_time(amount, element, m.kind, factor, exposed=self._exposed(m)), element,
                   quiet=True, spell=spell)

    def _hurt(self, m: Monster, amount: float, element: Element | None, *, quiet: bool = False, bursts: bool = True,
              spell: bool = False) -> None:
        """Damage as it is felt (the pipeline's, or holy damage's whole amount)."""
        if m.hp <= 0:
            return
        m.hp -= amount
        if not quiet:
            self._emit("hit", m.id, element)
        if m.hp <= 0:
            self._died(m, element, bursts, spell)

    def _died(self, m: Monster, element: Element | None, bursts: bool, spell: bool) -> None:
        # A monster its kind's shaman stands near rises once, unless a burst tore it apart: one killed it (bursts is
        # False), or its own death bursts (Shatter, Corpse Explosion), which leaves nothing to raise
        bursting = bursts and ((self.perks.shatter and m.chill_left > 0) or (self.perks.corpse_explosion and m.amplified > 0))
        if bursts and not bursting and not m.risen and m.kind.leader is None:
            raise_kind = m.kind.key
            for leader in self.monsters:
                if leader.hp > 0 and leader.kind.leader is not None:
                    spec = leader.kind.leader
                    if spec.raises == raise_kind:
                        lx, ly = self.position(leader)
                        mx, my = self.position(m)
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

        self.gold += m.bounty
        self.kills += 1
        if spell:
            self.spell_kills += 1
        if not m.bonus:   # a bonus kill pays no bounty and no XP: the clean clear pays instead
            self._earn(kill_xp(m.max_hp))
        where = self.position(m)
        self._emit("death", m.id, m.kind.key, element, where, m.bounty)
        if m.salvage:
            self.salvage_held += m.salvage
            self._emit("salvage", m.id, where, m.salvage)
        amplified = m.amplified > 0
        if amplified and self.perks.life_tap:
            self.mana = min(self.mana_max, self.mana + m.bounty / 5)
        if m.kind.leader is not None and self.perks.soul_harvest:
            self.mana = min(self.mana_max, self.mana + SOUL)
        if self.perks.contagion and m.poison:
            self._spread(m, where)
        if bursts and self.perks.shatter and m.chill_left > 0:
            around = [o for o in self._around(where[0], where[1], SHATTER_RADIUS, flyers=True) if o is not m]
            self._emit("shatter", m.id, where)
            for o in around:   # a death burst takes no factor and no armor; a monster it kills does not burst in turn
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
            if o is m or o.hp <= 0:
                continue
            x, y = self.position(o)
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
        if m.bonus and self.bonus is not None:
            self.bonus.alive -= 1
        if m.breach:
            self.breach_remaining -= 1
            if m.hp > 0:
                self.breach_failed = True
            if self.breach_remaining == 0:
                if self.breach_failed:
                    self._emit("breach_failed")
                else:
                    self.breach_cleared = True
                    self._emit("breach_cleared", self.breach_mode)
                    if self.breach_mode == "cash":
                        cache = BALANCE.breach_cache()
                        self.gold += cache
                        self._emit("breach_cash", cache)

    def _curses(self, dt: float) -> None:
        if any(m.hp <= 0 for m in self.monsters):
            self._bury()
        for t in self.towers.values():
            if t.hymn > 0:   # whole steps: a hymn of 6 s lasts 120 of them
                t.hymn = t.hymn - dt if t.hymn - dt > 1e-9 else 0.0
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
                self._earn(clear_xp(w + 1))
                for cell in sorted(self.blighted):   # a cleared wave lifts every taken cell one wave nearer open
                    left, past = self.blighted[cell]
                    if left - 1 <= 0:
                        del self.blighted[cell]
                        self._emit("blight_clear", cell)
                    else:
                        self.blighted[cell] = (left - 1, past)
                for d in self.doors:
                    if d.built:
                        d.hp += (self.gate_life - d.hp) * self.perks.gate_mend
                self._emit("cleared", w, bonus)
        pack = self.bonus
        if pack is not None and pack.alive == 0:
            self.bonus = None
            if pack.leaked:
                self.lives -= pack.fail   # the ravage, over whatever the pack leaked
                self._emit("bonus", pack.stake, "failed")
            else:
                self.gold += pack.wager + pack.profit
                self._earn(pack.xp)
                self._emit("bonus", pack.stake, "cleared")
            if self.outcome is None:
                self.break_left = pack.saved_break
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


def _furthest_first(monsters: list[Monster], level: Level) -> None:
    """Sort by remaining route distance, nearest the sanctuary first, keeping equal order."""
    for i in range(1, len(monsters)):
        m = monsters[i]
        remaining = level.route(m.route).length - m.s
        j = i - 1
        while j >= 0 and level.route(monsters[j].route).length - monsters[j].s > remaining:
            monsters[j + 1] = monsters[j]
            j -= 1
        monsters[j + 1] = m


def _standing(m: Monster) -> bool:
    """A small monster standing still for a knife: battering a gate, or held (frozen)."""
    return m.kind.small and (m.door >= 0 or m.frozen > 0)


def _inside(s: float, spans: tuple[tuple[float, float], ...]) -> bool:
    for a, b in spans:
        if a <= s <= b:
            return True
    return False

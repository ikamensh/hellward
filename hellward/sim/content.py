"""Every monster, leader, curse, tower and wave, as tables.

Distances are in tiles, times in seconds, damage and life in hit points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.sums import half_up


class Element(str, Enum):
    PHYSICAL = "physical"
    FIRE = "fire"
    LIGHTNING = "lightning"
    COLD = "cold"
    POISON = "poison"
    BONE = "bone"
    NATURE = "nature"


class Curse(str, Enum):
    WEAKEN = "weaken"
    DECREPIFY = "decrepify"
    DIM_VISION = "dim_vision"
    BONE_PRISON = "bone_prison"


@dataclass(frozen=True)
class CurseSpec:
    name: str
    duration: float
    radius: float = 1.5
    damage: float = 1.0   # multiplies the tower's damage
    rate: float = 1.0     # multiplies its attacks per second
    range: float = 1.0    # multiplies its reach
    silenced: bool = False
    blurb: str = ""


CURSES: Final[dict[Curse, CurseSpec]] = {
    Curse(key): CurseSpec(row["name"], float(row["duration"]), radius=float(row["radius"]), damage=float(row["damage"]),
                          rate=float(row["rate"]), range=float(row["range"]), silenced=bool(row["silenced"]),
                          blurb=row["blurb"])
    for key, row in tuning.table("curses").items()
}


@dataclass(frozen=True)
class LeaderSpec:
    curses: tuple[Curse, ...]
    cast_range: float = 4.5
    cooldown: float = 9.0
    channel: float = 1.0      # the visible incantation between the choice and the curse landing
    first_cast: float = 3.0   # seconds after it appears before it may first choose
    widen: float = 0.0        # added to every radius it casts
    raises: str = ""          # the monster kind it raises
    raise_reach: float = 3.0  # tile-centre distance within which it raises
    mark: float = 0.0         # seconds a marked curse burns on its spot before it lands; 0 = chanted as today
    burn: float = 0.0         # mana burned per tower the curse catches


@dataclass(frozen=True)
class BlightSpec:
    verb: str                 # what it does to the cell: "web", "desecrate"
    past: str = "blighted"    # what the cell is then called
    reach: float = 4.0        # tile-centre distance within which it takes an empty cell
    delay: float = 6.0        # seconds after it appears before it marks, once a wave
    telegraph: float = 2.0    # the visible mark between the choice and the cell taken (R6: at least 1.5)
    waves: int = 2            # cleared waves the cell stays taken


PROTECTED: Final = tuning.number("battle.protected")
VULNERABLE: Final = tuning.number("battle.vulnerable")
FACTOR_CAP: Final = tuning.number("battle.factor_cap")
BOSS_STRIKE_LIVES: Final = tuning.integer("battle.boss_strike_lives")
_EDGE: Final = 1e-9   # a product that is a whole number but for the last bit rounds as that whole number


@dataclass(frozen=True)
class MonsterKind:
    key: str
    name: str
    hp: float
    speed: float
    bounty: int
    lives: int = 1            # what one strike at the shrine costs: battle.boss_strike_lives for a boss
    door_dps: float = 1.0
    protected: tuple[Element, ...] = ()
    vulnerable: tuple[Element, ...] = ()
    armor: int = 0            # taken off every hit
    boss: bool = False        # struck back to its portal from the shrine instead of obliterated
    flying: bool = False
    leader: LeaderSpec | None = None
    blight: BlightSpec | None = None
    size: float = 0.6        # drawn height in tiles, for the view and the hit radius
    movement: str = "direct"  # "wander" takes a seeded detour; "direct" runs the shortest route

    def __post_init__(self) -> None:
        if self.movement not in ("direct", "wander"):
            raise ValueError(f"{self.key}: unknown movement {self.movement!r}")
        tags = (*self.protected, *self.vulnerable)
        if len(set(tags)) != len(tags):
            raise ValueError(f"{self.key}: an element is tagged twice")
        if len(tags) > 2 and not self.boss:
            raise ValueError(f"{self.key}: at most two element tags, unless a boss")
        if Element.PHYSICAL in tags:
            raise ValueError(f"{self.key}: physical is never tagged: armor is what physical fears")
        if self.armor < 0:
            raise ValueError(f"{self.key}: negative armor")

    def taken(self, element: Element, exposed: bool = False) -> float:
        """The element's factor on a hit: protected, vulnerable, or whole. An exposed monster (poisoned, under
        Lower Resist) is protected against nothing."""
        if element in self.vulnerable:
            return VULNERABLE
        if element in self.protected and not exposed:
            return PROTECTED
        return 1.0

    @property
    def small(self) -> bool:
        """A monster the movers move: it costs one life and is neither a boss nor a leader."""
        return self.lives == 1 and not self.boss and self.leader is None


def felt_hit(hit: float, element: Element | None, kind: MonsterKind, factor: float = 1.0, *,
             exposed: bool = False) -> int:
    """The damage a hit deals a monster of this kind: the element's factor times ``factor`` (every other factor:
    amplification, aura, a knife on a standing monster, a leap's decay, a splash's share), capped at
    battle.factor_cap; the hit rounded to a whole number, up when the capped product is above 1, down when below,
    half up when it is 1; less the kind's armor; at least 1. Holy damage (``element`` None) takes no factor and no
    armor. Every hit in the rules, the planner's estimate and the server's hover table come through here."""
    if element is None:
        return max(1, math.floor(hit + 0.5 + _EDGE))
    product = factor * kind.taken(element, exposed)
    if product > FACTOR_CAP:
        product = FACTOR_CAP
    value = hit * product
    if product > 1.0:
        whole = math.ceil(value - _EDGE)
    elif product < 1.0:
        whole = math.floor(value + _EDGE)
    else:
        whole = math.floor(value + 0.5 + _EDGE)
    return max(1, whole - kind.armor)


def felt_over_time(amount: float, element: Element, kind: MonsterKind, factor: float = 1.0, *,
                   exposed: bool = False) -> float:
    """Damage over time (venom, the burning floor): the element's factor and ``factor`` (amplification), capped as a
    hit's are, with no armor and no rounding."""
    product = factor * kind.taken(element, exposed)
    if product > FACTOR_CAP:
        product = FACTOR_CAP
    return amount * product


def _leader(row: dict[str, Any]) -> LeaderSpec:
    spec = dict(tuning.table("battle.leader_defaults"))
    for key, value in row.items():
        if key not in spec and key != "curses":
            raise KeyError(f"unknown leader value {key}")
        spec[key] = value
    return LeaderSpec(tuple(Curse(c) for c in spec["curses"]), cast_range=float(spec["cast_range"]),
                      cooldown=float(spec["cooldown"]), channel=float(spec["channel"]),
                      first_cast=float(spec["first_cast"]), widen=float(spec["widen"]), raises=spec["raises"],
                      raise_reach=float(spec["raise_reach"]), mark=float(spec["mark"]), burn=float(spec["burn"]))


def _blight(row: dict[str, Any]) -> BlightSpec:
    spec = dict(tuning.table("battle.blight_defaults"))
    for key, value in row.items():
        if key not in spec:
            raise KeyError(f"unknown blight value {key}")
        spec[key] = value
    return BlightSpec(verb=str(spec["verb"]), past=str(spec["past"]), reach=float(spec["reach"]),
                      delay=float(spec["delay"]), telegraph=float(spec["telegraph"]), waves=int(spec["waves"]))


def _monster(key: str, row: dict[str, Any]) -> MonsterKind:
    leader = row.get("leader")
    blight = row.get("blight")
    boss = bool(row["boss"])
    if boss == ("lives" in row):
        raise ValueError(f"{key}: a boss's strike costs battle.boss_strike_lives, any other monster its own lives")
    return MonsterKind(key, row["name"], hp=half_up(float(row["life"])), speed=float(row["speed"]),
                       bounty=int(row["bounty"]), lives=BOSS_STRIKE_LIVES if boss else int(row["lives"]),
                       door_dps=float(row["door_dps"]),
                       protected=tuple(Element(e) for e in row["protected"]),
                       vulnerable=tuple(Element(e) for e in row["vulnerable"]), armor=int(row["armor"]), boss=boss,
                       flying=bool(row["flying"]), leader=None if leader is None else _leader(leader),
                       blight=None if blight is None else _blight(blight),
                       size=float(row["size"]), movement=row["movement"])


MONSTERS: Final[dict[str, MonsterKind]] = {key: _monster(key, row) for key, row in tuning.table("monsters").items()}


@dataclass(frozen=True)
class TowerLevel:
    cost: int
    damage: float
    rate: float           # attacks per second
    range: float
    splash: float = 0.0   # radius of a fire bolt's blast
    chains: int = 0       # extra monsters a lightning bolt jumps to
    chill: float = 0.0    # slow a frost nova applies (0.4 = 40% slower, and 40% weaker blows on doors)
    chill_time: float = 0.0
    poison: float = 0.0   # damage per second of one venom stack
    poison_time: float = 0.0
    lasting: float = 0.0  # seconds an amplification lasts
    leader_bonus: float = 0.0   # equipped pattern's extra damage share against a leader


@dataclass(frozen=True)
class TowerKind:
    key: str
    name: str
    element: Element
    attack: str           # "bolt", "chain", "nova", "venom", "hook", "amplify" or "aura"
    levels: tuple[TowerLevel, ...]
    blurb: str
    bolt_speed: float = 9.0   # tiles per second; a nova and a chain strike at once


def _ranks(row: dict[str, Any], name: str) -> tuple[float, ...]:
    values = row.get(name)
    if values is None:
        return (0.0, 0.0, 0.0)
    if len(values) != 3:
        raise ValueError(f"{name} needs one value per rank")
    return tuple(float(v) for v in values)


def _tower(key: str, row: dict[str, Any]) -> TowerKind:
    price = float(row["price"])
    if "damage_role" in row:
        damage: tuple[float, ...] = tuple(BALANCE.tower_damage(rank, float(row["damage_role"])) for rank in range(3))
    else:
        damage = _ranks(row, "damage")
    poison: tuple[float, ...] = (tuple(BALANCE.tower_damage(rank, float(row["poison_role"])) for rank in range(3))
                                 if "poison_role" in row else _ranks(row, "poison"))
    rate, reach, splash = _ranks(row, "rate"), _ranks(row, "range"), _ranks(row, "splash")
    chill, chill_time, poison_time, lasting = (_ranks(row, "chill"), _ranks(row, "chill_time"),
                                               _ranks(row, "poison_time"), _ranks(row, "lasting"))
    rank_units = row.get("rank_cost_units")
    units = None if rank_units is None else (float(rank_units[0]), float(rank_units[1]), float(rank_units[2]))
    levels = tuple(TowerLevel(BALANCE.tower_cost(rank, price, units), damage[rank], rate[rank], reach[rank],
                              splash=splash[rank], chill=chill[rank], chill_time=chill_time[rank], poison=poison[rank],
                              poison_time=poison_time[rank], lasting=lasting[rank])
                   for rank in range(3))
    return TowerKind(key, row["name"], Element(row["element"]), row["attack"], levels, row["blurb"],
                     bolt_speed=float(row["bolt_speed"]))


TOWERS: Final[dict[str, TowerKind]] = {key: _tower(key, row) for key, row in tuning.table("towers").items()}

MAX_POISON_STACKS: Final = tuning.integer("battle.max_poison_stacks")
SELL_REFUND: Final = tuning.number("battle.sell_refund")


@dataclass(frozen=True)
class DoorSpec:
    cost: int
    hp: float
    repair: float          # share of its missing life a standing door regains when a wave is cleared


DOOR: Final = DoorSpec(BALANCE.tower_cost(0, tuning.number("battle.gate.cost_units")),
                       tuning.number("battle.gate.life"), tuning.number("battle.gate.repair"))


@dataclass(frozen=True)
class Group:
    kind: str
    count: int
    interval: float
    start: float = 0.0     # seconds after the wave begins
    route: str = "main"    # entrance/route named by the level; the default follows its ordinary entrance


@dataclass(frozen=True)
class Wave:
    groups: tuple[Group, ...]
    bonus: int              # gold for clearing it


@dataclass(frozen=True)
class SpellSpec:
    key: str
    name: str
    mana: float
    aim: str              # what a click chooses: "tower", "monster" or "floor"
    blurb: str
    damage: float = 0.0   # absolute: against the monsters' own life, everywhere the same
    radius: float = 0.0
    delay: float = 0.0    # seconds between the cast and the strike
    lasting: float = 0.0  # seconds the ground burns, or the monsters stay frozen
    burn: float = 0.0     # damage per second of the burning ground
    recharge: float = 0.0 # seconds after a cast before it can be cast again
    rate: float = 1.0     # multiplies the attacks per second of the tower it is aimed at, while it lasts


SPELLS: Final[dict[str, SpellSpec]] = {
    key: SpellSpec(key, row["name"], float(row["mana"]), row["aim"], row["blurb"],
                   damage=BALANCE.arrow_hit * float(row["damage_hits"]), radius=float(row["radius"]),
                   delay=float(row["delay"]), lasting=float(row["lasting"]), burn=BALANCE.arrow_hit * float(row["burn_hits"]),
                   recharge=float(row["recharge"]), rate=float(row["rate"]))
    for key, row in tuning.table("spells").items()
}

START_LIVES: Final = tuning.integer("battle.start_lives")
MANA_MAX: Final = tuning.number("battle.mana_max")
MANA_START: Final = tuning.number("battle.mana_start")
MANA_REGEN: Final = tuning.number("battle.mana_regen")
WAVE_BREAK: Final = tuning.number("battle.wave_break")
EARLY_CALL_GOLD: Final = BALANCE.base_gold_unit / tuning.number("battle.early_call_seconds_per_unit")
BURN_RADIUS: Final = tuning.number("battle.skills.burn_radius")
SHATTER_RADIUS: Final = tuning.number("battle.skills.shatter_radius")
SHATTER_SHARE: Final = tuning.number("battle.skills.shatter_share")
CONTAGION_REACH: Final = tuning.number("battle.skills.contagion_reach")
THORNS: Final = tuning.number("battle.skills.thorns")
SOUL: Final = tuning.number("battle.skills.soul")
CORPSE_SHARE: Final = tuning.number("battle.skills.corpse_share")
CORPSE_RADIUS: Final = tuning.number("battle.skills.corpse_radius")
HURRICANE_RADIUS: Final = tuning.number("battle.skills.hurricane_radius")
HURRICANE_SLOW: Final = tuning.number("battle.skills.hurricane_slow")
TWISTER_PERIOD: Final = tuning.number("battle.skills.twister_period")
TWISTER_RADIUS: Final = tuning.number("battle.skills.twister_radius")
TWISTER_HELD: Final = tuning.number("battle.skills.twister_held")

"""Every monster, leader, curse, tower and wave, as tables.

Distances are in tiles, times in seconds, damage and life in hit points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from hellward.sim import tuning
from hellward.sim.balance import BALANCE


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
class MonsterKind:
    key: str
    name: str
    hp: float
    speed: float
    bounty: int
    lives: int = 1
    door_dps: float = 1.0
    resist: dict[Element, float] = field(default_factory=dict)  # 1.0 immune, negative a weakness
    flying: bool = False
    leader: LeaderSpec | None = None
    size: float = 0.6        # drawn height in tiles, for the view and the hit radius
    movement: str = "direct"  # "wander" takes a seeded detour; "direct" runs the shortest route

    def __post_init__(self) -> None:
        if self.movement not in ("direct", "wander"):
            raise ValueError(f"{self.key}: unknown movement {self.movement!r}")

    def taken(self, element: Element) -> float:
        return 1.0 - self.resist.get(element, 0.0)


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


def _monster(key: str, row: dict[str, Any]) -> MonsterKind:
    leader = row.get("leader")
    return MonsterKind(key, row["name"], hp=BALANCE.effective_hp(float(row["life"]), 0, 0), speed=float(row["speed"]),
                       bounty=int(row["bounty"]), lives=int(row["lives"]), door_dps=float(row["door_dps"]),
                       resist={Element(e): float(v) for e, v in row["resist"].items()}, flying=bool(row["flying"]),
                       leader=None if leader is None else _leader(leader), size=float(row["size"]),
                       movement=row["movement"])


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
    attack: str           # "bolt", "chain", "nova", "venom", "amplify" or "aura"
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
                                 if "poison_role" in row else (0.0, 0.0, 0.0))
    rate, reach, splash = _ranks(row, "rate"), _ranks(row, "range"), _ranks(row, "splash")
    chill, chill_time, poison_time, lasting = (_ranks(row, "chill"), _ranks(row, "chill_time"),
                                               _ranks(row, "poison_time"), _ranks(row, "lasting"))
    levels = tuple(TowerLevel(BALANCE.tower_cost(rank, price), damage[rank], rate[rank], reach[rank], splash=splash[rank],
                              chill=chill[rank], chill_time=chill_time[rank], poison=poison[rank],
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
                       BALANCE.base_hp * tuning.number("battle.gate.life_hp"), tuning.number("battle.gate.repair"))


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
    hp: float = 1.0         # every monster's life is multiplied by this


@dataclass(frozen=True)
class SpellSpec:
    key: str
    name: str
    mana: float
    aim: str              # what a click chooses: "tower", "monster" or "floor"
    blurb: str
    damage: float = 0.0   # at a wave life multiplier of 1; it grows with the monsters' life
    radius: float = 0.0
    delay: float = 0.0    # seconds between the cast and the strike
    lasting: float = 0.0  # seconds the ground burns, or the monsters stay frozen
    burn: float = 0.0     # damage per second of the burning ground
    recharge: float = 0.0 # seconds after a cast before it can be cast again


SPELLS: Final[dict[str, SpellSpec]] = {
    key: SpellSpec(key, row["name"], float(row["mana"]), row["aim"], row["blurb"],
                   damage=BALANCE.arrow_hit * float(row["damage_hits"]), radius=float(row["radius"]),
                   delay=float(row["delay"]), lasting=float(row["lasting"]), burn=BALANCE.arrow_hit * float(row["burn_hits"]),
                   recharge=float(row["recharge"]))
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
WARD: Final = tuning.number("battle.skills.ward")
CORPSE_SHARE: Final = tuning.number("battle.skills.corpse_share")
CORPSE_RADIUS: Final = tuning.number("battle.skills.corpse_radius")
HURRICANE_RADIUS: Final = tuning.number("battle.skills.hurricane_radius")
HURRICANE_SLOW: Final = tuning.number("battle.skills.hurricane_slow")
TWISTER_PERIOD: Final = tuning.number("battle.skills.twister_period")
TWISTER_RADIUS: Final = tuning.number("battle.skills.twister_radius")
TWISTER_HELD: Final = tuning.number("battle.skills.twister_held")

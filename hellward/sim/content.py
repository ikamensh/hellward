"""Every monster, leader, curse, tower and wave, as tables.

Distances are in tiles, times in seconds, damage and life in hit points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Element(str, Enum):
    FIRE = "fire"
    LIGHTNING = "lightning"
    COLD = "cold"
    POISON = "poison"


class Curse(str, Enum):
    WEAKEN = "weaken"
    DECREPIFY = "decrepify"
    DIM_VISION = "dim_vision"
    BONE_PRISON = "bone_prison"


@dataclass(frozen=True)
class CurseSpec:
    name: str
    duration: float
    damage: float = 1.0   # multiplies the tower's damage
    rate: float = 1.0     # multiplies its attacks per second
    range: float = 1.0    # multiplies its reach
    silenced: bool = False
    blurb: str = ""


CURSES: dict[Curse, CurseSpec] = {
    Curse.WEAKEN: CurseSpec("Weaken", 8.0, damage=0.35, blurb="deals a third of its damage"),
    Curse.DECREPIFY: CurseSpec("Decrepify", 8.0, rate=0.4, blurb="attacks at 40% speed"),
    Curse.DIM_VISION: CurseSpec("Dim Vision", 8.0, range=0.55, blurb="sees half as far"),
    Curse.BONE_PRISON: CurseSpec("Bone Prison", 4.5, silenced=True, blurb="caged: cannot attack"),
}


@dataclass(frozen=True)
class LeaderSpec:
    curses: tuple[Curse, ...]
    cast_range: float = 4.5
    cooldown: float = 9.0
    channel: float = 1.0      # the visible incantation between the choice and the curse landing
    first_cast: float = 3.0   # seconds after it appears before it may first choose


@dataclass(frozen=True)
class MonsterKind:
    key: str
    name: str
    hp: float
    speed: float
    bounty: int
    lives: int = 1
    door_dps: float = 8.0
    resist: dict[Element, float] = field(default_factory=dict)  # 1.0 immune, negative a weakness
    flying: bool = False
    leader: LeaderSpec | None = None
    size: float = 0.6        # drawn height in tiles, for the view and the hit radius

    def taken(self, element: Element) -> float:
        return 1.0 - self.resist.get(element, 0.0)


F, L, C, P = Element.FIRE, Element.LIGHTNING, Element.COLD, Element.POISON

MONSTERS: dict[str, MonsterKind] = {m.key: m for m in (
    MonsterKind("fallen", "Fallen", hp=48, speed=1.35, bounty=4, door_dps=7, size=0.55),
    MonsterKind("skeleton", "Skeleton", hp=95, speed=1.0, bounty=7, door_dps=11, resist={P: 1.0, C: 0.25}, size=0.75),
    MonsterKind("zombie", "Zombie", hp=240, speed=0.6, bounty=12, door_dps=20, resist={F: -0.5, P: 0.5}, size=0.8),
    MonsterKind("goatman", "Goatman", hp=140, speed=1.1, bounty=9, door_dps=15, resist={L: 0.5}, size=0.85),
    MonsterKind("gargoyle", "Gargoyle", hp=85, speed=1.5, bounty=10, resist={F: 0.5, C: 0.25}, flying=True, size=0.75),
    MonsterKind("overlord", "Overlord", hp=520, speed=0.65, bounty=28, lives=2, door_dps=65, resist={F: 0.25, C: 0.25}, size=1.05),
    MonsterKind("azazel", "Azazel the Flayer", hp=2600, speed=0.5, bounty=300, lives=10, door_dps=140,
                resist={F: 1.0, L: 0.25, C: 0.25, P: 0.25}, size=1.6),
    MonsterKind("shaman", "Fallen Shaman", hp=130, speed=1.0, bounty=30, lives=2, door_dps=4, resist={F: 0.25},
                leader=LeaderSpec((Curse.WEAKEN,)), size=0.65),
    MonsterKind("priest", "Bone Priest", hp=210, speed=0.9, bounty=40, lives=2, door_dps=6, resist={P: 1.0, C: 0.25},
                leader=LeaderSpec((Curse.BONE_PRISON, Curse.DIM_VISION), cooldown=10.0), size=0.85),
    MonsterKind("witch", "Blood Witch", hp=260, speed=0.95, bounty=45, lives=2, door_dps=6, resist={F: 0.25, L: 0.25},
                leader=LeaderSpec((Curse.DECREPIFY, Curse.WEAKEN), cooldown=8.5), size=0.85),
)}


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


@dataclass(frozen=True)
class TowerKind:
    key: str
    name: str
    element: Element
    attack: str           # "bolt", "chain", "nova" or "venom"
    levels: tuple[TowerLevel, ...]
    blurb: str
    bolt_speed: float = 9.0   # tiles per second; a nova and a chain strike at once


TOWERS: dict[str, TowerKind] = {t.key: t for t in (
    TowerKind("pyre", "Pyre", F, "bolt", (
        TowerLevel(70, 24, 1.0, 3.0),
        TowerLevel(90, 40, 1.0, 3.2, splash=0.9),
        TowerLevel(150, 70, 1.05, 3.4, splash=1.2),
    ), "Hurls firebolts; from the second rank they burst into fireballs.", bolt_speed=8.0),
    TowerKind("storm", "Storm Obelisk", L, "chain", (
        TowerLevel(100, 18, 1.2, 2.8, chains=2),
        TowerLevel(110, 26, 1.3, 3.0, chains=3),
        TowerLevel(170, 38, 1.4, 3.2, chains=5),
    ), "Chain lightning leaps from monster to monster."),
    TowerKind("frost", "Frost Shrine", C, "nova", (
        TowerLevel(85, 9, 0.6, 2.0, chill=0.4, chill_time=2.0),
        TowerLevel(95, 15, 0.65, 2.2, chill=0.5, chill_time=2.2),
        TowerLevel(150, 24, 0.7, 2.4, chill=0.6, chill_time=2.5),
    ), "A frost nova chills everything near it: slower feet, weaker blows on doors."),
    TowerKind("plague", "Plague Totem", P, "venom", (
        TowerLevel(80, 6, 0.8, 3.0, poison=14, poison_time=4.0),
        TowerLevel(95, 10, 0.85, 3.2, poison=24, poison_time=4.0),
        TowerLevel(160, 16, 0.9, 3.4, poison=40, poison_time=4.5),
    ), "Venom seeks the strongest monster it can poison; poison stacks up to four times.", bolt_speed=7.0),
)}

MAX_POISON_STACKS = 4
SELL_REFUND = 0.7


@dataclass(frozen=True)
class DoorSpec:
    cost: int = 60
    hp: float = 650.0
    repair: float = 0.5    # share of its missing life a standing door regains when a wave is cleared


DOOR = DoorSpec()


@dataclass(frozen=True)
class Group:
    kind: str
    count: int
    interval: float
    start: float = 0.0     # seconds after the wave begins


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


SPELLS: dict[str, SpellSpec] = {s.key: s for s in (
    SpellSpec("cleanse", "Cleanse", 35, "tower", "Burns every curse off one tower."),
    SpellSpec("smite", "Smite", 30, "monster", "Holy lightning strikes one monster, and no resistance softens it. "
              "A leader it strikes while pondering or chanting loses its curse.", damage=100),
    SpellSpec("meteor", "Meteor", 60, "floor", "Falls a moment after the cast and leaves the floor burning.", damage=110,
              radius=1.4, delay=1.2, lasting=3.0, burn=12),
    SpellSpec("orb", "Frozen Orb", 50, "floor", "Freezes everything near it: no walking, no battering, and a leader's "
              "curse breaks.", damage=50, radius=1.8, lasting=2.5),
)}

START_LIVES = 20
MANA_MAX = 100.0
MANA_START = 60.0
MANA_REGEN = 1.5
WAVE_BREAK = 25.0          # seconds between a cleared wave and the next, unless called early
EARLY_CALL_GOLD = 1.0      # gold per second of break skipped
BURN_RADIUS = 1.1          # the burning floor a meteor leaves
SHATTER_RADIUS = 1.2
SHATTER_SHARE = 0.1        # of a shattered monster's full life
CONTAGION_REACH = 1.5
THORNS = 0.5               # a gate under Thorns returns this share of each blow, as it would land unchilled
SOUL = 10.0                # mana a slain leader gives under Soul Harvest
WARD = 8.0                 # seconds a cleansed tower is warded under Salvation

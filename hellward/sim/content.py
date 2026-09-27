"""Every monster, leader, curse, tower and wave, as tables.

Distances are in tiles, times in seconds, damage and life in hit points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Final


class Element(str, Enum):
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
    Curse.WEAKEN: CurseSpec("Weaken", 8.0, radius=1.5, damage=0.35, blurb="deals a third of its damage"),
    Curse.DECREPIFY: CurseSpec("Decrepify", 8.0, radius=1.5, rate=0.4, blurb="attacks at 40% speed"),
    Curse.DIM_VISION: CurseSpec("Dim Vision", 8.0, radius=2.3, range=0.55, blurb="sees half as far"),
    Curse.BONE_PRISON: CurseSpec("Bone Prison", 4.5, radius=1.0, silenced=True, blurb="caged: cannot attack"),
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
    door_dps: float = 8.0
    resist: dict[Element, float] = field(default_factory=dict)  # 1.0 immune, negative a weakness
    flying: bool = False
    leader: LeaderSpec | None = None
    size: float = 0.6        # drawn height in tiles, for the view and the hit radius

    def taken(self, element: Element) -> float:
        return 1.0 - self.resist.get(element, 0.0)


F, L, C, P = Element.FIRE, Element.LIGHTNING, Element.COLD, Element.POISON
B, N = Element.BONE, Element.NATURE

MONSTERS: Final[dict[str, MonsterKind]] = {m.key: m for m in (
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
    MonsterKind("priest", "Bone Acolyte", hp=210, speed=0.9, bounty=40, lives=2, door_dps=6, resist={P: 1.0, C: 0.25},
                leader=LeaderSpec((Curse.BONE_PRISON, Curse.DIM_VISION), cooldown=10.0), size=0.85),
    MonsterKind("witch", "Blood Witch", hp=260, speed=0.95, bounty=45, lives=2, door_dps=6, resist={F: 0.25, L: 0.25},
                leader=LeaderSpec((Curse.DECREPIFY, Curse.WEAKEN), cooldown=8.5), size=0.85),
    MonsterKind("flayer", "Flayer", hp=60, speed=1.45, bounty=4, door_dps=8, resist={F: 0.25}, size=0.5),
    MonsterKind("zealot", "Zealot", hp=190, speed=1.0, bounty=10, door_dps=16, resist={L: 0.4, F: 0.25}, size=0.85),
    MonsterKind("spider", "Spider", hp=120, speed=1.35, bounty=8, door_dps=10, resist={P: 1.0, C: -0.25}, size=0.7),
    MonsterKind("bat", "Blood Bat", hp=55, speed=1.9, bounty=5, flying=True, resist={C: 0.5, P: 0.25}, size=0.5),
    MonsterKind("hulk", "Thorned Hulk", hp=760, speed=0.55, bounty=30, lives=2, door_dps=70, resist={P: 1.0, C: 0.25, F: -0.25}, size=1.1),
    MonsterKind("drowned", "The Drowned", hp=320, speed=0.7, bounty=14, door_dps=22, resist={C: 0.5, P: 0.5, L: -0.25}, size=0.85),
    MonsterKind("fetish", "Fetish Shaman", hp=150, speed=1.1, bounty=35, lives=2, door_dps=4, resist={F: 0.25}, size=0.6,
                leader=LeaderSpec((Curse.WEAKEN,), cooldown=9.0, raises="flayer")),
    MonsterKind("inquisitor", "Zakarum Inquisitor", hp=280, speed=0.95, bounty=45, lives=2, door_dps=6, resist={L: 0.4, F: 0.25}, size=0.9,
                leader=LeaderSpec((Curse.WEAKEN, Curse.DIM_VISION), cooldown=12.0, mark=1.5)),
    MonsterKind("bone_priest", "The Bone Priest", hp=6000, speed=0.45, bounty=0, lives=20, door_dps=150,
                resist={P: 1.0, C: 0.25, F: 0.25, L: 0.25}, size=1.6,
                leader=LeaderSpec((Curse.BONE_PRISON, Curse.WEAKEN, Curse.DECREPIFY, Curse.DIM_VISION), cast_range=6.0,
                                  cooldown=8.0, widen=1.0, burn=5.0)),
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
    lasting: float = 0.0  # seconds an amplification lasts


@dataclass(frozen=True)
class TowerKind:
    key: str
    name: str
    element: Element
    attack: str           # "bolt", "chain", "nova" or "venom"
    levels: tuple[TowerLevel, ...]
    blurb: str
    bolt_speed: float = 9.0   # tiles per second; a nova and a chain strike at once


TOWERS: Final[dict[str, TowerKind]] = {t.key: t for t in (
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
    TowerKind("altar", "Bone Altar", B, "amplify", (
        TowerLevel(90, 0.30, 0.25, 3.0, splash=1.0, lasting=2.0),
        TowerLevel(100, 0.45, 1 / 3.6, 3.2, splash=1.2, lasting=2.2),
        TowerLevel(160, 0.60, 1 / 3.2, 3.4, splash=1.4, lasting=2.5),
    ), "Lays Amplify Damage on the thickest knot of monsters in reach: they take more damage from everything."),
    TowerKind("grove", "Druid Grove", N, "aura", (
        TowerLevel(100, 0.20, 0.0, 1.5),
        TowerLevel(110, 0.30, 0.0, 1.5),
        TowerLevel(170, 0.40, 0.0, 2.3),
    ), "Its aura makes every tower within reach strike harder. Groves do not stack."),
)}

MAX_POISON_STACKS: Final = 4
SELL_REFUND: Final = 0.7


@dataclass(frozen=True)
class DoorSpec:
    cost: int = 60
    hp: float = 650.0
    repair: float = 0.5    # share of its missing life a standing door regains when a wave is cleared


DOOR: Final = DoorSpec()


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
    recharge: float = 0.0 # seconds after a cast before it can be cast again


SPELLS: Final[dict[str, SpellSpec]] = {s.key: s for s in (
    SpellSpec("cleanse", "Cleanse", 35, "tower", "Burns every curse off one tower."),
    SpellSpec("smite", "Smite", 35, "monster", "Holy lightning strikes one monster, and no resistance softens it. "
              "A leader it strikes while pondering or chanting loses its curse, but its next curse cannot be broken.", damage=100,
              recharge=8.0),
    SpellSpec("meteor", "Meteor", 60, "floor", "Falls a moment after the cast and leaves the floor burning.", damage=110,
              radius=1.4, delay=1.2, lasting=3.0, burn=12, recharge=10.0),
    SpellSpec("orb", "Frozen Orb", 50, "floor", "Freezes everything near it: no walking, no battering, and a leader's "
              "curse breaks (its next one cannot).", damage=50, radius=1.8, lasting=2.5, recharge=12.0),
)}

START_LIVES: Final = 20
MANA_MAX: Final = 100.0
MANA_START: Final = 60.0
MANA_REGEN: Final = 1.5
WAVE_BREAK: Final = 25.0          # seconds between a cleared wave and the next, unless called early
EARLY_CALL_GOLD: Final = 1.0      # gold per second of break skipped
BURN_RADIUS: Final = 1.1          # the burning floor a meteor leaves
SHATTER_RADIUS: Final = 1.2
SHATTER_SHARE: Final = 0.1        # of a shattered monster's full life
CONTAGION_REACH: Final = 1.5
THORNS: Final = 0.5               # a gate under Thorns returns this share of each blow, as it would land unchilled
SOUL: Final = 10.0                # mana a slain leader gives under Soul Harvest
WARD: Final = 8.0                 # seconds a cleansed tower is warded under Salvation
CORPSE_SHARE: Final = 0.15        # share of an amplified monster's full life its burst deals
CORPSE_RADIUS: Final = 1.2        # how far a corpse explosion reaches
HURRICANE_RADIUS: Final = 2.5     # how far a grove's slowing reaches
HURRICANE_SLOW: Final = 0.8       # walkers near a grove move this share of their speed
TWISTER_PERIOD: Final = 4.0       # seconds between a grove's roots
TWISTER_RADIUS: Final = 2.5       # how far a grove's root reaches
TWISTER_HELD: Final = 1.5         # seconds a twister holds its monster

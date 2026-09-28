"""Authored tower patterns and the equipment fixed before a defence.

Recipes and effects are data here. The campaign pays for forging; the simulation bakes the equipped
effects into a tower family's ranks when a World begins. No game or art dependency belongs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping


@dataclass(frozen=True)
class Pattern:
    key: str
    name: str
    family: str
    salvage_cost: int
    blurb: str
    trophy_cost: int = 0
    first_location: int = 1                 # 1-based campaign position at which forging opens
    damage_delta: tuple[float, float, float] = (0.0, 0.0, 0.0)
    splash_delta: tuple[float, float, float] = (0.0, 0.0, 0.0)
    chain_delta: tuple[int, int, int] = (0, 0, 0)
    leader_damage_bonus: float = 0.0         # extra share of damage to leaders, after rank damage
    rate_factor: float = 1.0                 # multiplies attacks per second at every rank


PATTERNS: Final[Mapping[str, Pattern]] = MappingProxyType({p.key: p for p in (
    Pattern("honed_string", "Honed String", "arrow", 3,
            "Every Arrow hit gains 1 damage, a strong early gain that stays flat.", first_location=2,
            damage_delta=(1.0, 1.0, 1.0)),
    Pattern("laminated_limbs", "Laminated Limbs", "arrow", 6,
            "Arrow gains no damage at rank I, then 1 at rank II and 2 at rank III.", first_location=2,
            damage_delta=(0.0, 1.0, 2.0)),
    Pattern("blast_chamber", "Blast Chamber", "pyre", 8,
            "Rank III Pyres burst in a small area around the struck monster.", trophy_cost=3, first_location=7,
            splash_delta=(0.0, 0.0, 0.8)),
    Pattern("forked_coil", "Forked Coil", "storm", 9,
            "Rank III Storm strikes leap to one additional monster.", trophy_cost=2, first_location=10,
            chain_delta=(0, 0, 1)),
    Pattern("execution_bow", "Execution Bow", "arrow", 10,
            "Arrow towers attack more slowly but hit leaders much harder; later ranks add damage.",
            trophy_cost=2, first_location=11,
            damage_delta=(0.0, 1.0, 2.0), leader_damage_bonus=1.5, rate_factor=0.55),
)})


@dataclass(frozen=True)
class Loadout:
    """At most one known pattern per tower family; order is canonical for saves and cache keys."""

    equipped: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        keys = tuple(self.equipped)
        families: set[str] = set()
        for key in keys:
            pattern = PATTERNS.get(key)
            if pattern is None:
                raise ValueError(f"Unknown tower pattern: {key}")
            if pattern.family in families:
                raise ValueError(f"Only one pattern can be equipped for {pattern.family} towers")
            families.add(pattern.family)
        object.__setattr__(self, "equipped", tuple(sorted(keys)))

    def for_family(self, family: str) -> Pattern | None:
        """The modifier for a tower family, or none when that family is unequipped."""
        for key in self.equipped:
            pattern = PATTERNS[key]
            if pattern.family == family:
                return pattern
        return None


EMPTY_LOADOUT: Final = Loadout()

"""The small common combat scale shared by Hellward's locations.

Indices are zero-based: location 0 is Tristram and wave 0 is its first wave.
Monster kinds supply a role multiplier; unusual encounters may add their own
multiplier without needing another location-wide life table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class BalanceProfile:
    base_hp: float = 6.0
    location_growth: float = 1.055
    wave_growth: float = 1.05
    arrow_hit: int = 2
    base_gold_unit: int = 12
    starting_units: float = 3.0
    starting_units_growth: float = 0.5
    wave_income_units: float = 1.0
    wave_income_growth_units: float = 0.5
    wave_density_decay: float = 0.5
    minimum_wave_density: float = 0.4
    rank_cost_units: tuple[float, float, float] = (1.0, 2 / 3, 1.0)
    salvage_budget: int = 3
    salvage_sale_fraction: float = 1 / 3
    breach_pack_income_units: float = 0.5
    breach_cache_units: float = 0.8

    def __post_init__(self) -> None:
        for name, value in (("base_hp", self.base_hp), ("starting_units", self.starting_units),
                            ("wave_income_units", self.wave_income_units)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name, value in (("location_growth", self.location_growth), ("wave_growth", self.wave_growth)):
            if not math.isfinite(value) or value < 1:
                raise ValueError(f"{name} must be finite and at least one")
        if not math.isfinite(self.wave_income_growth_units) or self.wave_income_growth_units < 0:
            raise ValueError("wave_income_growth_units must be finite and nonnegative")
        if not math.isfinite(self.starting_units_growth) or self.starting_units_growth < 0:
            raise ValueError("starting_units_growth must be finite and nonnegative")
        if not math.isfinite(self.wave_density_decay) or self.wave_density_decay < 0:
            raise ValueError("wave_density_decay must be finite and nonnegative")
        if not math.isfinite(self.minimum_wave_density) or not 0 < self.minimum_wave_density <= 1:
            raise ValueError("minimum_wave_density must be between zero and one")
        for name, value in (("arrow_hit", self.arrow_hit), ("base_gold_unit", self.base_gold_unit)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if len(self.rank_cost_units) != 3 or any(not math.isfinite(unit) or unit <= 0 for unit in self.rank_cost_units):
            raise ValueError("rank_cost_units must have three finite positive values")
        if type(self.salvage_budget) is not int or self.salvage_budget < 0:
            raise ValueError("salvage_budget must be a nonnegative integer")
        if not math.isfinite(self.salvage_sale_fraction) or self.salvage_sale_fraction <= 0:
            raise ValueError("salvage_sale_fraction must be finite and positive")
        for name, value in (("breach_pack_income_units", self.breach_pack_income_units),
                            ("breach_cache_units", self.breach_cache_units)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

    def effective_hp(self, role_hp: float, location_index: int, wave_index: int,
                     encounter_factor: float = 1.0) -> int:
        """Life of one enemy in a particular wave, before damage resistance."""
        self._index("location_index", location_index)
        self._index("wave_index", wave_index)
        for name, value in (("role_hp", role_hp), ("encounter_factor", encounter_factor)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        hp = round(self.base_hp * role_hp * self.location_growth ** location_index
                   * self.wave_growth ** wave_index * encounter_factor)
        if hp < 1:
            raise ValueError("effective HP must be at least one")
        return hp

    def arrow_damage(self, rank: int) -> int:
        """A single Arrow hit at zero-based rank (rank I is zero)."""
        if rank not in (0, 1, 2):
            raise ValueError("Arrow rank must be 0, 1 or 2")
        return self.arrow_hit + rank

    def tower_damage(self, rank: int, role_damage: float = 1.0) -> int:
        """A direct hit for a tower role, using Arrow's rank progression as the unit."""
        if not math.isfinite(role_damage) or role_damage <= 0:
            raise ValueError("role_damage must be finite and positive")
        damage = round(self.arrow_damage(rank) * role_damage)
        if damage < 1:
            raise ValueError("tower damage must be at least one")
        return damage

    def tower_cost(self, rank: int, role_price: float = 1.0, location_index: int = 0) -> int:
        """The price of a tower rank, in the local gold unit.

        Catalog ranks use location zero; the battle applies its location index when
        charging for a build or upgrade.
        """
        if not math.isfinite(role_price) or role_price <= 0:
            raise ValueError("role_price must be finite and positive")
        self.arrow_damage(rank)  # validates the rank shared by damage and prices
        cost = round(self.gold_unit(location_index) * self.rank_cost_units[rank] * role_price)
        if cost < 1:
            raise ValueError("tower cost must be at least one")
        return cost

    def gold_unit(self, location_index: int) -> int:
        """Price of a rank-I Arrow at this location, and the budget's unit."""
        self._index("location_index", location_index)
        return round(self.base_gold_unit * self.location_growth ** location_index)

    def starting_gold(self, location_index: int) -> int:
        """Battle gold in hand before the first wave."""
        return round(self.gold_unit(location_index)
                     * (self.starting_units + location_index * self.starting_units_growth))

    def wave_density(self, location_index: int) -> float:
        """Retire the old area-attack swarm counts while keeping late packs substantial."""
        self._index("location_index", location_index)
        return max(self.minimum_wave_density,
                   1.0 / (1.0 + self.wave_density_decay * max(0, location_index - 1)))

    def wave_income(self, location_index: int, wave_index: int) -> int:
        """Total ordinary-wave gold budget, shared by kills and its clear reward.

        It depends on the location and wave, not the number of monster bodies;
        authored swarms therefore cannot multiply income by accident.
        """
        self._index("wave_index", wave_index)
        return round(self.gold_unit(location_index)
                     * (self.wave_income_units + self.wave_income_growth_units * wave_index))

    def wave_kill_budget(self, location_index: int, wave_index: int, bodies: int) -> int:
        """Gold assigned to kills; the rest is paid only when the wave clears."""
        if type(bodies) is not int or bodies < 0:
            raise ValueError("bodies must be a nonnegative integer")
        budget = self.wave_income(location_index, wave_index)
        if bodies == 0:
            return 0
        return min(budget, max(bodies, round(budget * 0.75)))

    def wave_clear_bonus(self, location_index: int, wave_index: int, bodies: int) -> int:
        return self.wave_income(location_index, wave_index) - self.wave_kill_budget(location_index, wave_index, bodies)

    def wave_payouts(self, location_index: int, wave_index: int, weights: tuple[int, ...]) -> tuple[int, ...]:
        """Deterministic integer shares for the spawns in one wave, in spawn order."""
        return self._allocate_gold(self.wave_kill_budget(location_index, wave_index, len(weights)), weights)

    def breach_payouts(self, location_index: int, weights: tuple[int, ...]) -> tuple[int, ...]:
        """Extra kill gold earned by the optional side pack."""
        budget = round(self.gold_unit(location_index) * self.breach_pack_income_units)
        return self._allocate_gold(budget, weights)

    def breach_cache(self, location_index: int) -> int:
        """Cash cache for clearing the optional pack instead of keeping its trophy."""
        return round(self.gold_unit(location_index) * self.breach_cache_units)

    @staticmethod
    def _allocate_gold(budget: int, weights: tuple[int, ...]) -> tuple[int, ...]:
        if any(type(weight) is not int or weight < 0 for weight in weights):
            raise ValueError("gold weights must be nonnegative integers")
        bodies = len(weights)
        if bodies == 0:
            return ()
        base = 1 if budget >= bodies else 0
        extra = budget - base * bodies
        total_weight = 0
        for weight in weights:
            total_weight += max(1, weight)
        cumulative = 0
        previous = 0
        payouts: list[int] = []
        for weight in weights:
            cumulative += max(1, weight)
            apportioned = cumulative * extra // total_weight
            payouts.append(base + apportioned - previous)
            previous = apportioned
        return tuple(payouts)

    def salvage_sale_gold(self, location_index: int) -> int:
        """Battle gold from selling one piece instead of banking it for a pattern."""
        return max(1, round(self.gold_unit(location_index) * self.salvage_sale_fraction))

    @staticmethod
    def _index(name: str, value: int) -> None:
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")


BALANCE: Final = BalanceProfile()

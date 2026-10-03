"""The common combat scale and the gold economy shared by every location.

A monster's life is its own (``monsters.toml``), the same at every location; what grows with depth is the
roster — harder kinds, more bodies — not the monsters. Prices do not grow either: the gold unit is the same
everywhere, and a wave's gold depends only on the wave. ``economy.toml`` holds every number here; waves and
maps are authored against these, and the balance tools verify them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from hellward.sim import tuning
from hellward.sim.sums import half_up


@dataclass(frozen=True)
class BalanceProfile:
    arrow_hit: int
    base_gold_unit: int
    starting_units: float
    wave_income_units: float
    wave_income_growth_units: float
    rank_cost_units: tuple[float, float, float]
    salvage_budget: int
    salvage_sale_fraction: float
    breach_pack_income_units: float
    breach_cache_units: float

    def __post_init__(self) -> None:
        for name, value in (("starting_units", self.starting_units),
                            ("wave_income_units", self.wave_income_units)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.wave_income_growth_units) or self.wave_income_growth_units < 0:
            raise ValueError("wave_income_growth_units must be finite and nonnegative")
        for name, value in (("arrow_hit", self.arrow_hit), ("base_gold_unit", self.base_gold_unit)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be an integer of at least one")
        if not isinstance(self.salvage_budget, int) or isinstance(self.salvage_budget, bool) \
                or self.salvage_budget < 0:
            raise ValueError("salvage_budget must be a nonnegative integer")
        if not math.isfinite(self.salvage_sale_fraction) or not 0 < self.salvage_sale_fraction <= 1:
            raise ValueError("salvage_sale_fraction must be between zero and one")
        for name, value in (("breach_pack_income_units", self.breach_pack_income_units),
                            ("breach_cache_units", self.breach_cache_units)):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")

    @staticmethod
    def _index(name: str, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError(f"{name} must be a nonnegative integer")

    def arrow_damage(self, rank: int) -> int:
        """Arrow's hit at a rank, the damage unit: rank adds one."""
        if rank not in (0, 1, 2):
            raise ValueError("rank must be 0, 1 or 2")
        return self.arrow_hit + rank

    def tower_damage(self, rank: int, role_damage: float) -> int:
        """A tower rank's hit from its damage role, rounded half up, at least one."""
        if not math.isfinite(role_damage) or role_damage <= 0:
            raise ValueError("role_damage must be finite and positive")
        damage = half_up(self.arrow_damage(rank) * role_damage)
        if damage < 1:
            raise ValueError("tower damage must be at least one")
        return damage

    def tower_cost(self, rank: int, role_price: float = 1.0,
                   rank_cost_units: tuple[float, float, float] | None = None) -> int:
        """The price of a tower rank, in the gold unit.

        A tower kind may price its ranks apart from the common ``rank_cost_units``.
        """
        if not math.isfinite(role_price) or role_price <= 0:
            raise ValueError("role_price must be finite and positive")
        self.arrow_damage(rank)  # validates the rank shared by damage and prices
        units = self.rank_cost_units if rank_cost_units is None else rank_cost_units
        cost = round(self.gold_unit() * units[rank] * role_price)
        if cost < 1:
            raise ValueError("tower cost must be at least one")
        return cost

    def gold_unit(self) -> int:
        """Price of a rank-I Arrow: the gold unit, the same at every location."""
        return self.base_gold_unit

    def income_unit(self) -> int:
        """What a wave's gold is counted in: the gold unit."""
        return self.base_gold_unit

    def starting_gold(self) -> int:
        """Battle gold in hand before the first wave."""
        return round(self.base_gold_unit * self.starting_units)

    def wave_income(self, wave_index: int) -> int:
        """Total ordinary-wave gold budget, shared by kills and its clear reward.

        It depends on the wave, not the number of monster bodies; authored swarms
        therefore cannot multiply income by accident.
        """
        self._index("wave_index", wave_index)
        return round(self.income_unit() * (self.wave_income_units + self.wave_income_growth_units * wave_index))

    def wave_kill_budget(self, wave_index: int, bodies: int) -> int:
        """Gold assigned to kills; the rest is paid only when the wave clears."""
        self._index("bodies", bodies)
        budget = self.wave_income(wave_index)
        if bodies == 0:
            return 0
        return min(budget, max(bodies, round(budget * 0.75)))

    def wave_clear_bonus(self, wave_index: int, bodies: int) -> int:
        """Clear bonus: leftover income after its kills."""
        return self.wave_income(wave_index) - self.wave_kill_budget(wave_index, bodies)

    def wave_payouts(self, wave_index: int, weights: tuple[int, ...]) -> tuple[int, ...]:
        """Split of the kill budget across one weight per ordinary body."""
        return self._allocate_gold(self.wave_kill_budget(wave_index, len(weights)), weights)

    def breach_payouts(self, weights: tuple[int, ...]) -> tuple[int, ...]:
        """Extra kill gold earned by the optional side pack."""
        budget = round(self.income_unit() * self.breach_pack_income_units)
        return self._allocate_gold(budget, weights)

    def breach_cache(self) -> int:
        """Cash cache for clearing the optional pack instead of keeping its trophy."""
        return round(self.income_unit() * self.breach_cache_units)

    def salvage_sale_gold(self) -> int:
        """Battle gold from selling one piece instead of banking it for a pattern."""
        return max(1, round(self.income_unit() * self.salvage_sale_fraction))

    @staticmethod
    def _allocate_gold(budget: int, weights: tuple[int, ...]) -> tuple[int, ...]:
        """Split of a gold budget across one nonnegative weight per paid body: one gold each when the budget
        covers the bodies, the rest apportioned by weight, in a single pass."""
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


def _profile() -> BalanceProfile:
    row = tuning.table("economy")
    units = row["rank_cost_units"]
    return BalanceProfile(**{**row, "rank_cost_units": (float(units[0]), float(units[1]), float(units[2]))})


BALANCE: BalanceProfile = _profile()


def load_profile() -> BalanceProfile:
    """The active profile, re-read (tests pin it against the tuning data)."""
    return _profile()

"""The shared combat scale and battle-gold budget."""

from dataclasses import replace

import pytest

from hellward.sim.balance import BALANCE
from hellward.sim.content import MONSTERS, TOWERS


def test_opening_fights_use_small_hits():
    """The first defence stays within the small scale and needs several arrows per monster."""
    assert [BALANCE.arrow_damage(rank) for rank in range(3)] == [2, 3, 4]
    assert 2 <= -(-MONSTERS["fallen"].hp // BALANCE.arrow_damage(0)) <= 5


def test_a_location_starts_with_three_arrow_prices_and_an_ordinary_wave_pays_one():
    """Prices are flat with depth; a wave's gold grows only with the wave."""
    assert BALANCE.gold_unit() == 12
    assert BALANCE.income_unit() == 12
    assert BALANCE.starting_gold() == 36
    assert BALANCE.wave_income(0) == 12
    assert BALANCE.wave_income(4) == 36


@pytest.mark.parametrize("change", (
    {"arrow_hit": 0}, {"base_gold_unit": 0}, {"starting_units": 0},
    {"wave_income_units": 0}, {"wave_income_growth_units": -0.1},
    {"salvage_budget": -1}, {"salvage_sale_fraction": 0}, {"salvage_sale_fraction": 1.5},
    {"breach_pack_income_units": -0.1}, {"breach_cache_units": float("nan")},
))
def test_an_invalid_profile_fails_when_created(change):
    """A malformed economy must be found before a defence begins."""
    with pytest.raises(ValueError):
        replace(BALANCE, **change)


def test_invalid_calls_cannot_produce_a_plausible_battle_number():
    """Bad wiring should fail where the profile is called."""
    with pytest.raises(ValueError):
        BALANCE.tower_damage(3, 1.0)
    with pytest.raises(ValueError):
        BALANCE.tower_damage(0, 0.0)
    with pytest.raises(ValueError):
        BALANCE.tower_cost(-1)
    with pytest.raises(ValueError):
        BALANCE.wave_income(-1)
    with pytest.raises(ValueError):
        BALANCE.wave_clear_bonus(0, -1)
    with pytest.raises(ValueError):
        BALANCE.wave_payouts(0, (1, -1))


def test_a_few_profile_changes_reach_the_gold_economy():
    """Tuning knobs propagate while a role's Arrow damage stays earned, not automatic."""
    changed = replace(BALANCE, base_gold_unit=16, wave_income_growth_units=1.0)
    assert changed.gold_unit() > BALANCE.gold_unit()
    assert changed.starting_gold() > BALANCE.starting_gold()
    assert changed.wave_income(0) > BALANCE.wave_income(0)
    assert changed.wave_income(4) - changed.wave_income(0) > BALANCE.wave_income(4) - BALANCE.wave_income(0)
    assert changed.arrow_damage(0) == BALANCE.arrow_damage(0)


def test_monster_roles_share_the_small_opening_scale():
    """The first pack and its leader are readable, while bosses remain distinct."""
    assert all(1 <= MONSTERS[k].hp <= 20 for k in ("fallen", "zombie", "shaman"))
    assert MONSTERS["fallen"].hp < MONSTERS["zombie"].hp < MONSTERS["shaman"].hp
    assert MONSTERS["fallen"].bounty == 1
    assert MONSTERS["fallen"].hp < MONSTERS["carver"].hp < MONSTERS["devilkin"].hp < MONSTERS["dark_one"].hp
    assert MONSTERS["skeleton"].hp < MONSTERS["overlord"].hp < MONSTERS["azazel"].hp
    assert MONSTERS["flayer"].hp < MONSTERS["hulk"].hp < MONSTERS["bone_priest"].hp
    assert all(1 <= monster.hp < 200 for monster in MONSTERS.values())


def test_base_tower_ranks_keep_hits_small_and_area_damage_locked():
    """Buying an ordinary tower rank alone cannot grant a blast, chain or nova."""
    assert TOWERS["arrow"].levels[0].cost == BALANCE.gold_unit()
    damaging = (TOWERS[kind] for kind in ("arrow", "pyre", "storm", "frost", "plague"))
    assert all(1 <= level.damage <= 20 for tower in damaging for level in tower.levels)
    assert all(level.splash == 0 for level in TOWERS["pyre"].levels)
    assert all(level.chains == 0 for level in TOWERS["storm"].levels)
    assert TOWERS["frost"].attack == "bolt"
    assert TOWERS["arrow"].levels[0].cost < TOWERS["pyre"].levels[0].cost


def test_wave_gold_is_capped_by_profile_even_if_a_swarm_has_more_bodies():
    for weights in ((1,), (1,) * 8, (1,) * 80, (1, 2, 6, 1, 1)):
        payouts = BALANCE.wave_payouts(0, weights)
        assert len(payouts) == len(weights)
        assert all(amount >= 0 for amount in payouts)
        assert sum(payouts) + BALANCE.wave_clear_bonus(0, len(weights)) == BALANCE.wave_income(0)
    assert all(amount >= 1 for amount in BALANCE.wave_payouts(0, (1,) * 8))
    assert BALANCE.wave_payouts(0, (1, 5))[1] > BALANCE.wave_payouts(0, (1, 5))[0]

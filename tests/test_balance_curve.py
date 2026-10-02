"""The shared combat scale and battle-gold budget."""

from dataclasses import replace

import pytest

from hellward.sim.balance import BALANCE
from hellward.sim.content import MONSTERS, TOWERS


def test_opening_fights_use_small_hits_and_no_large_enemy_life():
    """The first defence stays within the requested 1–20 scale and needs several arrows."""
    assert 1 <= BALANCE.effective_hp(1.0, 0, 0) <= 20
    assert 2 <= -(-BALANCE.effective_hp(1.0, 0, 0) // BALANCE.arrow_damage(0)) <= 5
    assert BALANCE.effective_hp(2.0, 0, 4) == 24
    assert [BALANCE.arrow_damage(rank) for rank in range(3)] == [2, 3, 4]


def test_a_location_starts_with_three_arrow_prices_and_an_ordinary_wave_pays_one():
    """Prices stay flat with depth; the stipend grows with the monsters' life, income a little slower."""
    assert BALANCE.gold_unit(0) == 12
    assert BALANCE.starting_gold(0) == 36
    assert BALANCE.wave_income(0, 0) == 12
    assert BALANCE.wave_income(0, 4) == 36
    assert BALANCE.gold_unit(11) == 12
    assert BALANCE.income_unit(11) == 42
    assert BALANCE.starting_gold(11) == 184
    assert BALANCE.wave_income(11, 0) == 42


@pytest.mark.parametrize("change", (
    {"base_hp": 0}, {"life_growth": 0.9}, {"wave_growth": float("nan")},
    {"income_growth": 0.9}, {"stipend_growth": float("nan")},
    {"arrow_hit": 0}, {"base_gold_unit": 0}, {"starting_units": 0},
    {"wave_income_units": 0}, {"wave_income_growth_units": -0.1},
))
def test_an_invalid_profile_fails_when_created(change):
    """A malformed curve must be found before a defence begins."""
    with pytest.raises(ValueError):
        replace(BALANCE, **change)


def test_invalid_stage_or_role_cannot_produce_a_plausible_battle_number():
    """Bad campaign wiring should fail where the profile is called."""
    with pytest.raises(ValueError):
        BALANCE.effective_hp(0, 0, 0)
    with pytest.raises(ValueError):
        BALANCE.effective_hp(1, -1, 0)
    with pytest.raises(ValueError):
        BALANCE.effective_hp(1, 0, -1)
    with pytest.raises(ValueError):
        BALANCE.gold_unit(-1)
    with pytest.raises(ValueError):
        BALANCE.wave_income(0, -1)


def test_a_few_profile_changes_reach_late_encounters_and_the_gold_economy():
    """Tuning knobs propagate while a role's Arrow damage stays earned, not automatic."""
    changed = replace(BALANCE, base_hp=8, life_growth=1.2, base_gold_unit=16)
    assert changed.effective_hp(1, 0, 0) == 8
    assert changed.effective_hp(1, 11, 7) > BALANCE.effective_hp(1, 11, 7)
    assert changed.gold_unit(11) > BALANCE.gold_unit(11)
    assert changed.starting_gold(11) > BALANCE.starting_gold(11)
    assert changed.wave_income(11, 0) > BALANCE.wave_income(11, 0)
    assert changed.arrow_damage(0) == BALANCE.arrow_damage(0)


def test_monster_roles_share_the_small_opening_scale():
    """The first pack and its leader are readable, while bosses remain distinct."""
    assert all(1 <= MONSTERS[k].hp <= 20 for k in ("fallen", "zombie", "shaman"))
    assert MONSTERS["fallen"].hp < MONSTERS["zombie"].hp < MONSTERS["shaman"].hp
    assert MONSTERS["fallen"].bounty == 1
    assert MONSTERS["skeleton"].hp < MONSTERS["overlord"].hp < MONSTERS["azazel"].hp
    assert MONSTERS["flayer"].hp < MONSTERS["hulk"].hp < MONSTERS["bone_priest"].hp
    assert all(1 <= monster.hp < 200 for monster in MONSTERS.values())


def test_base_tower_ranks_keep_hits_small_and_area_damage_locked():
    """Buying an ordinary tower rank alone cannot grant a blast, chain or nova."""
    assert TOWERS["arrow"].levels[0].cost == BALANCE.gold_unit(0)
    damaging = (TOWERS[kind] for kind in ("arrow", "pyre", "storm", "frost", "plague"))
    assert all(1 <= level.damage <= 20 for tower in damaging for level in tower.levels)
    assert all(level.splash == 0 for level in TOWERS["pyre"].levels)
    assert all(level.chains == 0 for level in TOWERS["storm"].levels)
    assert TOWERS["frost"].attack == "bolt"
    assert TOWERS["arrow"].levels[0].cost < TOWERS["pyre"].levels[0].cost


def test_wave_gold_is_capped_by_profile_even_if_a_swarm_has_more_bodies():
    for weights in ((1,), (1,) * 8, (1,) * 80, (1, 2, 6, 1, 1)):
        payouts = BALANCE.wave_payouts(0, 0, weights)
        assert len(payouts) == len(weights)
        assert all(amount >= 0 for amount in payouts)
        assert sum(payouts) + BALANCE.wave_clear_bonus(0, 0, len(weights)) == BALANCE.wave_income(0, 0)
    assert all(amount >= 1 for amount in BALANCE.wave_payouts(0, 0, (1,) * 8))
    assert BALANCE.wave_payouts(0, 0, (1, 5))[1] > BALANCE.wave_payouts(0, 0, (1, 5))[0]

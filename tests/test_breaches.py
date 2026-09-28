"""Optional side entrances are announced choices with conditional rewards."""

from dataclasses import replace

import pytest

from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import GRAVEYARD, LOCATIONS
from hellward.sim.content import Group, Wave
from hellward.sim.model import Refused, World


def _three_wave_graveyard() -> World:
    wave = Wave((Group("skeleton", 1, 1.0),), 0)
    location = replace(GRAVEYARD, waves=(wave, wave, wave), wave_names=("one", "two", "three"))
    return World(location, seed=4)


def _clear_one_wave(world: World) -> None:
    world.call_wave()
    while world.schedule:
        world.step()
    for monster in list(world.monsters):
        world._hurt(monster, monster.hp, None)
    world.step()


def test_six_breaches_have_sealed_routes_and_unique_pack_foes():
    assert set(BREACHES) == {"graveyard", "catacombs", "hells_gate", "spider_forest", "drowned_city", "temple"}
    for key, spec in BREACHES.items():
        location = LOCATIONS[key]
        assert location.level.route("breach").entrance != location.level.route("main").entrance
        assert spec.after_wave + 1 < len(location.waves)
        assert all(group.route != "breach" for wave in location.waves for group in wave.groups)
        assert any(group.kind not in location.monsters for group in spec.groups)


def test_opened_breach_adds_a_side_pack_and_reaches_a_trophy_receipt():
    world = _three_wave_graveyard()
    with pytest.raises(Refused):
        world.choose_breach("trophy")
    _clear_one_wave(world)
    _clear_one_wave(world)
    assert world.breach_offered
    world.choose_breach("trophy")
    assert world.clone().breach_mode == "trophy"
    world.call_wave()
    while world.schedule:
        world.step()
    side = [monster for monster in world.monsters if monster.breach]
    assert len(side) == BREACHES["graveyard"].count
    assert all(monster.route == "breach" for monster in side)
    assert [monster.elite_name for monster in side if monster.elite_name] == ["Ashwing"]
    for monster in list(world.monsters):
        world._hurt(monster, monster.hp, None)
    world.step()
    assert world.outcome == "victory"
    assert world.breach_cleared


def test_side_leak_voids_cash_cache_even_after_other_side_kills():
    world = _three_wave_graveyard()
    _clear_one_wave(world)
    _clear_one_wave(world)
    world.choose_breach("cash")
    world.call_wave()
    while world.schedule:
        world.step()
    side = next(monster for monster in world.monsters if monster.breach)
    side.s = world.level.route(side.route).length - 0.01
    world.step()
    before = world.gold
    ordinary_kill_gold = sum(monster.bounty for monster in world.monsters if not monster.breach)
    side_kill_gold = sum(monster.bounty for monster in world.monsters if monster.breach)
    for monster in list(world.monsters):
        world._hurt(monster, monster.hp, None)
    world.step()
    assert world.breach_failed and not world.breach_cleared
    assert world.gold == before + ordinary_kill_gold + side_kill_gold + world.waves[-1].bonus

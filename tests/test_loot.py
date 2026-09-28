"""Monster salvage, its same-run sale, and the trade with future forging."""

from dataclasses import replace

import pytest

from hellward.sim.balance import BALANCE
from hellward.sim.campaign import TRISTRAM
from hellward.sim.content import Group, Wave
from hellward.sim.model import Refused, World


def _short_world() -> World:
    wave = Wave((Group("fallen", 1, 1.0),), 0)
    location = replace(TRISTRAM, waves=(wave, wave), wave_names=("first", "second"))
    return World(location, seed=12)


def test_a_seeded_salvage_drop_can_be_sold_during_a_break():
    world = _short_world()
    world.call_wave()
    while world.schedule:
        world.step()
    monster = world.monsters[0]
    assert monster.salvage == 1
    assert world.clone().monsters[0].salvage == 1
    world._hurt(monster, monster.hp, None)
    world.step()
    assert world.salvage_held == 1
    assert world.break_left is not None
    before = world.gold
    world.sell_salvage(1)
    assert world.salvage_held == 0
    assert world.gold == before + BALANCE.salvage_sale_gold(0)
    assert world.clone().salvage_sold == 1


def test_a_leak_loses_its_assigned_salvage_and_sales_wait_for_breaks():
    world = _short_world()
    world.call_wave()
    while world.schedule:
        world.step()
    with pytest.raises(Refused, match="break"):
        world.sell_salvage(1)
    monster = world.monsters[0]
    monster.s = world.level.route(monster.route).length - 0.01
    world.step()
    assert world.salvage_held == 0
    assert world.break_left is not None
    with pytest.raises(Refused, match="salvage"):
        world.sell_salvage(1)

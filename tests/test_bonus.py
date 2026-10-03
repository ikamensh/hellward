"""Bonus waves: the wager, the pack while the break clock stops, and the clean clear's pay."""

from __future__ import annotations

from dataclasses import replace

import pytest

from hellward.sim.bonus import BonusPack, draw
from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.content import MONSTERS, Wave
from hellward.sim.locations.common import g
from hellward.sim.model import SIM_DT, Refused, World


def micro(*waves: Wave) -> World:
    """Tristram's ground with authored waves: breaks on demand."""
    return World(replace(LOCATIONS["tristram"], waves=waves,
                         wave_names=tuple(f"pack{i}" for i in range(len(waves)))), seed=1)


def done(world: World) -> bool:
    """Quiet: decided, or a break with nothing standing, spawning or summoned."""
    return world.outcome is not None or (world.break_left is not None and world.bonus is None
                                         and not world.monsters and not world.schedule)


def slay(world: World) -> None:
    """Fell every monster as it comes until quiet."""
    for _ in range(20000):
        for m in list(world.monsters):
            world._hurt(m, 10000.0, None)
        world.step(SIM_DT)
        if done(world):
            return
    raise AssertionError("undecided")


def amble(world: World) -> None:
    """Let the defence play itself out, killing nothing."""
    for _ in range(20000):
        world.step(SIM_DT)
        if done(world):
            return
    raise AssertionError("undecided")


def broken_in() -> World:
    """A world in the break after its second wave, rich enough for any wager."""
    world = micro(*[Wave((g("fallen", 1),), 10) for _ in range(3)])
    world.gold = 1000
    for _ in range(2):
        world.call_wave()
        slay(world)
    assert world.break_left is not None and world.outcome is None
    return world


def test_summon_is_refused_outside_its_time_and_purse():
    one = Wave((g("fallen", 1),), 10)
    world = micro(one, one, one)
    world.gold = 1000
    pack = draw(world.location, 1, 1, 0)
    with pytest.raises(Refused, match="from wave 2's break"):
        world.summon(pack)   # the first break: no wave cleared yet
    world.call_wave()
    with pytest.raises(Refused, match="during a break"):
        world.summon(pack)   # a wave walks
    slay(world)
    world.call_wave()
    slay(world)
    poor = draw(world.location, 1, 1, 0)
    world.gold = poor.wager - 1
    with pytest.raises(Refused, match=f"takes {poor.wager} gold"):
        world.summon(poor)
    world.gold = 1000
    world.summon(draw(world.location, 1, 1, 0))
    with pytest.raises(Refused, match="already fights"):
        world.summon(draw(world.location, 2, 1, 0))


def test_summon_wagers_spawns_scaled_and_stops_the_break():
    world = broken_in()
    pack = draw(world.location, 2, 1, 0)
    left, gold = world.break_left, world.gold
    world.summon(pack)
    assert world.gold == gold - pack.wager
    assert world.break_left is None and not world.can_call_wave
    assert ("bonus", 2, "summoned") in world.events
    while not world.monsters:
        world.step(SIM_DT)
    tougher = world.monsters[0]
    assert tougher.bonus and tougher.bounty == 0 and tougher.salvage == 0
    assert tougher.max_hp == tougher.kind.hp * pack.life_factor
    assert world.break_left is None   # the clock stops while the pack lives
    assert left is not None


def test_a_clean_clear_pays_the_wager_the_profit_and_the_xp_and_resumes():
    world = broken_in()
    pack = draw(world.location, 2, 1, 0)
    saved, gold, xp = world.break_left, world.gold - pack.wager, world.xp_total
    world.summon(pack)
    slay(world)
    assert ("bonus", 2, "cleared") in world.events
    assert world.gold == gold + pack.wager + pack.profit
    assert world.xp_total == xp + pack.xp
    assert world.break_left == saved   # the clock resumes where it stopped
    assert world.can_call_wave
    world.step(SIM_DT)
    assert world.break_left is not None and world.break_left < saved


def test_a_leak_fails_the_pack_and_pays_nothing():
    world = broken_in()
    pack = draw(world.location, 1, 1, 0)
    gold, xp, lives = world.gold - pack.wager, world.xp_total, world.lives
    world.summon(pack)
    amble(world)   # no towers: the pack walks out
    assert ("bonus", 1, "failed") in world.events
    assert world.gold == gold and world.xp_total == xp
    assert world.lives < lives


def test_a_bonus_kill_pays_no_bounty_and_no_xp_mid_fight():
    world = broken_in()
    pack = draw(world.location, 1, 1, 0)
    world.summon(pack)
    while not world.monsters:
        world.step(SIM_DT)
    gold, xp = world.gold, world.xp_total
    world._hurt(world.monsters[0], 10000.0, None)
    assert (world.gold, world.xp_total) == (gold, xp)


def test_a_boss_strike_fails_the_pack_but_it_fights_on_until_slain():
    world = broken_in()
    pack = BonusPack(1, (g("azazel", 1),), 1.0, None, wager=12, profit=24, xp=10.0, lives=5)
    world.summon(pack)
    while not [e for e in world.events if e[0] == "returned"]:
        world.step(SIM_DT)
        if world.outcome is not None:
            raise AssertionError("the shrine fell to one boss")
    assert world.bonus is not None and world.bonus.leaked
    world._hurt(world.monsters[0], 100000.0, None)
    slay(world)
    assert ("bonus", 1, "failed") in world.events
    assert world.wave_alive[world.wave] == 0


def test_the_breached_locations_lend_their_elite_to_stake_two():
    assert BREACHES, "no breached locations to lend from"
    for key in BREACHES:
        index = ORDER.index(key)
        elite = draw(LOCATIONS[key], 2, 3, index).extra
        assert elite == BREACHES[key].elite.kind


def test_a_clone_carries_the_live_pack():
    world = broken_in()
    world.summon(draw(world.location, 3, 1, 0))
    while not world.monsters:
        world.step(SIM_DT)
    clone = world.clone()
    assert clone.bonus is not None and world.bonus is not None
    assert (clone.bonus.stake, clone.bonus.alive, clone.bonus.leaked) == (
        world.bonus.stake, world.bonus.alive, world.bonus.leaked)
    assert len(clone.bonus_schedule) == len(world.bonus_schedule)
    assert clone.bonus is not world.bonus


def test_every_location_draws_a_pack_at_every_stake():
    for index, key in enumerate(ORDER):
        location = LOCATIONS[key]
        for stake in (1, 2, 3):
            pack = draw(location, stake, 9, index)
            assert pack.pack and pack.lives > 0 and pack.wager > 0 and pack.profit > 0
            assert pack.extra is None or pack.extra in MONSTERS


def test_each_stake_faces_a_coming_host_never_the_climax_for_stake_three_nor_a_boss():
    location = LOCATIONS["graveyard"]
    waves = location.waves
    first = draw(location, 1, 7, 0, wave=0)
    assert [g.kind for g in first.groups] == [g.kind for g in waves[1].groups
                                              if not MONSTERS[g.kind].boss]
    third = draw(location, 3, 7, 0, wave=0)
    assert [g.kind for g in third.groups] == [g.kind for g in waves[2].groups
                                              if not MONSTERS[g.kind].boss]
    capped = draw(location, 3, 7, 0, wave=len(waves) - 2)
    assert [g.kind for g in capped.groups] == [g.kind for g in waves[-2].groups
                                               if not MONSTERS[g.kind].boss]
    first_capped = draw(location, 1, 7, 0, wave=len(waves) - 2)
    assert [g.kind for g in first_capped.groups] == [g.kind for g in waves[-1].groups
                                                     if not MONSTERS[g.kind].boss]
    for index, key in enumerate(ORDER):
        for stake in (1, 2, 3):
            pack = draw(LOCATIONS[key], stake, 9, index, wave=1)
            assert all(not MONSTERS[g.kind].boss for g in pack.pack)

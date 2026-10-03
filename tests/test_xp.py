"""Experience: kills and cleared waves count it, thresholds level up and refill the mana."""

from __future__ import annotations

from dataclasses import replace

from hellward.sim import planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import Wave
from hellward.sim.locations.common import g
from hellward.sim.model import SIM_DT, World
from hellward.sim.players import PLAYERS
from hellward.sim.players.hands import defend, reference_kit
from hellward.sim.xp import clear_xp, kill_xp, xp_next


def micro(*groups) -> World:
    """Tristram's ground with one authored wave: kills and clears on demand."""
    pack = Wave(groups, 10)
    return World(replace(LOCATIONS["tristram"], waves=(pack,), wave_names=("pack",)), seed=1)


def until(world: World) -> None:
    """Step to the defence's decision, bounded against a stuck world."""
    for _ in range(20000):
        if world.outcome is not None:
            return
        world.step(SIM_DT)
    raise AssertionError("undecided")


def test_a_kill_grants_its_felled_life_and_a_clear_grants_its_number():
    world = micro(g("fallen", 1))
    world.call_wave()
    while not world.monsters:
        world.step(SIM_DT)
    m = world.monsters[0]
    world._hurt(m, 10000.0, None)
    assert world.xp == kill_xp(m.max_hp)
    while world.outcome is None:
        world.step(SIM_DT)
    assert world.xp == kill_xp(m.max_hp) + clear_xp(1)
    assert clear_xp(3) == 3 * clear_xp(1)


def test_crossing_the_threshold_levels_up_refills_the_mana_and_tells_the_view():
    world = micro(g("fallen", 1))
    world.mana = 5.0
    world._earn(xp_next(1) + xp_next(2))
    assert world.xp_level == 3
    assert world.mana == world.mana_max
    assert [e for e in world.events if e[0] == "level_up"] == [("level_up", 2), ("level_up", 3)]


def test_exactly_enough_xp_always_levels():
    world = micro(g("fallen", 1))
    world._earn(xp_next(1))
    assert world.xp_level == 2 and world.xp == 0.0


def test_the_levels_crossed_do_not_evaporate_from_the_total():
    world = micro(g("fallen", 1))
    world._earn(xp_next(1) + xp_next(2) + 3.0)
    assert world.xp_level == 3
    assert world.xp_total == xp_next(1) + xp_next(2) + 3.0


def test_a_real_defence_counts_kills_clears_and_levels():
    seen: list = []
    player = PLAYERS["warden"](1)
    world, _ = defend(reference_kit(LOCATIONS["tristram"], player.draft(LOCATIONS["tristram"], 0), 1),
                      player, planner=planner.smart, watch=lambda w: seen.extend(w.events))
    assert world.outcome == "victory"
    assert world.xp > clear_xp(1)
    assert world.xp_level >= 2
    assert ("level_up", 2) in seen


def test_a_clone_carries_the_count():
    world = micro(g("fallen", 1))
    world._earn(5.0)
    clone = world.clone()
    assert (clone.xp, clone.xp_level) == (world.xp, world.xp_level)


def test_spawn_and_built_carry_their_kinds():
    world = micro(g("fallen", 1))
    world.gold = 1000
    tile = next((x, y) for y in range(world.level.height) for x in range(world.level.width)
                if world.buildable(x, y))
    tower = world.build("arrow", tile)
    assert ("built", tower.id, "arrow") in world.events
    world.call_wave()
    while not [e for e in world.events if e[0] == "spawn"]:
        world.step(SIM_DT)
    assert world.monsters and ("spawn", world.monsters[0].id, "fallen") in world.events


def test_a_leak_grants_no_kill_xp_only_the_clear():
    world = micro(g("fallen", 1))
    world.call_wave()
    until(world)
    assert world.lives == 19 and world.xp == clear_xp(1)

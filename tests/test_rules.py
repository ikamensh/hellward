"""The rules, through the World's public commands and its step."""

import math
import random
from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.content import DOOR, MONSTERS, SPELLS, START_LIVES, Curse, Group, Wave
from hellward.sim.level import Tile
from hellward.sim.model import SIM_DT, Refused, World

CATHEDRAL = campaign.CATHEDRAL.level


def with_waves(*waves: Wave) -> campaign.Location:
    """The cathedral with these waves instead of its own."""
    return replace(campaign.CATHEDRAL, waves=waves, wave_names=tuple(f"wave {i}" for i in range(len(waves))))


def wave_of(kind: str, count: int = 1, interval: float = 1.0) -> campaign.Location:
    return with_waves(Wave((Group(kind, count, interval),), 10))


def run(world: World, seconds: float, dt: float = SIM_DT) -> None:
    end = world.time + seconds
    while world.time < end - 1e-9 and world.outcome is None:
        world.step(dt)


def started(world: World) -> World:
    world.call_wave()
    return world


def test_coverage_is_the_path_within_reach():
    """Property: s is covered exactly when the path point at s lies within reach of the tile's centre."""
    rng = random.Random(4)
    for _ in range(40):
        tile = (rng.randrange(CATHEDRAL.width), rng.randrange(CATHEDRAL.height))
        reach = rng.uniform(0.8, 4.0)
        spans = CATHEDRAL.coverage(tile, reach)
        for i in range(400):
            s = CATHEDRAL.length * i / 399
            x, y = CATHEDRAL.point(s)
            inside = math.hypot(x - tile[0] - 0.5, y - tile[1] - 0.5) <= reach
            covered = any(a - 1e-6 <= s <= b + 1e-6 for a, b in spans)
            near_edge = abs(math.hypot(x - tile[0] - 0.5, y - tile[1] - 0.5) - reach) < 1e-3
            assert covered == inside or near_edge


def test_door_sockets_are_arches_on_the_path():
    for x, y in CATHEDRAL.doors:
        assert CATHEDRAL.tile(x, y) is Tile.DOOR
        assert {CATHEDRAL.tile(x - 1, y), CATHEDRAL.tile(x + 1, y)} == {Tile.WALL}


def test_an_unopposed_monster_walks_the_path_and_costs_its_lives():
    world = started(World(wave_of("overlord")))
    run(world, CATHEDRAL.length / MONSTERS["overlord"].speed + 2)
    assert world.lives == START_LIVES - MONSTERS["overlord"].lives


def test_a_gate_holds_walkers_until_they_break_it():
    world = World(wave_of("zombie", count=3))
    world.gold = 1000
    world.build_door(0)
    started(world)
    door_s = CATHEDRAL.door_s[0]
    run(world, door_s / MONSTERS["zombie"].speed + 6)
    assert world.doors[0].built
    assert world.doors[0].hp < DOOR.hp
    assert all(m.s < door_s for m in world.monsters)
    run(world, 200)
    assert not world.doors[0].built
    assert world.lives == START_LIVES - 3


def test_flyers_pass_over_a_gate():
    world = World(wave_of("gargoyle"))
    world.gold = 1000
    for i in range(3):
        world.build_door(i)
    started(world)
    run(world, CATHEDRAL.length / MONSTERS["gargoyle"].speed + 2)
    assert world.lives == START_LIVES - 1
    assert all(d.hp == DOOR.hp for d in world.doors)


def kill_time(curse: Curse | None) -> float:
    world = World(wave_of("zombie"))
    world.gold = 1000
    tower = world.build("pyre", (4, 3))
    if curse is not None:
        tower.curses[curse] = 1000.0
    started(world)
    while world.monsters or world.schedule:
        world.step()
        assert world.time < 300
    return world.time


def test_every_curse_but_none_slows_a_kill():
    plain = kill_time(None)
    for curse in (Curse.WEAKEN, Curse.DECREPIFY, Curse.DIM_VISION):
        assert kill_time(curse) > plain, curse


def test_bone_prison_silences_and_cleanse_lifts_it():
    world = World(wave_of("zombie"))
    world.gold = 1000
    tower = world.build("pyre", (4, 3))
    tower.curses[Curse.BONE_PRISON] = 1000.0   # held open while the zombie walks into reach
    started(world)
    run(world, 6)   # well inside the pyre's reach by now
    zombie = world.monsters[0]
    assert zombie.hp == pytest.approx(zombie.max_hp)
    world.mana = SPELLS["cleanse"].mana
    world.cleanse(tower.id)
    assert world.mana == 0 and not tower.curses
    run(world, 3)
    assert zombie.hp < zombie.max_hp
    with pytest.raises(Refused):
        world.cleanse(tower.id)


def test_commands_refuse_what_the_rules_forbid():
    world = World()
    with pytest.raises(Refused):
        world.build("pyre", CATHEDRAL.path_tiles[3])
    world.build("pyre", (4, 3))
    with pytest.raises(Refused):
        world.build("frost", (4, 3))
    world.gold = 0
    with pytest.raises(Refused):
        world.build("frost", (5, 3))
    with pytest.raises(Refused):
        world.build_door(1)


def test_selling_refunds_most_of_what_was_spent():
    world = World()
    tower = world.build("storm", (4, 3))
    world.upgrade(tower.id)
    spent = campaign.CATHEDRAL.start_gold - world.gold
    refund = world.sell(tower.id)
    assert 0.6 * spent <= refund < spent
    assert not world.towers


def test_a_clone_plays_on_exactly_like_its_original_and_leaves_it_alone():
    world = World(seed=5)
    world.gold = 2000
    for kind, tile in (("pyre", (4, 3)), ("storm", (7, 8)), ("frost", (10, 9)), ("plague", (14, 6))):
        world.build(kind, tile)
    world.build_door(1)
    started(world)
    run(world, 20)
    twin = world.clone()
    before = [(m.id, m.s, m.hp) for m in world.monsters]
    run(twin, 15)
    assert [(m.id, m.s, m.hp) for m in world.monsters] == before
    run(world, 15)
    assert [(m.id, m.s, m.hp) for m in world.monsters] == [(m.id, m.s, m.hp) for m in twin.monsters]
    assert (world.gold, world.lives, world.doors[1].hp) == (twin.gold, twin.lives, twin.doors[1].hp)


def test_each_cleared_wave_pays_its_bonus_once_even_when_called_early():
    waves = (Wave((Group("fallen", 2, 0.5),), 11), Wave((Group("fallen", 2, 0.5),), 13), Wave((Group("fallen", 1, 1),), 17))
    world = World(with_waves(*waves))
    world.gold = 1000
    world.build("storm", (7, 3))
    world.build("pyre", (4, 3))
    started(world)
    run(world, 1.5)
    world.call_wave()   # the first wave's fallen are still walking
    gold = world.gold
    kills = []
    while world.outcome is None:
        world.step()
        kills += [e for e in world.events if e[0] in ("death", "cleared")]
        world.events.clear()
        if world.can_call_wave:
            world.call_wave()
        assert world.time < 400
    cleared = [e[1] for e in kills if e[0] == "cleared"]
    assert sorted(cleared) == [0, 1, 2]
    bounties = sum(e[5] for e in kills if e[0] == "death")
    assert world.gold >= gold + bounties + 11 + 13 + 17 - 1   # early-call gold may add to it
    assert world.outcome == "victory"


def test_a_broken_gate_lies_in_rubble_until_the_fight_dies_down_between_waves():
    zombies = Wave((Group("zombie", 2, 0.3),), 10)
    world = World(with_waves(zombies, zombies))
    world.gold = 1000
    world.build_door(0)
    started(world)
    while world.doors[0].built:
        run(world, 1)
        assert world.time < 300
    run(world, 2)   # the zombies have walked on out of the arch
    with pytest.raises(Refused, match="rubble"):
        world.build_door(0)
    while world.break_left is None:   # the wave's last monster falls or gets through, and the break begins
        run(world, 1)
        assert world.time < 600
    world.build_door(0)
    assert world.doors[0].built


def test_a_monster_a_spell_kills_between_steps_walks_no_further():
    world = World(wave_of("fallen"))
    started(world)
    run(world, 2)
    fallen = world.monsters[0]
    world.mana = 100
    world.smite(fallen.id)
    assert not world.monsters
    lives = world.lives
    run(world, 1)
    assert world.lives == lives and world.kills == 1

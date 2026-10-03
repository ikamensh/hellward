"""The rules, through the World's public commands and its step."""

import math
import random
from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.content import MONSTERS, SPELLS, START_LIVES, TOWERS, Curse, Group, Wave
from hellward.sim.level import Level, Tile
from hellward.sim.model import SIM_DT, Refused, World

ARENA = Level("Rules field", 20, 12,
              ((0, 5), (3, 5), (3, 7), (9, 7), (9, 5), (15, 5), (15, 7), (19, 7)),
              ((3, 6), (9, 6), (15, 6)))


def with_waves(*waves: Wave) -> campaign.Location:
    """An authored arena with these waves at their base life, independent of campaign layouts and unlocks."""
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    return replace(campaign.CATHEDRAL, level=ARENA, arsenal=arsenal, waves=waves,
                   wave_names=tuple(f"wave {i}" for i in range(len(waves))))


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
        tile = (rng.randrange(ARENA.width), rng.randrange(ARENA.height))
        reach = rng.uniform(0.8, 4.0)
        spans = ARENA.coverage(tile, reach)
        for i in range(400):
            s = ARENA.length * i / 399
            x, y = ARENA.point(s)
            inside = math.hypot(x - tile[0] - 0.5, y - tile[1] - 0.5) <= reach
            covered = any(a - 1e-6 <= s <= b + 1e-6 for a, b in spans)
            near_edge = abs(math.hypot(x - tile[0] - 0.5, y - tile[1] - 0.5) - reach) < 1e-3
            assert covered == inside or near_edge


def test_door_sockets_are_arches_on_the_path():
    for x, y in ARENA.doors:
        assert ARENA.tile(x, y) is Tile.DOOR
        assert {ARENA.tile(x - 1, y), ARENA.tile(x + 1, y)} == {Tile.WALL}


def test_an_unopposed_monster_walks_the_path_and_costs_its_lives():
    world = started(World(wave_of("overlord")))
    run(world, ARENA.length / MONSTERS["overlord"].speed + 2)
    assert world.lives == START_LIVES - MONSTERS["overlord"].lives


def test_an_ordinary_monster_strikes_the_shrine_and_is_gone():
    world = started(World(wave_of("zombie")))
    run(world, ARENA.length / MONSTERS["zombie"].speed + 2)
    leaks = [e for e in world.events if e[0] == "leak"]
    assert len(leaks) == 1 and leaks[0][2:] == ("zombie", 1)
    assert not world.monsters and world.lives == START_LIVES - 1


def test_a_boss_strikes_for_five_and_walks_again_from_its_portal_with_its_life():
    world = started(World(wave_of("azazel"), hardness=50.0))   # nothing here kills him
    world.gold = 1000
    world.build("arrow", (4, 3))
    walk = ARENA.length / MONSTERS["azazel"].speed
    run(world, walk + 2)
    azazel = world.monsters[0]
    assert azazel.kind.boss and azazel.strikes == 1 and azazel.s < 3
    assert [e for e in world.events if e[0] == "returned"] == [("returned", azazel.id, "azazel", 5, 1)]
    assert not [e for e in world.events if e[0] == "leak"]
    assert world.lives == START_LIVES - 5
    hurt = azazel.hp
    assert hurt < azazel.max_hp   # the arrows' work stays on him
    run(world, walk)
    assert azazel.strikes == 2 and world.lives == START_LIVES - 10 and azazel.hp <= hurt
    run(world, 2 * walk)
    assert world.outcome == "defeat"   # four strikes: 20 lives


def test_a_gate_holds_walkers_until_they_break_it():
    world = World(wave_of("zombie", count=3))
    world.gold = 1000
    world.build_door(0)
    started(world)
    door_s = ARENA.door_s[0]
    run(world, door_s / MONSTERS["zombie"].speed + 6)
    assert world.doors[0].built
    assert world.doors[0].hp < world.gate_life
    assert all(m.s <= door_s for m in world.monsters)
    run(world, 200)
    assert not world.doors[0].built
    assert world.lives == START_LIVES - 3


def test_flyers_pass_over_a_gate():
    world = World(wave_of("gargoyle"))
    world.gold = 1000
    for i in range(3):
        world.build_door(i)
    started(world)
    run(world, ARENA.length / MONSTERS["gargoyle"].speed + 2)
    assert world.lives == START_LIVES - 1
    assert all(d.hp == world.gate_life for d in world.doors)


def kill_time(curse: Curse | None) -> float:
    world = World(wave_of("zombie"))
    world.gold = 1000
    tower = world.build("pyre", (7, 8))
    if curse is not None:
        tower.curses[curse] = 1000.0
    started(world)
    while world.monsters or world.schedule:
        world.step()
        assert world.time < 300
    assert world.kills == 1 and world.lives == START_LIVES
    return world.time


def test_every_curse_but_none_slows_a_kill():
    plain = kill_time(None)
    for curse in (Curse.WEAKEN, Curse.DECREPIFY, Curse.DIM_VISION):
        assert kill_time(curse) > plain, curse


def test_bone_prison_silences_until_it_lapses():
    world = World(wave_of("zombie"))
    world.gold = 1000
    tower = world.build("pyre", (4, 4))
    tower.curses[Curse.BONE_PRISON] = 6.0   # held while the zombie walks into reach
    started(world)
    run(world, 6 - SIM_DT)   # well inside the pyre's reach by now
    zombie = world.monsters[0]
    assert zombie.hp == pytest.approx(zombie.max_hp)
    run(world, 3)
    assert not tower.curses
    assert zombie.hp < zombie.max_hp


def test_commands_refuse_what_the_rules_forbid():
    world = World(wave_of("fallen"))
    with pytest.raises(Refused):
        world.build("pyre", ARENA.path_tiles[3])
    world.build("pyre", (4, 3))
    with pytest.raises(Refused):
        world.build("frost", (4, 3))
    world.gold = 0
    with pytest.raises(Refused):
        world.build("frost", (5, 3))
    with pytest.raises(Refused):
        world.build_door(1)


def test_selling_refunds_most_of_what_was_spent():
    from hellward.sim.skills import perks
    world = World(wave_of("fallen"), perks=perks({"unlock_storm", "adept_lightning"}))
    world.gold = 3 * world.cost("storm")
    initial_gold = world.gold
    tower = world.build("storm", (4, 3))
    world.upgrade(tower.id)
    spent = initial_gold - world.gold
    refund = world.sell(tower.id)
    assert 0.6 * spent <= refund < spent
    assert not world.towers


def test_a_clone_plays_on_exactly_like_its_original_and_leaves_it_alone():
    world = World(with_waves(Wave((Group("overlord", 4, 3.0), Group("zombie", 10, 1.0)), 10)), seed=5)
    world.gold = 2000
    for kind, tile in (("pyre", (4, 3)), ("storm", (7, 8)), ("frost", (10, 9)), ("plague", (13, 6))):
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
    fallen.hp = min(fallen.hp, SPELLS["smite"].damage * world.power())
    world.smite(fallen.id)
    assert not world.monsters
    lives = world.lives
    run(world, 1)
    assert world.lives == lives and world.kills == 1

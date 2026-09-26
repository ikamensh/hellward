"""Curses strike an area: a marked spot, a radius, and every tower the circle catches."""

from dataclasses import replace

import pytest

from hellward.sim import campaign, planner
from hellward.sim.content import CURSES, MONSTERS, Curse, Element, Group, MonsterKind, Wave
from hellward.sim.model import SIM_DT, Monster, Refused, Tower, World

CENTRE = (12, 2)   # every tile of the 3x3 block around it is bare floor on the cathedral


def waves_of(kind: str) -> campaign.Location:
    pack = Wave((Group(kind, 1, 1.0),), 10)
    return replace(campaign.CATHEDRAL, waves=(pack,), wave_names=("pack",), life=1.0)


def world_with_leader(kind: str = "shaman", seed: int = 7) -> World:
    world = World(waves_of(kind), seed=seed)
    world.gold = 10000
    world.call_wave()
    while not any(m.kind.key == kind for m in world.monsters):
        world.step()
        assert world.time < 30
    return world


def park(world: World, leader_id: int, spot: tuple[int, int]) -> None:
    """Hold the leader on the path tile nearest the spot, well within its cast."""
    leader = world.monster(leader_id)
    tile = min(world.level.path_tiles, key=lambda t: (t[0] - spot[0]) ** 2 + (t[1] - spot[1]) ** 2)
    leader.s = world.level.s_of(tile)


def leader_id(world: World, kind: str) -> int:
    return next(m.id for m in world.monsters if m.kind.key == kind)


def cursed_events(world: World) -> list[tuple]:
    return [e for e in world.events if e[0] == "cursed"]


def test_weaken_catches_a_3x3_block_and_no_tower_two_tiles_away():
    world = world_with_leader("shaman")
    block = [(CENTRE[0] + dx, CENTRE[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    assert all(world.level.buildable(*tile) for tile in block)
    far = next(t for t in [(14, 2), (12, 4), (10, 2)] if world.level.buildable(*t))
    assert (far[0] - CENTRE[0]) ** 2 + (far[1] - CENTRE[1]) ** 2 == 4
    for tile in block:
        world.build("pyre", tile)
    world.build("storm", far)
    assert [t.tile for t in world.caught(CENTRE, CURSES[Curse.WEAKEN].radius)] == block
    lid = leader_id(world, "shaman")
    park(world, lid, CENTRE)
    world.events.clear()
    world._land(lid, Curse.WEAKEN, CENTRE)
    near = {t.id for t in world.towers.values() if t.tile in block}
    assert len(near) == 9
    for t in world.towers.values():
        if t.tile in block:
            assert t.curses == {Curse.WEAKEN: CURSES[Curse.WEAKEN].duration}
        else:
            assert not t.curses
    assert world.curses_landed == 1
    assert cursed_events(world) == [("cursed", lid, CENTRE, Curse.WEAKEN, tuple(sorted(near)))]


def test_dim_vision_catches_a_knights_move_away():
    world = world_with_leader("priest")
    knight, diagonal = (CENTRE[0] + 2, CENTRE[1] + 1), (CENTRE[0] + 1, CENTRE[1] + 1)
    assert world.level.buildable(*knight) and world.level.buildable(*diagonal)
    world.build("pyre", knight)
    world.build("storm", diagonal)
    lid = leader_id(world, "priest")
    park(world, lid, CENTRE)
    world.events.clear()
    world._land(lid, Curse.DIM_VISION, CENTRE)
    caught = {t.id for t in world.towers.values() if t.curses}
    assert len(caught) == 2
    assert world.curses_landed == 1
    assert cursed_events(world) == [("cursed", lid, CENTRE, Curse.DIM_VISION, tuple(sorted(caught)))]


def test_bone_prison_does_not_catch_a_diagonal_neighbour():
    world = world_with_leader("priest")
    diagonal = (CENTRE[0] + 1, CENTRE[1] + 1)
    assert world.level.buildable(*diagonal)
    world.build("pyre", diagonal)
    lid = leader_id(world, "priest")
    park(world, lid, CENTRE)
    world.events.clear()
    world._land(lid, Curse.BONE_PRISON, CENTRE)
    assert not any(t.curses for t in world.towers.values())
    assert cursed_events(world) == []
    assert [e for e in world.events if e[0] == "fizzle"] == [("fizzle", lid, CENTRE)]


def test_a_warded_tower_is_spared_and_the_curse_counts_once():
    world = world_with_leader("shaman")
    tiles = [CENTRE, (CENTRE[0] + 1, CENTRE[1]), (CENTRE[0], CENTRE[1] + 1)]
    for tile in tiles:
        world.build("pyre", tile)
    warded = world.tower_at(CENTRE)
    warded.ward = 8.0
    lid = leader_id(world, "shaman")
    park(world, lid, CENTRE)
    world.events.clear()
    world._land(lid, Curse.WEAKEN, CENTRE)
    assert not warded.curses
    others = sorted(t.id for t in world.towers.values() if t is not warded)
    assert cursed_events(world) == [("cursed", lid, CENTRE, Curse.WEAKEN, tuple(others))]
    assert [e for e in world.events if e[0] == "ward_holds"] == [("ward_holds", lid, warded.id, Curse.WEAKEN)]
    assert world.curses_landed == 1


def test_selling_the_tower_under_the_mark_does_not_stop_the_curse():
    world = world_with_leader("shaman")
    world.build("pyre", CENTRE)
    world.build("storm", (CENTRE[0] + 1, CENTRE[1]))
    neighbour = world.tower_at((CENTRE[0] + 1, CENTRE[1]))
    world.sell(world.tower_at(CENTRE).id)
    assert world.tower_at(CENTRE) is None
    lid = leader_id(world, "shaman")
    park(world, lid, CENTRE)
    world.events.clear()
    world._land(lid, Curse.WEAKEN, CENTRE)
    assert neighbour.curses == {Curse.WEAKEN: CURSES[Curse.WEAKEN].duration}
    assert cursed_events(world) == [("cursed", lid, CENTRE, Curse.WEAKEN, (neighbour.id,))]


def test_a_cursed_tower_cannot_be_sold():
    world = world_with_leader("shaman")
    tower = world.build("pyre", CENTRE)
    lid = leader_id(world, "shaman")
    park(world, lid, CENTRE)
    world._land(lid, Curse.WEAKEN, CENTRE)
    assert tower.curses
    gold = world.gold
    with pytest.raises(Refused, match="The curse holds it."):
        world.sell(tower.id)
    assert world.tower_at(CENTRE) is tower and world.gold == gold


def chill_world() -> tuple[World, Tower, float]:
    world = World(campaign.CATHEDRAL, seed=11)
    world.gold = 10000
    tower = world.build("frost", (4, 3))
    s = next(s for s in (i * 0.25 for i in range(int(world.level.length * 4))) if world.in_reach(tower, s))
    return world, tower, s


def chill_monster(world: World, s: float, kind: MonsterKind, monster_id: int) -> Monster:
    m = Monster(monster_id, kind, 0, 0.0, 0.0, kind.hp, 0.0)
    m.s = s
    world.monsters.append(m)
    return m


def test_frost_chill_follows_cold_resistance():
    world, tower, s = chill_world()
    fallen = chill_monster(world, s, MONSTERS["fallen"], 101)
    skeleton = chill_monster(world, s, MONSTERS["skeleton"], 102)
    world.step(SIM_DT)
    assert [e[0] for e in world.events if e[0] == "nova"] == ["nova"]
    assert fallen.chill == pytest.approx(tower.stats.chill)
    assert skeleton.chill == pytest.approx(tower.stats.chill * 0.75)
    assert fallen.chill_left > 0 and skeleton.chill_left > 0


def test_a_cold_immune_monster_is_not_chilled_at_all():
    world, _, s = chill_world()
    immune = replace(MONSTERS["fallen"], key="icebound", name="Icebound", resist={Element.COLD: 1.0})
    monster = chill_monster(world, s, immune, 103)
    world.step(SIM_DT)
    assert monster.chill == 0.0
    assert monster.chill_left == 0.0


def test_the_planner_prefers_the_spot_whose_circle_holds_more_working_towers():
    pack = Wave((Group("skeleton", 6, 0.6), Group("shaman", 1, 1, start=3.0)), 10)
    world = World(replace(campaign.CATHEDRAL, waves=(pack,), wave_names=("pack",), life=1.0))
    world.gold = 5000
    pair = [(6, 1), (7, 1)]
    single = (4, 3)
    for tile in (*pair, single):
        world.build("pyre", tile)
    world.call_wave()
    while world.time < 5.5:
        world.step()
    shaman = leader_id(world, "shaman")
    options = planner.candidates(world, world.monster(shaman))
    assert sum(1 for o in options if o.spot == pair[1]) == 0   # it catches the same towers as its neighbour
    decision = planner.decide(world, shaman, timing=False)
    assert decision.cast is not None
    assert decision.cast.spot == pair[0]
    assert [t.tile for t in world.caught(decision.cast.spot, CURSES[decision.cast.curse].radius)] == pair

"""The four spells, through the World's commands: what each does to monsters, gates and towers, and that none of them
touches the leaders' curses (S1)."""

from dataclasses import replace

import pytest

from hellward.sim import campaign, planner
from hellward.sim.campaign import g
from hellward.sim.content import MONSTERS, SPELLS, TOWERS, Curse, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import SIM_DT, Refused, World
from hellward.sim.skills import perks


ARENA = Level("Spell field", 16, 11, ((0, 6), (4, 6), (4, 8), (10, 8), (10, 6), (15, 6)), ((4, 7),))


def world_of(*groups: Group, location: campaign.Location | None = None, **kwargs) -> World:
    base = location if location is not None else campaign.CATACOMBS
    level = base.level if location is not None else ARENA
    if location is None:
        arsenal = replace(base.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
        base = replace(base, arsenal=arsenal)
    waves = (Wave(tuple(groups), 10),)
    return World(replace(base, level=level, waves=waves, wave_names=("test",)), **kwargs)


def run(world: World, seconds: float) -> None:
    end = world.time + seconds
    while world.time < end - 1e-9 and world.outcome is None:
        world.step(SIM_DT)


def events(world: World, kind: str) -> list[tuple]:
    return [e for e in world.events if e[0] == kind]


def chanting_leader(**kwargs) -> tuple[World, int]:
    """A Bone Acolyte mid-chant at the only tower, a Pyre by its path."""
    world = world_of(g("priest", 1), planner=planner.smart, **kwargs)
    world.gold = 1000
    world.build("pyre", (5, 5))
    world.call_wave()
    while not any(m.chanting for m in world.monsters):
        world.step()
        assert world.time < 30
    return world, world.monsters[0].id


def cast_everything(world: World, leader: int) -> None:
    """Every spell there is, each aimed at the leader or where it stands, or at the tower under its sign."""
    priest = world.monster(leader)
    tower = next(iter(world.towers.values()))
    x, y = world.position(priest)
    for key, spec in SPELLS.items():
        world.mana = 1000
        world.recharge.clear()
        if spec.aim == "monster":
            world.smite(leader)
        elif spec.aim == "floor":
            {"meteor": world.meteor, "orb": world.orb}[key](x, y)
        else:
            world.hymn(tower.id)


def test_no_spell_breaks_a_pondering_or_a_chant_and_the_curse_lands():
    """S1: whatever strikes a leader that does not die of it, its pondering goes on to a chant and the chant lands."""
    world = world_of(g("priest", 1), planner=planner.smart, hardness=20.0)   # a priest the spells cannot kill
    world.gold = 1000
    world.build("pyre", (5, 5))
    world.call_wave()
    while not events(world, "ponder"):
        world.step()
        assert world.time < 30
    leader = world.monsters[0].id
    cast_everything(world, leader)   # while it ponders
    while not events(world, "chant"):
        world.step()
        assert world.time < 30
    cast_everything(world, leader)   # while it chants
    assert world.monster(leader).chanting
    run(world, 2)
    assert events(world, "cursed")
    assert not {"broken", "cleansed", "ward_holds"} & {e[0] for e in world.events}


def test_no_spell_lifts_a_curse():
    """S1: a cursed tower carries its curse to the end, whatever is cast."""
    world, leader = chanting_leader(hardness=20.0)
    run(world, 2)
    tower = next(iter(world.towers.values()))
    assert tower.curses
    left = dict(tower.curses)
    cast_everything(world, leader)
    assert tower.curses == left
    assert not hasattr(world, "cleanse") and "cleanse" not in SPELLS


def test_a_frozen_monster_neither_walks_nor_batters_and_a_frozen_leader_keeps_its_chant():
    world = world_of(g("zombie", 3, 0.3))
    world.gold = 1000
    world.build_door(0)
    world.call_wave()
    run(world, world.doors[0].s / MONSTERS["zombie"].speed + 3)   # the zombies are at the gate
    assert any(m.door == 0 for m in world.monsters)
    world.mana = 100
    world.orb(*world.level.point(world.monsters[0].s))
    frozen = [(m.id, m.s) for m in world.monsters]
    gate = world.doors[0].hp
    run(world, SPELLS["orb"].lasting - 0.2)
    assert [(m.id, m.s) for m in world.monsters] == frozen
    assert world.doors[0].hp == gate
    run(world, 1.0)
    assert world.doors[0].hp < gate

    world, leader = chanting_leader(hardness=20.0)
    world.mana = 100
    world.orb(*world.level.point(world.monster(leader).s))
    assert world.monster(leader).frozen > 0 and world.monster(leader).chanting


def test_a_meteor_lands_after_its_delay_and_leaves_the_floor_burning():
    world = world_of(g("overlord", 1))
    world.call_wave()
    run(world, 1.0)
    overlord = world.monsters[0]
    world.mana = 100
    where = world.level.point(overlord.s + overlord.kind.speed * SPELLS["meteor"].delay)
    world.meteor(*where)
    run(world, SPELLS["meteor"].delay - 0.1)
    assert overlord.hp == overlord.max_hp
    run(world, 0.2)
    assert events(world, "meteor")
    struck = overlord.hp
    assert struck < overlord.max_hp
    run(world, 1.0)
    assert overlord.hp < struck   # still in the fire it walks through
    assert world.hazards


def test_spells_need_mana_and_a_place_in_the_locations_arsenal():
    world = world_of(g("fallen", 3), location=campaign.TRISTRAM)
    world.call_wave()
    run(world, 2)
    world.mana = 100
    world.gold = 1000
    tower = world.build("arrow", next((x, y) for y in range(world.level.height) for x in range(world.level.width)
                                      if world.level.buildable(x, y)))
    with pytest.raises(Refused, match="Battle Hymn"):
        world.hymn(tower.id)   # Tristram teaches only Smite
    world = world_of(g("fallen", 3))
    world.call_wave()
    run(world, 2)
    world.mana = SPELLS["smite"].mana - 1
    with pytest.raises(Refused, match="mana"):
        world.smite(world.monsters[0].id)
    world.mana = 100
    world.smite(world.monsters[0].id)
    assert world.mana == pytest.approx(100 - SPELLS["smite"].mana)


def bolts_loosed(world: World, seconds: float) -> int:
    world.record = True
    world.events.clear()
    run(world, seconds)
    return len(events(world, "bolt"))


def test_battle_hymn_doubles_a_towers_attacks_for_its_while():
    """S3's boost: the hymned arrow looses twice as many arrows while the hymn lasts, and as many as before after."""
    world = world_of(g("zombie", 1), hardness=20.0)   # it lives through both
    world.gold = 1000
    arrow = world.build("arrow", (3, 5))
    world.call_wave()
    run(world, 3.0)   # the zombie walks into reach
    plain = bolts_loosed(world.clone(), SPELLS["hymn"].lasting)
    world.mana = 100
    world.hymn(arrow.id)
    assert world.mana == pytest.approx(100 - SPELLS["hymn"].mana) and events(world, "hymn") == [("hymn", arrow.id)]
    assert arrow.rate_mult() == SPELLS["hymn"].rate == 2.0
    hymned = bolts_loosed(world, SPELLS["hymn"].lasting)
    assert abs(hymned - 2 * plain) <= 1 and plain >= 3
    assert arrow.hymn == 0 and arrow.rate_mult() == 1.0
    with pytest.raises(Refused, match="gathers itself"):
        world.hymn(arrow.id)   # 15 s to gather itself again
    with pytest.raises(Refused):
        world.hymn(9999)


def test_a_clone_with_spells_in_the_air_plays_on_like_its_original():
    world = world_of(g("overlord", 4, 0.5), g("skeleton", 6, 0.4), g("priest", 1, start=2.0),
                     perks=perks({"unlock_pyre", "adept_fire", "fire_ball", "master_fire", "blaze",
                                  "unlock_frost", "unlock_hymn", "unlock_orb", "unlock_meteor"}))
    world.gold = 2000
    world.build("pyre", (5, 5))
    world.build("frost", (9, 5))
    world.call_wave()
    run(world, 6)
    world.mana = 200
    world.meteor(*world.level.point(world.monsters[-1].s))
    world.orb(*world.level.point(world.monsters[0].s))
    twin = world.clone()
    run(world, 8)
    run(twin, 8)
    assert [(m.id, m.s, m.hp) for m in world.monsters] == [(m.id, m.s, m.hp) for m in twin.monsters]
    assert (world.gold, world.lives, world.mana, world.kills) == (twin.gold, twin.lives, twin.mana, twin.kills)


def test_a_spell_gathers_itself_after_a_cast_before_it_can_be_cast_again():
    world = world_of(g("overlord", 3, 0.5))
    world.call_wave()
    run(world, 3)
    world.mana = 400
    world.smite(world.monsters[0].id)
    with pytest.raises(Refused, match="gathers itself"):
        world.smite(world.monsters[0].id)
    world.meteor(*world.level.point(world.monsters[0].s))   # another spell is not held back
    run(world, SPELLS["smite"].recharge + SIM_DT)
    world.smite(world.monsters[0].id)

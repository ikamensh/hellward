"""The four spells, through the World's commands: what each does to monsters, gates and the leaders' curses."""

from dataclasses import replace

import pytest

from hellward.sim import campaign, planner
from hellward.sim.campaign import g
from hellward.sim.content import MONSTERS, SPELLS, Curse, Group, Wave
from hellward.sim.model import SIM_DT, ForcedCurse, Refused, World
from hellward.sim.skills import perks


def world_of(*groups: Group, location: campaign.Location = campaign.CATACOMBS, **kwargs) -> World:
    waves = (Wave(tuple(groups), 10),)
    return World(replace(location, waves=waves, wave_names=("test",)), **kwargs)


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


def test_smite_breaks_a_chant_and_the_leader_waits_its_whole_cooldown():
    world, leader = chanting_leader()
    world.mana = 100
    world.smite(leader)
    priest = world.monster(leader)
    assert not priest.chanting and events(world, "broken")
    assert priest.hp < priest.max_hp
    run(world, 2)
    assert not any(t.curses for t in world.towers.values())
    assert not events(world, "cursed")
    assert priest.cooldown > 5


def test_a_frozen_monster_neither_walks_nor_batters_and_a_frozen_leader_loses_its_chant():
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

    world, leader = chanting_leader()
    world.mana = 100
    world.orb(*world.level.point(world.monster(leader).s))
    assert not world.monster(leader).chanting and events(world, "broken")


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
    with pytest.raises(Refused, match="Smite"):
        world.smite(world.monsters[0].id)   # Tristram teaches only Cleanse
    world = world_of(g("fallen", 3))
    world.call_wave()
    run(world, 2)
    world.mana = SPELLS["smite"].mana - 1
    with pytest.raises(Refused, match="mana"):
        world.smite(world.monsters[0].id)
    world.mana = 100
    world.smite(world.monsters[0].id)
    assert world.mana == pytest.approx(100 - SPELLS["smite"].mana)


def test_under_salvation_a_cleansed_tower_is_warded_and_no_leader_can_curse_it():
    world, leader = chanting_leader(perks=perks({"holy_shield", "salvation"}))
    pyre = next(iter(world.towers.values()))
    pyre.curses[Curse.WEAKEN] = 5.0
    world.mana = 100
    world.cleanse(pyre.id)
    assert world.mana == pytest.approx(75)
    assert pyre.ward > 0
    assert pyre.id not in {t.id for t in planner.reachable(world, world.monster(leader))}
    world.forced.append(ForcedCurse(world.time, leader, Curse.BONE_PRISON, pyre.id))
    run(world, 2)
    assert not pyre.curses and events(world, "ward_holds")


def test_a_clone_with_spells_in_the_air_plays_on_like_its_original():
    world = world_of(g("overlord", 4, 0.5), g("skeleton", 6, 0.4), g("priest", 1, start=2.0),
                     perks=perks({"fire_mastery", "fire_ball", "blaze"}))
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

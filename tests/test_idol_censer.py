"""The mechanics towers: the idol's free smites feed the cast verb, the censer's answer burns on a leak."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import SPELLS, TOWERS, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import CENSER_HURT, IDOL_EVERY, Refused, World
from hellward.sim.skills import perks


def arena() -> World:
    level = Level("Mechanics field", 25, 14,
                  ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))
    waves = (Wave((Group("skeleton", 3, 0.5),), 10),)
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=level, arsenal=arsenal, waves=waves, wave_names=("pack",))
    world = World(location, seed=7)
    world.gold = 10000
    return world


def floor(world: World) -> tuple[int, int]:
    return next((x, y) for y in range(14) for x in range(25) if world.buildable(x, y))


def test_the_idol_smites_for_free_and_counts_the_cast():
    world = arena()
    idol = world.build("idol", floor(world))
    world.call_wave()
    while not world.monsters:
        world.step()
    target = max(world.monsters, key=lambda m: m.s)
    idol.timer = IDOL_EVERY[0] - 0.01
    mana, casts = world.mana, world.spells_cast
    world.step(0.05)
    assert world.spells_cast == casts + 1
    assert world.mana == min(world.mana_max, mana + world.perks.mana_regen * 0.05)   # free but for regen
    assert ("smite", target.id, world.position(target)) in world.events
    assert target.hp < target.kind.hp


def test_the_idols_smites_feed_the_cast_relics():
    world = arena()
    world.relics = ("trance",)
    idol = world.build("idol", floor(world))
    world.call_wave()
    while not world.monsters:
        world.step()
    idol.timer = IDOL_EVERY[0] - 0.01
    world.step(0.05)
    assert world.fervor > 0   # the Battle Trance fires on the idol's cast
    assert ("relic", "trance", "The Battle Trance") in world.events


def test_the_idol_waits_for_a_target_and_serves_ranks():
    world = arena()
    idol = world.build("idol", floor(world))
    idol.timer = IDOL_EVERY[0] + 10.0
    world.step(0.05)   # no monsters: the rite waits, nothing spent
    assert idol.timer == IDOL_EVERY[0] + 10.0
    assert not [e for e in world.events if e[0] == "smite"]
    assert IDOL_EVERY[2] < IDOL_EVERY[0]


def test_the_censer_immolates_a_leak_in_its_reach_once_a_wave():
    world = arena()
    end = (24.5, 11.5)   # the path's end, where leaks strike
    tile = min(((x, y) for y in range(14) for x in range(25) if world.buildable(x, y)),
               key=lambda t: (t[0] + 0.5 - end[0]) ** 2 + (t[1] + 0.5 - end[1]) ** 2)
    censer = world.build("censer", tile)
    world.call_wave()
    while len(world.monsters) < 3:
        world.step()
        assert world.time < 60
    for m in world.monsters:   # the pack crowds the shrine, in the censer's reach
        m.s = world.level.route("main").length - 0.05
    gold, lives = world.gold, world.lives
    world.step(0.05)
    assert ("immolated", censer.id) in world.events
    assert world.lives < lives   # the leak still struck: the answer is not a pardon
    assert world.gold > gold   # but what burned short of the gate paid its bounty
    n = len([e for e in world.events if e[0] == "immolated"])
    world.step(0.05)
    assert len([e for e in world.events if e[0] == "immolated"]) == n   # once a wave
    assert CENSER_HURT[2] > CENSER_HURT[0]


def test_a_censer_out_of_reach_stays_silent():
    world = arena()
    censer = world.build("censer", floor(world))   # far from the shrine
    world.call_wave()
    while world.schedule or world.monsters:
        world.step()
        assert world.time < 300
    assert not [e for e in world.events if e[0] == "immolated"]
    assert censer.timer == 0.0


def test_mechanics_towers_are_locked_until_taught_and_offered_late():
    world = World(LOCATIONS["catacombs"], perks=perks(frozenset()))
    world.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if world.buildable(x, y))
    with pytest.raises(Refused, match="locked"):
        world.build("idol", tile)
    taught = World(LOCATIONS["catacombs"],
                   perks=perks({"unlock_idol", "adept_idol", "master_idol", "unlock_censer"}))
    taught.gold = 10000
    tile = next((x, y) for y in range(20) for x in range(30) if taught.buildable(x, y))
    idol = taught.build("idol", tile)
    taught.upgrade(idol.id)
    taught.upgrade(idol.id)
    assert idol.level == 2
    assert "idol" in LOCATIONS["catacombs"].arsenal.towers
    assert "censer" in LOCATIONS["caves"].arsenal.towers
    assert "idol" not in LOCATIONS["tristram"].arsenal.towers
    assert taught.rank_needs(taught.towers[idol.id]) is None

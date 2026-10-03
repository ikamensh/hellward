"""The Moon Well and the Effigy: one waters its neighbours' charges, the other eats the curses
landing near it. (M4: fourteen kinds; M6: two in five mechanics towers.)"""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.content import CURSES, TOWERS, Curse, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import CHARGES_MAX, WELL_EVERY, World
from hellward.sim.skills import perks

ARENA = Level("Mechanics field", 25, 14,
              ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))
CENTRE = (11, 3)   # open 3x3 build area beside this test field's route


def arena(kind: str = "skeleton") -> World:
    pack = Wave((Group(kind, 1, 1.0),), 10)
    location = replace(campaign.JUNGLE, level=ARENA, waves=(pack,), wave_names=("pack",))
    world = World(location, seed=7)
    world.gold = 10000
    return world


def test_fourteen_kinds_two_in_five_mechanics():
    mechanics = [key for key, kind in TOWERS.items() if kind.attack not in ("bolt", "chain", "nova", "venom", "hook")]
    assert len(TOWERS) >= 14
    assert len(mechanics) / len(TOWERS) >= 0.4
    assert {"well", "effigy"} <= set(mechanics)


def test_the_well_waters_the_attuned_neighbour_with_the_fewest_charges():
    world = arena()
    world.call_wave()
    while not world.monsters:
        world.step()
    well = world.build("well", CENTRE)
    low = world.build("arrow", (CENTRE[0] - 1, CENTRE[1]))
    high = world.build("arrow", (CENTRE[0] + 1, CENTRE[1]))
    world.attune(low.id)
    world.attune(high.id)
    low.charges, high.charges = 1.0, 2.5
    well.timer = WELL_EVERY[0] - 0.01
    world.events.clear()
    world.step(0.05)
    assert ("charge_given", well.id, low.id) in world.events
    assert low.charges == pytest.approx(2.0 + 0.05 / 15.0)
    assert high.charges == pytest.approx(2.5 + 0.05 / 15.0)


def test_the_well_waits_for_a_thirsty_neighbour_and_skips_itself():
    world = arena()
    world.call_wave()
    while not world.monsters:
        world.step()
    well = world.build("well", CENTRE)
    neighbour = world.build("arrow", (CENTRE[0] - 1, CENTRE[1]))
    world.attune(neighbour.id)
    well.attuned, well.charges = True, CHARGES_MAX   # attuned by hand: the gate forbids it in play,
    # yet the watering must skip itself regardless
    well.timer = WELL_EVERY[0]
    world.events.clear()
    world.step(0.05)
    assert not [e for e in world.events if e[0] == "charge_given"]   # all full: nothing given
    assert well.timer >= WELL_EVERY[0]   # still due: it waters the moment a charge goes
    well.charges = 0.0   # its own thirst does not count
    world.events.clear()
    world.step(0.05)
    assert not [e for e in world.events if e[0] == "charge_given"]
    neighbour.charges = 0.0
    world.events.clear()
    world.step(0.05)
    assert ("charge_given", well.id, neighbour.id) in world.events


def test_the_well_never_strikes():
    world = arena()
    world.build("well", CENTRE)
    world.call_wave()
    for _ in range(600):
        world.step()
    assert not world.bolts
    assert world.kills == 0


def world_with_shaman() -> World:
    world = arena("shaman")
    world.call_wave()
    while not any(m.kind.key == "shaman" for m in world.monsters):
        world.step()
        assert world.time < 30
    return world


def park(world: World, spot: tuple[int, int]) -> int:
    lid = next(m.id for m in world.monsters if m.kind.key == "shaman")
    leader = world.monster(lid)
    assert leader is not None
    tile = min(world.level.path_tiles, key=lambda t: (t[0] - spot[0]) ** 2 + (t[1] - spot[1]) ** 2)
    leader.s = world.level.s_of(tile)
    return lid


def test_a_curse_landing_near_an_effigy_goes_to_it_instead():
    world = world_with_shaman()
    block = [(CENTRE[0] + dx, CENTRE[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    assert all(world.level.buildable(*tile) for tile in block)
    arrows = [world.build("arrow", tile) for tile in block[:8]]
    rod = world.build("effigy", block[8])
    lid = park(world, CENTRE)
    world.events.clear()
    world._land(lid, Curse.WEAKEN, CENTRE)
    landed = [e for e in world.events if e[0] == "cursed"]
    assert len(landed) == 1 and landed[0][4] == (rod.id,)
    assert all(not t.curses for t in arrows)
    assert rod.curses[Curse.WEAKEN] == CURSES[Curse.WEAKEN].duration


def test_a_sullied_effigy_wards_nothing_and_a_far_one_neither():
    world = world_with_shaman()
    arrows = [world.build("arrow", (CENTRE[0] + dx, CENTRE[1])) for dx in (-1, 0, 1)]
    rod = world.build("effigy", (CENTRE[0], CENTRE[1] + 1))
    rod.curses[Curse.WEAKEN] = 5.0
    lid = park(world, CENTRE)
    world.events.clear()
    world._land(lid, Curse.DIM_VISION, CENTRE)
    landed = [e for e in world.events if e[0] == "cursed"][0]
    assert {world.towers[i].tile for i in landed[4]} >= {t.tile for t in arrows}
    far = next(tile for y in range(14) for x in range(25) for tile in [(x, y)]
               if world.level.buildable(x, y) and (x - CENTRE[0]) ** 2 + (y - CENTRE[1]) ** 2 > 25)
    distant = world.build("effigy", far)
    rod.curses.clear()
    world.sell(rod.id)
    world.events.clear()
    world._land(lid, Curse.DIM_VISION, CENTRE)
    landed = [e for e in world.events if e[0] == "cursed"][0]
    assert {world.towers[i].tile for i in landed[4]} >= {t.tile for t in arrows}
    assert distant.id not in landed[4] and not distant.curses


def test_the_nearest_unsullied_effigy_takes_it():
    world = world_with_shaman()
    world.build("arrow", CENTRE)
    near = world.build("effigy", (CENTRE[0] + 1, CENTRE[1]))
    far = world.build("effigy", (CENTRE[0] + 2, CENTRE[1]))
    lid = park(world, CENTRE)
    world.events.clear()
    world._land(lid, Curse.WEAKEN, CENTRE)
    landed = [e for e in world.events if e[0] == "cursed"][0]
    assert landed[4] == (near.id,)
    assert not far.curses

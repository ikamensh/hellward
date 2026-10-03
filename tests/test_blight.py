"""Blight (R6, R7): a shaman desecrates, a spider webs — an empty cell taken from later building,
marked visibly before it lands, for two cleared waves."""

from dataclasses import replace

import pytest

from hellward.sim import campaign
from hellward.sim.campaign import ACTS, LOCATIONS
from hellward.sim.content import MONSTERS, SPELLS, TOWERS, Group, Wave
from hellward.sim.level import Level
from hellward.sim.model import BLIGHT_MAX, Refused, World
from hellward.sim.skills import perks


def arena(kind: str = "spider", waves: int = 3) -> World:
    level = Level("Blight field", 25, 14,
                  ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))
    authored = tuple(Wave((Group(kind, 2, 0.5),), 10) for _ in range(waves))
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=level, arsenal=arsenal, waves=authored,
                       wave_names=tuple(f"pack {i}" for i in range(waves)))
    world = World(location, seed=7)
    world.gold = 10000
    return world


def test_each_act_blights_through_its_own_kind():
    blighters = {key for key, kind in MONSTERS.items() if kind.blight is not None}
    assert blighters == {"shaman", "spider"}
    for act, keys in ACTS.items():
        walked = {g.kind for key in keys for wave in LOCATIONS[key].waves for g in wave.groups}
        assert blighters & walked, f"act {act}: no blighter walks its waves"
    for key in blighters:
        spec = MONSTERS[key].blight
        assert spec is not None and spec.telegraph >= 1.5 and spec.waves == 2


def test_a_blighter_marks_its_best_empty_cell_before_it_lands():
    world = arena()
    world.call_wave()
    while not any(e[0] == "blight_mark" for e in world.events):
        world.step()
    mark = next(e for e in world.events if e[0] == "blight_mark")
    _, monster_id, cell, seconds, past = mark
    assert seconds >= 1.5 and past == "webbed"
    assert cell not in world.blighted          # the mark burns first; the cell is still open
    assert world.tower_at(cell) is None
    while not any(e[0] == "blight" for e in world.events):
        world.step()
    assert world.blighted[cell] == (2, "webbed")


def test_a_taken_cell_holds_no_tower_and_frees_after_two_cleared_waves():
    world = arena()
    world.call_wave()
    while not world.blighted:
        world.step()
    cell = next(iter(world.blighted))
    with pytest.raises(Refused):
        world.build("arrow", cell)
    while world.wave < 2:
        if world.break_left is not None:
            world.call_wave()
        world.step()
        assert world.outcome is None
    assert cell not in world.blighted
    world.build("arrow", cell)


def test_a_tower_raised_on_the_mark_wins_the_race():
    world = arena()
    world.call_wave()
    while not any(e[0] == "blight_mark" for e in world.events):
        world.step()
    mark = next(e for e in world.events if e[0] == "blight_mark")
    world.build("arrow", mark[2])
    landed = [e for e in world.events if e[0] == "blight" and e[2] == mark[2]]
    while not any(e[0] == "blight_fizzle" for e in world.events):
        world.step()
    assert not landed and mark[2] not in world.blighted


def test_a_slain_marker_takes_nothing():
    world = arena()
    world.call_wave()
    while not any(e[0] == "blight_mark" for e in world.events):
        world.step()
    mark = next(e for e in world.events if e[0] == "blight_mark")
    for m in world.monsters:
        m.hp = 0.0
    for _ in range(100):
        world.step()
    assert mark[2] not in world.blighted
    assert not [e for e in world.events if e[0] == "blight" and e[2] == mark[2]]


def test_five_taken_or_marked_cells_at_most():
    world = arena("spider", waves=1)
    world.call_wave()
    for _ in range(3000):
        world.step()
        marked = {m.blight_cell for m in world.monsters if m.blight_cell != (-1, -1)}
        assert len(world.blighted) + len(marked) <= BLIGHT_MAX
        if world.outcome is not None:
            break


def test_a_defence_takes_five_cells_in_all():
    from hellward.sim.model import BLIGHT_CELLS
    level = Level("Blight field", 25, 14,
                  ((0, 2), (9, 2), (9, 8), (19, 8), (19, 11), (24, 11)), ((9, 5),))
    authored = tuple(Wave((Group("spider", 6, 0.5),), 10) for _ in range(3))
    arsenal = replace(campaign.CATHEDRAL.arsenal, towers=tuple(TOWERS), spells=tuple(SPELLS), gates=True)
    location = replace(campaign.CATHEDRAL, level=level, arsenal=arsenal, waves=authored,
                       wave_names=("a", "b", "c"))
    world = World(location, seed=7)
    world.call_wave()
    for _ in range(20000):
        if world.break_left is not None:
            world.call_wave()
        world.step()
        assert len(world.blighted_cells) <= BLIGHT_CELLS
        if world.outcome is not None:
            break
    assert world.blights >= 1
    assert len(world.blighted_cells) <= BLIGHT_CELLS


def test_a_clone_carries_the_taken_cells_and_the_marks():
    world = arena()
    world.call_wave()
    while not any(e[0] == "blight_mark" for e in world.events):
        world.step()
    while not world.blighted:
        world.step()
    clone = world.clone()
    assert clone.blighted == world.blighted
    assert {(m.id, m.blight_cell) for m in clone.monsters if m.blight_cell != (-1, -1)} == \
        {(m.id, m.blight_cell) for m in world.monsters if m.blight_cell != (-1, -1)}
    for _ in range(50):
        world.step()
        clone.step()
    assert clone.blighted == world.blighted
    assert clone.blights == world.blights


def test_a_blighter_marks_once_a_wave():
    world = arena("spider", waves=1)
    world.call_wave()
    for _ in range(3000):
        world.step()
        if world.outcome is not None:
            break
    marks = [e for e in world.events if e[0] == "blight_mark"]
    assert marks and len({e[1] for e in marks}) == len(marks)


def test_the_frame_state_carries_each_taken_cell_and_each_mark():
    from hellward.server.protocol import state
    world = arena()
    world.call_wave()
    while not world.blighted:
        world.step()
    found = state(world)
    assert found["blighted"]
    cell = next(iter(world.blighted))
    assert [cell[0], cell[1], 2, "webbed"] in found["blighted"]
    for entry in found["blight_marks"]:
        assert len(entry) == 4 and entry[2] >= 0


def test_the_battle_names_which_kinds_blight():
    from hellward.server.protocol import battle_start, monster_table
    world = arena()
    found = battle_start(world, demo=True, breach_claim=None)
    assert found["monsters"]["spider"]["blight"] == {"verb": "web", "past": "webbed", "reach": 4.0,
                                                    "telegraph": 2.0, "waves": 2}
    assert monster_table(world, "skeleton")["blight"] is None

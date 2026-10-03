"""The ground as a resource: cell worth, boulders, and clearing them.

Worth is the simulation's reckoning of how much of the monsters' walk a tower reaches, per kind and per
state of the gates; the map tools analyze with the same numbers. Boulders are clearable rock: during any
break, for one income unit, then two, then three, opening their cell. The battle's start carries the worth
tables and the boulders; `clear` is an order like any other, and its ghost replays it.
"""

import dataclasses

import pytest

from hellward.server.battle import Battle
from hellward.sim import planner, worth
from hellward.sim.balance import BALANCE
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import TOWERS
from hellward.sim.model import SIM_DT, Refused, World
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import Hands, react_for
from tools import maps


def bouldered(key: str = "graveyard", count: int = 2):
    """The location with boulders on its first open floor cells."""
    location = LOCATIONS[key]
    level = location.level
    floor = [(x, y) for y in range(level.height) for x in range(level.width) if level.buildable(x, y)]
    assert len(floor) > count
    return dataclasses.replace(location, level=dataclasses.replace(level, boulders=frozenset(floor[:count])))


def test_worth_is_the_map_tools_reckoning_with_every_gate_built():
    for key in ("tristram", "graveyard", "docks"):
        location = LOCATIONS[key]
        walkers = maps.traffic(location)
        for cells in (list(maps.worth_map(location.level, walkers))[:25],):
            for at in cells:
                assert maps.cell_worth(location.level, walkers, at) == pytest.approx(
                    worth.cell(location.level, walkers.every, walkers.ground, at,
                               TOWERS["arrow"].levels[0].range, built=frozenset(range(len(location.level.doors)))))


def test_a_knife_counts_a_gate_queue_twice_and_a_gate_adds_only_its_queue():
    location = LOCATIONS["graveyard"]
    every, ground = worth.shares(location.level, location.waves)
    reach = TOWERS["arrow"].levels[0].range
    seen = False
    for at, _ in worth.worth_map(location.level, location.waves, "arrow").items():
        bare = worth.cell(location.level, every, ground, at, reach)
        with_gate = worth.cell(location.level, every, ground, at, reach, built=frozenset({0}))
        knife = worth.cell(location.level, every, ground, at, reach, knife=True, built=frozenset({0}))
        assert with_gate >= bare
        assert knife - with_gate == pytest.approx(with_gate - bare)   # the queue bonus, counted twice
        seen = seen or with_gate > bare
    assert seen   # some cell reaches the queue


def test_worth_grows_with_reach_and_boulders_carry_their_would_be_worth():
    location = bouldered()
    arrow = worth.worth_map(location.level, location.waves, "arrow")
    far = worth.worth_map(location.level, location.waves, "ballista")
    assert set(arrow) == set(far)
    assert all(far[at] >= arrow[at] for at in arrow)   # 3.2 tiles of reach see more than 2.8
    for at in location.level.boulders:
        assert arrow[at] > 0   # a boulder's would-be worth, once cleared


def test_clearing_costs_one_unit_then_two_then_three_and_opens_the_cell():
    location = bouldered(count=3)
    world = World(location, seed=1)
    assert world.break_left is not None   # the break before wave 1 counts
    unit = BALANCE.income_unit()
    tiles = sorted(location.level.boulders)
    assert world.clear(tiles[0]) == unit
    assert world.clear(tiles[1]) == 2 * unit
    assert ("cleared_boulder", tiles[1], 2 * unit) in world.events
    assert world.buildable(*tiles[0]) and not world.buildable(*tiles[2])
    world.gold += 100
    world.build("arrow", tiles[0])
    assert world.tower_at(tiles[0]) is not None
    with pytest.raises(Refused):
        world.clear(tiles[0])   # already cleared
    with pytest.raises(Refused):
        world.clear((0, 0))     # no boulder there
    world.call_wave()
    world.step(SIM_DT)
    assert world.break_left is None
    with pytest.raises(Refused):
        world.clear(tiles[2])   # not during a wave
    assert world.clone().cleared == world.cleared


def test_a_clear_order_is_logged_and_its_ghost_clears_the_same_cell():
    location = bouldered()
    battle = Battle(location, seed=1, planner=planner.RandomLeaders(1))
    tile = sorted(location.level.boulders)[0]
    refused, _ = battle.order("clear", {"tile": [0, 0]})
    assert refused is not None
    refused, _ = battle.order("clear", {"tile": list(tile)})
    assert refused is None
    assert battle.commands == [[0.0, "clear", list(tile)]]
    assert battle.world.buildable(*tile)
    start = battle.start()
    assert start["boulders"] and start["clear"] == [BALANCE.income_unit(), 2 * BALANCE.income_unit()]
    assert set(start["worth"]) == set(location.arsenal.towers)
    assert start["worth"]["arrow"]["bare"] and len(start["worth"]["arrow"]["gates"]) == 1
    ghost = Ghost({"version": 2, "location": "graveyard", "seed": 1, "skills": [], "loadout": [],
                   "commands": [[0.0, "clear", list(tile)]]})
    replayed = World(location, seed=1)
    hands = Hands(replayed, react_for(1))
    ghost.act(hands)
    replayed.step(SIM_DT)
    assert replayed.buildable(*tile)

"""Scripted defenders read all entrances as physical space and separate travel routes."""

from dataclasses import replace

import pytest

from hellward.sim.campaign import TRISTRAM
from hellward.sim.content import Group, Wave
from hellward.sim.level import Level, Route
from hellward.sim.model import Monster, World
from hellward.sim.players import PLAYERS
from hellward.sim.players.adaptive import Study
from hellward.sim.players.corner import path_corners, tile_value_for_kind
from hellward.sim.players.hands import defend
from hellward.sim.players.ordinary import Ordinary, tile_scores
from hellward.sim.players.planned import _busy
from hellward.sim.players.warden import _near, tile_value
from hellward.sim.content import MONSTERS
from tools.campaign_balance import leaders_spawned


def yard():
    level = Level("yard", 9, 9, ((0, 7), (8, 7)), (),
                  extra_routes=(Route("north", ((0, 1), (6, 1), (6, 7), (8, 7))),
                                Route("detour", ((0, 1), (2, 1), (2, 4), (5, 4), (5, 7), (8, 7)))))
    return replace(TRISTRAM, level=level,
                   waves=(Wave((Group("fallen", 5, 0.5, route="north"),), 0),),
                   wave_names=("The yard",))


def sealed_yard():
    """An optional corridor far enough from the ordinary route to tempt an uninformed build."""
    level = Level("sealed yard", 25, 14, ((0, 6), (24, 6)), (),
                  extra_routes=(Route("breach", ((0, 12), (10, 12), (10, 9), (20, 9), (20, 6), (24, 6))),))
    return replace(TRISTRAM, level=level,
                   waves=(Wave((Group("fallen", 5, 0.5),), 0),), wave_names=("The yard",))


def test_ordinary_build_score_ignores_a_sealed_breach_corridor():
    world = World(sealed_yard())
    tile = (12, 10)
    assert world.level.buildable(*tile)
    assert dict((tile, score) for score, tile in tile_scores(world))[tile] == 0.0


def test_warden_draft_values_only_entrances_used_by_ordinary_waves():
    location = sealed_yard()
    assert tile_value(location, "arrow", (12, 10), 3.0) == 0.0


def test_corner_draft_ignores_bends_in_a_sealed_breach_corridor():
    location = sealed_yard()
    assert path_corners(location.level) == []
    assert tile_value_for_kind(location, "arrow", (12, 10), 3.0) == 0.0


def test_players_do_not_confuse_equal_distances_on_different_routes():
    world = World(yard(), seed=3)
    tower = world.build("arrow", (4, 2))
    kind = MONSTERS["fallen"]
    side = Monster(100, kind, 0, 0.0, 0.0, kind.hp, 0.0, route="north")
    main = Monster(101, kind, 0, 0.0, 0.0, kind.hp, 0.0)
    side.s = main.s = 4.0
    world.monsters.append(side)

    assert _busy(world, tower)
    assert _near(world, 4.5, 1.5, 1.0) == [side]
    world.monsters[:] = [main]
    assert not _busy(world, tower)
    assert _near(world, 4.5, 1.5, 1.0) == []


def test_adaptive_study_keeps_side_entrance_separate_from_main_path():
    world = World(yard(), seed=3)
    study = Study(world)
    main = study.bin(4, "main")
    north = study.bin(4, "north")
    detour = study.bin(4, "detour")

    assert len({main, north, detour}) == 3
    assert study.guess["fallen"][main] == 0
    assert study.guess["fallen"][north] > 0
    assert study.guess["fallen"][detour] > 0
    assert north in {b for b, _ in study.cover((4, 2), 2.0)}
    assert main not in {b for b, _ in study.cover((4, 2), 2.0)}


def test_campaign_counter_handles_the_route_in_a_pending_spawn():
    location = replace(yard(), waves=(Wave((Group("shaman", 1, 1.0, route="north"),), 0),))
    world = World(location)
    world.call_wave()
    assert leaders_spawned(world) == 0
    while world.schedule:
        world.step()
    assert leaders_spawned(world) == 1


@pytest.mark.parametrize("player", ["ordinary", "adaptive"])
def test_players_finish_a_defence_with_wandering_side_route_enemies(player):
    location = yard()
    routes: set[str] = set()

    def watch(world: World) -> None:
        for event in world.events:
            if event[0] == "spawn":
                monster = world.monster(event[1])
                assert monster is not None
                routes.add(monster.route)

    defender = PLAYERS[player](3)
    world, _ = defend(location, defender, seed=3, sigils=0, planner=None, watch=watch, limit=150.0)

    assert world.outcome in ("victory", "defeat")
    assert routes == {"north", "detour"}
    assert all(t.kind.key == "arrow" for t in world.towers.values())
    if isinstance(defender, Ordinary):
        assert defender.planned and all(kind == "arrow" for kind, _ in defender.planned)

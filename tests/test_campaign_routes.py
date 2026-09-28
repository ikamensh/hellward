"""Open campaign fields have two ordinary entrances and reserved bonus breaches."""

from dataclasses import replace

import pytest

from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.level import Tile
from hellward.sim.model import World


BREACHES = frozenset({"graveyard", "catacombs", "hells_gate", "spider_forest", "drowned_city", "temple"})


@pytest.mark.parametrize("key", ORDER[1:])
def test_campaign_field_has_two_used_entrances_and_bounded_wander_routes(key):
    location = LOCATIONS[key]
    level = location.level
    routes = {route.key: route for route in level.routes}
    assert {"main", "meander", "side", "side_detour"} <= routes.keys()
    assert routes["main"].entrance == routes["meander"].entrance
    assert routes["side"].entrance == routes["side_detour"].entrance
    assert routes["main"].entrance != routes["side"].entrance
    assert {route.exit for route in level.routes} == {level.waypoints[-1]}
    assert all(route.length <= routes["main"].length * 1.6 for route in level.routes)
    assert routes["meander"].length >= routes["main"].length * 1.15
    assert routes["side_detour"].length >= routes["side"].length * 1.15

    groups = [group for wave in location.waves for group in wave.groups]
    authored = {group.route for group in groups}
    assert authored == {"main", "side"}
    bodies = sum(group.count for group in groups)
    side = sum(group.count for group in groups if group.route == "side")
    assert 0.25 <= side / bodies <= 0.75
    assert all(group.route != "breach" for group in groups)


@pytest.mark.parametrize("key", ORDER[1:])
def test_breaches_are_sealed_and_open_fields_leave_room_to_build(key):
    level = LOCATIONS[key].level
    routes = {route.key: route for route in level.routes}
    assert ("breach" in routes) == (key in BREACHES)
    if key in BREACHES:
        assert routes["breach"].entrance not in {routes["main"].entrance, routes["side"].entrance}
        assert routes["breach"].length < routes["main"].length * 0.7
    assert sum(level.tile(x, y) is Tile.FLOOR
               for y in range(level.height) for x in range(level.width)) >= 140
    assert level.obstacles


def test_cave_and_city_fields_keep_their_hazards_out_of_all_routes():
    for key in ("caves", "docks", "drowned_city"):
        level = LOCATIONS[key].level
        assert level.pools
        assert all(not (route.tiles & level.pools) for route in level.routes)


def test_graveyard_wave_uses_both_entrances_but_keeps_its_breach_sealed():
    graveyard = LOCATIONS["graveyard"]
    location = replace(graveyard, waves=(graveyard.waves[1],), wave_names=("The Hungry Dead",))
    world = World(location, seed=5)
    world.call_wave()
    while world.schedule:
        world.step()

    by_kind = {kind: {m.route for m in world.monsters if m.kind.key == kind}
               for kind in ("zombie", "skeleton")}
    assert by_kind["zombie"] <= {"main", "meander"} and by_kind["zombie"]
    assert by_kind["skeleton"] <= {"side", "side_detour"} and by_kind["skeleton"]
    assert all(m.route != "breach" for m in world.monsters)

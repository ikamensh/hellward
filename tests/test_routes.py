"""Authored monster routes through an open defence map."""

import math
import random

import pytest

from hellward.sim.level import Level, Route, Tile


def test_a_diagonal_route_uses_exact_distance_at_each_turn():
    """A turn can fall between whole tiles of distance, and movement still follows the right leg."""
    route = Route("detour", ((0, 0), (3, 4), (6, 4)))

    assert route.entrance == (0, 0)
    assert route.length == 8.0
    assert route.point(4.5) == (3.2, 4.1)
    assert route.point(5.25) == (3.75, 4.5)
    assert route.heading(4.5) == (0.6, 0.8)
    assert route.heading(5.25) == (1.0, 0.0)
    assert math.dist(route.point(0), route.point(5)) == 5.0


def test_route_coverage_matches_physical_reach_along_diagonal_legs():
    """Range covers a route exactly where its points lie within the tower's radius."""
    route = Route("detour", ((0, 0), (3, 4), (6, 4), (8, 7)))
    rng = random.Random(713)
    for _ in range(40):
        tile = (rng.randrange(0, 9), rng.randrange(0, 8))
        reach = rng.uniform(0.5, 3.5)
        spans = route.coverage(tile, reach)
        for _ in range(20):
            s = rng.uniform(0, route.length)
            x, y = route.point(s)
            distance = math.dist((x, y), (tile[0] + 0.5, tile[1] + 0.5))
            if abs(distance - reach) > 1e-6:
                assert any(a <= s <= b for a, b in spans) == (distance < reach)


def test_an_authored_entrance_can_bypass_a_gate_on_the_main_route():
    """Gate positions belong to routes, so a side entrance need not share the main chokepoint."""
    level = Level(
        "open yard", 9, 9,
        waypoints=((0, 4), (4, 4), (4, 7), (8, 7)),
        doors=((4, 5),),
        extra_routes=(Route("north", ((0, 1), (2, 1), (6, 2), (7, 4), (7, 7), (8, 7))),),
    )

    assert tuple(route.key for route in level.routes) == ("main", "north")
    assert level.route("main").entrance == (0, 4)
    assert level.route("north").entrance == (0, 1)
    assert level.crossings("main") == ((0, 5.0),)
    assert level.crossings("north") == ()
    assert level.tile(6, 2) is Tile.PATH
    assert not level.buildable(6, 2)


def test_every_route_reaches_the_same_sanctuary():
    """A committed trail must not strand its monsters at another edge."""
    with pytest.raises(ValueError, match="sanctuary"):
        Level("yard", 9, 9, ((0, 4), (8, 4)), (),
              extra_routes=(Route("stray", ((0, 1), (8, 1))),))


def test_a_side_entrance_starts_on_the_map_edge():
    """An enemy cannot appear without a visible entry point."""
    with pytest.raises(ValueError, match="entrance"):
        Level("yard", 9, 9, ((0, 4), (8, 4)), (),
              extra_routes=(Route("hidden", ((2, 2), (5, 2), (8, 4))),))


def test_a_route_cannot_slip_through_a_gate_sideways():
    """A gate stops a trail only when the trail crosses its arch face."""
    with pytest.raises(ValueError, match="door.*sideways"):
        Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
              extra_routes=(Route("diagonal", ((0, 1), (4, 5), (8, 7))),))


def test_gate_crossing_has_the_side_routes_own_distance():
    """A gate on two trails can stop each at its own route-local position."""
    level = Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
                  extra_routes=(Route("north", ((0, 1), (1, 2), (4, 2), (4, 7), (8, 7))),))

    assert level.crossings("main") == ((0, 5.0),)
    assert level.crossings("north")[0][0] == 0
    assert level.crossings("north")[0][1] == pytest.approx(math.sqrt(2) + 6)


def test_an_authored_trail_cannot_cross_a_pool():
    """Routes cannot silently walk through an unwalkable map tile."""
    with pytest.raises(ValueError, match="pool"):
        Level("yard", 9, 9, ((0, 4), (8, 4)), (), pools=frozenset({(3, 2)}),
              extra_routes=(Route("north", ((0, 2), (6, 2), (6, 4), (8, 4))),))


def test_a_route_cannot_clip_a_gate_tile_without_using_the_arch():
    """A diagonal cutting the gate's footprint must be rejected even if it misses the centre."""
    with pytest.raises(ValueError, match="door"):
        Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
              extra_routes=(Route("clip", ((0, 2), (8, 7))),))


def test_an_authored_trail_stays_inside_the_map():
    """An offscreen detour cannot hide travel time from the player."""
    with pytest.raises(ValueError, match="outside"):
        Level("yard", 9, 9, ((0, 4), (8, 4)), (),
              extra_routes=(Route("outside", ((0, 1), (4, -2), (8, 4))),))


def test_only_an_entrance_or_the_sanctuary_can_pierce_an_edge_wall():
    """A route cannot follow the outside wall to bypass the arena."""
    with pytest.raises(ValueError, match="wall"):
        Level("yard", 9, 9, ((0, 4), (8, 4)), (),
              extra_routes=(Route("wall", ((0, 1), (0, 3), (8, 4))),))


def test_a_side_route_cannot_use_the_wall_beside_a_gate():
    """A gate arch's flanking wall remains solid even when a side route is authored."""
    with pytest.raises(ValueError, match="gate wall"):
        Level("yard", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
              extra_routes=(Route("flank", ((0, 1), (5, 3), (5, 5), (7, 5), (7, 7), (8, 7))),))


def test_authored_hall_separates_monster_space_from_tower_plots():
    """A hall can be wider than a route, but neither hall nor route tiles accept towers."""
    hall = frozenset((x, 4) for x in range(9)) | frozenset(
        (x, y) for x in range(1, 8) for y in (3, 5))
    level = Level("split floor", 9, 9, ((0, 4), (8, 4)), (), halls=hall)

    assert level.walkable_tiles == hall
    assert level.tile(4, 3) is Tile.PATH
    assert level.walkable(4, 3) and not level.buildable(4, 3)
    assert level.tile(4, 2) is Tile.FLOOR
    assert level.buildable(4, 2) and not level.walkable(4, 2)
    assert all(level.walkable(math.floor(level.point(s)[0]), math.floor(level.point(s)[1]))
               for s in (level.length * i / 100 for i in range(101)))


def test_a_route_cannot_leave_an_authored_hall():
    """An omitted hall tile must not silently become a monster path over a tower plot."""
    hall = frozenset((x, 4) for x in range(9) if x != 5)
    with pytest.raises(ValueError, match="outside.*hall"):
        Level("broken hall", 9, 9, ((0, 4), (8, 4)), (), halls=hall)


def test_an_authored_hall_keeps_gate_walls_closed():
    """A wider hall must not turn a gate's flanking wall into monster floor."""
    path = frozenset({(x, 4) for x in range(5)} | {(4, y) for y in range(4, 8)} |
                     {(x, 7) for x in range(4, 9)})
    with pytest.raises(ValueError, match="gate wall"):
        Level("open flank", 9, 9, ((0, 4), (4, 4), (4, 7), (8, 7)), ((4, 5),),
              halls=path | {(5, 5)})

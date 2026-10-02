"""The map survey (tools/maps.py): what a cell is worth, which cells are prime, how much ground is occupied."""

import math

import pytest

from hellward.sim.campaign import LOCATIONS
from hellward.sim.level import Level
from tools.maps import (LEAST_OCCUPIED, MOST_PRIME, QUEUE_FRONT, REFERENCE_REACH, entrance_worth, main, occupy,
                        prime_cells, propose, survey, traffic, worth_map)


def _distance_to_route(cell: tuple[int, int], waypoints: tuple[tuple[int, int], ...]) -> float:
    """Distance from a cell's centre to a route's centreline, by plain segment geometry."""
    px, py = cell[0] + 0.5, cell[1] + 0.5
    best = math.inf
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        x0, y0, x1, y1 = x0 + 0.5, y0 + 0.5, x1 + 0.5, y1 + 0.5
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - x0 - t * dx, py - y0 - t * dy))
    return best


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_a_cell_is_worth_something_exactly_when_a_walked_route_is_in_reach(key):
    """Worth is route reached: nothing beyond the reach of every walked route, something within it."""
    location = LOCATIONS[key]
    level = location.level
    walked = traffic(location).every
    worth = worth_map(level, traffic(location))
    for cell, value in worth.items():
        nearest = min(_distance_to_route(cell, route.waypoints) for route in level.routes if walked[route.key] > 0)
        if nearest > REFERENCE_REACH + 1e-6:
            assert value == 0, (key, cell)
        elif nearest < REFERENCE_REACH - 1e-6:
            assert value > 0, (key, cell)


def _without_gates(level: Level) -> Level:
    return Level(level.name, level.width, level.height, level.waypoints, (), level.obstacles, level.pools,
                 level.boulders, level.extra_routes, halls=level.walkable_tiles)


@pytest.mark.parametrize("key", [key for key, location in LOCATIONS.items() if location.level.doors])
def test_a_gate_adds_worth_to_the_cells_that_reach_its_queue_and_takes_none(key):
    """A gate holds walkers in a queue before it: the cells beside the queue gain, and no cell loses."""
    location = LOCATIONS[key]
    level, walkers = location.level, traffic(location)
    gated, open_ = worth_map(level, walkers), worth_map(_without_gates(level), walkers)
    assert all(gated[cell] >= open_[cell] for cell in gated)
    (_, crossing), = level.crossings("main")
    qx, qy = level.route("main").point(crossing - QUEUE_FRONT)
    beside_queue = [cell for cell in gated if math.dist((cell[0] + 0.5, cell[1] + 0.5), (qx, qy)) < REFERENCE_REACH]
    assert all(gated[cell] > open_[cell] for cell in beside_queue), key   # the Jungle's gate has halls all round


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_worth_grows_with_reach(key):
    """A longer reach never loses a stretch of walk or a queue, so no cell is worth less for it."""
    location = LOCATIONS[key]
    walkers = traffic(location)
    shorter = worth_map(location.level, walkers, REFERENCE_REACH)
    longer = worth_map(location.level, walkers, REFERENCE_REACH + 0.4)
    assert all(longer[cell] >= shorter[cell] for cell in shorter)
    assert sum(longer.values()) > sum(shorter.values())


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_rock_on_a_cell_takes_that_cell_from_the_prime_ones_and_nothing_else(key):
    """Prime is measured against the map's best: rock on a lesser cell leaves the prime cells as they were, and
    rock on a prime cell (not the best) takes exactly that one."""
    location = LOCATIONS[key]
    walkers = traffic(location)
    worth = worth_map(location.level, walkers)
    prime = prime_cells(worth)
    lesser = max((cell for cell in worth if cell not in prime), key=worth.__getitem__)
    assert prime_cells(worth_map(occupy(location.level, rock=[lesser]), walkers)) == prime
    if len(prime) > 1:
        second = sorted(prime, key=worth.__getitem__)[-2]
        assert prime_cells(worth_map(occupy(location.level, rock=[second]), walkers)) == prime - {second}


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_the_proposal_meets_r1_and_leaves_every_approach_its_best_spot(key):
    """Occupying the proposed cells brings the map to R1, and no entrance loses its own best cell."""
    location = LOCATIONS[key]
    proposal = propose(location)
    level = occupy(location.level, proposal.rock, proposal.water)
    after = survey(location, level)
    assert len(after.prime) <= MOST_PRIME and after.occupied_share >= LEAST_OCCUPIED
    assert after.prime == proposal.keep
    before, kept = entrance_worth(location, location.level), entrance_worth(location, level)
    assert all(max(kept[e].values()) == max(before[e].values()) for e in before)


def test_the_survey_prints_every_location_and_draws_its_heatmap(tmp_path, capsys):
    main(["--out", str(tmp_path)])
    table = capsys.readouterr().out
    assert all(key in table for key in LOCATIONS)
    assert sorted(path.stem for path in tmp_path.glob("*.png")) == sorted(LOCATIONS)

"""The campaign's locations and its order: every map is sound and every location can be reached."""

import pytest

from hellward.sim.campaign import LAST, LOCATIONS, ORDER, SIGIL_LIVES, sigils
from hellward.sim.content import MONSTERS, SPELLS, START_LIVES, TOWERS
from hellward.sim.level import Tile


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_every_map_runs_from_its_edge_to_its_edge_with_its_arches_on_the_path(key):
    level = LOCATIONS[key].level
    for x, y in (level.waypoints[0], level.waypoints[-1]):
        assert x in (0, level.width - 1) or y in (0, level.height - 1)
    for x, y in level.doors:
        assert level.tile(x, y) is Tile.DOOR
        vertical = level.tile(x, y - 1) in (Tile.PATH, Tile.DOOR)
        across = [(x - 1, y), (x + 1, y)] if vertical else [(x, y - 1), (x, y + 1)]
        assert all(level.tile(*t) is Tile.WALL for t in across)   # an arch in a wall across the path
    for tile in level.obstacles | level.pools:
        assert tile not in level.path_tiles
    assert sum(level.buildable(x, y) for x in range(level.width) for y in range(level.height)) > 80


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_a_location_names_only_what_exists(key):
    location = LOCATIONS[key]
    assert set(location.monsters) <= set(MONSTERS)
    assert set(location.arsenal.towers) <= set(TOWERS)
    assert set(location.arsenal.spells) <= set(SPELLS)
    assert any(MONSTERS[k].leader is not None for k in location.monsters)


def test_the_campaign_goes_down_in_order_and_every_location_opens():
    for i, key in enumerate(ORDER):
        assert all(ORDER.index(need) < i for need in LOCATIONS[key].requires)
    assert ORDER[-1] == LAST
    assert all(LOCATIONS[key].requires == (before,) for before, key in zip(ORDER, ORDER[1:]))   # one way down
    offered = [set(LOCATIONS[k].arsenal.towers) | set(LOCATIONS[k].arsenal.spells) for k in ORDER]
    for earlier, later in zip(offered, offered[1:]):
        assert earlier <= later   # nothing once taught is taken away further down


def test_sigils_grow_with_the_life_kept_and_a_fall_earns_none():
    assert sigils("defeat", START_LIVES) == 0
    earned = [sigils("victory", lives) for lives in range(1, START_LIVES + 1)]
    assert earned == sorted(earned) and earned[0] == 1 and earned[-1] == 3
    assert [sigils("victory", need) for need in SIGIL_LIVES] == [1, 2, 3]
